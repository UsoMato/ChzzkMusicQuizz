import asyncio
import csv
import json
import os
import random
import sys
from contextlib import asynccontextmanager
from typing import List

import aiohttp
import socketio
import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# 빌드 시 주입된 시크릿 모듈 가져오기 (존재할 경우)
try:
    import built_secrets
except ImportError:
    built_secrets = None


# PyInstaller 호환 경로 처리
def resource_path(relative_path):
    """PyInstaller 번들 또는 개발 환경에서 리소스 경로 반환 (번들 내부 파일용)"""
    try:
        # PyInstaller가 생성한 임시 폴더
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_data_path(relative_path):
    """실행 파일과 같은 폴더에 있는 데이터 파일 경로 (CSV, .env 등 사용자 파일용)"""
    if getattr(sys, "frozen", False):
        # PyInstaller로 빌드된 exe 실행 시
        base_path = os.path.dirname(sys.executable)
    else:
        # 개발 환경
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# 환경 변수 로드 (실행 파일 폴더의 .env)
load_dotenv(get_data_path(".env"))

# 빌드 시 주입된 시크릿 로드 (.env 파일이 우선순위를 가짐)
if built_secrets:
    built_secrets.load_secrets()

# Socket.IO 클라이언트 (Open API)
sio = socketio.AsyncClient(reconnection=False, logger=True, engineio_logger=True)
current_access_token = None
current_session_key = None
is_shutting_down = False


@sio.event
async def connect():
    print("Socket connected")


@sio.event
async def disconnect():
    print("Socket disconnected")
    if not is_shutting_down and current_access_token:
        print("Connection lost. Attempting to reconnect in 1 second...")
        await asyncio.sleep(1)
        # 재연결 시도 (새로운 소켓 URL 요청 포함)
        asyncio.create_task(connect_to_chzzk_socket(current_access_token))


@sio.on("SYSTEM")
async def on_system(data):
    global current_session_key
    print(f"SYSTEM event received: {data}")

    # data가 문자열이면 JSON 파싱
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            print("Failed to parse SYSTEM event data as JSON")
            return

    # sessionKey 추출
    # 데이터 구조가 명확하지 않으므로 여러 경로 시도
    session_key = data.get("sessionKey")
    if not session_key and isinstance(data, dict) and "data" in data:
        session_key = data["data"].get("sessionKey")

    if session_key:
        current_session_key = session_key
        print(f"Session Key obtained: {session_key}")
        if current_access_token:
            await subscribe_chat(session_key, current_access_token)


def handle_game_answer(username: str, answer: str):
    """게임 정답 처리 로직"""
    # 게임이 진행 중이 아니면 무시
    if not game_state.is_playing:
        return

    # 정답 페이지를 보여주는 중이면 무시 (정답 입력 불가)
    if game_state.showing_answer:
        return

    # 현재 노래가 없으면 무시
    if game_state.current_song_index >= len(songs_data):
        return

    answer = answer.strip()

    # 빈 메시지 무시
    if not answer:
        return

    current_song = songs_data[game_state.current_song_index]

    # 이미 3명의 정답자가 나왔으면 무시
    if len(game_state.current_winners) >= 3:
        return

    # 이미 정답을 맞춘 사람은 무시
    if username in game_state.current_winners:
        return

    # 여러 정답 중 하나라도 일치하면 정답으로 인정 (띄어쓰기 무시)
    answer_normalized = answer.lower().replace(" ", "")
    is_correct = any(
        answer_normalized == title.strip().lower().replace(" ", "")
        for title in current_song.title
    )

    if is_correct:
        # 순위에 따른 점수 계산
        points = 0
        rank = len(game_state.current_winners)
        if rank == 0:
            points = 1
        elif rank == 1:
            points = 1
        elif rank == 2:
            points = 1

        # 플레이어 점수 업데이트
        player_found = False
        for player in game_state.players:
            if player.username == username:
                player.score += points
                player_found = True
                break

        if not player_found:
            game_state.players.append(Player(username=username, score=points))

        # 현재 노래의 정답자 저장
        game_state.current_winners.append(username)
        print(
            f"✅ {username} 님이 정답을 맞혔습니다 ({rank + 1}등, {points}점): {answer}"
        )


