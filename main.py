import asyncio
import csv
import os
import random
from contextlib import asynccontextmanager
from typing import List

import uvicorn
from chzzkpy.unofficial.chat import ChatClient, ChatMessage
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# 환경 변수 로드
load_dotenv()

# 채팅 클라이언트 전역 변수
chat_client = None
chat_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 서버의 생명주기 관리"""
    # 서버 시작 시
    load_songs()
    await start_chat_client()

    yield

    # 서버 종료 시
    await stop_chat_client()


app = FastAPI(title="노래 맞추기 게임", lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 치지직 채팅 클라이언트 (환경 변수에서 설정 읽기)
CHZZK_CHANNEL_ID = os.getenv("CHZZK_CHANNEL_ID", "")
CHZZK_NID_AUT = os.getenv("CHZZK_NID_AUT", "")
CHZZK_NID_SES = os.getenv("CHZZK_NID_SES", "")

chat_client = None
chat_task = None

if CHZZK_CHANNEL_ID and CHZZK_NID_AUT and CHZZK_NID_SES:
    # ChatClient 초기화 (인증은 start 시점에 수행)
    chat_client = ChatClient(CHZZK_CHANNEL_ID)


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
    current_winner: str = ""  # 현재 노래의 정답자 닉네임
    song_order: List[int] = []  # 랜덤 순서로 재생할 노래 인덱스 리스트
    played_count: int = 0  # 재생한 곡 수
    showing_answer: bool = False  # 정답 페이지를 보여주는 중인지 여부


# 게임 상태 저장
game_state = GameState(
    current_song_index=0, 
    players=[], 
    is_playing=False, 
    show_hint=False, 
    current_winner="",
    song_order=[],
    played_count=0,
    showing_answer=False
)

songs_data: List[Song] = []


def unescape_string(s: str) -> str:
    """이스케이프 시퀀스를 실제 문자로 변환"""
    result = []
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            # 백슬래시 다음 문자를 그대로 추가
            result.append(s[i + 1])
            i += 2
        else:
            result.append(s[i])
            i += 1
    return ''.join(result)


def parse_escaped_list(content: str) -> List[str]:
    """이스케이프 문자를 고려하여 쉼표로 구분된 리스트 파싱"""
    items = []
    current_item = []
    i = 0
    
    while i < len(content):
        if content[i] == '\\' and i + 1 < len(content):
            # 이스케이프된 문자를 그대로 추가
            current_item.append(content[i + 1])
            i += 2
        elif content[i] == ',':
            # 이스케이프되지 않은 쉼표: 아이템 구분자
            item = ''.join(current_item).strip()
            if item:
                items.append(item)
            current_item = []
            i += 1
        else:
            current_item.append(content[i])
            i += 1
    
    # 마지막 아이템 추가
    item = ''.join(current_item).strip()
    if item:
        items.append(item)
    
    return items


def load_songs():
    """CSV 파일에서 노래 데이터 로드"""
    global songs_data
    songs_data = []
    csv_path = "songs.csv"

    if not os.path.exists(csv_path):
        print(f"Warning: {csv_path} not found. Using empty song list.")
        return

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
                    title_list = [unescape_string(title_str.strip())] if title_str.strip() else []

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
    except Exception as e:
        print(f"Error loading songs: {e}")


def setup_chat_handlers():
    """치지직 채팅 이벤트 핸들러 설정"""
    if not chat_client:
        return

    @chat_client.event
    async def on_chat(message: ChatMessage):
        """채팅 메시지 수신 시 정답 체크"""
        print(f"Received chat from {message.profile.nickname}: {message.content}")
        # 게임이 진행 중이 아니면 무시
        if not game_state.is_playing:
            return

        # 정답 페이지를 보여주는 중이면 무시 (정답 입력 불가)
        if game_state.showing_answer:
            return

        # 현재 노래가 없으면 무시
        if game_state.current_song_index >= len(songs_data):
            return

        username = message.profile.nickname
        answer = message.content.strip()

        # 빈 메시지 무시
        if not answer:
            return

        current_song = songs_data[game_state.current_song_index]

        # 이미 정답자가 있으면 무시 (최초 정답자만 점수 획득)
        if game_state.current_winner:
            return

        # 여러 정답 중 하나라도 일치하면 정답으로 인정 (띄어쓰기 무시)
        answer_normalized = answer.lower().replace(" ", "")
        is_correct = any(
            answer_normalized == title.strip().lower().replace(" ", "")
            for title in current_song.title
        )

        if is_correct:
            # 플레이어 점수 업데이트
            player_found = False
            for player in game_state.players:
                if player.username == username:
                    player.score += 1
                    player_found = True
                    break

            if not player_found:
                game_state.players.append(Player(username=username, score=1))

            # 현재 노래의 정답자 저장
            game_state.current_winner = username
            print(f"✅ {username} 님이 정답을 맞혔습니다: {answer}")


async def start_chat_client():
    """치지직 채팅 클라이언트를 백그라운드에서 시작"""
    global chat_client, chat_task

    # 환경 변수에서 설정 읽기
    CHZZK_CHANNEL_ID = os.getenv("CHZZK_CHANNEL_ID", "")
    CHZZK_NID_AUT = os.getenv("CHZZK_NID_AUT", "")
    CHZZK_NID_SES = os.getenv("CHZZK_NID_SES", "")

    if not (CHZZK_CHANNEL_ID and CHZZK_NID_AUT and CHZZK_NID_SES):
        print("Chzzk credentials not configured. Chat integration disabled.")
        return

    try:
        print(f"Starting Chzzk chat client for channel: {CHZZK_CHANNEL_ID}")
        chat_client = ChatClient(CHZZK_CHANNEL_ID)
        setup_chat_handlers()

        # start()를 백그라운드 태스크로 실행
        import asyncio

        chat_task = asyncio.create_task(chat_client.start(CHZZK_NID_AUT, CHZZK_NID_SES))
        print("Chzzk chat client started successfully")
    except Exception as e:
        import traceback

        print(f"Error starting chat client: {e}")
        print(traceback.format_exc())


async def stop_chat_client():
    """치지직 채팅 클라이언트 종료"""
    global chat_client, chat_task

    if chat_task and not chat_task.done():
        chat_task.cancel()
        try:
            await chat_task
        except asyncio.CancelledError:
            pass

    if chat_client:
        try:
            await chat_client.close()
        except Exception as e:
            print(f"Error closing chat client: {e}")


@app.get("/")
async def root():
    return {"message": "노래 맞추기 게임 API"}


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
        "winner": game_state.current_winner  # 정답자 닉네임 포함
    }


@app.get("/api/game/winner")
async def get_current_winner():
    """현재 노래의 정답자 닉네임 반환"""
    return {"winner": game_state.current_winner}


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
    game_state.current_winner = ""  # 정답자 초기화
    game_state.showing_answer = False  # 정답 페이지 플래그 초기화
    
    print(f"Game started with random order: {song_indices[:5]}...")  # 처음 5개만 로그
    return {"message": "Game started", "state": game_state}


@app.post("/api/game/next")
async def next_song():
    """다음 곡으로 이동 (랜덤 순서)"""
    game_state.played_count += 1
    game_state.show_hint = False
    game_state.current_winner = ""  # 정답자 초기화
    game_state.showing_answer = False  # 정답 페이지 플래그 초기화 (새 곡으로 이동하면 정답 입력 가능)

    # 모든 곡을 재생했는지 확인
    if game_state.played_count >= len(game_state.song_order):
        game_state.is_playing = False
        return {"message": "Game finished", "state": game_state}

    # 다음 곡 인덱스 가져오기
    game_state.current_song_index = game_state.song_order[game_state.played_count]
    print(f"Next song: index {game_state.current_song_index} ({game_state.played_count + 1}/{len(game_state.song_order)})")
    
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
        return {"is_correct": False, "username": username, "answer": answer, "message": "정답 페이지 중입니다"}

    # 이미 정답자가 있으면 정답이어도 점수 부여하지 않음
    if game_state.current_winner:
        return {"is_correct": False, "username": username, "answer": answer, "message": "이미 정답자가 있습니다"}

    current_song = songs_data[game_state.current_song_index]

    # 여러 정답 중 하나라도 일치하면 정답으로 인정 (띄어쓰기 무시)
    answer_normalized = answer.strip().lower().replace(" ", "")
    is_correct = any(
        answer_normalized == title.strip().lower().replace(" ", "")
        for title in current_song.title
    )

    if is_correct:
        # 플레이어 점수 업데이트
        player_found = False
        for player in game_state.players:
            if player.username == username:
                player.score += 1
                player_found = True
                break

        if not player_found:
            game_state.players.append(Player(username=username, score=1))

        # 현재 노래의 정답자 저장
        game_state.current_winner = username

    return {"is_correct": is_correct, "username": username, "answer": answer}


@app.get("/api/game/results", response_model=List[Player])
async def get_results():
    """게임 결과 반환 (점수 순으로 정렬)"""
    sorted_players = sorted(game_state.players, key=lambda p: p.score, reverse=True)
    return sorted_players


@app.get("/api/game/state")
async def get_game_state():
    """현재 게임 상태 반환"""
    total_songs = len(game_state.song_order) if game_state.song_order else len(songs_data)
    current_progress = game_state.played_count + 1 if game_state.is_playing else game_state.played_count
    
    return {
        **game_state.dict(),
        "total_songs": total_songs,
        "current_progress": current_progress,
    }


# 프론트엔드 정적 파일 서빙 (빌드 후)
if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
