FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY static /usr/share/nginx/html/static
COPY admin /usr/share/nginx/html/admin

# /admin/ is a real directory. Keeping "$uri/" in try_files makes Nginx
# internally redirect the directory request back to itself until it returns 500.
# Patch the effective container config until the source stanza is simplified.
RUN sed -i 's#try_files \$uri \$uri/ /admin/index.html;#try_files \$uri /admin/index.html;#' \
      /etc/nginx/conf.d/default.conf \
    && test -f /usr/share/nginx/html/admin/index.html \
    && test -f /usr/share/nginx/html/admin/admin.css \
    && test -f /usr/share/nginx/html/admin/admin.js

HEALTHCHECK --interval=10s --timeout=5s --retries=20 --start-period=10s \
  CMD wget -qO- http://127.0.0.1/healthz >/dev/null 2>&1 \
    && wget -qO- http://127.0.0.1/admin/ | grep -q 'SuMeMe 管理后台' \
    || exit 1
