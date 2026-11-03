FROM python:3.13.7-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN groupadd --gid 10001 agent && useradd --uid 10001 --gid 10001 --no-create-home agent && mkdir -p /var/lib/semaporter-agent && chown agent:agent /var/lib/semaporter-agent
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY semaporter_agent ./semaporter_agent
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD ["python", "-c", "import socket; socket.create_connection(('127.0.0.1',8000),2).close()"]
ENTRYPOINT ["python", "-m", "semaporter_agent"]

FROM runtime AS test
USER root
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests
USER 10001:10001
ENTRYPOINT []
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM runtime AS production
