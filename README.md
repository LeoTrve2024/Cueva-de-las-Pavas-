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

- `PUT /api/v1/afluencia/visitantes/{fecha}`: registra los visitantes reales de un día (`{"visitantes": 120, "nota": "..."}`).
- `GET /api/v1/afluencia/comparacion?desde=YYYY-MM-DD&hasta=YYYY-MM-DD`: compara visitantes reales con las visitas estimadas.

El historial y el registro de visitantes requieren autenticación Basic. Las credenciales por defecto son `admin` / `admin` (definidas en `.env` y `nginx/.htpasswd`); **deben cambiarse antes de publicar**. La pantalla de administración está en `/#admin`.

## Regla de afluencia

`S = redondear(0.6 × (100 − P) + 0.4 × D)`

- `P`: probabilidad máxima diaria de precipitación.
- `D`: 50 en días laborables y 100 en sábados/domingo.
- 0–39: baja.
- 40–69: media.
- 70–100: alta.

## Visitas estimadas (experimental)

Cada día disponible incluye `visitas_estimadas`: `171 × S / 50,9`, redondeado a decenas. 171 es el promedio diario de las 62 550 visitas de 2023 (MINCETUR, ficha 4838, conteo de 4 semanas) y 50,9 es la puntuación de un día promedio (en 2023 llovió ≥ 1 mm en 212 de 365 días según Open-Meteo). Es una escala de referencia, no una medición ni una predicción validada. El valor se calcula al responder y no se guarda en la base de datos.

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
