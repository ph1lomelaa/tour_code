import { useEffect, useState } from "react";
import { getReferenceData, ReferenceData } from "../../src/lib/api/settings";

export interface ReferenceOptions {
  hotels: string[];
  countries: string[];
  routes: { code: string; departure_city: string }[];
  airlines: { code: string; label: string }[];
  touragents: { name: string; bin: string; is_default: boolean }[];
}

// Используются, пока справочники грузятся или если бэкенд недоступен.
// Совпадают с начальными данными db/seed_reference.py.
const FALLBACK: ReferenceOptions = {
  hotels: [
    "Hilton Makkah Convention Hotel",
    "Swissotel Makkah",
    "Pullman ZamZam Makkah",
    "Fairmont Makkah Clock Royal Tower",
    "Conrad Makkah",
    "Anjum Hotel Makkah",
    "Elaf Kinda Hotel",
    "Millennium Al Aqeeq Hotel",
    "Raffles Makkah",
    "Jumeirah Jabal Omar Makkah",
    "Dar Al Tawhid Makkah",
    "Dar Al Taqwa Madinah 5*",
    "Courtyard by Marriott",
  ],
  countries: [
    "Саудовская Аравия",
    "Казахстан",
    "Катар",
    "Объединенные Арабские Эмираты",
    "Турция",
  ],
  routes: [
    { code: "ALA-DOH-JED", departure_city: "Almaty" },
    { code: "JED-DOH-ALA", departure_city: "Jeddah" },
    { code: "ALA-JED", departure_city: "Almaty" },
    { code: "ALA-MED", departure_city: "Almaty" },
    { code: "NQZ-JED", departure_city: "Nur-Sultan" },
    { code: "NQZ-MED", departure_city: "Nur-Sultan" },
    { code: "NQZ-ALA", departure_city: "Nur-Sultan" },
    { code: "SCO-MED", departure_city: "Shymkent" },
    { code: "SCO-JED", departure_city: "Shymkent" },
    { code: "CIT-MED", departure_city: "Shymkent" },
    { code: "CIT-JED", departure_city: "Shymkent" },
    { code: "DXB-MED", departure_city: "Dubai" },
    { code: "DXB-JED", departure_city: "Dubai" },
  ],
  airlines: [
    { code: "KC", label: "KC — Air Astana" },
    { code: "DV", label: "DV — SCAT" },
    { code: "FZ", label: "FZ — Flydubai" },
    { code: "EK", label: "EK — Emirates" },
    { code: "QR", label: "QR — Qatar Airways" },
    { code: "THY", label: "THY — Turkish Airlines" },
  ],
  touragents: [
    { name: "Хикмет Travel", bin: "080340019818", is_default: true },
    { name: "HICKMET PREMIUM", bin: "240340000277", is_default: false },
    { name: "NIYET", bin: "230940022228", is_default: false },
    { name: "AL-MARWA", bin: "030340005591", is_default: false },
  ],
};

const toOptions = (data: ReferenceData): ReferenceOptions => ({
  hotels: data.hotels.map((h) => h.name || "").filter(Boolean),
  countries: data.countries.map((c) => c.name_ru || "").filter(Boolean),
  routes: data.routes.map((r) => ({ code: r.code || "", departure_city: r.departure_city || "" })),
  airlines: data.airlines.map((a) => ({
    code: a.code || "",
    label: a.name ? `${a.code} — ${a.name}` : a.code || "",
  })),
  touragents: data.touragents.map((t) => ({
    name: t.name || "",
    bin: t.bin || "",
    is_default: Boolean(t.is_default),
  })),
});

let cached: ReferenceOptions | null = null;
let inflight: Promise<ReferenceOptions> | null = null;

const loadReference = (): Promise<ReferenceOptions> => {
  if (!inflight) {
    inflight = getReferenceData()
      .then((data) => {
        cached = toOptions(data);
        return cached;
      })
      .catch((error) => {
        inflight = null;
        throw error;
      });
  }
  return inflight;
};

/** Сбросить кеш после изменений в «Настройках». */
export const invalidateReferenceData = () => {
  cached = null;
  inflight = null;
};

export function useReferenceData(): { options: ReferenceOptions; loaded: boolean } {
  const [options, setOptions] = useState<ReferenceOptions>(cached || FALLBACK);
  const [loaded, setLoaded] = useState(Boolean(cached));

  useEffect(() => {
    if (cached) return;
    let alive = true;
    loadReference()
      .then((data) => {
        if (!alive) return;
        setOptions(data);
        setLoaded(true);
      })
      .catch((error) => {
        console.warn("Справочники недоступны, используются встроенные значения", error);
      });
    return () => {
      alive = false;
    };
  }, []);

  return { options, loaded };
}

/** Список вариантов + текущее значение, если его уже нет в справочнике (старые туры). */
export const withCurrent = (values: string[], current?: string): string[] =>
  current && !values.includes(current) ? [current, ...values] : values;
