"""
노래 맞추기 게임 런처
- tkinter GUI로 게임 설정 및 참가자 관리
- FastAPI 서버를 백그라운드에서 실행
- CSV 파일 선택, 참가자 목록/점수 표시
"""

import glob
import logging
import os
import shutil
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, scrolledtext, ttk

import requests


# 로깅 설정
class TextHandler(logging.Handler):
    """tkinter Text 위젯에 로그를 출력하는 핸들러"""

    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)

        def append():
            self.text_widget.configure(state="normal")
            self.text_widget.insert(tk.END, msg + "\n")
            self.text_widget.see(tk.END)
            self.text_widget.configure(state="disabled")

        # GUI 스레드에서 실행
        self.text_widget.after(0, append)


# 전역 로거
logger = logging.getLogger("NoMatGame")
logger.setLevel(logging.DEBUG)


# PyInstaller 호환 경로 처리
def resource_path(relative_path):
    """PyInstaller 번들 또는 개발 환경에서 리소스 경로 반환"""
    try:
        # PyInstaller가 생성한 임시 폴더
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_data_path(relative_path):
    """실행 파일과 같은 폴더에 있는 데이터 파일 경로 (CSV, .env 등)"""
    if getattr(sys, "frozen", False):
        # PyInstaller로 빌드된 exe 실행 시
        base_path = os.path.dirname(sys.executable)
    else:
        # 개발 환경
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class ServerManager:
    """FastAPI 서버를 별도 스레드에서 관리"""

    def __init__(self, host="0.0.0.0", port=8000):
        self.host = host
        self.port = port
        self.server_thread = None
        self.server = None
        self.is_running = False
        logger.debug(f"ServerManager 초기화: host={host}, port={port}")

    def start(self):
        """서버를 백그라운드 스레드에서 시작"""
        if self.is_running:
            logger.warning("서버가 이미 실행 중입니다")
            return True

        logger.info("서버 시작 시도...")

        def run_server():
            try:
                import uvicorn

                from main import app

                logger.debug("uvicorn 설정 중...")

                # uvicorn 로깅 설정 비활성화 (충돌 방지)
                log_config = {
                    "version": 1,
                    "disable_existing_loggers": False,
                    "formatters": {
                        "default": {
                            "format": "%(levelprefix)s %(message)s",
                            "use_colors": False,
                        },
                        "access": {
                            "format": "%(levelprefix)s %(client_addr)s - %(request_line)s %(status_code)s",
                            "use_colors": False,
                        },
                    },
                    "handlers": {
                        "default": {
                            "formatter": "default",
                            "class": "logging.NullHandler",
                        },
                        "access": {
                            "formatter": "access",
                            "class": "logging.NullHandler",
                        },
                    },
                    "loggers": {
                        "uvicorn": {"handlers": ["default"], "level": "INFO"},
                        "uvicorn.error": {"level": "INFO"},
                        "uvicorn.access": {
                            "handlers": ["access"],
                            "level": "INFO",
                            "propagate": False,
                        },
                    },
                }

                config = uvicorn.Config(
                    app,
                    host=self.host,
                    port=self.port,
                    log_level="warning",
                    reload=False,
                    log_config=log_config,
                )
                self.server = uvicorn.Server(config)
                self.is_running = True
                logger.info(f"서버 실행 중: http://{self.host}:{self.port}")
                self.server.run()
                self.is_running = False
                logger.info("서버 종료됨")
            except Exception as e:
                import traceback

                logger.error(f"서버 실행 오류: {e}")
                logger.error(traceback.format_exc())
                self.is_running = False

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        # 서버가 시작될 때까지 대기
        logger.debug("서버 응답 대기 중...")
        for i in range(50):  # 최대 5초 대기
            time.sleep(0.1)
            try:
                response = requests.get(
                    f"http://localhost:{self.port}/api/game/state", timeout=1
                )
                if response.status_code == 200:
                    logger.info("서버 시작 완료!")
                    return True
            except Exception:
                if i % 10 == 0:
                    logger.debug(f"서버 연결 대기... ({i / 10:.1f}초)")

        logger.error("서버 시작 타임아웃 (5초)")
        return False

    def stop(self):
        """서버 종료"""
        logger.info("서버 종료 요청...")
        if self.server and self.is_running:
            self.server.should_exit = True
            self.is_running = False
            logger.info("서버 종료 완료")


