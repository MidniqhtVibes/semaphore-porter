# Semaphore Tenant Portal

Webportal zur mandantenfähigen Verwaltung von Semaphore-UI-Projekten und zur kontrollierten Ausführung freigegebener Task Templates. Administratoren verwalten Verbindungen, Projektvorlagen, Tenants, Benutzer, Gruppen, Policies und Berechtigungen. Portalbenutzer sehen nur ihre zugewiesenen Tenants und Tasks.

Die bisherige Windows/WPF-Anwendung bleibt in `src/` erhalten. Der produktive Zielstack liegt in `frontend/`, `backend/` und `docker-compose.yml`.

## Architektur

```text
Browser :443
    |
    v
Caddy (TLS)  ---- internes Edge-Netz ---->  Nginx + React SPA
                                                   |
                                             internes App-Netz
                                                   |
                                                FastAPI  ---- Egress ----> Semaphore UI API
                                                   |
                                             internes DB-Netz
                                                   |
                                               PostgreSQL
```

- Caddy terminiert im mitgelieferten TLS-Profil HTTPS und erneuert Zertifikate automatisch.
- PostgreSQL und FastAPI veröffentlichen keine Host-Ports; PostgreSQL besitzt auch keinen Internetzugang.
- Nur FastAPI besitzt ein ausgehendes Netz für den Semaphore-Server.
- Nginx ist ohne TLS-Profil ausschließlich auf `127.0.0.1:8080` erreichbar, etwa für einen bereits vorhandenen Host-Reverse-Proxy.
- Tenant-, Template- und Run-Zugriffe werden im Backend anhand interner UUIDs und der aktuellen Mitgliedschaften geprüft.
- Task-Parameter werden nie direkt durchgereicht: Die serverseitige Policy validiert Eingaben und ergänzt Fixed/Hidden-Werte.

Weitere Details: [Architektur und Sicherheitsmodell](docs/ARCHITECTURE.md) und [Migration vom Windows-Konfigurator](docs/MIGRATION.md).

## Enthaltene Funktionen

- Rollen `system_admin`, `tenant_admin`, `operator` und `viewer`
- Benutzer, Gruppen, Tenant-Mitgliedschaften und Task-Berechtigungen
- verschlüsselte Speicherung des Semaphore-Service-Tokens
- Semaphore-Verbindungstest, Projektauswahl, Backup-Export und Restore-basierter Tenant-Wizard
- idempotente Creation Jobs mit explizitem Zustand bei unklarem Restore-Ergebnis
- Synchronisierung der Task Templates und Survey-Felder
- Policies für `fixed`, `hidden`, `enum`, `integer_range`, `string` und `boolean`
- secret-freie, versionierte Presets
- Task-Start, Status, Live-Ausgabe per Server-Sent Events, Abbruch und Historie
- Audit-Log, Login-Limitierung, Argon2-Passwörter, serverseitige Sessions und CSRF-Schutz
- Alembic-Migrationen und persistentes PostgreSQL-Volume

## Versionen

Die Runtime-Images und direkten Abhängigkeiten sind fest versioniert:

- PostgreSQL 17.6 Alpine
- Python 3.13.7, FastAPI 0.116.1, SQLAlchemy 2.0.43, Alembic 1.16.5
- Node 22.19.0 für den Build, React 19.1.1, TypeScript 5.9.2, Vite 7.1.5
- Nginx 1.29.1 Alpine zur Auslieferung und als API-Reverse-Proxy
- Caddy 2.10.2 Alpine als optionales TLS-Gateway

`frontend/package-lock.json` fixiert den vollständigen Frontend-Dependency-Graph.

## Voraussetzungen für den Server

- Linux/x86-64 mit Docker Engine und Docker Compose 2.33.1 oder neuer
- `docker-compose.yml` und eine lokale `.env`; ein Checkout des Quellcodes ist nicht erforderlich
- erreichbare Semaphore-UI-Instanz und ein Service-Token mit den benötigten Projekt-/Task-Rechten
- für das eingebaute TLS-Gateway: ein DNS-Name, der auf den Host zeigt, sowie eingehend erreichbare TCP-Ports 80 und 443
- Zugriff auf GHCR; bei privaten Packages einmalig `docker login ghcr.io` mit einem Token mit Leserecht ausführen

Python, Node.js, .NET und `docker compose build` werden auf dem Server nicht benötigt. Compose zieht die beiden von GitHub Actions gebauten Portal-Images sowie die festgelegten offiziellen PostgreSQL- und Caddy-Images.

## Produktive Installation

