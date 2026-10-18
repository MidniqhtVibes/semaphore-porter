# Semaphore Tenant Portal

Webportal zur mandantenfähigen Verwaltung von Semaphore-UI-Projekten und zur kontrollierten Ausführung freigegebener Task Templates. Administratoren verwalten Verbindungen, Projektvorlagen, Tenants, Benutzer, Gruppen, Policies und Berechtigungen. Portalbenutzer sehen nur ihre zugewiesenen Tenants und Tasks.

Dieses Repository enthält ausschließlich die Web-App in `frontend/`, `backend/` und `docker-compose.yml`. Die frühere Windows-Anwendung einschließlich EXE-/DLL-Artefakten, Desktop-Tests und Windows-Build wurde entfernt; frühere Stände bleiben über die Git-Historie erreichbar.

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
- FastAPI besitzt ein eigenes ausgehendes Netz für Semaphore und optional Vault. Das Frontend erhält eine separate Bridge für die Host-Portfreigabe; diese ermöglicht auch ausgehenden Netzwerkzugriff, aber keinen direkten Datenbankzugriff.
- Nginx ist standardmäßig auf `127.0.0.1:8080` erreichbar, etwa für einen bereits vorhandenen Host-Reverse-Proxy. Adresse und Port lassen sich über `PORTAL_BIND_ADDRESS` und `PORTAL_PUBLIC_PORT` ändern; der lokale Test unten verwendet Port 18092.
- Tenant-, Template- und Run-Zugriffe werden im Backend anhand interner UUIDs und der aktuellen Mitgliedschaften geprüft.
- Task-Parameter werden nie direkt durchgereicht: Die serverseitige Policy validiert Eingaben und ergänzt Fixed/Hidden-Werte.

Weitere Details: [Architektur und Sicherheitsmodell](docs/ARCHITECTURE.md) und [Migration vom Windows-Konfigurator](docs/MIGRATION.md).

Die direkte Verwaltung, Bearbeitung und Duplizierung von Semaphore-Projekten sowie die gemeinsame Pflege von `tenant_slug` und `runtime_scope_id` in `Semaphore-Defaults` beschreibt [Projektverwaltung](docs/PROJECT_MANAGEMENT.md).

## Enthaltene Funktionen

- Rollen `system_admin`, `tenant_admin`, `operator` und `viewer`
- Benutzer, Gruppen, Tenant-Mitgliedschaften und Task-Berechtigungen
- Anmeldung mit Benutzername oder E-Mail-Adresse; eindeutige Benutzernamen in der Benutzerverwaltung
- verschlüsselte Speicherung des Semaphore-Service-Tokens
- Semaphore-Verbindungstest, Projektauswahl, Backup-Export und Restore-basierter Tenant-Wizard
- direkte Projektverwaltung: erstellen, bearbeiten, bestätigt löschen und als neuen Tenant duplizieren
- gemeinsame Pflege von `tenant_slug` und `runtime_scope_id` in `Semaphore-Defaults`
- Mehrfachauswahl von Anwendungen, Datenbankprovidern und Testdatensätzen im Tenant-Wizard
- idempotente Creation Jobs mit explizitem Zustand bei unklarem Restore-Ergebnis
- optionale Vault-KV-v2-Anlage mit Existenzprüfung, zentralen AppRole-/Registry-Zugängen, Secret-Eingabe oder Generierung und Wiederaufnahme
- Synchronisierung der Task Templates und Survey-Felder
- Policies für `fixed`, `hidden`, `enum`, `integer_range`, `string` und `boolean`
- secret-freie, versionierte Presets
- Task-Start, Status, Live-Ausgabe per Server-Sent Events, Abbruch und Historie
- Audit-Log, Login-Limitierung, Argon2-Passwörter, serverseitige Sessions und CSRF-Schutz
- Alembic-Migrationen und persistentes PostgreSQL-Volume
- neutrale helle/dunkle Basis, GitHub Black, SIT Hell/Dunkel und eigene Unternehmensdesigns mit Live-Vorschau; festes Portal-Tor als Website-Symbol

Der aktuelle Release-Zwischenstand ist in [CHANGELOG.md](CHANGELOG.md) dokumentiert. Die noch ausstehende Abnahme gegen die konkrete Semaphore-Instanz steht im [Implementierungsstatus](docs/IMPLEMENTATION_STATUS.md).

Die konkret durchzuführenden Prüfungen stehen im [Abnahmetestplan](docs/ABNAHMETESTS.md). Zielbild, Einrichtung und Betrieb der Vault-Integration stehen vollständig in [Vault-Implementierung](docs/VAULT_IMPLEMENTIERUNG.md). Die frühere [Vault-Bewertung](docs/VAULT_BEWERTUNG.md) bleibt als historische Recherche erhalten.

