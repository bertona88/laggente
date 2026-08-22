ARG NODE_IMAGE=node:22-alpine
ARG NGINX_IMAGE=nginx:1.28-alpine

FROM ${NODE_IMAGE} AS web-dependencies
WORKDIR /build
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM web-dependencies AS web-build
COPY apps/web/ ./
RUN npm run build

FROM ${NGINX_IMAGE}

COPY infra/gateway/nginx.conf /etc/nginx/nginx.conf
COPY --from=web-build /build/dist/ /usr/share/nginx/html/
RUN test -s /usr/share/nginx/html/index.html && nginx -t

USER 101:101

EXPOSE 8080

ENTRYPOINT []
CMD ["nginx", "-g", "daemon off;"]
