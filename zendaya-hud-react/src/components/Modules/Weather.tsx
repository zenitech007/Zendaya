import { useEffect, useState } from "react";
import ModulePanel from "./ModulePanel";

interface WX {
  tempC: number;
  code: number;
  windKph: number;
  humidity: number;
  city: string;
}

const WMO: Record<number, { label: string; icon: string }> = {
  0: { label: "Clear", icon: "☀" },
  1: { label: "Mostly Clear", icon: "🌤" },
  2: { label: "Partly Cloudy", icon: "⛅" },
  3: { label: "Overcast", icon: "☁" },
  45: { label: "Fog", icon: "🌫" },
  48: { label: "Rime Fog", icon: "🌫" },
  51: { label: "Drizzle", icon: "🌦" },
  61: { label: "Rain", icon: "🌧" },
  63: { label: "Rain", icon: "🌧" },
  65: { label: "Heavy Rain", icon: "🌧" },
  71: { label: "Snow", icon: "🌨" },
  80: { label: "Showers", icon: "🌦" },
  95: { label: "Thunderstorm", icon: "⛈" },
};

async function fetchWeather(): Promise<WX | null> {
  try {
    const geo = await fetch("https://ipapi.co/json/").then((r) => r.json());
    const lat = geo.latitude;
    const lon = geo.longitude;
    const city = geo.city ?? "Unknown";
    const wx = await fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m`
    ).then((r) => r.json());
    const c = wx.current;
    return {
      tempC: Math.round(c.temperature_2m),
      code: c.weather_code,
      windKph: Math.round(c.wind_speed_10m),
      humidity: c.relative_humidity_2m,
      city,
    };
  } catch {
    return null;
  }
}

export default function Weather() {
  const [wx, setWx] = useState<WX | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchWeather().then((r) => {
      if (!alive) return;
      if (r) setWx(r);
      else setErr(true);
    });
    return () => {
      alive = false;
    };
  }, []);

  const desc = wx ? WMO[wx.code] ?? { label: "—", icon: "·" } : null;

  return (
    <ModulePanel title="Weather">
      {!wx && !err && (
        <div className="text-center py-8 tracking-widest" style={{ opacity: 0.6 }}>
          Loading…
        </div>
      )}
      {err && (
        <div className="text-center py-8" style={{ color: "#ff8a3c" }}>
          Couldn't reach weather service.
        </div>
      )}
      {wx && desc && (
        <div>
          <div className="text-center text-xs tracking-[0.3em] mb-1" style={{ opacity: 0.7 }}>
            {wx.city.toUpperCase()}
          </div>
          <div className="flex items-center justify-center gap-4">
            <div style={{ fontSize: "3.2em", lineHeight: 1 }}>{desc.icon}</div>
            <div>
              <div className="text-5xl" style={{ color: "#ff8a3c" }}>
                {wx.tempC}°
              </div>
              <div className="text-sm tracking-widest" style={{ opacity: 0.75 }}>
                {desc.label}
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 mt-5 text-sm">
            <div
              className="px-3 py-2 rounded"
              style={{
                background: "rgba(255,138,60,0.06)",
                border: "1px solid rgba(255,138,60,0.18)",
              }}
            >
              <div className="text-xs tracking-widest" style={{ opacity: 0.6 }}>
                WIND
              </div>
              <div>{wx.windKph} kph</div>
            </div>
            <div
              className="px-3 py-2 rounded"
              style={{
                background: "rgba(255,138,60,0.06)",
                border: "1px solid rgba(255,138,60,0.18)",
              }}
            >
              <div className="text-xs tracking-widest" style={{ opacity: 0.6 }}>
                HUMIDITY
              </div>
              <div>{wx.humidity}%</div>
            </div>
          </div>
        </div>
      )}
    </ModulePanel>
  );
}
