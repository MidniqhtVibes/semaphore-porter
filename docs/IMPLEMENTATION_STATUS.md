# Implementierungs- und Abnahmestatus

## Ausbau der Projektverwaltung

Die direkte Verwaltung tatsächlicher Semaphore-Projekte ist ergänzt: Erstellen, Umbenennen, bestätigtes Remote-Löschen, Bearbeiten/Hinzufügen von Variablengruppen, Repositories, Inventories, Templates und Zugangsdaten sowie Duplizieren über den reparierten Tenant-Wizard. `tenant_slug` und `runtime_scope_id` werden gemeinsam in `Semaphore-Defaults` gepflegt und nicht als Survey-Variablen erzeugt. Details, Ablauf und Betriebsgrenzen stehen in [PROJECT_MANAGEMENT.md](PROJECT_MANAGEMENT.md).

Zusätzlich korrigiert: Entwurfswiederaufnahme, Vorlagenwechsel, vollständig leere Gruppenauswahl, initiale Policies für den aktuellen Stack, Statusaktualisierung der Tasklisten, API-seitiger Passwortwechselzwang, Sitzungswiderruf nach Passwortreset und Bedienung von Gruppenmitgliedschaften/Zugriffsentzug.

Lokale Prüfung am 15.10.2026: **39 Backend-Tests und 7 Frontend-Tests bestanden**, TypeScript/Vite-Produktionsbuild erfolgreich, `npm audit` mit **0 bekannten Schwachstellen**. Backend-Prüfung mit SQLite und simulierten Semaphore-Antworten unter WSL; diese Ergebnisse ersetzen weder den PostgreSQL-/Compose-Smoke-Test noch die Live-Abnahme. Frontend-Build und CI verwenden npm 11.6.2; Router, Vite und Vitest wurden mit aktualisierter Lockdatei auf korrigierte Versionen angehoben.

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
