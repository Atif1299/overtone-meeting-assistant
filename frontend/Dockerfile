# Multi-stage: build Vite app, serve static files with nginx on $PORT (Cloud Run).
# Build args bake API URLs at build time (required for Vite).
#
# Example:
#   docker build -f frontend/Dockerfile frontend \
#     --build-arg VITE_API_BASE=https://YOUR-API-xxx.run.app \
#     --build-arg VITE_WS_BASE=wss://YOUR-API-xxx.run.app

FROM node:20-bookworm-slim AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE
ARG VITE_WS_BASE
ENV VITE_API_BASE=${VITE_API_BASE}
ENV VITE_WS_BASE=${VITE_WS_BASE}

RUN npm run build

FROM nginx:1.27-alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx/templates/default.conf.template /etc/nginx/templates/default.conf.template

ENV PORT=8080
EXPOSE 8080
