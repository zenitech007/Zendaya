import { useZendaya } from "../../store/zendayaStore";
import { useWeather } from "../../hooks/useWeather";
import type { WeatherForm } from "../../scenes/weatherForms";

const LABELS: Record<WeatherForm, string> = {
  clear: "Clear",
  clouds: "Cloudy",
  rain: "Rain",
  snow: "Snow",
  storm: "Storm",
  fog: "Fog",
};

/** Floating holographic temp/condition/city/wind/humidity; weather scene only. */
export default function WeatherReadout() {
  const activeModule = useZendaya((s) => s.activeModule);
  const wx = useWeather();

  if (activeModule !== "weather") return null;

  return (
    <div className="zen-weather-readout">
      {wx.loading && <div className="zen-wx-status">Locating…</div>}
      {!wx.loading && wx.error && <div className="zen-wx-status">Weather unavailable</div>}
      {!wx.loading && !wx.error && (
        <>
          <div className="zen-wx-temp">{wx.tempC != null ? Math.round(wx.tempC) : "--"}°</div>
          <div className="zen-wx-cond">{LABELS[wx.form]}</div>
          <div className="zen-wx-city">{wx.city}</div>
          <div className="zen-wx-meta">
            <span>wind {wx.windKph != null ? Math.round(wx.windKph) : "--"} km/h</span>
            <span>humidity {wx.humidity != null ? Math.round(wx.humidity) : "--"}%</span>
          </div>
        </>
      )}
    </div>
  );
}
