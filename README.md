# Cueva de las Pavas

Implementación del diseño técnico del primer avance para una aplicación turística de Cueva de las Pavas.

## Arquitectura

- React + Vite para la vista pública.
- Nginx como entrada HTTP/HTTPS y proxy.
- `clima`: FastAPI + Open-Meteo, con caché de una hora y persistencia en `clima`.
- `afluencia`: FastAPI, regla experimental 1 y persistencia en `afluencia`.
- PostgreSQL con esquemas y roles separados por microservicio.
- Docker Compose para ejecución local y posterior traslado a EC2.

## Configuración

Copiar `.env.example` a `.env` y completar **CLIMA_LATITUDE** y **CLIMA_LONGITUDE** con las coordenadas WGS84 verificadas del balneario. El proyecto no incluye coordenadas inventadas.

Para la demostración local:

```bash
bun run setup
docker compose up --build
```

La interfaz queda en `https://localhost` (certificado autofirmado de desarrollo). El navegador puede mostrar una advertencia por tratarse de un certificado local.

## API

- `GET /api/v1/clima/actual`
- `GET /api/v1/clima/pronostico`
- `GET /api/v1/afluencia/pronostico`
- `GET /api/v1/afluencia/historial?desde=YYYY-MM-DD&hasta=YYYY-MM-DD&pagina=1`
- `GET /health`

El historial requiere autenticación Basic. Las credenciales de desarrollo se definen en `.env`; deben cambiarse antes de publicar.

## Regla de afluencia

`S = redondear(0.6 × (100 − P) + 0.4 × D)`

- `P`: probabilidad máxima diaria de precipitación.
- `D`: 50 en días laborables y 100 en sábados/domingo.
- 0–39: baja.
- 40–69: media.
- 70–100: alta.

Un dato climático faltante no se convierte en lluvia cero: la fecha queda como `sin_estimacion`.

## Validación

```bash
bun run lint
bun run typecheck
bun run test
bun run build
```

Las pruebas cubren los ejemplos de la fórmula y los límites 39/40 y 69/70, además de las pruebas existentes del servicio Clima.

## AWS EC2

El Compose está preparado como base de la demostración en una única instancia EC2. Para producción deben sustituirse las credenciales de ejemplo, usar un certificado TLS válido, proteger secretos fuera del repositorio y configurar respaldos externos de PostgreSQL.