## Versionen

Die Runtime-Images und direkten Abhängigkeiten sind fest versioniert:

- PostgreSQL 17.6 Alpine
- Python 3.13.7, FastAPI 0.116.1, SQLAlchemy 2.0.43, Alembic 1.16.5
- Node 22.19.0 und npm 11.6.2 für den Build, React 19.1.1, TypeScript 5.9.2, Vite 7.3.7
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

## Lokal unter Windows testen

Benötigt werden eine laufende Docker Engine für Linux-Container und Docker Compose. Python und Node.js müssen auf dem Windows-Host nicht installiert sein, da die Builds in Docker stattfinden.

In PowerShell im Repository-Stamm eine `.env` anlegen, falls noch keine existiert:

```powershell
if (!(Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

Die `CHANGE_ME`-Platzhalter stehen in `.env.example` und nach dem Kopieren in `.env`. Vor dem ersten Start folgende Werte in `.env` ersetzen:

| Variable | Einzutragender Wert |
|---|---|
| `POSTGRES_PASSWORD` | Eigenes zufälliges Datenbankpasswort aus URL-sicheren Zeichen, z. B. Hex-Zeichen |
| `PORTAL_SECRET_KEY` | Eigener zufälliger Schlüssel mit mindestens 32 Zeichen |
| `PORTAL_FERNET_KEY` | URL-safe Base64 aus genau 32 Zufallsbytes; kein frei gewähltes Passwort |
| `PORTAL_BOOTSTRAP_ADMIN_EMAIL` | E-Mail-Adresse des ersten Administrators |
| `PORTAL_BOOTSTRAP_ADMIN_PASSWORD` | Initiales Administratorpasswort; mindestens 12 Zeichen verwenden |

Die Docker-Befehle zur Erzeugung zufälliger Werte stehen unter [Produktive Installation](#produktive-installation), Schritt 2. Bestehende Schlüssel und Datenbankpasswörter bei einem späteren Start beibehalten.

Zusätzlich für selbst gebaute lokale Images diese Einstellungen setzen:

```dotenv
PORTAL_IMAGE_REGISTRY=semaphore-portal-local
PORTAL_IMAGE_TAG=dev
PORTAL_PULL_POLICY=missing
PORTAL_COOKIE_SECURE=false
PORTAL_BIND_ADDRESS=127.0.0.1
PORTAL_PUBLIC_PORT=18092
```

In PowerShell im Repository starten:

```powershell
docker build -t semaphore-portal-local-backend:dev ./backend
docker build -t semaphore-portal-local-frontend:dev ./frontend
docker compose -p semaphore-porter-local up -d --wait
docker compose -p semaphore-porter-local ps
```

Danach `http://127.0.0.1:18092` öffnen und mit den Bootstrap-Admin-Zugangsdaten aus `.env` anmelden. Bei einem neu angelegten Konto fordert der erste Login einen Passwortwechsel. Nach einem bereits erfolgten Passwortwechsel gilt das neue Kontopasswort; der Bootstrap überschreibt es nicht.

