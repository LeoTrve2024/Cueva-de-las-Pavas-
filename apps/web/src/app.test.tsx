import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "./app";

const forecast = {
  consultado_en: "2026-10-06T10:00:00-05:00",
  calculado_en: "2026-10-06T10:00:00-05:00",
  version_reglas: "1",
  dias: Array.from({ length: 7 }, (_, i) => ({
    fecha: `2026-10-${String(6 + i).padStart(2, "0")}`,
    estado: "disponible",
    puntuacion: 88,
    nivel: "alta",
    visitas_estimadas: 300,
    factores: { lluvia_pct: 20, factor_dia: 100 },
    explicacion: "Lluvia 20 % y fin de semana",
  })),
};
const weather = {
  momento_dato: "2026-10-06T10:00:00-05:00",
  temperatura: 24,
  codigo_clima: 1,
  estado: "disponible",
  motivo: null,
};

describe("application", () => {
  it("renders the weekly tourist view", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          json: async () => (url.includes("afluencia") ? forecast : weather),
        }),
      ),
    );
    render(<App />);
    expect(screen.getByRole("heading", { name: "Cueva de las Pavas" })).toBeInTheDocument();
    expect(await screen.findByText("Compara los próximos siete días")).toBeInTheDocument();
    expect((await screen.findAllByText("88/100")).length).toBeGreaterThan(0);
    expect(screen.getByText(/Mejor día para ir/)).toBeInTheDocument();
    expect(screen.getByText("Lluvia 20 %")).toBeInTheDocument();
    expect(screen.getByText("48 de 60 pts")).toBeInTheDocument();
  });

  it("shows the admin login at #admin", () => {
    window.location.hash = "#admin";
    render(<App />);
    expect(screen.getByRole("heading", { name: "Acceso de administración" })).toBeInTheDocument();
    window.location.hash = "";
  });
});
