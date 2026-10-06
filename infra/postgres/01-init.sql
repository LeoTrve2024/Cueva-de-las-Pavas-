-- Inicialización de la base de datos para los dos microservicios.
-- Las coordenadas del balneario se configuran fuera de PostgreSQL.
CREATE USER pavas_clima WITH PASSWORD 'pavas_clima_local';
CREATE USER pavas_afluencia WITH PASSWORD 'pavas_afluencia_local';

GRANT CONNECT ON DATABASE pavas TO pavas_clima, pavas_afluencia;

CREATE SCHEMA IF NOT EXISTS clima AUTHORIZATION pavas_clima;
CREATE SCHEMA IF NOT EXISTS afluencia AUTHORIZATION pavas_afluencia;

GRANT USAGE, CREATE ON SCHEMA clima TO pavas_clima;
GRANT USAGE, CREATE ON SCHEMA afluencia TO pavas_afluencia;