Die Anmeldung akzeptiert Benutzername oder E-Mail-Adresse. Für den ersten Administrator wird der Benutzername automatisch aus dem Teil vor `@` gebildet; bei Namenskonflikten oder unzulässigen Zeichen wird er angepasst. Den tatsächlich vergebenen Namen unter **Benutzer & Gruppen → Benutzername** ansehen und bei Bedarf ändern. Bestehende Konten erhalten ihren Namen beim Update automatisch. Details stehen in [Berechtigungen und Benutzerverwaltung](docs/PERMISSIONS.md#anmeldung-mit-benutzername-oder-e-mail-adresse).

Ohne das Profil `tls` wird `PORTAL_DOMAIN` nicht verwendet und kann leer bleiben. Eine eigene Domain oder ein DNS-Eintrag ist für den lokalen Test nicht erforderlich. `localhost` und `127.0.0.1` sind als erlaubte Hosts bereits enthalten; eigene Hostnamen in `PORTAL_ALLOWED_HOSTS` ergänzen. Port 18092 kann durch einen anderen freien Port ersetzt werden; die Browser-Adresse entsprechend anpassen.

Falls Rancher Desktop bei Loopback-Bindung trotz gesunder Container einen Timeout liefert, `PORTAL_BIND_ADDRESS=0.0.0.0` setzen und denselben `up`-Befehl erneut ausführen. Dieser Workaround wurde lokal geprüft; der Frontend-Port ist damit auch auf den übrigen Netzwerkschnittstellen des Rechners veröffentlicht. Die Compose-Vorgabe bleibt `127.0.0.1`.

Status der API: `http://127.0.0.1:18092/api/health`.

Den lokalen Stack stoppen und später mit derselben `.env` wieder starten:

```powershell
docker compose -p semaphore-porter-local stop
docker compose -p semaphore-porter-local up -d --wait
```

Die beiden Befehle werden je nach gewünschter Aktion einzeln ausgeführt. Zum erneuten Start nach dem Stoppen in Rancher genügt der zweite Befehl, sobald die Docker Engine wieder läuft. Der Projektname `semaphore-porter-local` und das Datenbank-Volume bleiben dabei erhalten; ein Neubau der Images ist für einen Neustart nicht erforderlich.

Nach Codeänderungen die betroffenen Images mit den oben gezeigten `docker build`-Befehlen neu bauen und anschließend `docker compose -p semaphore-porter-local up -d --wait --force-recreate` ausführen. Auch bei lokalen Status-, Log- und Backup-Befehlen immer `-p semaphore-porter-local` verwenden, damit sie denselben Stack ansprechen.

## Produktive Installation

1. `docker-compose.yml` und `.env.example` in ein geschütztes Verzeichnis auf dem Server kopieren, `.env.example` in `.env` umbenennen und die Datei nur für den Betreiber lesbar machen:

   ```bash
   install -d -m 750 /opt/semaphore-portal
   cd /opt/semaphore-portal
   cp /pfad/zu/docker-compose.yml .
   cp /pfad/zu/.env.example .env
   chmod 600 .env
   ```

2. Alle `CHANGE_ME`-Werte sowie die Bootstrap-Admin-E-Mail und `PORTAL_ALLOWED_HOSTS` in `.env` anpassen. Für das mitgelieferte TLS-Gateway außerdem `PORTAL_DOMAIN` auf den eigenen DNS-Namen setzen. Bei einem vorhandenen Reverse-Proxy ohne Profil `tls` wird diese Variable nicht verwendet. Sichere Werte lassen sich mit einem temporären Python-Container erzeugen:

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

Portal-Konten sind von Semaphore-Konten getrennt. Benutzer benötigen für die freigegebenen Portal-Tasks keinen eigenen Semaphore-Login. Die globale Rolle `tenant_admin` hat derzeit keine eigene Verwaltungsoberfläche; die Administration erfordert `system_admin`. Tenant-Zuordnungen, Task-Rechte und Policies sind in [Berechtigungen und Benutzerverwaltung](docs/PERMISSIONS.md) erklärt.

1. Unter **Administration → Semaphore** Basis-URL, Service-Token und optional eine HTTP(S)-Proxy-URL speichern. URLs mit eingebetteten Zugangsdaten werden abgelehnt.
2. Unter **Projektvorlagen** ein vorhandenes Semaphore-Projekt als Vorlage sichern. Das Portal speichert eine unveränderte Backup-Fassung und einen strukturellen Katalog.
3. Optional Benutzer und Gruppen anlegen.
4. **Tenant erstellen** starten, Vorlage und Tenant-Daten wählen, Task Templates auswählen, Zugriffe zuordnen und die Zusammenfassung bestätigen.
5. Nach dem Restore Tasks synchronisieren, Policies prüfen und Task-Berechtigungen vergeben.
6. Den Tenant erst aktivieren, wenn Projektzuordnung, Policy und Zugriffe vollständig sind.

Der Wizard führt keine Remote-Löschung durch. Auch beim Entfernen eines Portal-Tenants bleibt das Semaphore-Projekt erhalten.

Unter **Semaphore-Projekte** können Administratoren das tatsächliche Remote-Projekt dagegen ausdrücklich bestätigt löschen sowie Ressourcen bearbeiten und neue Tenant-Kopien erstellen.

Die Mehrfachauswahl in Schritt 3 des Wizards legt die erlaubten Anwendungen, Datenbankprovider und Testdatensätze für die Projektkopie und ihre Initial-Policies fest. Die Anlage des Tenants startet keinen Deployment-Task und importiert keine Testdaten. Bei einer späteren Task-Ausführung wird jeweils ein Wert pro Variable ausgewählt; die Kompatibilität der Kombination prüft der Deployment-Stack. Ablauf und Grenzen stehen in [Projektverwaltung](docs/PROJECT_MANAGEMENT.md).

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

## Vault einrichten

Nach dem Update unter **Administration → Vault** Server-URL, KV-v2-Mount, Tenantwurzel und beide AppRole-Zugänge hinterlegen: einen Schreibzugang für den Porter und den vorhandenen Semaphore-Lesezugang. Der Leser bleibt dieselbe bestehende AppRole. Ist seine bisherige Secret-ID nicht mehr bekannt, stellt ein Vault-Administrator einmalig eine zusätzliche Secret-ID dieser Rolle aus; die laufende Semaphore-Konfiguration bleibt gültig.

Registry-Passwörter pro Anwendung zentral eintragen und **Vault-Anlage im Tenant-Assistenten anbieten** aktivieren. Geheimnisse werden mit dem bestehenden Fernet-Key verschlüsselt und nicht zurückgegeben. Zum Beibehalten gespeicherter Zugangswerte die Eingabefelder leer lassen.

Im Tenant-Assistenten ist die Vault-Anlage bei neu gewählter Vorlage dann vorbelegt und in Schritt 5 abwählbar. Schritt 7 zeigt die exakten neuen Objekte und die Eingabe-/Generierungswahl. AzubiOrga-Crypto-Werte standardmäßig manuell eintragen, wenn sie vom Image vorgegeben sind. Die Anlage prüft alle Zielobjekte vor dem ersten Schreiben und überschreibt nichts. Noch kein Deployment wird gestartet.

Ohne konfigurierte Vault-Integration funktioniert der bisherige Ablauf weiter. Unternehmens-CA, benötigte Vault-Rechte, Umgang mit Teilfehlern und Katalogexport sind in [docs/VAULT_IMPLEMENTIERUNG.md](docs/VAULT_IMPLEMENTIERUNG.md) beschrieben.

## Entwicklung und Tests

Für die folgenden Befehle werden Python 3.13 beziehungsweise Node.js 22.19.0 und npm 11.6.2 auf dem Entwicklungsrechner benötigt. Beide Abschnitte jeweils im Repository-Stamm beginnen, beispielsweise in getrennten PowerShell-Fenstern.

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
npm install --global npm@11.6.2
npm ci
npm test
npm run build
```

API-Dokumentation im laufenden System: `https://<PORTAL_DOMAIN>/api/docs` beziehungsweise beim lokalen Test oben `http://127.0.0.1:18092/api/docs`. Das maschinenlesbare Schema steht unter `/api/openapi.json`. Bei einem anderen `PORTAL_PUBLIC_PORT` die lokale Adresse entsprechend anpassen.

## Fehlerdiagnose

Unter **Designs** lassen sich Neutral Hell, Neutral Dunkel, GitHub Black, SIT Hell, SIT Dunkel und eigene Varianten auswählen. Das Designstudio zeigt die vollständige Navigation und bietet Farbauswahl, Logo- und Textgestaltung. Format und Bedienung stehen in [Designs und Unternehmensfarben](docs/DESIGNS.md).

Die Einrichtung von Portal-Konten, Tenant-Zugriffen und Task-Rechten ist in [Berechtigungen und Benutzerverwaltung](docs/PERMISSIONS.md) beschrieben.

- **Backend bleibt unhealthy:** `docker compose logs backend` prüfen; häufig fehlen Variablen oder der Fernet-Key ist ungültig.
- **GHCR-Pull wird abgelehnt:** Package-Sichtbarkeit prüfen oder `docker login ghcr.io` mit einem Token mit Package-Leserecht wiederholen.
- **Caddy erhält kein Zertifikat:** DNS-Auflösung, Firewall/NAT für TCP 80 und 443 sowie `docker compose --profile tls logs gateway` prüfen.
- **Login setzt kein Cookie:** Bei lokalem HTTP muss `PORTAL_COOKIE_SECURE=false` gelten; in Produktion ist `true` erforderlich.
- **Host wird abgelehnt:** Hostnamen zu `PORTAL_ALLOWED_HOSTS` hinzufügen und Backend neu erstellen.
- **Semaphore nicht erreichbar:** URL, DNS, Zertifikatskette, Proxy und Container-Egress prüfen. Der Client deaktiviert die TLS-Prüfung nicht.
- **Restore-Ergebnis unklar:** Creation Job im Adminbereich prüfen. Das Portal sucht vor einem erneuten POST exakt nach dem Projektnamen, um Duplikate zu vermeiden.
- **Task nicht sichtbar/startbar:** aktiver Tenant, synchronisiertes Template, aktive Policy, Tenant-Mitgliedschaft und Task-Berechtigung kontrollieren.

Der Funktionsstand und die noch erforderliche Abnahme gegen die echte Firmeninstanz stehen in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).
