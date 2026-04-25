// utils/audioChime.ts
export const playChime = (url?: string) => {
  const audio = new Audio(url ?? "/sounds/listening-chime.mp3");
  audio.volume = 0.6;
  audio.play().catch(() => {});
};
