FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
COPY docs ./docs
COPY schemas ./schemas
COPY openapi ./openapi
COPY governance ./governance
COPY trust ./trust
COPY corpus ./corpus
COPY cases ./cases
COPY fixtures ./fixtures
COPY benchmarks ./benchmarks

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e . \
    && chmod +x /app/scripts/docker-entrypoint.sh

EXPOSE 8000

ENV OPENCRITIQUE_EXECUTION_MODE=compose

HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz').read()"

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["opencritique-registry", "serve", "--host", "0.0.0.0", "--port", "8000"]