class GameLauncher(tk.Tk):
    """게임 런처 메인 GUI"""

    def __init__(self):
        super().__init__()

        self.title("🎵 노래 맞추기 게임 관리자")
        self.geometry("800x750")
        self.resizable(True, True)

        # 서버 매니저
        self.server_manager = ServerManager()
        self.api_base = "http://localhost:8000"

        # 현재 선택된 CSV 파일
        self.current_csv = tk.StringVar(value="songs.csv")

        # UI 구성
        self.create_widgets()

        # 로깅 핸들러 설정 (UI 생성 후)
        self.setup_logging()

        logger.info("노래 맞추기 게임 관리자 시작")
        logger.info(f"실행 경로: {get_data_path('')}")

        # 참가자 목록 자동 갱신
        self.update_participants_periodically()

        # 창 닫기 이벤트
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_logging(self):
        """로깅 핸들러 설정"""
        # Text 위젯 핸들러
        text_handler = TextHandler(self.log_text)
        text_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
        )
        text_handler.setFormatter(formatter)
        logger.addHandler(text_handler)

        # 콘솔 핸들러 (개발용)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    def create_widgets(self):
        """UI 위젯 생성"""

        # 메인 프레임
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === 서버 상태 섹션 ===
        server_frame = ttk.LabelFrame(main_frame, text="🖥️ 서버 상태", padding="10")
        server_frame.pack(fill=tk.X, pady=(0, 10))

        server_top_frame = ttk.Frame(server_frame)
        server_top_frame.pack(fill=tk.X)

        self.server_status_label = ttk.Label(
            server_top_frame, text="⏹️ 서버 중지됨", font=("맑은 고딕", 11)
        )
        self.server_status_label.pack(side=tk.LEFT)

        self.open_browser_btn = ttk.Button(
            server_top_frame,
            text="🌐 브라우저에서 게임 열기",
            command=self.open_browser,
            state=tk.DISABLED,
        )
        self.open_browser_btn.pack(side=tk.RIGHT, padx=(10, 0))

        self.stop_server_btn = ttk.Button(
            server_top_frame,
            text="⏹️ 서버 중지",
            command=self.stop_server,
            state=tk.DISABLED,
        )
        self.stop_server_btn.pack(side=tk.RIGHT, padx=(5, 0))

        self.start_server_btn = ttk.Button(
            server_top_frame, text="▶️ 서버 시작", command=self.start_server
        )
        self.start_server_btn.pack(side=tk.RIGHT)

        # === CSV 파일 선택 섹션 ===
        csv_frame = ttk.LabelFrame(
            main_frame, text="📂 노래 목록 (CSV) 선택", padding="10"
        )
        csv_frame.pack(fill=tk.X, pady=(0, 10))

        csv_select_frame = ttk.Frame(csv_frame)
        csv_select_frame.pack(fill=tk.X)

        # CSV 파일 드롭다운
        self.csv_combo = ttk.Combobox(
            csv_select_frame, textvariable=self.current_csv, state="readonly", width=40
        )
        self.csv_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.refresh_csv_list()

        ttk.Button(
            csv_select_frame,
            text="🔄 새로고침",
            command=self.refresh_csv_list,
            width=10,
        ).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(
            csv_select_frame, text="📁 파일 찾기...", command=self.browse_csv, width=12
        ).pack(side=tk.LEFT, padx=(5, 0))

        # CSV 로드 버튼
        load_frame = ttk.Frame(csv_frame)
        load_frame.pack(fill=tk.X, pady=(10, 0))

        self.load_csv_btn = ttk.Button(
            load_frame, text="📥 선택한 CSV 로드", command=self.load_csv
        )
        self.load_csv_btn.pack(side=tk.LEFT)

        self.csv_status_label = ttk.Label(load_frame, text="", font=("맑은 고딕", 9))
        self.csv_status_label.pack(side=tk.LEFT, padx=(10, 0))

        # === 참가자 목록 섹션 ===
        participants_frame = ttk.LabelFrame(
            main_frame, text="👥 참가자 목록 및 점수", padding="10"
        )
        participants_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 테이블 (Treeview)
        columns = ("rank", "username", "score")
        self.participants_tree = ttk.Treeview(
            participants_frame, columns=columns, show="headings", height=15
        )

        self.participants_tree.heading("rank", text="순위")
        self.participants_tree.heading("username", text="닉네임")
        self.participants_tree.heading("score", text="점수")

        self.participants_tree.column("rank", width=60, anchor=tk.CENTER)
        self.participants_tree.column("username", width=300, anchor=tk.W)
        self.participants_tree.column("score", width=100, anchor=tk.CENTER)

        # 스크롤바
        scrollbar = ttk.Scrollbar(
            participants_frame, orient=tk.VERTICAL, command=self.participants_tree.yview
        )
        self.participants_tree.configure(yscrollcommand=scrollbar.set)

        self.participants_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 참가자 수 표시
        self.participant_count_label = ttk.Label(
            main_frame, text="총 참가자: 0명", font=("맑은 고딕", 10)
        )
        self.participant_count_label.pack(anchor=tk.W)

        # === 게임 상태 섹션 ===
        game_frame = ttk.LabelFrame(main_frame, text="🎮 게임 상태", padding="10")
        game_frame.pack(fill=tk.X)

        self.game_status_label = ttk.Label(
            game_frame, text="게임 대기 중", font=("맑은 고딕", 11)
        )
        self.game_status_label.pack(side=tk.LEFT)

        self.reset_btn = ttk.Button(
            game_frame, text="🔄 점수 초기화", command=self.reset_scores
        )
        self.reset_btn.pack(side=tk.RIGHT)

        # === 디버그 로그 섹션 ===
        log_frame = ttk.LabelFrame(main_frame, text="📋 디버그 로그", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # 로그 텍스트 위젯
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=8, state="disabled", font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 로그 컨트롤 버튼
        log_control_frame = ttk.Frame(log_frame)
        log_control_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(
            log_control_frame, text="🗑️ 로그 지우기", command=self.clear_log
        ).pack(side=tk.RIGHT)

    def refresh_csv_list(self):
        """실행 파일 폴더의 CSV 파일 목록 갱신"""
        data_dir = get_data_path("")
        csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
        csv_names = [os.path.basename(f) for f in csv_files]

        logger.debug(f"CSV 파일 검색: {data_dir}")
        logger.debug(f"발견된 CSV 파일: {csv_names}")

        if not csv_names:
            csv_names = ["songs.csv (파일 없음)"]

        self.csv_combo["values"] = csv_names

        if csv_names and self.current_csv.get() not in csv_names:
            self.current_csv.set(csv_names[0])

    def browse_csv(self):
        """파일 탐색기로 CSV 선택"""
        data_dir = get_data_path("")
        filepath = filedialog.askopenfilename(
            title="노래 목록 CSV 파일 선택",
            initialdir=data_dir,
            filetypes=[("CSV 파일", "*.csv"), ("모든 파일", "*.*")],
        )

        if filepath:
            logger.info(f"CSV 파일 선택: {filepath}")
            # 파일을 실행 파일 폴더로 복사
            filename = os.path.basename(filepath)
            dest_path = get_data_path(filename)

            # 원본과 대상이 다를 경우에만 복사
            if os.path.abspath(filepath) != os.path.abspath(dest_path):
                try:
                    shutil.copy2(filepath, dest_path)
                    logger.info(f"파일 복사됨: {filepath} -> {dest_path}")
                except Exception as e:
                    logger.error(f"파일 복사 실패: {e}")
                    messagebox.showerror("오류", f"파일 복사 실패: {e}")
                    return

            self.current_csv.set(filename)

            # 드롭다운에 추가
            current_values = list(self.csv_combo["values"])
            if filename not in current_values:
                current_values.append(filename)
                self.csv_combo["values"] = current_values

    def load_csv(self):
        """선택한 CSV 파일을 서버에 로드"""
        csv_file = self.current_csv.get()

        if not csv_file or "파일 없음" in csv_file:
            messagebox.showwarning("경고", "CSV 파일을 선택해주세요.")
            return

        if not self.server_manager.is_running:
            messagebox.showwarning(
                "경고", "서버가 실행 중이 아닙니다. 먼저 서버를 시작해주세요."
            )
            return

        logger.info(f"CSV 로드 요청: {csv_file}")
        self.csv_status_label.config(text="⏳ 로딩 중...", foreground="orange")

        def send_request():
            try:
                response = requests.post(
                    f"{self.api_base}/api/game/load-csv",
                    json={"filename": csv_file},
                    timeout=5,
                )
                self.after(0, lambda: self._handle_load_response(response))
            except Exception:
                self.after(0, lambda: self._handle_load_error(e))

        threading.Thread(target=send_request, daemon=True).start()

    def _handle_load_response(self, response):
        if response.status_code == 200:
            data = response.json()
            count = data.get("song_count", 0)
            self.csv_status_label.config(
                text=f"✅ {count}곡 로드됨", foreground="green"
            )
            logger.info(f"CSV 로드 성공: {count}곡")
        else:
            self.csv_status_label.config(text="❌ 로드 실패", foreground="red")
            logger.error(f"CSV 로드 실패: {response.text}")
            messagebox.showerror("오류", f"CSV 로드 실패: {response.text}")

    def _handle_load_error(self, e):
        self.csv_status_label.config(text="❌ 오류 발생", foreground="red")
        logger.error(f"CSV 로드 오류: {e}")
        messagebox.showerror("오류", f"서버 연결 실패: {e}")

    def start_server(self):
        """서버 시작"""
        logger.info("서버 시작 버튼 클릭")
        self.server_status_label.config(text="⏳ 서버 시작 중...", foreground="orange")
        self.start_server_btn.config(state=tk.DISABLED)
        self.update()

        def _start():
            success = self.server_manager.start()

            if success:
                self.server_status_label.config(
                    text="✅ 서버 실행 중 (http://localhost:8000)", foreground="green"
                )
                self.open_browser_btn.config(state=tk.NORMAL)
                self.stop_server_btn.config(state=tk.NORMAL)
                self.start_server_btn.config(state=tk.DISABLED)

                # 프론트엔드 상태 확인
                try:
                    response = requests.get(f"{self.api_base}/", timeout=3)
                    if (
                        response.status_code == 200
                        and "<!DOCTYPE html>" in response.text[:100]
                    ):
                        logger.info("프론트엔드 서빙 확인됨")
                    else:
                        logger.warning("프론트엔드가 로드되지 않았습니다")
                except Exception as e:
                    logger.warning(f"프론트엔드 확인 실패: {e}")

                # 기본 CSV 로드 상태 확인
                try:
                    response = requests.get(f"{self.api_base}/api/songs", timeout=3)
                    if response.status_code == 200:
                        songs = response.json()
                        self.csv_status_label.config(
                            text=f"✅ {len(songs)}곡 로드됨", foreground="green"
                        )
                        logger.info(f"기본 CSV 로드됨: {len(songs)}곡")
                except Exception as e:
                    logger.debug(f"기본 CSV 상태 확인 실패: {e}")
            else:
                self.server_status_label.config(
                    text="❌ 서버 시작 실패", foreground="red"
                )
                self.start_server_btn.config(state=tk.NORMAL)
                logger.error("서버 시작 실패")
                messagebox.showerror(
                    "오류",
                    "서버를 시작할 수 없습니다. 포트 8000이 이미 사용 중일 수 있습니다.",
                )

        threading.Thread(target=_start, daemon=True).start()

    def stop_server(self):
        """서버 중지"""
        logger.info("서버 중지 버튼 클릭")
        self.server_manager.stop()
        self.server_status_label.config(text="⏹️ 서버 중지됨", foreground="black")
        self.open_browser_btn.config(state=tk.DISABLED)
        self.stop_server_btn.config(state=tk.DISABLED)
        self.start_server_btn.config(state=tk.NORMAL)
        self.csv_status_label.config(text="")

    def open_browser(self):
        """브라우저에서 게임 열기"""
        logger.info("브라우저에서 게임 열기")
        webbrowser.open("http://localhost:8000")

    def clear_log(self):
        """로그 지우기"""
        self.log_text.configure(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state="disabled")
        logger.debug("로그 지움")

    def update_participants_periodically(self):
        """2초마다 참가자 목록 갱신 (백그라운드 스레드에서 실행)"""
        if not self.server_manager.is_running:
            self.after(2000, self.update_participants_periodically)
            return

        def _fetch_and_update():
            try:
                # 참가자 목록
                response = requests.get(f"{self.api_base}/api/game/results", timeout=1)
                players = response.json() if response.status_code == 200 else []

                # 게임 상태
                state_response = requests.get(
                    f"{self.api_base}/api/game/state", timeout=1
                )
                state = (
                    state_response.json() if state_response.status_code == 200 else {}
                )

                # UI 업데이트는 메인 스레드에서 실행
                self.after(0, lambda: self._update_participants_ui(players, state))
            except Exception:
                pass  # 연결 실패 시 무시

        threading.Thread(target=_fetch_and_update, daemon=True).start()
        self.after(2000, self.update_participants_periodically)

    def _update_participants_ui(self, players, state):
        """UI 업데이트 (메인 스레드에서 실행)"""
        try:
            # 기존 항목 삭제
            for item in self.participants_tree.get_children():
                self.participants_tree.delete(item)

            # 새 항목 추가
            for idx, player in enumerate(players, 1):
                rank_text = (
                    f"🥇 {idx}"
                    if idx == 1
                    else (
                        f"🥈 {idx}"
                        if idx == 2
                        else (f"🥉 {idx}" if idx == 3 else str(idx))
                    )
                )
                self.participants_tree.insert(
                    "",
                    tk.END,
                    values=(rank_text, player["username"], f"{player['score']}점"),
                )

            self.participant_count_label.config(text=f"총 참가자: {len(players)}명")

            # 게임 상태 업데이트
            if state.get("is_playing"):
                progress = state.get("current_progress", 0)
                total = state.get("total_songs", 0)
                self.game_status_label.config(
                    text=f"🎵 게임 진행 중 ({progress}/{total}곡)", foreground="blue"
                )
            else:
                self.game_status_label.config(text="⏸️ 게임 대기 중", foreground="black")
        except Exception:
            pass

    def reset_scores(self):
        """참가자 점수 초기화"""
        if not self.server_manager.is_running:
            messagebox.showwarning("경고", "서버가 실행 중이 아닙니다.")
            return

        if messagebox.askyesno("확인", "모든 참가자의 점수를 초기화하시겠습니까?"):
            logger.info("점수 초기화 요청")

            def _reset():
                try:
                    response = requests.post(
                        f"{self.api_base}/api/game/reset-scores", timeout=5
                    )
                    if response.status_code == 200:
                        # UI 업데이트는 메인 스레드에서
                        self.after(0, lambda: self._update_participants_ui([], {}))
                        self.after(0, lambda: logger.info("점수 초기화 완료"))
                        self.after(
                            0,
                            lambda: messagebox.showinfo(
                                "완료", "점수가 초기화되었습니다."
                            ),
                        )
                    else:
                        self.after(
                            0,
                            lambda: logger.error(f"점수 초기화 실패: {response.text}"),
                        )
                        self.after(
                            0, lambda: messagebox.showerror("오류", "점수 초기화 실패")
                        )
                except Exception as e:
                    self.after(
                        0, lambda err=e: logger.error(f"점수 초기화 오류: {err}")
                    )
                    self.after(
                        0,
                        lambda err=e: messagebox.showerror(
                            "오류", f"서버 연결 실패: {err}"
                        ),
                    )

            threading.Thread(target=_reset, daemon=True).start()

    def on_closing(self):
        """앱 종료 시 서버도 종료"""
        if self.server_manager.is_running:
            if messagebox.askokcancel(
                "종료", "게임 서버를 종료하고 프로그램을 닫으시겠습니까?"
            ):
                logger.info("프로그램 종료 (서버 실행 중)")
                self.server_manager.stop()
                self.destroy()
        else:
            logger.info("프로그램 종료")
            self.destroy()


def main():
    app = GameLauncher()
    app.mainloop()


if __name__ == "__main__":
    main()
