import { useState, useEffect } from 'react';
import axios from 'axios';
import './Leaderboard.css';

interface Player {
    username: string;
    score: number;
}

function Leaderboard() {
    const [players, setPlayers] = useState<Player[]>([]);

    useEffect(() => {
        // 초기 로드
        loadLeaderboard();

        // 2초마다 리더보드 업데이트
        const interval = setInterval(loadLeaderboard, 2000);

        return () => clearInterval(interval);
    }, []);

    const loadLeaderboard = async () => {
        try {
            const response = await axios.get('/api/game/results');
            setPlayers(response.data);
        } catch (error) {
            console.error('Failed to load leaderboard:', error);
        }
    };

    if (players.length === 0) {
        return null; // 플레이어가 없으면 리더보드 표시 안 함
    }

    return (
        <div className="leaderboard">
            <h3 className="leaderboard-title">🏆 리더보드</h3>
            <div className="leaderboard-list">
                {players.slice(0, 5).map((player, index) => (
                    <div key={player.username} className={`leaderboard-item rank-${index + 1}`}>
                        <span className="rank">
                            {index === 0 && '🥇'}
                            {index === 1 && '🥈'}
                            {index === 2 && '🥉'}
                            {index > 2 && `${index + 1}.`}
                        </span>
                        <span className="username">{player.username}</span>
                        <span className="score">{player.score}점</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default Leaderboard;
