export type Visemes = { aa: number; ih: number; ee: number; oh: number; ou: number };

function clean(v: unknown): number {
  const n = typeof v === "number" ? v : 0;
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(1, n));
}

export function normaliseVisemes(input: Partial<Visemes> | Record<string, unknown>): Visemes {
  return {
    aa: clean((input as any).aa),
    ih: clean((input as any).ih),
    ee: clean((input as any).ee),
    oh: clean((input as any).oh),
    ou: clean((input as any).ou),
  };
}
