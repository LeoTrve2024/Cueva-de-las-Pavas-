export type Level = "baja" | "media" | "alta";

export type Day = {
  fecha: string;
  estado: "disponible" | "sin_estimacion";
  puntuacion: number | null;
  nivel: Level | null;
  visitas_estimadas: number | null;
  factores: { lluvia_pct: number; factor_dia: number } | null;
  explicacion: string;
};

export type Forecast = {
  consultado_en: string;
  calculado_en: string;
  version_reglas: string;
  dias: Day[];
};

export type Weather = {
  momento_dato: string | null;
  temperatura: number | null;
  codigo_clima: number | null;
  estado: "disponible" | "sin_datos";
  motivo: string | null;
};

export type Comparison = {
  resumen: {
    dias_comparados: number;
    error_absoluto_medio: number | null;
    sesgo_medio: number | null;
  };
  resultados: {
    fecha: string;
    visitantes_reales: number;
    nota: string | null;
    puntuacion: number | null;
    nivel: Level | null;
    visitas_estimadas: number | null;
    diferencia: number | null;
  }[];
};

type Options = { method?: string; body?: unknown; auth?: string };

export const basicAuth = (user: string, password: string): string => {
  const bytes = new TextEncoder().encode(`${user}:${password}`);
  return `Basic ${btoa(String.fromCharCode(...bytes))}`;
};

export const api = async <T>(path: string, options: Options = {}): Promise<T> => {
  const headers: Record<string, string> = {};
  if (options.auth) headers.Authorization = options.auth;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(`/api/v1${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : null;
    if (response.status === 401) throw new Error(detail ?? "Usuario o contraseña incorrectos.");
    throw new Error(detail ?? "No se pudo consultar el servicio.");
  }
  return response.json() as Promise<T>;
};

export const LEVEL_LABEL: Record<Level, string> = { baja: "Baja", media: "Media", alta: "Alta" };

const dateOf = (iso: string) => new Date(`${iso}T12:00:00`);
export const weekday = (iso: string, style: "short" | "long" = "short") =>
  dateOf(iso).toLocaleDateString("es-PE", { weekday: style });
export const dayMonth = (iso: string) =>
  dateOf(iso).toLocaleDateString("es-PE", { day: "2-digit", month: "short" });
export const longDate = (iso: string) =>
  dateOf(iso).toLocaleDateString("es-PE", { weekday: "long", day: "numeric", month: "long" });
