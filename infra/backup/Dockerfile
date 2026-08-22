ARG POSTGRES_IMAGE=postgres:16-alpine
FROM ${POSTGRES_IMAGE}

RUN apk add --no-cache coreutils util-linux tar \
    && addgroup -S -g 10001 backup \
    && adduser -S -D -H -u 10001 -G backup backup

COPY --chown=10001:10001 infra/backup/backup.sh /opt/backup/backup.sh
COPY --chown=10001:10001 infra/backup/archive-uploads.sh /opt/backup/archive-uploads.sh
COPY --chown=10001:10001 infra/backup/healthcheck.sh /opt/backup/healthcheck.sh
COPY --chown=10001:10001 infra/backup/restore-verify.sh /opt/backup/restore-verify.sh

RUN chmod 0555 /opt/backup/backup.sh /opt/backup/archive-uploads.sh /opt/backup/healthcheck.sh /opt/backup/restore-verify.sh \
    && sh -n /opt/backup/backup.sh \
    && sh -n /opt/backup/archive-uploads.sh \
    && sh -n /opt/backup/healthcheck.sh \
    && sh -n /opt/backup/restore-verify.sh

USER 10001:10001

ENTRYPOINT []
CMD ["/opt/backup/backup.sh", "daemon"]
