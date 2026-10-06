FROM node:24-alpine AS build
WORKDIR /app
COPY package.json bun.lock /app/
COPY apps/web/package.json apps/web/package.json
RUN npm install --global bun@1.4.0 && bun --version && bun install --frozen-lockfile
COPY apps/web /app/apps/web
RUN bun run --cwd apps/web build

FROM nginx:alpine
COPY --from=build /app/apps/web/dist /usr/share/nginx/html
