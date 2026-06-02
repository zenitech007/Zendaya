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

interface IpapiResponse {
  latitude?: number;
  longitude?: number;
  city?: string;
}
interface OpenMeteoCurrent {
  temperature_2m?: number;
  weather_code?: number;
  wind_speed_10m?: number;
  relative_humidity_2m?: number;
}
interface OpenMeteoResponse {
  current?: OpenMeteoCurrent;
}

// Module-level cache shared by the scene and the readout; ~10-min TTL.
let _cache: CacheEntry | null = null;
// Shared in-flight request so multiple consumers (scene + readout) mounting on
// the same tick issue a single network round-trip instead of racing duplicates.
let _inflight: Promise<WeatherCore> | null = null;
const TTL = 10 * 60 * 1000;

async function fetchJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  // Without this, a 429/5xx error body still resolves `.json()` and the bad
  // payload silently flows through (e.g. weather_code defaults to 0 = "Clear").
  if (!r.ok) throw new Error(`${r.status} ${r.statusText || "request failed"}`);
  return (await r.json()) as T;
}

async function fetchWeather(): Promise<WeatherCore> {
  const geo = await fetchJson<IpapiResponse>("https://ipapi.co/json/");
  if (geo.latitude == null || geo.longitude == null) {
    throw new Error("geolocation unavailable");
  }
  const city = geo.city ?? "—";
  const url =
    `https://api.open-meteo.com/v1/forecast?latitude=${geo.latitude}&longitude=${geo.longitude}` +
    `&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m`;
  const wx = await fetchJson<OpenMeteoResponse>(url);
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

/** Dedupe concurrent first-load fetches into one shared promise. */
function loadWeather(): Promise<WeatherCore> {
  if (!_inflight) {
    _inflight = fetchWeather().finally(() => {
      _inflight = null;
    });
  }
  return _inflight;
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
    loadWeather()
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
