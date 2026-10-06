import { type FormEvent, useCallback, useState } from "react";
import { api, basicAuth, type Comparison, dayMonth, LEVEL_LABEL, weekday } from "./api";

const isoDate = (date: Date) => date.toLocaleDateString("sv-SE");

function range() {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - 29);
  return { desde: isoDate(start), hasta: isoDate(end) };
}

const signed = (value: number) => (value > 0 ? `+${value}` : `${value}`);

export function AdminView() {
  const [user, setUser] = useState("admin");
  const [password, setPassword] = useState("");
  const [auth, setAuth] = useState<string | null>(null);
  const [data, setData] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [fecha, setFecha] = useState(isoDate(new Date()));
  const [visitantes, setVisitantes] = useState("");
  const [nota, setNota] = useState("");

  const load = useCallback(async (header: string) => {
    const { desde, hasta } = range();
    setData(
      await api<Comparison>(`/afluencia/comparacion?desde=${desde}&hasta=${hasta}`, {
        auth: header,
      }),
    );
  }, []);

  const login = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const header = basicAuth(user, password);
      await load(header);
      setAuth(header);
      setPassword("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo iniciar sesión.");
    } finally {
      setBusy(false);
    }
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (!auth) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api(`/afluencia/visitantes/${fecha}`, {
        method: "PUT",
        auth,
        body: { visitantes: Number(visitantes), nota: nota.trim() || null },
      });
      await load(auth);
      setNotice(`Registro guardado para el ${dayMonth(fecha)}.`);
      setVisitantes("");
      setNota("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo guardar el registro.");
    } finally {
      setBusy(false);
    }
  };

  const maxValue = Math.max(
    1,
    ...(data?.resultados.flatMap((row) => [row.visitantes_reales, row.visitas_estimadas ?? 0]) ??
      []),
  );

  return (
    <>
      <header className="hero">
        <div>
          <p className="eyebrow">Administración</p>
          <h1>Registro de visitantes</h1>
          <p className="lead">
            Anota cuántas personas visitaron el balneario cada día y compáralas con la estimación
            del índice.
          </p>
        </div>
        <a className="place" href="#inicio">
          ← Volver al pronóstico
        </a>
      </header>

      {error && (
        <div className="alert" role="alert">
          <strong>Algo salió mal.</strong>
          <span>{error}</span>
        </div>
      )}

      {!auth && (
        <form className="panel login" onSubmit={login}>
          <h2>Acceso de administración</h2>
          <label>
            Usuario
            <input
              value={user}
              onChange={(e) => setUser(e.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label>
            Contraseña
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <button type="submit" className="primary" disabled={busy}>
            {busy ? "Entrando…" : "Entrar"}
          </button>
        </form>
      )}

      {auth && data && (
        <>
          <section className="stats" aria-label="Resumen de la comparación">
            <div>
              <span className="label">Días comparados</span>
              <strong>{data.resumen.dias_comparados}</strong>
            </div>
            <div>
              <span className="label">Error medio</span>
              <strong>
                {data.resumen.error_absoluto_medio == null
                  ? "—"
                  : `${data.resumen.error_absoluto_medio} visitas`}
              </strong>
            </div>
            <div>
              <span className="label">Sesgo medio</span>
              <strong>
                {data.resumen.sesgo_medio == null
                  ? "—"
                  : `${signed(data.resumen.sesgo_medio)} visitas`}
              </strong>
              <small>Positivo: la estimación se pasa. Negativo: se queda corta.</small>
            </div>
          </section>

          <form className="panel entry" onSubmit={save}>
            <h2>Registrar un día</h2>
            <label>
              Fecha
              <input
                type="date"
                value={fecha}
                max={isoDate(new Date())}
                onChange={(e) => setFecha(e.target.value)}
                required
              />
            </label>
            <label>
              Visitantes
              <input
                type="number"
                min={0}
                max={100000}
                inputMode="numeric"
                value={visitantes}
                onChange={(e) => setVisitantes(e.target.value)}
                required
              />
            </label>
            <label className="wide">
              Nota (opcional)
              <input
                value={nota}
                maxLength={200}
                onChange={(e) => setNota(e.target.value)}
                placeholder="Feriado, evento, cierre parcial…"
              />
            </label>
            <button type="submit" className="primary" disabled={busy}>
              {busy ? "Guardando…" : "Guardar"}
            </button>
            {notice && (
              <p className="ok" role="status">
                {notice}
              </p>
            )}
            <p className="hint">Si ya hay un registro para esa fecha, se reemplaza.</p>
          </form>

          <section>
            <div className="section-heading">
              <div>
                <p className="eyebrow">Últimos 30 días</p>
                <h2>Estimado vs. real</h2>
              </div>
              <span className="legend">
                <span className="swatch est" /> Estimado <span className="swatch real" /> Real
              </span>
            </div>
            {data.resultados.length === 0 ? (
              <p className="empty">
                Aún no hay registros. Anota los visitantes de hoy para empezar a comparar.
              </p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Puntuación</th>
                      <th>Comparación</th>
                      <th>Estimado</th>
                      <th>Real</th>
                      <th>Diferencia</th>
                      <th>Nota</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.resultados.map((row) => (
                      <tr key={row.fecha}>
                        <td>
                          {weekday(row.fecha)} {dayMonth(row.fecha)}
                        </td>
                        <td>
                          {row.puntuacion == null ? "—" : `${row.puntuacion}/100`}
                          {row.nivel && (
                            <small className={`pill level-${row.nivel}`}>
                              {LEVEL_LABEL[row.nivel]}
                            </small>
                          )}
                        </td>
                        <td className="pair">
                          <div className="bar est">
                            <i
                              style={{
                                width: `${((row.visitas_estimadas ?? 0) / maxValue) * 100}%`,
                              }}
                            />
                          </div>
                          <div className="bar real">
                            <i style={{ width: `${(row.visitantes_reales / maxValue) * 100}%` }} />
                          </div>
                        </td>
                        <td>{row.visitas_estimadas ?? "—"}</td>
                        <td>
                          <b>{row.visitantes_reales}</b>
                        </td>
                        <td>{row.diferencia == null ? "—" : signed(row.diferencia)}</td>
                        <td>{row.nota ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="hint">
              La estimación es la última puntuación calculada para esa fecha. Solo hay estimación
              para los días en que la app estuvo encendida y los tuvo en su pronóstico de siete
              días.
            </p>
          </section>
        </>
      )}
    </>
  );
}
