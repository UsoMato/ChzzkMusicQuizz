@echo off
REM 노래 맞추기 게임 빌드 스크립트
REM Windows PowerShell 또는 CMD에서 실행

echo ========================================
echo 노래 맞추기 게임 빌드 시작
echo ========================================

REM 1. 프론트엔드 빌드
echo.
echo [1/3] 프론트엔드 빌드 중...
cd frontend
call npm install
call npm run build
cd ..

if not exist "frontend\dist" (
    echo 오류: 프론트엔드 빌드 실패!
    pause
    exit /b 1
)
echo 프론트엔드 빌드 완료!

REM 2. Python 패키지 설치
echo.
echo [2/3] Python 패키지 설치 중...
pip install pyinstaller requests

REM 2.5 시크릿 주입 (빌드용 secrets.py 생성)
echo.
echo [2.5/3] 시크릿 주입 중...
python build_secrets.py

REM 3. PyInstaller로 exe 생성
echo.
echo [3/3] exe 파일 생성 중...
uv run pyinstaller nomat.spec --clean

if exist "dist\NoMatGame\NoMatGame.exe" (
    echo.
    echo ========================================
    echo 빌드 완료!
    echo 결과물: dist\NoMatGame\NoMatGame.exe
    echo ========================================
    echo.
    echo 배포 시 다음 파일/폴더를 함께 배포하세요:
    echo   - dist\NoMatGame\ 폴더 전체
    echo   - songs.csv 파일 (NoMatGame.exe와 같은 폴더에 복사)
) else (
    echo 오류: exe 파일 생성 실패!
)

pause
