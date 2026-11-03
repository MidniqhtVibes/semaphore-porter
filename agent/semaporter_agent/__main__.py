import os
import ssl
import uvicorn
from .app import create_app, Policy

def main():
    os.umask(0o077)
    policy = Policy.from_file(os.environ.get("AGENT_POLICY_FILE", "/etc/semaporter-agent/policy.json"))
    cert, key = os.environ.get("AGENT_TLS_CERT_FILE"), os.environ.get("AGENT_TLS_KEY_FILE")
    if not cert or not key:
        raise SystemExit("AGENT_TLS_CERT_FILE und AGENT_TLS_KEY_FILE müssen für HTTPS gesetzt sein.")
    app = create_app(policy, socket_path=os.environ.get("AGENT_DOCKER_SOCKET", "/var/run/docker.sock"),
        journal_path=os.environ.get("AGENT_JOURNAL_PATH", "/var/lib/semaporter-agent/operations.sqlite3"))
    client_ca=os.environ.get("AGENT_CLIENT_CA_FILE")
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1, ssl_certfile=cert, ssl_keyfile=key,
        ssl_ca_certs=client_ca,ssl_cert_reqs=ssl.CERT_REQUIRED if client_ca else ssl.CERT_NONE,
        limit_concurrency=32,timeout_graceful_shutdown=30,access_log=False)


if __name__=="__main__": main()
