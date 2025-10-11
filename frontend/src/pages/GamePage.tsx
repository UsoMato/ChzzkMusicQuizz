import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import CircularProgress from '../components/CircularProgress';
import YouTubePlayer, { YouTubePlayerHandle } from '../components/YouTubePlayer';
import './GamePage.css';

interface Song {
  id: number;
  youtube_url: string;
  genre: string;
  hint: string | null;
  artist: string;
  start_time: number; // 재생 시작 지점 (초)
}

function GamePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [song, setSong] = useState<Song | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [showHint, setShowHint] = useState(false);
  const [volume, setVolume] = useState(100); // 볼륨 (0-100)
  const [duration] = useState(30); // 30초 재생
  const [hintDelay] = useState(15); // 15초 후 힌트 표시
  const timerRef = useRef<number | null>(null);
  const hintTimerRef = useRef<number | null>(null);
  const youtubePlayerRef = useRef<YouTubePlayerHandle>(null);

  useEffect(() => {
    // location이 변경될 때마다 (페이지 진입 시마다) 노래 로드 및 초기화
    console.log('GamePage - loading song, location:', location.pathname);
    setSong(null);
    setProgress(0);
    setShowHint(false);
    setIsPlaying(false);

    // 기존 타이머 정리
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (hintTimerRef.current) {
      clearTimeout(hintTimerRef.current);
      hintTimerRef.current = null;
    }

    loadCurrentSong();

    return () => {
      console.log('GamePage - cleaning up');
      if (timerRef.current) clearInterval(timerRef.current);
      if (hintTimerRef.current) clearTimeout(hintTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  const loadCurrentSong = async () => {
    try {
      const response = await axios.get('/api/game/current-song');
      setSong(response.data);
      startPlaying();
    } catch (error) {
      console.error('Failed to load song:', error);
      alert('노래를 불러오는데 실패했습니다.');
    }
  };

  const startPlaying = () => {
    setIsPlaying(true);
    setProgress(0);
    setShowHint(false);

    // YouTube 플레이어를 시작 지점으로 이동
    if (song && song.start_time > 0 && youtubePlayerRef.current) {
      youtubePlayerRef.current.seekTo(song.start_time);
    }

    // 진행바 타이머
    timerRef.current = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          stopPlaying();
          return 100;
        }
        return prev + (100 / duration);
      });
    }, 1000);

    // 힌트 타이머
    hintTimerRef.current = setTimeout(async () => {
      setShowHint(true);
      try {
        await axios.post('/api/game/show-hint');
      } catch (error) {
        console.error('Failed to show hint:', error);
      }
    }, hintDelay * 1000);
  };

  const stopPlaying = () => {
    setIsPlaying(false);
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (hintTimerRef.current) {
      clearTimeout(hintTimerRef.current);
      hintTimerRef.current = null;
    }
  };

  const handleTogglePlay = () => {
    if (isPlaying) {
      stopPlaying();
    } else {
      // progress가 100%면 시작 지점부터 다시 시작
      if (progress >= 100) {
        // YouTube 플레이어를 시작 지점으로 되돌림
        if (song && youtubePlayerRef.current) {
          youtubePlayerRef.current.seekTo(song.start_time || 0);
        }
        startPlaying();
      } else {
        // 일시정지 상태에서 재개할 때는 타이머만 다시 시작
        setIsPlaying(true);
        timerRef.current = setInterval(() => {
          setProgress((prev) => {
            if (prev >= 100) {
              stopPlaying();
              return 100;
            }
            return prev + (100 / duration);
          });
        }, 1000);
      }
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseInt(e.target.value);
    setVolume(newVolume);
  };

  const handleSkip = () => {
    stopPlaying();
    navigate('/answer');
  };

  // 치지직 채팅 연동 placeholder
  // TODO: 실제 치지직 API 연동 구현
  useEffect(() => {
    // 치지직 채팅에서 정답이 들어오면 이 함수가 호출되어야 함
    const handleChatAnswer = async (username: string, answer: string) => {
      try {
        const response = await axios.post('/api/game/check-answer', null, {
          params: { username, answer }
        });

        if (response.data.is_correct) {
          stopPlaying();
          navigate('/answer');
        }
      } catch (error) {
        console.error('Failed to check answer:', error);
      }
    };

    // 치지직 채팅 이벤트 리스너 등록 (추후 구현)
    // chzzkChat.on('message', handleChatAnswer);

    return () => {
      // 치지직 채팅 이벤트 리스너 해제
      // chzzkChat.off('message', handleChatAnswer);
    };
  }, [navigate]);

  if (!song) {
    return (
      <div className="game-page">
        <div className="loading">로딩 중...</div>
      </div>
    );
  }

  return (
    <div className="game-page">
      <div className="game-content">
        <h2 className="game-title">노래를 맞춰보세요!</h2>

        <div className="progress-container" onClick={handleTogglePlay}>
          <CircularProgress
            progress={progress}
            isPlaying={isPlaying}
          />
        </div>

        <div className="info-section">
          <div className="genre-info">
            <span className="label">장르:</span>
            <span className="value">{song.genre}</span>
          </div>

          {showHint && song.hint && (
            <div className="hint-info">
              <span className="label">힌트:</span>
              <span className="value">{song.hint}</span>
            </div>
          )}
        </div>

        <div className="controls-section">
          <div className="volume-control">
            <span className="volume-icon">🔊</span>
            <input
              type="range"
              min="0"
              max="100"
              value={volume}
              onChange={handleVolumeChange}
              className="volume-slider"
            />
            <span className="volume-value">{volume}%</span>
          </div>

          <div className="playback-controls">
            <button
              className="control-button play-pause-button"
              onClick={handleTogglePlay}
            >
              {isPlaying ? '⏸ 일시정지' : '▶ 재생'}
            </button>
            <button
              className="control-button skip-button"
              onClick={handleSkip}
            >
              ⏭ 스킵
            </button>
          </div>
        </div>

        <div className="chat-info">
          <p>💬 채팅으로 정답을 입력해주세요!</p>
          <p className="chat-subinfo">치지직 채팅 연동 대기 중...</p>
        </div>

        {/* 숨겨진 YouTube 플레이어 */}
        <div style={{ display: 'none' }}>
          <YouTubePlayer
            ref={youtubePlayerRef}
            url={song.youtube_url}
            playing={isPlaying}
            volume={volume}
            startTime={song.start_time}
            onEnded={stopPlaying}
          />
        </div>
      </div>
    </div>
  );
}

export default GamePage;
