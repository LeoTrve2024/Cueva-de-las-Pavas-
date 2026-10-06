# Desarrollo

Ejecutar los comandos desde la raíz del monorepo. Antes de entregar un cambio, ejecutar
`bun run check` y añadir pruebas cuando el comportamiento nuevo lo requiera.

## Organización

- `apps/web/src`: interfaz React. TypeScript estricto; evitar `any` y conversiones de tipo que
  oculten errores.
- `services/*/src`: código de cada microservicio. Tipar las interfaces y validar entradas con
  Pydantic. Mantener la creación de la aplicación en `create_app`.
- `services/*/tests`: pruebas del servicio. Las pruebas iniciales no requieren internet ni base
  de datos; las futuras integraciones deben distinguirse de las pruebas unitarias.
- Mantener los paquetes desplegables por separado. No importar código de otro microservicio.

## Herramientas

Biome se encarga de TypeScript, JavaScript, JSON y CSS; Ruff, del formato y lint de Python.
mypy y TypeScript comprueban tipos. No añadir herramientas que dupliquen estas responsabilidades
sin una necesidad concreta.

Los scripts `setup` y los comandos CI usan lockfiles. Para actualizar dependencias, utilizar
`bun add` o `uv add`, revisar sus cambios y volver a ejecutar las validaciones. No editar lockfiles
a mano.

## Configuración

Añadir variables nuevas a `.env.example` con valores de desarrollo o documentación. Nunca poner
secretos en el repositorio ni exponerlos con variables `VITE_`, que se incorporan al código público
de la web. Mantener los prefijos por servicio y la validación de sus valores.

Al introducir persistencia, definir migraciones de Alembic por servicio y pruebas de integración.
La infraestructura de producción y las credenciales de AWS se añadirán en una etapa separada.
