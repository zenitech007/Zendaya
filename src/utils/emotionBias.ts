export function emotionBias(text: string) {
  const t = text.toLowerCase();
  if (/(help|emergency|urgent|now|please help|don't|can't)/.test(t)) return 0.25;
  if (/(love|babe|please|thanks)/.test(t)) return 0.05;
  return 0;
}
