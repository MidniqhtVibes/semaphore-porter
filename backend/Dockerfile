FROM python:3.13.7-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN addgroup --system portal && adduser --system --ingroup portal portal
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY entrypoint.sh ./entrypoint.sh
# Windows checkouts may contain CRLF even before Git attributes are applied.
RUN sed -i 's/\r$//' ./entrypoint.sh && chmod 0555 ./entrypoint.sh && chown -R portal:portal /app
USER portal
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]

FROM runtime AS test
USER root
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests
ENV PYTHONPATH=/app
USER portal
ENTRYPOINT []
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM runtime AS production
