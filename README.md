# Semaphore Tenant Portal

Webportal zur mandantenfähigen Verwaltung von Semaphore-UI-Projekten und zur kontrollierten Ausführung freigegebener Task Templates. Administratoren verwalten Verbindungen, Projektvorlagen, Tenants, Benutzer, Gruppen, Policies und Berechtigungen. Portalbenutzer sehen nur ihre zugewiesenen Tenants und Tasks.

Die bisherige Windows/WPF-Anwendung bleibt in `src/` erhalten. Der produktive Zielstack liegt in `frontend/`, `backend/` und `docker-compose.yml`.

## Architektur

```text
Browser :8080
    |
    v
Nginx + React SPA  ---- internes Netz ---->  FastAPI
                                              |   |
                                  internes Netz   +---- Egress ----> Semaphore UI API
                                              |
                                          PostgreSQL
```

- Nur Nginx veröffentlicht einen Host-Port.
- PostgreSQL ist ausschließlich im internen Docker-Netz erreichbar.
- FastAPI besitzt ein zusätzliches ausgehendes Netz für den Semaphore-Server, aber keinen Host-Port.
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

Die Images und direkten Abhängigkeiten sind fest versioniert:

- PostgreSQL 17.6 Alpine
- Python 3.13.7, FastAPI 0.116.1, SQLAlchemy 2.0.43, Alembic 1.16.5
- Node 22.19.0 für den Build, React 19.1.1, TypeScript 5.9.2, Vite 7.1.5
- Nginx 1.29.1 Alpine zur Auslieferung und als API-Reverse-Proxy

`frontend/package-lock.json` fixiert den vollständigen Frontend-Dependency-Graph.

## Voraussetzungen

- Docker Engine mit Compose v2
- erreichbare Semaphore-UI-Instanz und ein Service-Token mit den benötigten Projekt-/Task-Rechten
- für Produktion: HTTPS-Reverse-Proxy und ein DNS-Name
- ausreichend Rechte für ein persistentes Docker-Volume

## Installation

1. Konfiguration anlegen:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Alle `CHANGE_ME`-Werte in `.env` ersetzen. Sichere Werte lassen sich ohne lokale Python-Installation erzeugen:

   ```powershell
   docker run --rm python:3.13.7-slim python -c "import secrets; print(secrets.token_urlsafe(64))"
   docker run --rm python:3.13.7-slim python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
   ```

   Die erste Ausgabe ist für `PORTAL_SECRET_KEY`, die zweite für `PORTAL_FERNET_KEY`. Für `POSTGRES_PASSWORD` einen langen URL-sicheren Zufallswert verwenden. Der Fernet-Key muss bei Updates und Restores unverändert bleiben, sonst kann das gespeicherte Semaphore-Token nicht mehr entschlüsselt werden.

3. Images bauen und Stack starten:

   ```powershell
   docker compose build
   docker compose up -d
   docker compose ps
   ```

4. `http://localhost:8080` öffnen und mit `PORTAL_BOOTSTRAP_ADMIN_EMAIL` sowie `PORTAL_BOOTSTRAP_ADMIN_PASSWORD` anmelden. Beim ersten Login ist ein Passwortwechsel erzwungen.

Beim Backend-Start laufen zuerst `alembic upgrade head` und der idempotente Bootstrap für Rollen, integrierte Presets und den ersten Administrator.

## Produktionskonfiguration

- `PORTAL_COOKIE_SECURE=true` setzen und das Portal nur über HTTPS betreiben.
- `PORTAL_ALLOWED_HOSTS` auf die tatsächlichen, kommaseparierten Hostnamen begrenzen. Die internen Healthcheck-Namen `localhost` und `127.0.0.1` werden automatisch ergänzt.
- Bootstrap-Passwort nach erfolgreicher Erstinstallation aus `.env` entfernen. Ein bestehender Admin wird dadurch nicht gelöscht.
- `.env`, Datenbank-Backups und Fernet-Key getrennt und zugriffsgeschützt sichern.
- Den Backend- oder PostgreSQL-Port nicht zusätzlich veröffentlichen.
- Bei einem vorgeschalteten Proxy den ursprünglichen Host beibehalten. TLS wird weder für das Portal noch für Semaphore deaktiviert.

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

```powershell
docker compose ps
docker compose logs --tail=200 backend
docker compose logs --tail=200 frontend
curl.exe --fail http://localhost:8080/api/health
```

Update:

```powershell
docker compose build --pull
docker compose up -d
```

Vor einem Update Datenbank und `.env`/Fernet-Key sichern. Die Schema-Aktualisierung erfolgt beim Backend-Start über Alembic.

Datenbank sichern und wiederherstellen:

```powershell
docker compose exec -T postgres pg_dump -U semaphore_portal -d semaphore_portal -Fc > portal.dump
Get-Content portal.dump -AsByteStream | docker compose exec -T postgres pg_restore -U semaphore_portal -d semaphore_portal --clean --if-exists
```

Die Werte für Benutzer und Datenbank bei abweichender `.env` entsprechend ersetzen. Ein Restore mit `--clean` überschreibt die Zieldatenbank und gehört in ein Wartungsfenster.

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

API-Schema im laufenden System: `http://localhost:8080/api/docs`.

## Fehlerdiagnose

- **Backend bleibt unhealthy:** `docker compose logs backend` prüfen; häufig fehlen Variablen oder der Fernet-Key ist ungültig.
- **Login setzt kein Cookie:** Bei lokalem HTTP muss `PORTAL_COOKIE_SECURE=false` gelten; in Produktion ist `true` erforderlich.
- **Host wird abgelehnt:** Hostnamen zu `PORTAL_ALLOWED_HOSTS` hinzufügen und Backend neu erstellen.
- **Semaphore nicht erreichbar:** URL, DNS, Zertifikatskette, Proxy und Container-Egress prüfen. Der Client deaktiviert die TLS-Prüfung nicht.
- **Restore-Ergebnis unklar:** Creation Job im Adminbereich prüfen. Das Portal sucht vor einem erneuten POST exakt nach dem Projektnamen, um Duplikate zu vermeiden.
- **Task nicht sichtbar/startbar:** aktiver Tenant, synchronisiertes Template, aktive Policy, Tenant-Mitgliedschaft und Task-Berechtigung kontrollieren.

Der Funktionsstand und die noch erforderliche Abnahme gegen die echte Firmeninstanz stehen in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).
