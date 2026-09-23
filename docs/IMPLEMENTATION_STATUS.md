# Implementierungs- und Abnahmestatus

## Implementiert

- Docker-Architektur mit React/Nginx, FastAPI und PostgreSQL
- Datenmodell und initiale Alembic-Migration
- Authentifizierung, Rollen, Gruppen, Tenant- und Task-Berechtigungen
- Semaphore-Verbindung, Backup-Katalog und Restore-basierter Wizard
- idempotente Creation Jobs und Wiederanlauf nach unklarem Restore
- Survey-Synchronisierung und serverseitige Policy Engine
- Benutzerportal, Task-Start, Status, Live-Logs, Stop und Historie
- Administration für Tenants, Benutzer, Gruppen, Vorlagen, Presets, Runs und Audit
- automatisierte Backend-/Frontend-Tests und produktionsnaher Compose-Smoke-Test vor der Image-Veröffentlichung
- reproduzierbarer Frontend-Build und testabhängiger Docker-Image-Build
- Veröffentlichung von Backend und Frontend als GHCR-Packages mit Release- und Commit-Tags
- produktive Pull-only-Compose-Datei ohne lokale App-Builds, mit getrennten internen Netzen und optional integriertem Caddy-TLS-Gateway

## Noch vor Produktivfreigabe abzunehmen

Ein Live-End-to-End-Test gegen die konkrete Firmeninstanz von Semaphore ist ohne deren URL und Service-Token nicht Bestandteil des lokalen Tests. Vor Produktivfreigabe sind deshalb mindestens folgende Punkte in einer Testumgebung zu bestätigen:

- Unternehmens-CA, DNS und optionaler Proxy aus dem Backend-Container
- Rechteumfang des Service-Tokens
- reale Backup-Struktur der verwendeten Projektvorlage
- Restore, exakte Projekt-ID-Zuordnung und Template-Synchronisierung
- Task-Start mit den realen Survey-Typen sowie Live-Ausgabe und Stop
- öffentlicher DNS-/ACME-Durchlauf beziehungsweise Einbindung in den vorhandenen Host-Reverse-Proxy, Secure-Cookie und erlaubte Hostnamen
- Datenbank-Backup und Wiederherstellung zusammen mit demselben Fernet-Key
- erfolgreicher erneuter Lauf beider GitHub-Workflows nach dem Push dieser Änderungen und Pull der veröffentlichten Images auf dem Zielserver

Das Portal schreibt weder in GitLab noch in Vault und kopiert keine privaten Schlüssel. Solche Integrationen benötigen einen eigenen, explizit autorisierten Ausbau.
