// 기본 BGM 풀 (T2 결과물이 나오기 전까지는 임시 샘플 URL 사용)
// 나중에 MusicGen 음원이 나오면 url 만 '/audio/xxx.mp3' 로 교체하면 됩니다.
// mood: 'calm' | 'normal' | 'upbeat'
const SAMPLE = (n) =>
  `https://www.soundhelix.com/examples/mp3/SoundHelix-Song-${n}.mp3`;

export const DEFAULT_TRACKS = [
  { id: 'default-1', url: SAMPLE(1), title: '기본 BGM 1', mood: 'calm' },
  { id: 'default-2', url: SAMPLE(2), title: '기본 BGM 2', mood: 'calm' },
  { id: 'default-3', url: SAMPLE(3), title: '기본 BGM 3', mood: 'normal' },
  { id: 'default-4', url: SAMPLE(4), title: '기본 BGM 4', mood: 'normal' },
  { id: 'default-5', url: SAMPLE(5), title: '기본 BGM 5', mood: 'upbeat' },
];

// 테스트용: "AI 곡 추가" 버튼이 사용할 샘플
export const TEST_AI_TRACKS = [6, 7, 8, 9, 10].map((n) => ({
  id: `ai-${n}`,
  url: SAMPLE(n),
  title: `AI 생성곡 ${n - 5}`,
  mood: 'normal',
}));