# 노래 맞추기 게임 (NOMAT)

치지직 스트리머와 함께하는 인터랙티브 노래 맞추기 웹 애플리케이션입니다.

## 📋 주요 기능

### 페이지 구성

- **인트로 페이지**: 게임 제목과 시작 버튼
- **맞추기 페이지**: 노래 재생 및 정답 입력 대기
  - 원형 진행바로 재생 상태 표시
  - 클릭으로 재생/일시정지 제어
  - 장르 표시
  - 일정 시간 후 힌트 표시
  - 치지직 채팅 연동 준비 (구현 예정)
- **정답 페이지**: 정답 표시 및 YouTube 영상 재생
  - 노래 제목, 아티스트, 장르 정보
  - 다음 곡으로 이동 버튼
- **결과 페이지**: 참가자 순위 표시
  - 점수 순으로 정렬된 랭킹

### 특징

- YouTube 영상 재생 (맞추기 페이지에서는 숨김 처리)
- CSV 파일 기반 노래 데이터 관리
- RESTful API 구조
- 반응형 디자인

## 🛠 기술 스택

### 백엔드

- Python 3.13+
- FastAPI
- Uvicorn
- Pydantic

### 프론트엔드

- React 18
- TypeScript
- Vite
- React Router
- Axios
- YouTube IFrame API

## 📦 설치 및 실행

### 1. Python 패키지 설치

```powershell
# Python 의존성 설치
pip install -e .
```

### 2. 프론트엔드 설치

```powershell
# frontend 디렉토리로 이동
cd frontend

# npm 패키지 설치
npm install
```

### 3. 노래 데이터 준비

`songs.csv` 파일에 노래 정보를 입력합니다:

```csv
title,youtube_url,artist,genre,hint,start_time
"[다이너마이트, Dynamite, 다이나마이트]",https://www.youtube.com/watch?v=gdZLi9oWNZg,BTS,K-Pop,다이너마이트,0
"[Butter, 버터]",https://www.youtube.com/watch?v=WMweEpGlu_U,BTS,K-Pop,버터처럼 부드럽게,10
```

**CSV 열 설명:**

- `title`: 노래 제목 (정답, 여러 정답 허용)
  - 단일 정답: `Dynamite`
  - 여러 정답: `"[다이너마이트, Dynamite, 다이나마이트]"` (대괄호로 묶고 쉼표로 구분)
  - 배열 형식을 사용하면 어느 하나를 입력해도 정답으로 인정
- `youtube_url`: YouTube 영상 URL
- `artist`: 아티스트명
- `genre`: 장르
- `hint`: 힌트 메시지
- `start_time`: 재생 시작 지점 (초 단위, 0이면 처음부터)

### 4. 개발 서버 실행

#### 백엔드 서버

```powershell
# 프로젝트 루트에서
python main.py
```

백엔드 서버: <http://localhost:8000>

#### 프론트엔드 서버

```powershell
# frontend 디렉토리에서
cd frontend
npm run dev
```

프론트엔드 서버: <http://localhost:3000>

### 5. 프로덕션 빌드

```powershell
# frontend 디렉토리에서
cd frontend
npm run build

# 빌드된 파일은 frontend/dist에 생성됩니다
# 백엔드 서버가 자동으로 정적 파일을 서빙합니다
```

## 📁 프로젝트 구조

```
nomat/
├── main.py                 # FastAPI 백엔드 서버
├── pyproject.toml          # Python 프로젝트 설정
├── songs.csv               # 노래 데이터
├── README.md
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── App.css
        ├── index.css
        ├── components/
        │   ├── CircularProgress.tsx
        │   ├── CircularProgress.css
        │   └── YouTubePlayer.tsx
        └── pages/
            ├── IntroPage.tsx
            ├── IntroPage.css
            ├── GamePage.tsx
            ├── GamePage.css
            ├── AnswerPage.tsx
            ├── AnswerPage.css
            ├── ResultPage.tsx
            └── ResultPage.css
```

## 🔌 API 엔드포인트

### 게임 관리

- `POST /api/game/start` - 게임 시작
- `POST /api/game/next` - 다음 곡으로 이동
- `POST /api/game/show-hint` - 힌트 표시
- `GET /api/game/state` - 게임 상태 조회

### 노래 정보

- `GET /api/songs` - 전체 노래 목록
- `GET /api/songs/{song_id}` - 특정 노래 정보
- `GET /api/game/current-song` - 현재 노래 정보 (정답 제외)
- `GET /api/game/current-song/answer` - 현재 노래 정답 정보

### 정답 체크

- `POST /api/game/check-answer?username={username}&answer={answer}` - 정답 확인

### 결과

- `GET /api/game/results` - 게임 결과 (점수순 정렬)

## 🚀 치지직 채팅 연동

치지직 채팅으로 시청자들이 실시간으로 정답을 맞출 수 있습니다!

### 설정 방법

1. **`.env` 파일 생성**

   프로젝트 루트에 `.env` 파일을 생성하고 다음 정보를 입력합니다:

   ```bash
   # 치지직 채널 ID (채널 URL의 마지막 부분)
   # 예: https://chzzk.naver.com/live/abc123 -> abc123
   CHZZK_CHANNEL_ID=your_channel_id_here

   # 네이버 인증 쿠키 값
   CHZZK_NID_AUT=your_nid_aut_cookie_here
   CHZZK_NID_SES=your_nid_ses_cookie_here
   ```

2. **네이버 쿠키 값 확인 방법**

   1. 웹브라우저에서 `chzzk.naver.com` 접속 후 로그인
   2. 개발자 도구 열기 (F12)
   3. `Application` (또는 `저장소`) 탭 선택
   4. `Cookies` → `https://chzzk.naver.com` 선택
   5. `NID_AUT`와 `NID_SES` 값을 복사하여 `.env` 파일에 입력

3. **서버 실행**

   ```powershell
   python main.py
   ```

   서버 시작 시 다음 메시지가 출력됩니다:

   ```
   Starting Chzzk chat client for channel: {your_channel_id}
   Chzzk chat client started in background thread
   ```

### 작동 방식

- 게임이 진행 중일 때, 시청자들이 채팅으로 정답을 입력합니다
- 백엔드가 자동으로 정답을 체크하고 점수를 기록합니다
- 정답을 맞춘 시청자에게 축하 메시지가 자동으로 전송됩니다

  ```
  🎉 {닉네임}님 정답! ({노래 제목})
  ```

- 여러 정답 형식을 허용합니다 (예: "다이너마이트", "Dynamite", "다이나마이트" 모두 정답)

### 주의사항

- 채팅 봇 기능을 사용하려면 네이버 계정으로 로그인이 필요합니다
- 쿠키 값은 주기적으로 변경될 수 있으므로, 연결이 끊기면 새로 확인해야 합니다
- `.env` 파일은 절대 공개 저장소에 업로드하지 마세요 (`.gitignore`에 추가 권장)

## 🎨 커스터마이징

### 타이머 설정

`frontend/src/pages/GamePage.tsx`:

```typescript
const [duration] = useState(30);    // 노래 재생 시간 (초)
const [hintDelay] = useState(15);   // 힌트 표시 시간 (초)
```

### 스타일 변경

각 페이지의 CSS 파일을 수정하여 스타일을 변경할 수 있습니다:

- `IntroPage.css`
- `GamePage.css`
- `AnswerPage.css`
- `ResultPage.css`
- `CircularProgress.css`

## 📝 라이선스

MIT License

## 🤝 기여

이슈와 Pull Request를 환영합니다!
