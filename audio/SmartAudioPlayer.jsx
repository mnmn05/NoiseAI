import { useRef } from 'react';
import { useSmartPlayer } from '../hooks/useSmartPlayer';
import { DEFAULT_TRACKS, TEST_AI_TRACKS } from '../data/defaultTracks';
import './SmartAudioPlayer.css';

const fmt = (sec) => {
  if (sec == null) return '--:--';
  const s = Math.max(0, Math.floor(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

export default function SmartAudioPlayer() {
  const {
    playlist,
    nowPlaying,
    isFallback,
    remaining,
    status,
    addTrack,
    play,
    pause,
    skip,
    seekToEnd,
  } = useSmartPlayer(DEFAULT_TRACKS);

  // 테스트용 AI 곡 추가 (실제로는 백엔드 응답에서 addTrack 호출)
  const testIdx = useRef(0);
  const addTestTrack = () => {
    const base = TEST_AI_TRACKS[testIdx.current % TEST_AI_TRACKS.length];
    testIdx.current += 1;
    addTrack({ ...base, id: `${base.id}-${testIdx.current}` });
  };

  return (
    <div className="sap">
      <section className="sap-now">
        <p className="sap-label">지금 재생 중</p>
        <h2>{nowPlaying ? nowPlaying.title : '재생 대기'}</h2>
        <p className="sap-meta">
          남은 시간 {fmt(remaining)}
          {isFallback && <span className="sap-badge">기본 BGM 대체 재생 중</span>}
        </p>

        <div className="sap-controls">
          {status === 'playing' ? (
            <button onClick={pause}>일시정지</button>
          ) : (
            <button onClick={play}>{status === 'idle' ? '재생 시작' : '다시 재생'}</button>
          )}
          <button onClick={skip} disabled={status !== 'playing'}>다음 곡</button>
        </div>
      </section>

      <section>
        <h3>대기열 ({playlist.length})</h3>
        {playlist.length === 0 ? (
          <p className="sap-empty">
            대기열이 비었어요. 곡이 끝나면 기본 BGM으로 이어서 재생해요.
          </p>
        ) : (
          <ol className="sap-queue">
            {playlist.map((t) => (
              <li key={t.id}>
                {t.title} <span className="sap-mood">{t.mood}</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="sap-test">
        <h3>테스트</h3>
        <button onClick={addTestTrack}>AI 곡 대기열에 추가</button>
        <button onClick={() => seekToEnd(8)} disabled={status !== 'playing'}>
          현재 곡 끝 8초 전으로 점프
        </button>
        <p className="sap-hint">
          점프 후 3초쯤 지나면(종료 5초 전) 크로스페이드가 시작돼요.
        </p>
      </section>
    </div>
  );
}