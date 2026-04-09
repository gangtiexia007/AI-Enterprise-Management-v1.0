# Stage 1: build React + Vite app
FROM node:20-alpine AS build

WORKDIR /app

COPY frontend/package.json ./
RUN npm config set registry https://mirrors.cloud.tencent.com/npm/ && npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: serve static assets with nginx
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
