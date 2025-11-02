import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import CircularProgress from '../components/CircularProgress';
import YouTubePlayer, { YouTubePlayerHandle } from '../components/YouTubePlayer';
import Leaderboard from '../components/Leaderboard';
import './GamePage.css';

interface Song {
  id: number;
  youtube_url: string;
  genre: string;
  hint: string; // 항상 힌트를 포함
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
  const [actualDuration, setActualDuration] = useState(60); // 실제 재생 시간 (노래 길이와 비교)
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
    } catch (error) {
      console.error('Failed to load song:', error);
      alert('노래를 불러오는데 실패했습니다.');
    }
  };

  // YouTube 플레이어가 준비되면 노래 길이를 가져와서 재생 시작
  const onPlayerReady = () => {
    if (!youtubePlayerRef.current) return;

    const player = youtubePlayerRef.current.getPlayer();
    if (!player || !player.getDuration) return;

    setTimeout(() => {
      try {
        const videoDuration = player.getDuration();
        const startTime = song?.start_time || 0;
        const remainingDuration = videoDuration - startTime;

        // 최대 60초, 노래가 60초보다 짧으면 노래 길이만큼 재생
        const playDuration = Math.min(60, remainingDuration);
        setActualDuration(playDuration);

        console.log(`Video duration: ${videoDuration}s, Start: ${startTime}s, Playing for: ${playDuration}s`);

        startPlaying(playDuration);
      } catch (error) {
        console.error('Failed to get video duration:', error);
        // 기본값으로 60초 재생
        setActualDuration(60);
        startPlaying(60);
      }
    }, 500); // 플레이어가 완전히 준비될 때까지 대기
  };

  const startPlaying = (playDuration: number) => {
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
        return prev + (100 / playDuration);
      });
    }, 1000);

    // 힌트 타이머 - 끝나기 15초 전
    const hintDelay = Math.max(0, playDuration - 15);
    if (hintDelay > 0) {
      hintTimerRef.current = setTimeout(() => {
        console.log('Showing hint');
        setShowHint(true);
      }, hintDelay * 1000);
    } else {
      // 재생 시간이 15초 이하면 즉시 힌트 표시
      setShowHint(true);
    }
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
        onPlayerReady(); // 재생 시간 재계산 후 시작
      } else {
        // 일시정지 상태에서 재개할 때는 타이머만 다시 시작
        setIsPlaying(true);
        timerRef.current = setInterval(() => {
          setProgress((prev) => {
            if (prev >= 100) {
              stopPlaying();
              return 100;
            }
            return prev + (100 / actualDuration);
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

  // 정답자 체크 - 주기적으로 정답자가 있는지 확인
  useEffect(() => {
    if (!isPlaying) return;

    const checkWinner = async () => {
      try {
        const response = await axios.get('/api/game/winner');
        if (response.data.winner) {
          console.log('Winner detected:', response.data.winner);
          stopPlaying();
          navigate('/answer');
        }
      } catch (error) {
        console.error('Failed to check winner:', error);
      }
    };

    // 1초마다 정답자 확인
    const winnerCheckInterval = setInterval(checkWinner, 1000);

    return () => {
      clearInterval(winnerCheckInterval);
    };
  }, [isPlaying, navigate]);

  if (!song) {
    return (
      <div className="game-page">
        <div className="loading">로딩 중...</div>
      </div>
    );
  }

  return (
    <div className="game-page">
      <Leaderboard />
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
            onReady={onPlayerReady}
          />
        </div>
      </div>
    </div>
  );
}

export default GamePage;
