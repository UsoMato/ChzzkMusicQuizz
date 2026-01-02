# 노래 맞추기 게임 (NOMAT)

치지직(Chzzk) 스트리머와 시청자가 함께 즐길 수 있는 인터랙티브 노래 맞추기 게임입니다.
YouTube 영상을 기반으로 노래 퀴즈를 진행하며, 채팅을 통해 정답을 맞출 수 있습니다.

## 📋 주요 기능

### 🎮 게임 플레이

- **인트로**: 게임 시작 대기 화면
- **문제 출제**:
  - YouTube 영상의 오디오만 재생 (화면 숨김)
  - 원형 타이머로 남은 시간 표시
  - 장르 및 힌트 제공
- **정답 공개**:
  - 정답 시 해당 뮤직비디오/영상 재생
  - 노래 제목, 아티스트 정보 표시
- **결과 발표**: 게임 종료 후 참여자들의 점수 랭킹 표시

## 📦 설치 및 실행 방법

### 일반 사용자 (실행 파일 사용)

1. **실행**: `NoMatGame.exe`를 실행합니다.
2. **설정**: 런처 화면에서 사용할 `songs.csv` 파일을 선택합니다.
3. **게임 시작**:
   - '서버 시작' 버튼을 누르면 백그라운드에서 게임 서버가 실행됩니다.
   - '브라우저 열기' 버튼으로 게임 화면(크롬 등)을 띄웁니다.
   - 브라우저에서 치지직에 로그인을 하면 채팅이 연동됩니다.
   - 방송 송출 프로그램(OBS 등)에 해당 브라우저 화면을 캡처하여 방송합니다.

### 노래 데이터 준비 (`songs.csv`)

`songs.csv` 파일은 다음 형식을 따릅니다:

```csv
title,artist,youtube_url,genre,hint,start_time
```

- **title**: 노래 제목 (정답)
- **artist**: 가수 이름
- **youtube_url**: YouTube 영상 링크
- **genre**: 장르 (예: 발라드, 댄스)
- **hint**: 힌트 텍스트
- **start_time**: 재생 시작 시간 (초 단위, 예: 60)

가수, 장르, 힌트 를 명시하지 않고 빈 칸으로 둘 수 있습니다.

예시:

```csv
title,artist,youtube_url,genre,hint,start_time
Dynamite,BTS,https://www.youtube.com/watch?v=gdZLi9oC1ZQ,댄스,2020년 발매,30
Shape of You,Ed Sheeran,https://www.youtube.com/watch?v=JGwWNGJdvx8,팝,2017년 히트곡,45
```

#### YouTube 플레이리스트 가져오기

`playlist_parser.py` 도구를 사용하여 YouTube 플레이리스트를 CSV로 변환할 수 있습니다.

```bash
python playlist_parser.py [플레이리스트URL]
```

*(참고: `yt-dlp` 라이브러리가 필요합니다)*

## 💻 개발자 가이드

### 요구 사항

- Python 3.13+
- uv
- Node.js 18+

### 프로젝트 구조

```
nomat/
├── frontend/          # React + Vite 프론트엔드
├── build/             # PyInstaller 빌드 아티팩트
├── dist/              # 빌드 결과물 (EXE)
├── main.py            # FastAPI 백엔드 서버
├── launcher.py        # Tkinter GUI 런처
├── playlist_parser.py # 유튜브 플레이리스트 파서
├── build.bat          # 통합 빌드 스크립트
└── nomat.spec         # PyInstaller 설정 파일
```

### 개발 환경 실행

1. **백엔드 실행**

   ```bash
   # 가상환경 생성 및 패키지 설치
   uv sync
   
   # 서버 실행
   uv run main.py
   ```

2. **프론트엔드 실행**

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### 빌드 (Build)

`build.bat` 스크립트를 실행하면 프론트엔드 빌드와 백엔드 패키징이 자동으로 수행됩니다.

```cmd
.\build.bat
```

빌드가 완료되면 `dist/NoMatGame/NoMatGame.exe` 파일이 생성됩니다.
