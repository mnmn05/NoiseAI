import { useCallback, useEffect, useRef, useState } from 'react';
import { Howl } from 'howler';

const FADE_MS = 5000; // 크로스페이드 길이 (5초)
const TRIGGER_SEC = 5; // 곡 종료 몇 초 전에 크로스페이드를 시작할지
const FIRST_FADE_MS = 1500; // 첫 곡 / 재시작 시 페이드인 길이
const TICK_MS = 250; // 남은 시간 체크 주기

/**
 * 스마트 재생 대기열 + 크로스페이드 플레이어
 *
 * - playlist(대기열): 초기값은 기본 곡 목록. addTrack() 으로 끝에 push.
 * - 곡 종료 5초 전: 현재 곡 fade(→0), 다음 곡 shift() 후 fade(0→1)
 * - 대기열이 비면: 기본 곡을 fallback 으로 돌려 음악이 끊기지 않게 함
 * - fallback 재생 중 새 곡이 들어오면: 즉시 새 곡으로 크로스페이드
 */
export function useSmartPlayer(defaultTracks) {
  // ---- UI 용 state ----
  const [playlist, setPlaylist] = useState(defaultTracks);
  const [nowPlaying, setNowPlaying] = useState(null);
  const [isFallback, setIsFallback] = useState(false);
  const [remaining, setRemaining] = useState(null);
  const [status, setStatus] = useState('idle'); // idle | playing | paused

  // ---- Howler 콜백/타이머에서 최신값을 읽기 위한 ref ----
  const queueRef = useRef([...defaultTracks]);
  const currentRef = useRef(null); // { track, howl, fallback }
  const fallbackIdxRef = useRef(0);
  const statusRef = useRef('idle');
  const errorCountRef = useRef(0);

  const setStatusBoth = (s) => {
    statusRef.current = s;
    setStatus(s);
  };
  const syncQueue = () => setPlaylist([...queueRef.current]);

  // 다음 곡 고르기: 대기열 우선(shift), 비어 있으면 기본곡 fallback
  const pickNext = useCallback(() => {
    if (queueRef.current.length > 0) {
      const track = queueRef.current.shift();
      syncQueue();
      return { track, fallback: false };
    }
    const n = defaultTracks.length;
    let track = defaultTracks[fallbackIdxRef.current % n];
    fallbackIdxRef.current += 1;
    // 방금 재생한 곡이 또 나오지 않게 한 칸 건너뜀
    if (n > 1 && currentRef.current?.track.id === track.id) {
      track = defaultTracks[fallbackIdxRef.current % n];
      fallbackIdxRef.current += 1;
    }
    return { track, fallback: true };
  }, [defaultTracks]);

  // 곡을 시작하면서 이전 곡과 크로스페이드
  const startTrack = useCallback(
    (track, fallback, fadeMs = FADE_MS) => {
      const prev = currentRef.current;

      const howl = new Howl({
        src: [track.url],
        html5: true, // 긴 mp3 스트리밍
        volume: 0,
        onend: () => {
          // 크로스페이드 없이 곡이 끝난 경우의 안전장치
          if (currentRef.current?.howl === howl) advance();
        },
        onloaderror: () => handleError(howl),
        onplayerror: () => handleError(howl),
      });

      currentRef.current = { track, howl, fallback };
      setNowPlaying(track);
      setIsFallback(fallback);
      setRemaining(null);

      howl.play();
      howl.fade(0, 1, fadeMs); // Fade-in

      if (prev) {
        // Fade-out 후 정리
        prev.howl.fade(prev.howl.volume(), 0, fadeMs);
        setTimeout(() => {
          prev.howl.stop();
          prev.howl.unload();
        }, fadeMs + 200);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const advance = useCallback(
    (fadeMs = FADE_MS) => {
      if (statusRef.current !== 'playing') return;
      const { track, fallback } = pickNext();
      startTrack(track, fallback, fadeMs);
    },
    [pickNext, startTrack]
  );

  // 로드 실패 시 다음 곡으로 (전부 실패하면 무한루프 방지)
  const handleError = useCallback(
    (howl) => {
      if (currentRef.current?.howl !== howl) return;
      errorCountRef.current += 1;
      if (errorCountRef.current > 5) {
        console.error('[SmartPlayer] 연속으로 재생에 실패해 중단합니다.');
        setStatusBoth('paused');
        return;
      }
      advance(500);
    },
    [advance]
  );

  // 남은 시간 감시 → 5초 전 크로스페이드 트리거
  useEffect(() => {
    const timer = setInterval(() => {
      const cur = currentRef.current;
      if (!cur || statusRef.current !== 'playing') return;

      const duration = cur.howl.duration();
      const pos = cur.howl.seek();
      if (!duration || typeof pos !== 'number') return; // 아직 로딩 중

      const left = duration - pos;
      setRemaining(left);
      if (pos > 0) errorCountRef.current = 0; // 정상 재생 확인

      if (left <= TRIGGER_SEC) advance();
    }, TICK_MS);

    return () => clearInterval(timer);
  }, [advance]);

  // 언마운트 정리
  useEffect(() => {
    return () => {
      currentRef.current?.howl.unload();
      currentRef.current = null;
    };
  }, []);

  // ===== 외부로 노출하는 API =====

  // 백엔드에서 새 AI 음악 URL 을 받으면 이 함수를 호출
  const addTrack = useCallback(
    (track) => {
      queueRef.current.push(track); // 대기열 맨 끝에 추가
      syncQueue();
      // fallback 재생 중이었다면 즉시 새 곡으로 크로스페이드
      if (currentRef.current?.fallback && statusRef.current === 'playing') {
        advance();
      }
    },
    [advance]
  );

  // 브라우저 자동재생 정책 때문에 첫 재생은 반드시 사용자 클릭으로 시작해야 함
  const play = useCallback(() => {
    if (statusRef.current === 'playing') return;
    if (currentRef.current) {
      currentRef.current.howl.play();
      setStatusBoth('playing');
      return;
    }
    setStatusBoth('playing');
    const { track, fallback } = pickNext();
    startTrack(track, fallback, FIRST_FADE_MS);
  }, [pickNext, startTrack]);

  const pause = useCallback(() => {
    currentRef.current?.howl.pause();
    setStatusBoth('paused');
  }, []);

  const skip = useCallback(() => advance(), [advance]);

  // 테스트용: 현재 곡을 끝나기 N초 전으로 점프
  const seekToEnd = useCallback((secondsBeforeEnd = 8) => {
    const howl = currentRef.current?.howl;
    if (!howl) return;
    const d = howl.duration();
    if (d) howl.seek(Math.max(0, d - secondsBeforeEnd));
  }, []);

  return {
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
  };
}