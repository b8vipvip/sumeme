FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY static /usr/share/nginx/html/static

HEALTHCHECK --interval=10s --timeout=5s --retries=20 --start-period=10s \
  CMD wget -qO- http://127.0.0.1/healthz >/dev/null 2>&1 || exit 1
