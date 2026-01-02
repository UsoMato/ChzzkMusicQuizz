import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useEffect, useState } from 'react';
import './IntroPage.css';

function IntroPage() {
  const navigate = useNavigate();
  const [chzzkStatus, setChzzkStatus] = useState<{ connected: boolean; has_token: boolean } | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  useEffect(() => {
    checkStatus();
  }, []);

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval>;
    if (isPolling) {
      intervalId = setInterval(checkStatus, 1000);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isPolling]);

  const checkStatus = async () => {
    try {
      const response = await axios.get('/api/chzzk/status');
      setChzzkStatus(response.data);

      if (response.data.connected) {
        setIsPolling(false);
      } else if (response.data.has_token) {
        // Token exists but not connected yet -> Connecting
        setIsPolling(true);
      }
    } catch (error) {
      console.error('Failed to check status:', error);
    }
  };

  const handleStart = async () => {
    try {
      // 게임 시작 API 호출
      await axios.post('/api/game/start');
      navigate('/game');
    } catch (error) {
      console.error('Failed to start game:', error);
      alert('게임 시작에 실패했습니다.');
    }
  };

  const handleChzzkLogin = () => {
    // VITE_CHZZK_CLIENT_ID는 빌드 시점에 환경 변수 값으로 대체됩니다.
    // 따라서 런타임(실행 파일)에는 .env 파일이 필요하지 않습니다.
    const clientId = import.meta.env.VITE_CHZZK_CLIENT_ID;
    const redirectUri = "http://localhost:8000/redirect";
    const state = Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);

    if (!clientId) {
      alert('Chzzk Client ID가 설정되지 않았습니다. 빌드 설정을 확인해주세요.');
      return;
    }

    const authUrl = `https://chzzk.naver.com/account-interlock?clientId=${clientId}&redirectUri=${encodeURIComponent(redirectUri)}&state=${state}`;
    window.location.href = authUrl;
  };

  const isConnected = chzzkStatus?.connected;
  const isConnecting = chzzkStatus?.has_token && !chzzkStatus?.connected;

  return (
    <div className="intro-page">
      <div className="intro-content">
        <h1 className="intro-title">🎵 노래 맞추기 🎵</h1>
        <p className="intro-subtitle">치지직 스트리머와 함께하는 음악 퀴즈</p>
        <div className="button-container">
          {isConnected ? (
            <button className="start-button" onClick={handleStart}>
              게임 시작
            </button>
          ) : isConnecting ? (
            <button className="chzzk-login-button" disabled>
              로그인 중...
            </button>
          ) : (
            <button className="chzzk-login-button" onClick={handleChzzkLogin}>
              치지직 연동
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default IntroPage;
