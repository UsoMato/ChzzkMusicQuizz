import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import YouTubePlayer from '../components/YouTubePlayer';
import './AnswerPage.css';

interface Song {
  id: number;
  title: string;
  youtube_url: string;
  artist: string;
  genre: string;
  hint: string;
}

function AnswerPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [song, setSong] = useState<Song | null>(null);

  useEffect(() => {
    // location이 변경될 때마다 (페이지 진입 시마다) 정답 로드
    console.log('AnswerPage - loading answer, location:', location.pathname);
    setSong(null); // 이전 노래 정보 초기화
    loadAnswer();

    return () => {
      console.log('AnswerPage - cleaning up');
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  const loadAnswer = async () => {
    try {
      const response = await axios.get('/api/game/current-song/answer');
      setSong(response.data);
    } catch (error) {
      console.error('Failed to load answer:', error);
      alert('정답 정보를 불러오는데 실패했습니다.');
    }
  };

  const handleNext = async () => {
    try {
      const response = await axios.post('/api/game/next');

      if (response.data.state.is_playing) {
        // 다음 곡이 있으면 게임 페이지로
        navigate('/game');
      } else {
        // 게임이 끝나면 결과 페이지로
        navigate('/result');
      }
    } catch (error) {
      console.error('Failed to go to next song:', error);
      alert('다음 곡으로 이동하는데 실패했습니다.');
    }
  };

  if (!song) {
    return (
      <div className="answer-page">
        <div className="loading">로딩 중...</div>
      </div>
    );
  }

  return (
    <div className="answer-page">
      <div className="answer-content">
        <h2 className="answer-title">🎉 정답입니다! 🎉</h2>

        <div className="youtube-container">
          <YouTubePlayer
            url={song.youtube_url}
            playing={true}
            controls={true}
          />
        </div>

        <div className="song-info">
          <h3 className="song-title">{song.title}</h3>
          <p className="song-artist">{song.artist}</p>
          <p className="song-genre">장르: {song.genre}</p>
        </div>

        <button className="next-button" onClick={handleNext}>
          다음 곡으로 →
        </button>
      </div>
    </div>
  );
}

export default AnswerPage;
