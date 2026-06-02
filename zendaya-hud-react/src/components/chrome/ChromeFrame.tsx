import { useZendaya } from "../../store/zendayaStore";
import { THEMES } from "../../themes/registry";
import RingChrome from "./RingChrome";
import ApertureChrome from "./ApertureChrome";
import ThemePicker from "./ThemePicker";

export default function ChromeFrame() {
  const id = useZendaya((s) => s.activeThemeId);
  const chrome = THEMES[id]?.chrome ?? "ring";

  return (
    <>
      <div className="zen-chrome-frame" aria-hidden>
        {chrome === "aperture" ? <ApertureChrome /> : <RingChrome />}
      </div>
      <ThemePicker />
    </>
  );
}
