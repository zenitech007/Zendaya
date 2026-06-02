import type { CSSProperties } from "react";
import { useZendaya } from "../../store/zendayaStore";
import { THEME_ORDER, THEMES } from "../../themes/registry";

export default function ThemePicker() {
  const active = useZendaya((s) => s.activeThemeId);
  const setTheme = useZendaya((s) => s.setTheme);

  return (
    <div className="zen-theme-picker" role="group" aria-label="Theme picker">
      {THEME_ORDER.map((id) => {
        const t = THEMES[id];
        const isActive = id === active;
        return (
          <button
            key={id}
            type="button"
            className={"zen-theme-dot" + (isActive ? " active" : "")}
            aria-label={t.name}
            aria-current={isActive}
            title={t.name}
            style={{ "--dot": t.primary } as CSSProperties}
            onClick={() => setTheme(id)}
          />
        );
      })}
    </div>
  );
}