1. `docker-compose.yml` und `.env.example` in ein geschütztes Verzeichnis auf dem Server kopieren, `.env.example` in `.env` umbenennen und die Datei nur für den Betreiber lesbar machen:

   ```bash
   install -d -m 750 /opt/semaphore-portal
   cd /opt/semaphore-portal
   cp /pfad/zu/docker-compose.yml .
   cp /pfad/zu/.env.example .env
   chmod 600 .env
   ```

2. Alle `CHANGE_ME`-Werte sowie `PORTAL_DOMAIN` und `PORTAL_ALLOWED_HOSTS` in `.env` ersetzen. Sichere Werte lassen sich mit einem temporären Python-Container erzeugen:

   ```bash
   docker run --rm python:3.13.7-slim python -c "import secrets; print(secrets.token_hex(48))"
   docker run --rm python:3.13.7-slim python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
   ```

   Die erste Ausgabe kann für `PORTAL_SECRET_KEY` und ein weiterer URL-sicherer Zufallswert für `POSTGRES_PASSWORD` verwendet werden; die zweite Ausgabe ist der `PORTAL_FERNET_KEY`. Dieser Fernet-Key muss bei Updates und Restores unverändert bleiben, sonst kann das gespeicherte Semaphore-Token nicht mehr entschlüsselt werden.

3. Für reproduzierbare Deployments `PORTAL_IMAGE_TAG` auf einen veröffentlichten `vX.Y.Z`- oder `sha-<vollständiger-Commit>`-Tag setzen. `latest` folgt dem aktuellen Stand von `main` und eignet sich vor allem für die Erstinbetriebnahme.

4. Den vollständigen Stack inklusive HTTPS starten:

   ```bash
   docker compose --profile tls pull
   docker compose --profile tls up -d --wait
   docker compose --profile tls ps
   ```

5. `https://<PORTAL_DOMAIN>` öffnen und mit `PORTAL_BOOTSTRAP_ADMIN_EMAIL` sowie `PORTAL_BOOTSTRAP_ADMIN_PASSWORD` anmelden. Beim ersten Login ist ein Passwortwechsel erzwungen. Danach beide Bootstrap-Werte in `.env` leeren und den Backend-Container neu erstellen; ein bestehender Administrator wird dabei nicht verändert:

   ```bash
   docker compose --profile tls up -d --force-recreate backend
   ```

Beim Backend-Start laufen zuerst `alembic upgrade head` und der idempotente Bootstrap für Rollen und integrierte Presets. `PORTAL_COOKIE_SECURE=true` muss in Produktion gesetzt bleiben.

### Vorhandenen Reverse-Proxy verwenden

Wenn auf demselben Host bereits ein TLS-Reverse-Proxy betrieben wird, den Stack ohne Profil mit `docker compose up -d --wait` starten und den Proxy auf `http://127.0.0.1:8080` leiten. Er muss den ursprünglichen `Host` und `X-Forwarded-Proto: https` weitergeben. Backend- oder PostgreSQL-Ports dürfen nicht zusätzlich veröffentlicht werden.

### GitHub Actions und Packages

Die Portal-CI testet zuerst Backend und Frontend. Danach startet sie mit den lokal gebauten Images genau die produktive Compose-Datei einschließlich PostgreSQL und Caddy und prüft Health- und Login-Route. Erst nach diesem Smoke-Test werden Packages veröffentlicht. Pull Requests und normale Branches bauen beide Images nur zur Prüfung. Erfolgreiche Pushes auf `main` veröffentlichen `latest`, `main` und einen unveränderlichen `sha-*`-Tag nach:

- `ghcr.io/midniqhtvibes/semaphore-porter-backend`
- `ghcr.io/midniqhtvibes/semaphore-porter-frontend`

Ein Git-Tag `vX.Y.Z` erzeugt zusätzlich SemVer-Tags. Der Image-Job beginnt erst, wenn beide Testjobs erfolgreich waren. Die Package-Sichtbarkeit muss in GitHub zum vorgesehenen Betriebsmodell passen: entweder öffentlich oder mit authentifiziertem Lesezugriff vom Server.

## Ersteinrichtung im Portal

1. Unter **Administration → Semaphore** Basis-URL, Service-Token und optional eine HTTP(S)-Proxy-URL speichern. URLs mit eingebetteten Zugangsdaten werden abgelehnt.
2. Unter **Projektvorlagen** ein vorhandenes Semaphore-Projekt als Vorlage sichern. Das Portal speichert eine unveränderte Backup-Fassung und einen strukturellen Katalog.
3. Optional Benutzer und Gruppen anlegen.
4. **Tenant erstellen** starten, Vorlage und Tenant-Daten wählen, Task Templates auswählen, Zugriffe zuordnen und die Zusammenfassung bestätigen.
5. Nach dem Restore Tasks synchronisieren, Policies prüfen und Task-Berechtigungen vergeben.
6. Den Tenant erst aktivieren, wenn Projektzuordnung, Policy und Zugriffe vollständig sind.