@sio.on("CHAT")
async def on_chat(data):
    """채팅 메시지 수신 (Open API)"""
    # print(f"OpenAPI Chat received: {data}")

    # data가 문자열이면 JSON 파싱
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            print("Failed to parse CHAT event data as JSON")
            return

    # 데이터 구조 파싱
    content = data.get("content", "")
    profile = data.get("profile", {})
    if profile is None:
        profile = {}
    nickname = profile.get("nickname", "")

    if content and nickname:
        # print(f"Chat: [{nickname}] {content}")
        handle_game_answer(nickname, content)


async def subscribe_chat(session_key: str, access_token: str):
    """채팅 이벤트 구독"""
    url = "https://openapi.chzzk.naver.com/open/v1/sessions/events/subscribe/chat"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    params = {"sessionKey": session_key}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, params=params) as response:
                if response.status == 200:
                    print(f"Subscribed to chat events for session {session_key}")
                else:
                    text = await response.text()
                    print(f"Failed to subscribe to chat: {response.status} - {text}")
        except Exception as e:
            print(f"Error subscribing to chat: {e}")


async def unsubscribe_chat(session_key: str, access_token: str):
    """채팅 이벤트 구독 취소"""
    url = "https://openapi.chzzk.naver.com/open/v1/sessions/events/unsubscribe/chat"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    params = {"sessionKey": session_key}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, params=params) as response:
                if response.status == 200:
                    print(f"Unsubscribed from chat events for session {session_key}")
                else:
                    text = await response.text()
                    print(
                        f"Failed to unsubscribe from chat: {response.status} - {text}"
                    )
        except Exception as e:
            print(f"Error unsubscribing from chat: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 서버의 생명주기 관리"""
    # 서버 시작 시
    load_songs()

    yield

    # 서버 종료 시
    print("Shutting down...")

    # Open API 소켓 정리
    if current_session_key and current_access_token:
        print(f"Unsubscribing from session: {current_session_key}")
        await unsubscribe_chat(current_session_key, current_access_token)

    if sio.connected:
        print("Disconnecting Socket.IO...")
        await sio.disconnect()


app = FastAPI(title="노래 맞추기 게임", lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 데이터 모델
class Song(BaseModel):
    id: int
    title: List[str]  # 여러 정답 허용 (예: ["다이너마이트", "Dynamite"])
    youtube_url: str
    artist: str
    genre: str
    hint: str
    start_time: int = 0  # 재생 시작 지점 (초)


class Player(BaseModel):
    username: str
    score: int


class GameState(BaseModel):
    current_song_index: int
    players: List[Player]
    is_playing: bool
    show_hint: bool
    current_winners: List[str] = []  # 현재 노래의 정답자 닉네임 리스트 (최대 3명)
    song_order: List[int] = []  # 랜덤 순서로 재생할 노래 인덱스 리스트
    played_count: int = 0  # 재생한 곡 수
    showing_answer: bool = False  # 정답 페이지를 보여주는 중인지 여부


class LoadCsvRequest(BaseModel):
    filename: str


# 게임 상태 저장
game_state = GameState(
    current_song_index=0,
    players=[],
    is_playing=False,
    show_hint=False,
    current_winners=[],
    song_order=[],
    played_count=0,
    showing_answer=False,
)

songs_data: List[Song] = []


def unescape_string(s: str) -> str:
    """이스케이프 시퀀스를 실제 문자로 변환"""
    result = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            # 백슬래시 다음 문자를 그대로 추가
            result.append(s[i + 1])
            i += 2
        else:
            result.append(s[i])
            i += 1
    return "".join(result)


def parse_escaped_list(content: str) -> List[str]:
    """이스케이프 문자를 고려하여 쉼표로 구분된 리스트 파싱"""
    items = []
    current_item = []
    i = 0

    while i < len(content):
        if content[i] == "\\" and i + 1 < len(content):
            # 이스케이프된 문자를 그대로 추가
            current_item.append(content[i + 1])
            i += 2
        elif content[i] == ",":
            # 이스케이프되지 않은 쉼표: 아이템 구분자
            item = "".join(current_item).strip()
            if item:
                items.append(item)
            current_item = []
            i += 1
        else:
            current_item.append(content[i])
            i += 1

    # 마지막 아이템 추가
    item = "".join(current_item).strip()
    if item:
        items.append(item)

    return items


def load_songs(csv_filename: str = "songs.csv"):
    """CSV 파일에서 노래 데이터 로드"""
    global songs_data
    songs_data = []
    csv_path = get_data_path(csv_filename)

    if not os.path.exists(csv_path):
        print(f"Warning: {csv_path} not found. Using empty song list.")
        return 0

    try:
        with open(csv_path, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for idx, row in enumerate(reader):
                # start_time을 정수로 변환, 없거나 잘못된 값이면 0
                try:
                    start_time = int(row.get("start_time", "0"))
                except (ValueError, TypeError):
                    start_time = 0

                # title을 배열로 파싱
                # 형식: "[다이너마이트, Dynamite]" 또는 "다이너마이트"
                # 이스케이프 문자 처리: \, \[ \] \" 등을 문자로 인식
                title_str = row.get("title", "")
                if title_str.startswith("[") and title_str.endswith("]"):
                    # 대괄호 제거하고 쉼표로 분리 (이스케이프된 쉼표는 분리하지 않음)
                    title_list = parse_escaped_list(title_str[1:-1])
                else:
                    # 단일 타이틀 (이스케이프 문자 해제)
                    title_list = (
                        [unescape_string(title_str.strip())]
                        if title_str.strip()
                        else []
                    )

                song = Song(
                    id=idx,
                    title=title_list,
                    youtube_url=row.get("youtube_url", ""),
                    artist=row.get("artist", ""),
                    genre=row.get("genre", ""),
                    hint=row.get("hint", ""),
                    start_time=start_time,
                )
                songs_data.append(song)
        print(f"Loaded {len(songs_data)} songs from CSV")
        return len(songs_data)
    except Exception as e:
        print(f"Error loading songs: {e}")
        return 0


@app.get("/api/health")
async def health_check():
    """서버 상태 확인 API"""
    return {"status": "ok", "message": "노래 맞추기 게임 API"}


@app.get("/api/songs", response_model=List[Song])
async def get_songs():
    """모든 노래 목록 반환"""
    return songs_data


@app.get("/api/songs/{song_id}", response_model=Song)
async def get_song(song_id: int):
    """특정 노래 정보 반환"""
    if song_id < 0 or song_id >= len(songs_data):
        raise HTTPException(status_code=404, detail="Song not found")
    return songs_data[song_id]


@app.get("/api/game/current-song")
async def get_current_song():
    """현재 플레이 중인 노래 정보 반환 (정답 제외)"""
    if game_state.current_song_index >= len(songs_data):
        raise HTTPException(status_code=404, detail="No more songs")

    song = songs_data[game_state.current_song_index]
    return {
        "id": song.id,
        "youtube_url": song.youtube_url,
        "genre": song.genre,
        "hint": song.hint,  # 힌트를 항상 포함 (프론트엔드에서 표시 시점 결정)
        "artist": song.artist,
        "start_time": song.start_time,
    }


@app.get("/api/game/current-song/answer")
async def get_current_song_answer():
    """현재 노래의 정답 정보 반환"""
    if game_state.current_song_index >= len(songs_data):
        raise HTTPException(status_code=404, detail="No more songs")

    # 정답 페이지로 진입했음을 표시 (정답 입력 방지)
    game_state.showing_answer = True

    song_data = songs_data[game_state.current_song_index]
    return {
        **song_data.dict(),
        "winner": ", ".join(game_state.current_winners)
        if game_state.current_winners
        else "",
    }


@app.get("/api/game/winner")
async def get_current_winner():
    """현재 노래의 정답자 닉네임 반환"""
    return {
        "winner": ", ".join(game_state.current_winners)
        if game_state.current_winners
        else "",
        "winner_count": len(game_state.current_winners),
    }


@app.post("/api/game/start")
async def start_game():
    """게임 시작"""
    # 랜덤 순서 생성 (중복 없이)
    song_indices = list(range(len(songs_data)))
    random.shuffle(song_indices)

    game_state.song_order = song_indices
    game_state.played_count = 0
    game_state.current_song_index = song_indices[0] if song_indices else 0
    game_state.players = []
    game_state.is_playing = True
    game_state.show_hint = False
    game_state.current_winners = []  # 정답자 초기화
    game_state.showing_answer = False  # 정답 페이지 플래그 초기화

    print(f"Game started with random order: {song_indices[:5]}...")  # 처음 5개만 로그
    return {"message": "Game started", "state": game_state}


@app.post("/api/game/next")
async def next_song():
    """다음 곡으로 이동 (랜덤 순서)"""
    game_state.played_count += 1
    game_state.show_hint = False
    game_state.current_winners = []  # 정답자 초기화
    game_state.showing_answer = (
        False  # 정답 페이지 플래그 초기화 (새 곡으로 이동하면 정답 입력 가능)
    )

    # 모든 곡을 재생했는지 확인
    if game_state.played_count >= len(game_state.song_order):
        game_state.is_playing = False
        return {"message": "Game finished", "state": game_state}

    # 다음 곡 인덱스 가져오기
    game_state.current_song_index = game_state.song_order[game_state.played_count]
    print(
        f"Next song: index {game_state.current_song_index} ({game_state.played_count + 1}/{len(game_state.song_order)})"
    )

    return {"message": "Next song", "state": game_state}


@app.post("/api/game/show-hint")
async def show_hint():
    """힌트 표시"""
    game_state.show_hint = True
    return {"message": "Hint shown", "show_hint": game_state.show_hint}


@app.post("/api/game/check-answer")
async def check_answer(username: str, answer: str):
    """
    정답 확인 (치지직 채팅 연동용)
    추후 치지직 API와 연동하여 구현 예정
    """
    if game_state.current_song_index >= len(songs_data):
        raise HTTPException(status_code=404, detail="No current song")

    # 정답 페이지를 보여주는 중이면 정답 입력 불가
    if game_state.showing_answer:
        return {
            "is_correct": False,
            "username": username,
            "answer": answer,
            "message": "정답 페이지 중입니다",
        }

    # 이미 3명의 정답자가 나왔으면 무시
    if len(game_state.current_winners) >= 3:
        return {
            "is_correct": False,
            "username": username,
            "answer": answer,
            "message": "이미 3명의 정답자가 나왔습니다",
        }

    # 이미 정답을 맞춘 사람은 무시
    if username in game_state.current_winners:
        return {
            "is_correct": False,
            "username": username,
            "answer": answer,
            "message": "이미 정답을 맞췄습니다",
        }

    current_song = songs_data[game_state.current_song_index]

    # 여러 정답 중 하나라도 일치하면 정답으로 인정 (띄어쓰기 무시)
    answer_normalized = answer.strip().lower().replace(" ", "")
    is_correct = any(
        answer_normalized == title.strip().lower().replace(" ", "")
        for title in current_song.title
    )

    if is_correct:
        # 순위에 따른 점수 계산
        points = 0
        rank = len(game_state.current_winners)
        if rank == 0:
            points = 1
        elif rank == 1:
            points = 1
        elif rank == 2:
            points = 1

        # 플레이어 점수 업데이트
        player_found = False
        for player in game_state.players:
            if player.username == username:
                player.score += points
                player_found = True
                break

        if not player_found:
            game_state.players.append(Player(username=username, score=points))

        # 현재 노래의 정답자 저장
        game_state.current_winners.append(username)

    return {"is_correct": is_correct, "username": username, "answer": answer}


@app.get("/api/game/results", response_model=List[Player])
async def get_results():
    """게임 결과 반환 (점수 순으로 정렬)"""
    sorted_players = sorted(game_state.players, key=lambda p: p.score, reverse=True)
    return sorted_players


@app.get("/api/game/state")
async def get_game_state():
    """현재 게임 상태 반환"""
    total_songs = (
        len(game_state.song_order) if game_state.song_order else len(songs_data)
    )
    current_progress = (
        game_state.played_count + 1
        if game_state.is_playing
        else game_state.played_count
    )

    return {
        **game_state.dict(),
        "total_songs": total_songs,
        "current_progress": current_progress,
    }


# 새 API: CSV 파일 로드
@app.post("/api/game/load-csv")
async def load_csv_file(request: LoadCsvRequest):
    """지정된 CSV 파일 로드"""
    csv_path = get_data_path(request.filename)

    if not os.path.exists(csv_path):
        raise HTTPException(
            status_code=404, detail=f"CSV file not found: {request.filename}"
        )

    count = load_songs(request.filename)
    return {
        "message": f"Loaded {count} songs",
        "song_count": count,
        "filename": request.filename,
    }


# 새 API: 점수 초기화
@app.post("/api/game/reset-scores")
async def reset_scores():
    """모든 참가자 점수 초기화"""
    game_state.players = []
    game_state.current_winners = []
    return {"message": "Scores reset", "players": []}


# 새 API: 전체 참가자 목록 (점수 포함)
@app.get("/api/game/participants")
async def get_all_participants():
    """전체 참가자 목록 반환 (점수 순 정렬)"""
    sorted_players = sorted(game_state.players, key=lambda p: p.score, reverse=True)
    return {
        "total_count": len(sorted_players),
        "players": [player.dict() for player in sorted_players],
    }


async def connect_to_chzzk_socket(access_token: str):
    """백그라운드에서 치지직 소켓 URL을 요청하고 연결을 설정"""
    global current_access_token
    current_access_token = access_token

    print("Starting background task for Chzzk socket connection...")
    try:
        async with aiohttp.ClientSession() as session:
            # 치지직 Open API 세션 생성 엔드포인트
            session_url = "https://openapi.chzzk.naver.com/open/v1/sessions/auth"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            async with session.get(session_url, headers=headers) as session_response:
                if session_response.status == 200:
                    session_data = await session_response.json()
                    # session_data 구조: {"code": 200, "message": "Success", "content": {"url": "wss://..."}}
                    socket_url = session_data.get("content", {}).get("url")
                    print(f"Background: Socket URL obtained: {socket_url}")

                    if socket_url:
                        try:
                            # 이미 연결되어 있다면 해제
                            if sio.connected:
                                await sio.disconnect()

                            # 소켓 연결
                            await sio.connect(socket_url, transports=["websocket"])
                            print("Socket.IO connection initiated")
                        except Exception as e:
                            print(f"Failed to connect to Socket.IO: {e}")
                else:
                    error_text = await session_response.text()
                    print(
                        f"Background: Failed to get session URL: {session_response.status} - {error_text}"
                    )
    except Exception as e:
        print(f"Background: Error in socket connection task: {e}")


@app.get("/redirect")
async def chzzk_callback(code: str, state: str, background_tasks: BackgroundTasks):
    """치지직 인증 콜백 및 토큰 발급"""
    client_id = os.getenv("CHZZK_CLIENT_ID")
    client_secret = os.getenv("CHZZK_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: Missing Client ID or Secret",
        )

    token_url = "https://openapi.chzzk.naver.com/auth/v1/token"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                token_url,
                json={
                    "grantType": "authorization_code",
                    "clientId": client_id,
                    "clientSecret": client_secret,
                    "code": code,
                    "state": state,
                },
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Failed to get access token: {error_text}",
                    )

                data = await response.json()
                # data 구조: {"code": 200, "message": "Success", "content": {"accessToken": "...", "refreshToken": "...", ...}}

                print(f"Chzzk Auth Success: {data}")

                # 엑세스 토큰으로 세션 URL 요청 (백그라운드 작업으로 실행)
                access_token = data.get("content", {}).get("accessToken")
                if access_token:
                    background_tasks.add_task(connect_to_chzzk_socket, access_token)

                return RedirectResponse(url="/")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Token exchange failed: {str(e)}"
            )


# 프론트엔드 정적 파일 서빙 (빌드 후)
frontend_dist_path = resource_path("frontend/dist")
print(f"[NoMat] Frontend path: {frontend_dist_path}")
print(f"[NoMat] Frontend exists: {os.path.exists(frontend_dist_path)}")
if os.path.exists(frontend_dist_path):
    print("[NoMat] Mounting frontend at /")
    app.mount(
        "/", StaticFiles(directory=frontend_dist_path, html=True), name="frontend"
    )
else:
    print("[NoMat] WARNING: Frontend not found! Game UI will not be available.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
