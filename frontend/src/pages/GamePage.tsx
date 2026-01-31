import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import CircularProgress from '../components/CircularProgress';
import YouTubePlayer, { YouTubePlayerHandle } from '../components/YouTubePlayer';
import Leaderboard from '../components/Leaderboard';
import ImageReveal from '../components/ImageReveal';
import './GamePage.css';

const isYoutubeUrl = (url: string) => {
  return url.includes('youtube.com') || url.includes('youtu.be');
};

const getImageSrc = (url: string) => {
  if (url.startsWith('http')) return url;
  return `/api/image?path=${encodeURIComponent(url)}`;
};

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
  const [showGenre, setShowGenre] = useState(false);
  const [showArtist, setShowArtist] = useState(false);
  const [volume, setVolume] = useState(100); // 볼륨 (0-100)
  const [actualDuration, setActualDuration] = useState(60); // 실제 재생 시간 (노래 길이와 비교)
  const timerRef = useRef<number | null>(null);
  const hintTimerRef = useRef<number | null>(null);
  const genreTimerRef = useRef<number | null>(null);
  const artistTimerRef = useRef<number | null>(null);
  const firstWinnerDetectedTimeRef = useRef<number | null>(null);
  const youtubePlayerRef = useRef<YouTubePlayerHandle>(null);

  useEffect(() => {
    // location이 변경될 때마다 (페이지 진입 시마다) 노래 로드 및 초기화
    console.log('GamePage - loading song, location:', location.pathname);
    setSong(null);
    setProgress(0);
    setShowHint(false);
    setShowGenre(false);
    setShowArtist(false);
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
    if (genreTimerRef.current) {
      clearTimeout(genreTimerRef.current);
      genreTimerRef.current = null;
    }
    if (artistTimerRef.current) {
      clearTimeout(artistTimerRef.current);
      artistTimerRef.current = null;
    }
    firstWinnerDetectedTimeRef.current = null;

    loadCurrentSong();

    return () => {
      console.log('GamePage - cleaning up');
      if (timerRef.current) clearInterval(timerRef.current);
      if (hintTimerRef.current) clearTimeout(hintTimerRef.current);
      if (genreTimerRef.current) clearTimeout(genreTimerRef.current);
      if (artistTimerRef.current) clearTimeout(artistTimerRef.current);
      firstWinnerDetectedTimeRef.current = null;
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
    setShowGenre(false);
    setShowArtist(false);

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

    // 장르 타이머 - 10초 후 표시
    genreTimerRef.current = setTimeout(() => {
      console.log('Showing genre');
      setShowGenre(true);
    }, 10000);

    // 가수 타이머 - 30초 후 표시
    artistTimerRef.current = setTimeout(() => {
      console.log('Showing artist');
      setShowArtist(true);
    }, 30000);

    // 힌트 타이머 - 끝나기 15초 전 (힌트가 있을 때만)
    if (song && song.hint) {
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
    }
  };

  // 이미지 문제일 경우 자동 시작
  useEffect(() => {
    if (song && !isYoutubeUrl(song.youtube_url) && !isPlaying) {
      setActualDuration(60);
      startPlaying(60);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [song]);

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
    if (genreTimerRef.current) {
      clearTimeout(genreTimerRef.current);
      genreTimerRef.current = null;
    }
    if (artistTimerRef.current) {
      clearTimeout(artistTimerRef.current);
      artistTimerRef.current = null;
    }
  };

  const handleTogglePlay = () => {
    if (isPlaying) {
      stopPlaying();
    } else {
      // progress가 100%면 시작 지점부터 다시 시작
      if (progress >= 100) {
        // 이미지 문제인 경우 바로 시작
        if (song && !isYoutubeUrl(song.youtube_url)) {
          setActualDuration(60);
          startPlaying(60);
          return;
        }

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
    navigate('/answer', { state: { skipped: true } });
  };

  // 정답자 체크 - 주기적으로 정답자가 있는지 확인
  useEffect(() => {
    const checkWinner = async () => {
      try {
        const response = await axios.get('/api/game/winner');
        const winnerCount = response.data.winner_count;

        // 정답자가 3명 이상이면 즉시 이동
        if (winnerCount >= 3) {
          console.log('3 Winners detected:', response.data.winner);
          stopPlaying();
          navigate('/answer');
          return;
        }

        // 정답자가 1명 이상이면 타이머 체크
        if (winnerCount >= 1) {
          if (firstWinnerDetectedTimeRef.current === null) {
            firstWinnerDetectedTimeRef.current = Date.now();
            console.log('First winner detected, starting 3s timer');
          } else {
            const elapsed = Date.now() - firstWinnerDetectedTimeRef.current;
            if (elapsed >= 3000) {
              console.log('3 seconds passed since first winner');
              stopPlaying();
              navigate('/answer');
            }
          }
        } else {
          // 정답자가 없으면 타이머 리셋
          firstWinnerDetectedTimeRef.current = null;
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
      <Leaderboard />
      <div className="game-content">
        <h2 className="game-title">노래를 맞춰보세요!</h2>

        <div className="progress-container" onClick={handleTogglePlay}>
          {song && !isYoutubeUrl(song.youtube_url) ? (
            <ImageReveal
              src={getImageSrc(song.youtube_url)}
            />
          ) : (
            <CircularProgress
              progress={progress}
              isPlaying={isPlaying}
            />
          )}
        </div>

        <div className="info-section">
          {showGenre && song.genre && (
            <div className="genre-info">
              <span className="label">장르:</span>
              <span className="value">{song.genre}</span>
            </div>
          )}

          {showArtist && song.artist && (
            <div className="artist-info">
              <span className="label">가수:</span>
              <span className="value">{song.artist}</span>
            </div>
          )}

          {showHint && song.hint && (
            <div className="hint-info">
              <span className="label">힌트:</span>
              <span className="value">{song.hint}</span>
            </div>
          )}
        </div>

        <div className="controls-section">
          {song && isYoutubeUrl(song.youtube_url) && (
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
          )}

          <div className="playback-controls">
            {song && isYoutubeUrl(song.youtube_url) && (
              <button
                className="control-button play-pause-button"
                onClick={handleTogglePlay}
              >
                {isPlaying ? '⏸ 일시정지' : '▶ 재생'}
              </button>
            )}
            <button
              className="control-button skip-button"
              onClick={handleSkip}
            >
              ⏭ 스킵
            </button>
          </div>
        </div>

        {/* 숨겨진 YouTube 플레이어 - 유튜브 URL일 때만 렌더링 */}
        {song && isYoutubeUrl(song.youtube_url) && (
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
        )}

        <div className="footer-info" style={{ marginTop: '20px', fontSize: '0.8rem', textAlign: 'center', opacity: 0.7 }}>
          치지직 스트리머 <a href="https://chzzk.naver.com/577506b2d214450f65587fb04adc243a" target="_blank" rel="noopener noreferrer" style={{ color: '#00ffa3', textDecoration: 'none' }}>우소 마토</a> 제작
        </div>
      </div>
    </div>
  );
}

export default GamePage;