Der Wizard führt keine Remote-Löschung durch. Auch beim Entfernen eines Portal-Tenants bleibt das Semaphore-Projekt erhalten.

## Policy-Regeln

| Typ | Verhalten |
|---|---|
| `fixed` | Fester Wert, nicht im Browser editierbar |
| `hidden` | Fester interner Wert, nicht an den Browser ausgeliefert |
| `enum` | Nur ein Wert aus `allowed_values` |
| `integer_range` | Ganzzahl innerhalb `minimum`/`maximum` |
| `string` | Text mit optionaler Länge und Regex |
| `boolean` | Strikter boolescher Wert |

Unbekannte Felder, manipulierte Fixed/Hidden-Werte und Regeln für nicht vorhandene Survey-Variablen werden serverseitig abgelehnt. Passwörter, Tokens oder private Schlüssel gehören in Semaphore Key Store beziehungsweise Vault, nicht in Policies oder Presets.

## Betrieb

Status und Logs:

```bash
docker compose --profile tls ps
docker compose --profile tls logs --tail=200 backend frontend gateway
curl --fail https://portal.example.com/api/health
```

Vor jedem Update die Datenbank sowie `.env`/Fernet-Key außerhalb des Hosts sichern. Danach `PORTAL_IMAGE_TAG` kontrolliert auf den gewünschten Release- oder SHA-Tag ändern und ausschließlich Images ziehen:

```bash
docker compose --profile tls pull
docker compose --profile tls up -d --wait
```

Die Schema-Aktualisierung erfolgt beim Backend-Start über Alembic. Für ein Rollback den vorherigen Image-Tag eintragen und dieselben beiden Befehle ausführen. Falls die neue Version bereits eine nicht rückwärtskompatible Datenbankmigration ausgeführt hat, muss auch das zur alten Version passende Datenbank-Backup wiederhergestellt werden.

Datenbank sichern:

```bash
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > portal.dump
```

Datenbank im Wartungsfenster wiederherstellen:

```bash
docker compose stop backend
docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < portal.dump
docker compose --profile tls up -d --wait
```

Ein Restore mit `--clean` überschreibt die Zieldatenbank. Datenbank-Backup und `.env` mit demselben Fernet-Key müssen gemeinsam, verschlüsselt und regelmäßig außerhalb des Docker-Hosts gesichert sowie testweise wiederhergestellt werden. Docker-Logs sind pro Container begrenzt; für zentrale Aufbewahrung ist ein externer Log-Collector erforderlich.

## Entwicklung und Tests

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest
```

Frontend:

```powershell
cd frontend
npm ci
npm test
npm run build
```

API-Schema im laufenden System: `https://<PORTAL_DOMAIN>/api/docs` beziehungsweise lokal `http://127.0.0.1:8080/api/docs`.

## Fehlerdiagnose

- **Backend bleibt unhealthy:** `docker compose logs backend` prüfen; häufig fehlen Variablen oder der Fernet-Key ist ungültig.
- **GHCR-Pull wird abgelehnt:** Package-Sichtbarkeit prüfen oder `docker login ghcr.io` mit einem Token mit Package-Leserecht wiederholen.
- **Caddy erhält kein Zertifikat:** DNS-Auflösung, Firewall/NAT für TCP 80 und 443 sowie `docker compose --profile tls logs gateway` prüfen.
- **Login setzt kein Cookie:** Bei lokalem HTTP muss `PORTAL_COOKIE_SECURE=false` gelten; in Produktion ist `true` erforderlich.
- **Host wird abgelehnt:** Hostnamen zu `PORTAL_ALLOWED_HOSTS` hinzufügen und Backend neu erstellen.
- **Semaphore nicht erreichbar:** URL, DNS, Zertifikatskette, Proxy und Container-Egress prüfen. Der Client deaktiviert die TLS-Prüfung nicht.
- **Restore-Ergebnis unklar:** Creation Job im Adminbereich prüfen. Das Portal sucht vor einem erneuten POST exakt nach dem Projektnamen, um Duplikate zu vermeiden.
- **Task nicht sichtbar/startbar:** aktiver Tenant, synchronisiertes Template, aktive Policy, Tenant-Mitgliedschaft und Task-Berechtigung kontrollieren.

Der Funktionsstand und die noch erforderliche Abnahme gegen die echte Firmeninstanz stehen in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).
