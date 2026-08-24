# Multi-stage: build Vite dashboard, serve with nginx on $PORT (Cloud Run).
#
# Example:
#   docker build -f dashboard/Dockerfile dashboard \
#     --build-arg VITE_API_BASE=https://YOUR-API-xxx.run.app \
#     --build-arg VITE_ADMIN_API_KEY=your-admin-key

FROM node:20-bookworm-slim AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE
ARG VITE_ADMIN_API_KEY
ENV VITE_API_BASE=${VITE_API_BASE}
ENV VITE_ADMIN_API_KEY=${VITE_ADMIN_API_KEY}

RUN npm run build

FROM nginx:1.27-alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx/templates/default.conf.template /etc/nginx/templates/default.conf.template

ENV PORT=8080
EXPOSE 8080
