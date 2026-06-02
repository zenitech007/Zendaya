import type { CSSProperties, ReactNode } from "react";
import { useZendaya } from "../store/zendayaStore";
import { THEMES } from "./registry";
import type { ThemeTokens } from "./types";

export function themeCssVars(t: ThemeTokens): Record<string, string> {
  return {
    "--zen-primary": t.primary,
    "--zen-accent": t.accent,
    "--zen-bg-0": t.bg[0],
    "--zen-bg-1": t.bg[1],
    "--zen-text-glow": t.textGlow,
    "--zen-grain": String(t.grain),
  };
}

export default function ThemeRoot({ children }: { children: ReactNode }) {
  const id = useZendaya((s) => s.activeThemeId);
  const tokens = THEMES[id] ?? THEMES.forge;
  return (
    <div
      className="zen-theme-root"
      data-theme={tokens.id}
      style={themeCssVars(tokens) as CSSProperties}
    >
      {children}
    </div>
  );
}
