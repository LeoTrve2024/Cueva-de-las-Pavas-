import { useEffect, useMemo, useState } from "react";
import { AdminView } from "./admin";
import {
  api,
  type Day,
  dayMonth,
  type Forecast,
  LEVEL_LABEL,
  longDate,
  type Weather,
  weekday,
} from "./api";

function weatherLabel(code: number | null): string {
  if (code === null) return "Sin datos";
  if (code === 0) return "Despejado";
  if ([1, 2, 3].includes(code)) return "Parcialmente nublado";
  if ([51, 53, 55, 61, 63, 65, 80, 81, 82].includes(code)) return "Lluvia";
  if ([95, 96, 99].includes(code)) return "Tormenta";
  return `Código ${code}`;
}

const fmt = (value: number) => value.toLocaleString("es-PE", { maximumFractionDigits: 1 });

function Breakdown({ day }: { day: Day }) {
  if (!day.factores) return null;
  const rainPoints = 0.6 * (100 - day.factores.lluvia_pct);
  const calendarPoints = 0.4 * day.factores.factor_dia;
  const weekend = day.factores.factor_dia === 100;
  return (
    <div className="breakdown">
      <div>
        <div className="breakdown-row">
          <span>Lluvia {fmt(day.factores.lluvia_pct)} %</span>
          <b>{fmt(rainPoints)} de 60 pts</b>
        </div>
        <div className="bar">
          <i style={{ width: `${(rainPoints / 60) * 100}%` }} />
        </div>
      </div>
      <div>
        <div className="breakdown-row">
          <span>{weekend ? "Fin de semana" : "Día laborable"}</span>
          <b>{fmt(calendarPoints)} de 40 pts</b>
        </div>
        <div className="bar">
          <i style={{ width: `${(calendarPoints / 40) * 100}%` }} />
        </div>
      </div>
    </div>
  );
}

function TouristView() {
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
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : "No se pudo cargar la información."),
      );
  }, []);

  const selectedDay = useMemo(
    () => forecast?.dias.find((day) => day.fecha === selected) ?? null,
    [forecast, selected],
  );

  const bestDay = useMemo(() => {
    const scored = forecast?.dias.filter((day) => day.puntuacion != null) ?? [];
    return scored.reduce<Day | null>(
      (best, day) => (best === null || (day.puntuacion ?? 0) > (best.puntuacion ?? 0) ? day : best),
      null,
    );
  }, [forecast]);

  return (
    <>
      <header className="hero">
        <div>
          <p className="eyebrow">Información turística</p>
          <h1>Cueva de las Pavas</h1>
          <p className="lead">
            Consulta el clima y una puntuación orientativa de afluencia para los próximos siete
            días.
          </p>
        </div>
        <div className="place">Mariano Dámaso Beraún · Huánuco</div>
      </header>

      {error && (
        <div className="alert" role="alert">
          <strong>No se pudo cargar la información.</strong>
          <span>{error}</span>
        </div>
      )}

      <section className="current" aria-label="Clima actual">
        <div>
          <span className="label">Clima actual</span>
          <strong>{weather ? weatherLabel(weather.codigo_clima) : "Cargando…"}</strong>
        </div>
        <div>
          <span className="label">Temperatura</span>
          <strong>
            {weather?.temperatura == null ? "—" : `${weather.temperatura.toFixed(1)} °C`}
          </strong>
        </div>
        <div>
          <span className="label">Actualizado</span>
          <strong>
            {weather?.momento_dato ? new Date(weather.momento_dato).toLocaleString("es-PE") : "—"}
          </strong>
        </div>
      </section>

      <section>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Pronóstico</p>
            <h2>Compara los próximos siete días</h2>
            {bestDay && (
              <p className="best">
                Mejor día para ir: <b>{longDate(bestDay.fecha)}</b> ({bestDay.puntuacion}/100)
              </p>
            )}
          </div>
          <span className="legend">
            Índice experimental · versión {forecast?.version_reglas ?? "1"}
          </span>
        </div>
        <div className="days">
          {forecast?.dias.map((day) => {
            const weekend = day.factores?.factor_dia === 100;
            return (
              <button
                type="button"
                className={`day-card level-${day.nivel ?? "none"} ${selected === day.fecha ? "selected" : ""}`}
                key={day.fecha}
                aria-pressed={selected === day.fecha}
                onClick={() => setSelected(day.fecha)}
              >
                <span className="day-name">
                  {weekday(day.fecha)}
                  {weekend && <small className="tag">Finde</small>}
                </span>
                <strong>{dayMonth(day.fecha)}</strong>
                <b>{day.puntuacion == null ? "—" : `${day.puntuacion}/100`}</b>
                <div className="bar">
                  <i style={{ width: `${day.puntuacion ?? 0}%` }} />
                </div>
                <small className="pill">
                  {day.nivel ? LEVEL_LABEL[day.nivel] : "Sin estimación"}
                </small>
                {day.visitas_estimadas != null && (
                  <span className="visits">≈ {day.visitas_estimadas} visitas</span>
                )}
                <em>{day.factores ? `${day.factores.lluvia_pct}% lluvia` : "Datos faltantes"}</em>
              </button>
            );
          }) ?? <p className="empty">Cargando pronóstico…</p>}
        </div>
      </section>

      {selectedDay && (
        <section className={`detail level-${selectedDay.nivel ?? "none"}`} aria-live="polite">
          <div>
            <p className="eyebrow">Detalle del día</p>
            <h2>{longDate(selectedDay.fecha)}</h2>
          </div>
          <div className="score">
            <span>Puntuación orientativa</span>
            <strong>
              {selectedDay.puntuacion == null ? "—" : `${selectedDay.puntuacion}/100`}
            </strong>
            <b className="pill">
              {selectedDay.nivel ? LEVEL_LABEL[selectedDay.nivel] : "Sin estimación"}
            </b>
            {selectedDay.visitas_estimadas != null && (
              <small>≈ {selectedDay.visitas_estimadas} visitas (estimación muy aproximada)</small>
            )}
          </div>
          <div className="explanation">
            <strong>¿Cómo se calcula?</strong>
            <p>{selectedDay.explicacion}</p>
            <Breakdown day={selectedDay} />
            <p>
              La cifra de visitas es una conversión experimental: usa el total de 2023 de MINCETUR
              (62 550 visitas, conteo de 4 semanas), por lo que no es una medición ni una
              probabilidad de asistencia.
            </p>
          </div>
        </section>
      )}

      <footer>
        Fuente meteorológica: Open-Meteo. Las puntuaciones son experimentales y deben validarse con
        registros diarios reales. <a href="#admin">Administración</a>
      </footer>
    </>
  );
}

const readView = () => (window.location.hash === "#admin" ? "admin" : "public");

export function App() {
  const [view, setView] = useState(readView);

  useEffect(() => {
    const onChange = () => setView(readView());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return <main className="shell">{view === "admin" ? <AdminView /> : <TouristView />}</main>;
}
