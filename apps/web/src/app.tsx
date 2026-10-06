import { useEffect, useMemo, useState } from "react";

type Day = {
  fecha: string;
  estado: "disponible" | "sin_estimacion";
  puntuacion: number | null;
  nivel: "baja" | "media" | "alta" | null;
  visitas_estimadas: number | null;
  factores: { lluvia_pct: number; factor_dia: number } | null;
  explicacion: string;
};

type Forecast = {
  consultado_en: string;
  calculado_en: string;
  version_reglas: string;
  dias: Day[];
};

type Weather = {
  momento_dato: string | null;
  temperatura: number | null;
  codigo_clima: number | null;
  estado: "disponible" | "sin_datos";
  motivo: string | null;
};

const api = async <T,>(path: string): Promise<T> => {
  const response = await fetch(`/api/v1${path}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Error inesperado." }));
    throw new Error(body.detail ?? "No se pudo consultar el servicio.");
  }
  return response.json() as Promise<T>;
};

function weatherLabel(code: number | null): string {
  if (code === null) return "Sin datos";
  if (code === 0) return "Despejado";
  if ([1, 2, 3].includes(code)) return "Parcialmente nublado";
  if ([51, 53, 55, 61, 63, 65, 80, 81, 82].includes(code)) return "Lluvia";
  if ([95, 96, 99].includes(code)) return "Tormenta";
  return `Código ${code}`;
}

export function App() {
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [weather, setWeather] = useState<Weather | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api<Forecast>("/afluencia/pronostico"), api<Weather>("/clima/actual")])
      .then(([nextForecast, nextWeather]) => {
        setForecast(nextForecast);
        setWeather(nextWeather);
        setSelected(nextForecast.dias[0]?.fecha ?? null);
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "No se pudo cargar la información."));
  }, []);

  const selectedDay = useMemo(
    () => forecast?.dias.find((day) => day.fecha === selected) ?? null,
    [forecast, selected],
  );

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Información turística</p>
          <h1>Cueva de las Pavas</h1>
          <p className="lead">Consulta el clima y una puntuación orientativa de afluencia para los próximos siete días.</p>
        </div>
        <div className="place">Mariano Dámaso Beraún · Huánuco</div>
      </header>

      {error && <div className="alert" role="alert"><strong>No se pudo cargar la información.</strong><span>{error}</span></div>}

      <section className="current" aria-label="Clima actual">
        <div><span className="label">Clima actual</span><strong>{weather ? weatherLabel(weather.codigo_clima) : "Cargando…"}</strong></div>
        <div><span className="label">Temperatura</span><strong>{weather?.temperatura == null ? "—" : `${weather.temperatura.toFixed(1)} °C`}</strong></div>
        <div><span className="label">Actualizado</span><strong>{weather?.momento_dato ? new Date(weather.momento_dato).toLocaleString("es-PE") : "—"}</strong></div>
      </section>

      <section>
        <div className="section-heading"><div><p className="eyebrow">Pronóstico</p><h2>Compara los próximos siete días</h2></div><span className="legend">Índice experimental · versión {forecast?.version_reglas ?? "1"}</span></div>
        <div className="days">
          {forecast?.dias.map((day) => (
            <button className={`day-card ${selected === day.fecha ? "selected" : ""}`} key={day.fecha} onClick={() => setSelected(day.fecha)}>
              <span>{new Date(`${day.fecha}T12:00:00`).toLocaleDateString("es-PE", { weekday: "short" })}</span>
              <strong>{new Date(`${day.fecha}T12:00:00`).toLocaleDateString("es-PE", { day: "2-digit", month: "short" })}</strong>
              <b>{day.puntuacion == null ? "—" : `${day.puntuacion}/100`}</b>
              <small>{day.nivel ? day.nivel.toUpperCase() : "SIN ESTIMACIÓN"}</small>
              <em>{day.factores ? `${day.factores.lluvia_pct}% lluvia` : "Datos faltantes"}</em>
            </button>
          )) ?? <p className="empty">Cargando pronóstico…</p>}
        </div>
      </section>

      {selectedDay && (
        <section className="detail" aria-live="polite">
          <div><p className="eyebrow">Detalle del día</p><h2>{new Date(`${selectedDay.fecha}T12:00:00`).toLocaleDateString("es-PE", { weekday: "long", day: "numeric", month: "long" })}</h2></div>
          <div className="score"><span>Puntuación orientativa</span><strong>{selectedDay.puntuacion == null ? "—" : `${selectedDay.puntuacion}/100`}</strong><b>{selectedDay.nivel ?? "Sin estimación"}</b>{selectedDay.visitas_estimadas != null && <small>≈ {selectedDay.visitas_estimadas} visitas (estimación muy aproximada)</small>}</div>
          <div className="explanation"><strong>¿Cómo se calcula?</strong><p>{selectedDay.explicacion}</p><p>La puntuación combina 60 % de la condición asociada a la lluvia y 40 % del factor de calendario. La cifra de visitas es una conversión experimental: usa el total de 2023 de MINCETUR (62 550 visitas, conteo de 4 semanas), por lo que no es una medición ni una probabilidad de asistencia.</p></div>
        </section>
      )}

      <footer>Fuente meteorológica: Open-Meteo. Las puntuaciones son experimentales y deben validarse con registros diarios reales.</footer>
    </main>
  );
}
