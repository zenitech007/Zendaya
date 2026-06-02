import { useEffect, useState } from "react";
import { wmoToForm, type WeatherForm } from "../scenes/weatherForms";

export interface WeatherData {
  tempC: number | null;
  code: number | null;
  windKph: number | null;
  humidity: number | null;
  city: string;
  form: WeatherForm;
  loading: boolean;
  error: string | null;
}

type WeatherCore = Omit<WeatherData, "loading" | "error">;
interface CacheEntry {
  data: WeatherCore;
  at: number;
}

// Module-level cache shared by the scene and the readout; ~10-min TTL.
let _cache: CacheEntry | null = null;
const TTL = 10 * 60 * 1000;

async function fetchWeather(): Promise<WeatherCore> {
  const geo = await fetch("https://ipapi.co/json/").then((r) => r.json());
  const lat = geo.latitude;
  const lon = geo.longitude;
  const city = geo.city ?? "—";
  const url =
    `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
    `&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m`;
  const wx = await fetch(url).then((r) => r.json());
  const c = wx.current ?? {};
  const code = c.weather_code ?? 0;
  return {
    tempC: c.temperature_2m ?? null,
    code,
    windKph: c.wind_speed_10m ?? null,
    humidity: c.relative_humidity_2m ?? null,
    city,
    form: wmoToForm(code),
  };
}

/** Geolocates via ipapi + fetches Open-Meteo current conditions; cached. */
export function useWeather(): WeatherData {
  const [state, setState] = useState<WeatherData>(() =>
    _cache
      ? { ..._cache.data, loading: false, error: null }
      : {
          tempC: null, code: null, windKph: null, humidity: null,
          city: "—", form: "clouds", loading: true, error: null,
        }
  );

  useEffect(() => {
    let alive = true;
    if (_cache && Date.now() - _cache.at < TTL) {
      setState({ ..._cache.data, loading: false, error: null });
      return;
    }
    setState((s) => ({ ...s, loading: true, error: null }));
    fetchWeather()
      .then((data) => {
        _cache = { data, at: Date.now() };
        if (alive) setState({ ...data, loading: false, error: null });
      })
      .catch((e) => {
        if (alive) setState((s) => ({ ...s, loading: false, error: String(e?.message ?? e) }));
      });
    return () => {
      alive = false;
    };
  }, []);

  return state;
}
