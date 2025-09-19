# syntax=docker/dockerfile:1.7-labs

# --- base (node) ---
FROM node:20-alpine AS nodebase
WORKDIR /app
COPY frontend/package.json ./package.json
COPY frontend/package-lock.json ./package-lock.json
COPY frontend/tsconfig.json ./tsconfig.json
COPY frontend/vite.config.ts ./vite.config.ts
COPY frontend/index.html ./index.html
COPY frontend/src ./src
RUN corepack enable && npm ci --no-audit --no-fund


# --- dev stage ---
FROM nodebase AS dev
ENV VITE_PORT=5173
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]


# --- build stage ---
FROM nodebase AS build
RUN npm run build


# --- prod stage (nginx) ---
FROM nginx:1.27-alpine AS prod
WORKDIR /usr/share/nginx/html
COPY --from=build /app/dist/ .
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
