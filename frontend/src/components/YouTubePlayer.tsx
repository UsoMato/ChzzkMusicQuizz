import { useEffect, useRef, useImperativeHandle, forwardRef } from 'react';

interface YouTubePlayerProps {
  url: string;
  playing?: boolean;
  controls?: boolean;
  volume?: number;
  onEnded?: () => void;
}

export interface YouTubePlayerHandle {
  setVolume: (volume: number) => void;
  getPlayer: () => any;
  seekTo: (seconds: number) => void;
}

const YouTubePlayer = forwardRef<YouTubePlayerHandle, YouTubePlayerProps>(
  ({ url, playing = false, controls = false, volume = 100, onEnded }, ref) => {
    const playerRef = useRef<HTMLIFrameElement>(null);
    const playerInstanceRef = useRef<any>(null);
    const playerIdRef = useRef(`youtube-player-${Math.random().toString(36).substr(2, 9)}`);
    const isPlayerReadyRef = useRef(false);

    // YouTube Video ID 추출
    const getVideoId = (url: string): string | null => {
      const regex = /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/;
      const match = url.match(regex);
      return match ? match[1] : null;
    };

    const videoId = getVideoId(url);

    useEffect(() => {
      // YouTube IFrame API 로드
      const loadYouTubeAPI = () => {
        if (!window.YT) {
          // 이미 스크립트가 로드 중인지 확인
          const existingScript = document.querySelector('script[src="https://www.youtube.com/iframe_api"]');
          if (!existingScript) {
            const tag = document.createElement('script');
            tag.src = 'https://www.youtube.com/iframe_api';
            const firstScriptTag = document.getElementsByTagName('script')[0];
            firstScriptTag.parentNode?.insertBefore(tag, firstScriptTag);
          }

          window.onYouTubeIframeAPIReady = () => {
            initializePlayer();
          };
        } else if (window.YT.Player) {
          // YouTube API가 이미 로드됨
          initializePlayer();
        } else {
          // API는 로드되었지만 Player가 아직 준비 안됨
          setTimeout(loadYouTubeAPI, 100);
        }
      };

      loadYouTubeAPI();

      return () => {
        if (playerInstanceRef.current) {
          try {
            isPlayerReadyRef.current = false;
            playerInstanceRef.current.destroy();
            playerInstanceRef.current = null;
          } catch (e) {
            console.error('Error in cleanup:', e);
          }
        }
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [videoId]);

    useEffect(() => {
      if (playerInstanceRef.current && isPlayerReadyRef.current) {
        try {
          if (playing) {
            playerInstanceRef.current.playVideo();
          } else {
            playerInstanceRef.current.pauseVideo();
          }
        } catch (error) {
          console.error('Error controlling playback:', error);
        }
      }
    }, [playing]);

    useEffect(() => {
      if (playerInstanceRef.current && isPlayerReadyRef.current && playerInstanceRef.current.setVolume) {
        try {
          playerInstanceRef.current.setVolume(volume);
        } catch (error) {
          console.error('Error setting volume:', error);
        }
      }
    }, [volume]);

    useImperativeHandle(ref, () => ({
      setVolume: (newVolume: number) => {
        if (playerInstanceRef.current && playerInstanceRef.current.setVolume) {
          playerInstanceRef.current.setVolume(newVolume);
        }
      },
      getPlayer: () => playerInstanceRef.current,
      seekTo: (seconds: number) => {
        if (playerInstanceRef.current && isPlayerReadyRef.current && playerInstanceRef.current.seekTo) {
          try {
            playerInstanceRef.current.seekTo(seconds, true);
          } catch (error) {
            console.error('Error seeking:', error);
          }
        }
      },
    }));

    const initializePlayer = () => {
      if (!videoId) return;

      // 기존 플레이어가 있으면 제거
      if (playerInstanceRef.current) {
        try {
          isPlayerReadyRef.current = false;
          playerInstanceRef.current.destroy();
          playerInstanceRef.current = null;
        } catch (e) {
          console.error('Error destroying player:', e);
        }
      }

      try {
        playerInstanceRef.current = new window.YT.Player(playerIdRef.current, {
          videoId: videoId,
          playerVars: {
            autoplay: playing ? 1 : 0,
            controls: controls ? 1 : 0,
            modestbranding: 1,
            rel: 0,
          },
          events: {
            onReady: (event: any) => {
              console.log('YouTube player ready');
              isPlayerReadyRef.current = true;
              // 볼륨 설정
              if (event.target && event.target.setVolume) {
                event.target.setVolume(volume);
              }
              // 자동 재생이 필요한 경우
              if (playing && event.target && event.target.playVideo) {
                event.target.playVideo();
              }
            },
            onStateChange: (event: any) => {
              if (event.data === window.YT.PlayerState.ENDED && onEnded) {
                onEnded();
              }
            },
            onError: (event: any) => {
              console.error('YouTube player error:', event.data);
            }
          },
        });
      } catch (error) {
        console.error('Error initializing player:', error);
      }
    };

    if (!videoId) {
      return <div>유효하지 않은 YouTube URL입니다.</div>;
    }

    return (
      <div className="youtube-player-container">
        <div id={playerIdRef.current} ref={playerRef}></div>
      </div>
    );
  }
);

YouTubePlayer.displayName = 'YouTubePlayer';

// YouTube IFrame API 타입 정의
declare global {
  interface Window {
    YT: any;
    onYouTubeIframeAPIReady: () => void;
  }
}

export default YouTubePlayer;
