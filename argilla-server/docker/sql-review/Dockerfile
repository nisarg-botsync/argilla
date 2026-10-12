# Argilla server 2.8.0 with the QuestDB endpoint and the SQL review setup command.
#
# The official image installs a wheel that needs a full frontend build. This image
# starts from that release instead and replaces its Python package with this branch,
# so the prebuilt frontend in argilla_server/static stays as it is.
#
# Build from the argilla-server folder:
#   docker buildx build --platform linux/amd64 -f docker/sql-review/Dockerfile -t botsync/argilla-custom:1.0.0 .
FROM argilla/argilla-server:v2.8.0

ARG SITE_PACKAGES=/opt/venv/lib/python3.13/site-packages

LABEL org.opencontainers.image.title="argilla-custom" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.description="Argilla server 2.8.0 with a QuestDB query endpoint for the SQL review panel"

USER root
COPY --chown=argilla:argilla src/argilla_server/ /tmp/argilla_server/
RUN test -d "$SITE_PACKAGES/argilla_server/static" && \
    cp -a /tmp/argilla_server/. "$SITE_PACKAGES/argilla_server/" && \
    rm -rf /tmp/argilla_server && \
    find "$SITE_PACKAGES/argilla_server" -name __pycache__ -type d -prune -exec rm -rf {} + && \
    python -c "import argilla_server.api.handlers.v1.questdb, argilla_server.cli.sql_review"
USER argilla
