# Semaphore Porter

Webportal für die zentrale Verwaltung von Semaphore-UI-Projekten, Mandanten und freigegebenen Automatisierungsaufgaben. Administratoren konfigurieren Projektvorlagen, Zugriffsrechte und Task-Parameter. Benutzer führen die für sie freigegebenen Tasks über eine gemeinsame Oberfläche aus und verfolgen Status und Ausgaben direkt im Browser.

[Installation](#installation) · [Lokaler Test](#lokaler-test) · [Erste Schritte](#erste-schritte) · [Designstudio](#designstudio) · [Dokumentation](#dokumentation)

## Funktionen

| Bereich | Möglichkeiten |
|---|---|
| Mandantenverwaltung | Tenants aus Projektvorlagen erstellen, Projekte zuordnen und Zugriffe verwalten |
| Projektverwaltung | Semaphore-Projekte erstellen, bearbeiten, duplizieren und nach Bestätigung löschen |
| Automatisierung | Freigegebene Task Templates starten, Live-Ausgaben anzeigen, Ausführungen abbrechen und die Historie einsehen |
| Parametersteuerung | Survey-Felder synchronisieren, Eingaben validieren und feste oder ausgeblendete Werte vorgeben |
| Benutzer und Berechtigungen | Lokale Konten, Gruppen, Tenant-Mitgliedschaften und einzelne Task-Freigaben verwalten |
| Vault-Integration | Optional neue KV-v2-Secrets für Tenants anlegen und AppRole- sowie Registry-Zugänge zentral konfigurieren |
| Gestaltung | Eigene Farben, Logos, Anmeldetexte und rechtliche Texte mit interaktiver Live-Vorschau gestalten |
| Nachvollziehbarkeit | Verwaltungsaktionen und Task-Ausführungen über Audit-Log und Ausführungshistorie verfolgen |

Portal-Konten und Semaphore-Konten sind getrennt. Benutzer benötigen für die freigegebenen Portal-Tasks keinen eigenen Semaphore-Login. Die Administration erfordert die Rolle `system_admin`; der Zugriff auf Tenants und Tasks richtet sich nach den gespeicherten Mitgliedschaften und Freigaben. Details beschreibt [Berechtigungen und Benutzerverwaltung](docs/PERMISSIONS.md).

## Architektur

```text
Browser
  │ HTTPS
  ▼
Caddy (optional) → Nginx / React → FastAPI → Semaphore UI API
                                    │    → Vault API (optional)
                                    ▼
                                PostgreSQL
```

| Komponente | Aufgabe |
|---|---|
| React, TypeScript und Vite | Administration, Benutzerportal und Designstudio |
| Nginx | Auslieferung des Frontends und Weiterleitung der API-Anfragen |
| FastAPI und SQLAlchemy | Authentifizierung, Berechtigungen, Policies und Integrationen |
| PostgreSQL | Persistente Speicherung der Portal-Daten |
| Caddy | Optionales HTTPS-Gateway mit automatischer Zertifikatsverwaltung |

Backend und Datenbank veröffentlichen keine Host-Ports. PostgreSQL befindet sich in einem internen Netz; das Backend besitzt einen separaten Netzwerkzugang zu Semaphore und optional Vault. Nginx ist standardmäßig unter `127.0.0.1:8080` erreichbar. Das optionale TLS-Profil veröffentlicht die Ports 80 und 443.

Die Anwendung verwendet Argon2-Passwort-Hashes, serverseitige Sitzungen, CSRF-Schutz und Login-Limitierung. Gespeicherte Integrationszugänge werden verschlüsselt. Task-Parameter werden im Backend anhand der jeweiligen Policy geprüft.

Weitere Details: [Architektur und Sicherheitsmodell](docs/ARCHITECTURE.md).

## Installation

### Voraussetzungen

- Docker Engine mit Linux-Containern und Docker Compose ab Version 2.33.1
- Linux/x86-64 für die bereitgestellten Container-Images
- Erreichbare Semaphore-UI-Instanz und Service-Token mit den erforderlichen Projekt- und Task-Rechten
- Zugriff auf die GitHub Container Registry; für private Packages eine Anmeldung mit `docker login ghcr.io`
- Für das integrierte HTTPS-Gateway: ein auf den Server zeigender DNS-Name und erreichbare TCP-Ports 80 und 443

Für den Betrieb mit fertigen Images genügen `docker-compose.yml` und eine lokale `.env`. Python und Node.js werden nur für die Entwicklung außerhalb der Container benötigt.

### 1. Konfiguration anlegen

Lege `docker-compose.yml` und `.env.example` in einem Verzeichnis auf dem Server ab. Erstelle dort die Konfiguration:

```bash
cp .env.example .env
chmod 600 .env
```

Ersetze alle `CHANGE_ME`-Werte. Die folgenden Angaben sind für den ersten Start erforderlich:

| Variable | Bedeutung |
|---|---|
| `POSTGRES_DB` | Name der Portal-Datenbank |
| `POSTGRES_USER` | Datenbankbenutzer |
| `POSTGRES_PASSWORD` | Zufälliges Datenbankpasswort aus URL-sicheren Zeichen |
| `PORTAL_SECRET_KEY` | Zufälliger Anwendungsschlüssel mit mindestens 32 Zeichen |
| `PORTAL_FERNET_KEY` | URL-safe Base64 aus genau 32 Zufallsbytes für die Verschlüsselung gespeicherter Zugänge |
| `PORTAL_BOOTSTRAP_ADMIN_EMAIL` | E-Mail-Adresse des ersten Administrators |
| `PORTAL_BOOTSTRAP_ADMIN_PASSWORD` | Initiales Administratorpasswort mit mindestens 12 Zeichen |
| `PORTAL_ALLOWED_HOSTS` | Durch Kommas getrennte erlaubte Hostnamen |
| `PORTAL_DOMAIN` | Öffentlicher DNS-Name bei Verwendung des TLS-Profils |

Zufallswerte lassen sich ohne lokale Python-Installation erzeugen. Führe den ersten Befehl für Datenbankpasswort und Anwendungsschlüssel jeweils separat aus; der zweite erzeugt den Fernet-Schlüssel:

```bash
docker run --rm python:3.13.7-slim python -c "import secrets; print(secrets.token_hex(48))"
docker run --rm python:3.13.7-slim python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Bewahre den Fernet-Schlüssel zusammen mit den Datenbanksicherungen auf. Er muss bei Neustarts, Updates und Wiederherstellungen erhalten bleiben, damit gespeicherte Zugangsdaten entschlüsselt werden können.

Weitere Einstellungen sind in [.env.example](.env.example) beschrieben. Für HTTPS muss `PORTAL_COOKIE_SECURE=true` gesetzt bleiben. Für reproduzierbare Installationen verwende einen veröffentlichten Release-Tag oder `sha-<vollständiger-Commit>` als `PORTAL_IMAGE_TAG`.

### 2. Mit HTTPS starten

```bash
docker compose --profile tls pull
docker compose --profile tls up -d --wait
docker compose --profile tls ps
```

Öffne `https://<PORTAL_DOMAIN>` und melde dich mit den Bootstrap-Zugangsdaten an. Beim ersten Login wird ein Passwortwechsel verlangt.

Anschließend können `PORTAL_BOOTSTRAP_ADMIN_EMAIL` und `PORTAL_BOOTSTRAP_ADMIN_PASSWORD` in `.env` geleert werden. Übernimm die Änderung mit:

```bash
docker compose up -d --no-deps backend
```

Die Bootstrap-Konfiguration legt den ersten Administrator an und überschreibt keine bestehenden Konten oder Passwörter. Datenbankmigrationen werden beim Start des Backends automatisch ausgeführt.

### Vorhandenen Reverse-Proxy verwenden

Starte den Stack ohne TLS-Profil:

```bash
docker compose pull
docker compose up -d --wait
```

Leite den vorhandenen HTTPS-Reverse-Proxy auf `http://127.0.0.1:8080`. Er muss den ursprünglichen `Host` sowie `X-Forwarded-Proto: https` weitergeben. Ergänze den öffentlichen Hostnamen in `PORTAL_ALLOWED_HOSTS` und behalte `PORTAL_COOKIE_SECURE=true` bei.

Ohne TLS-Profil wird `PORTAL_DOMAIN` nicht verwendet. Die Adresse des Frontends lässt sich über `PORTAL_BIND_ADDRESS` und `PORTAL_PUBLIC_PORT` konfigurieren.

## Lokaler Test

Für einen lokalen Test unter Windows werden Docker mit Linux-Containern und PowerShell benötigt. Die Images werden aus dem Quellcode gebaut; Python und Node.js müssen dafür nicht auf dem Host installiert sein.

Erstelle im Repository-Stamm eine `.env`, falls noch keine vorhanden ist:

```powershell
if (!(Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

Trage gültige Schlüssel, ein Datenbankpasswort und die Bootstrap-Zugangsdaten wie unter [Installation](#installation) beschrieben ein. Setze zusätzlich:

```dotenv
PORTAL_IMAGE_REGISTRY=semaphore-portal-local
PORTAL_IMAGE_TAG=dev
PORTAL_PULL_POLICY=missing
PORTAL_COOKIE_SECURE=false
PORTAL_BIND_ADDRESS=127.0.0.1
PORTAL_PUBLIC_PORT=18092
PORTAL_ALLOWED_HOSTS=localhost,127.0.0.1
```

Baue und starte den Stack im Repository-Stamm:

```powershell
docker build -t semaphore-portal-local-backend:dev ./backend
docker build -t semaphore-portal-local-frontend:dev ./frontend
docker compose -p semaphore-porter-local up -d --wait
```

Das Portal ist anschließend unter **http://127.0.0.1:18092** erreichbar. Verwende bei lokalen Status-, Log- und Betriebsbefehlen ebenfalls `-p semaphore-porter-local`, damit sie denselben Stack ansprechen.

Zum Stoppen dient `docker compose -p semaphore-porter-local stop`. Zum erneuten Start genügt derselbe `up`-Befehl; die vorhandene Datenbank und Konfiguration bleiben erhalten. Nach Codeänderungen baue die betroffenen Images neu und führe `up -d --wait` erneut aus.

## Erste Schritte

1. **Semaphore verbinden:** Unter **Semaphore** die Basis-URL, den Service-Token und bei Bedarf eine Proxy-URL hinterlegen. Die Verbindung testen.
2. **Projektvorlage anlegen:** Unter **Projektvorlagen** ein vorhandenes Semaphore-Projekt als Vorlage sichern.
3. **Zugriffe vorbereiten:** Benutzer und Gruppen erstellen und die vorgesehenen Rollen zuweisen.
4. **Tenant erstellen:** Im Assistenten Vorlage, Tenant-Daten, Anwendungen, Datenbankprovider und Testdatensätze auswählen. Tasks und Zugriffe festlegen und die Zusammenfassung bestätigen.
5. **Tasks freigeben:** Task Templates synchronisieren, Parameter-Policies prüfen und Task-Berechtigungen vergeben.
6. **Tenant aktivieren:** Den Tenant für die berechtigten Benutzer bereitstellen.

Die Anmeldung unterstützt Benutzername und E-Mail-Adresse. Benutzernamen lassen sich unter **Benutzer & Gruppen** verwalten.

Der Tenant-Assistent erstellt die Projektkopie und deren Konfiguration. Deployments und Testdatenimporte werden anschließend über die freigegebenen Tasks ausgeführt. Das Entfernen eines Portal-Tenants lässt das Semaphore-Projekt bestehen; dessen tatsächliches Löschen erfolgt separat und bestätigt unter **Semaphore-Projekte**.

Abläufe und Voraussetzungen beschreibt die [Projektverwaltung](docs/PROJECT_MANAGEMENT.md).

### Task-Parameter und Policies

| Policy-Typ | Verwendung |
|---|---|
| `fixed` | Fester, nicht editierbarer Wert |
| `hidden` | Serverseitiger Wert ohne Anzeige im Browser |
| `enum` | Auswahl aus vorgegebenen Werten |
| `integer_range` | Ganze Zahl innerhalb festgelegter Grenzen |
| `string` | Text mit optionaler Längen- und Regex-Prüfung |
| `boolean` | Wahrheitswert |

Versionierte Presets bündeln wiederverwendbare Parameter. Zugangsdaten gehören in Semaphore Key Store oder Vault; Presets und Policies sind für Konfigurationswerte vorgesehen.

### Vault einrichten

Unter **Vault** werden Server-URL, KV-v2-Mount, Tenantwurzel und AppRole-Zugänge konfiguriert. Ein Schreibzugang dient der Anlage neuer Objekte; ein Lesezugang wird für neue Semaphore-Projekte bereitgestellt. Registry-Zugänge können pro Anwendung hinterlegt werden.

Nach Aktivierung steht die Vault-Anlage im Tenant-Assistenten zur Verfügung. Die Zielobjekte werden vor dem Schreiben geprüft. Bestehende Secrets werden nicht überschrieben; unterbrochene Anlagen können anhand des gespeicherten Fortschritts wieder aufgenommen werden.

Die vollständige Einrichtung einschließlich erforderlicher Rechte, Unternehmens-CA und Fehlerbehandlung beschreibt [Vault-Integration](docs/VAULT_IMPLEMENTIERUNG.md).

## Designstudio

Unter **Designs** lassen sich Designs auswählen, erstellen, bearbeiten, importieren und exportieren. Neue Entwürfe starten auf neutraler Basis. Neutral Hell, Neutral Dunkel, GitHub Black, SIT Hell und SIT Dunkel stehen als gleichwertige Vorlagen zur Verfügung.

Das eigenständige Designstudio bietet:

- Farbwähler, abgestimmte Farbpaletten und eine Kontrastprüfung
- Logo-Upload, Logogröße und ein optionales Hintergrundbild für die Anmeldung
- Anpassbare Portal-, Anmelde-, Footer-, Impressums- und Datenschutztexte
- Live-Vorschauen für Anmeldung, Portal, Bedienelemente und rechtliche Seiten
- Das vollständige Hauptmenü mit Admin- und Benutzeransicht sowie mobilem Menü
- Desktop- und Mobilansicht sowie einen Vergleich mit dem Ausgangsdesign

Designs und rechtliche Texte werden im jeweiligen Browser gespeichert. Sie werden nicht als globale Betreiberkonfiguration auf andere Geräte oder Benutzerkonten übertragen. Ein JSON-Export überträgt die Gestaltung einschließlich eingebetteter Bilder.

Details: [Designs und Unternehmensfarben](docs/DESIGNS.md).

## Betrieb

Die folgenden Beispiele verwenden das produktive TLS-Profil. Für Installationen mit eigenem Reverse-Proxy entfällt `--profile tls`; für den lokalen Test kommt `-p semaphore-porter-local` hinzu.

### Status und Diagnose

```bash
docker compose --profile tls ps
docker compose --profile tls logs --tail=200 backend frontend gateway
curl --fail https://portal.example.com/api/health
```

Die API-Dokumentation liegt unter `/api/docs`, das OpenAPI-Schema unter `/api/openapi.json`. Docker-Logs werden anhand von `PORTAL_LOG_MAX_SIZE` und `PORTAL_LOG_MAX_FILES` begrenzt.

### Updates

Sichere vor einem Update die Datenbank und `.env`. Setze `PORTAL_IMAGE_TAG` auf den gewünschten veröffentlichten Stand und führe aus:

```bash
docker compose --profile tls pull
docker compose --profile tls up -d --wait
```

Migrationen laufen beim Backend-Start. Ein Rollback benötigt den vorherigen Image-Tag und gegebenenfalls eine dazu passende Datenbanksicherung, wenn die Migration nicht rückwärtskompatibel ist.

### Datenbank sichern und wiederherstellen

Die folgenden Befehle verwenden Bash. Eine Sicherung im PostgreSQL-Custom-Format erstellen:

```bash
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > portal.dump
```

Datenbanksicherung und `.env` mit dem zugehörigen Fernet-Schlüssel gemeinsam geschützt außerhalb des Hosts aufbewahren.

Zur Wiederherstellung im Wartungsfenster die Anwendungscontainer stoppen. Der Restore ersetzt die entsprechenden Daten in der Zieldatenbank:

```bash
docker compose stop frontend backend
docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < portal.dump
docker compose --profile tls up -d --wait
```

### Häufige Probleme

| Symptom | Prüfen |
|---|---|
| Backend startet nicht oder bleibt `unhealthy` | Backend-Logs, ersetzte `.env`-Platzhalter und gültigen Fernet-Schlüssel prüfen |
| Image-Pull schlägt fehl | Registry, vorhandenen Image-Tag und gegebenenfalls GHCR-Anmeldung prüfen |
| Anmeldung über lokales HTTP schlägt fehl | `PORTAL_COOKIE_SECURE=false` für den lokalen Test setzen |
| Hostname wird abgelehnt | Hostnamen in `PORTAL_ALLOWED_HOSTS` ergänzen und Backend neu erstellen |
| HTTPS-Zertifikat fehlt | DNS, Erreichbarkeit der Ports 80/443 und Gateway-Logs prüfen |
| Semaphore oder Vault nicht erreichbar | URL, DNS, Proxy, Zertifikatskette und Backend-Netzwerkzugang prüfen |
| Task fehlt oder lässt sich nicht starten | Aktiven Tenant, Template-Synchronisierung, Policy, Mitgliedschaft und Task-Freigabe prüfen |

## Entwicklung

Für die Entwicklung auf dem Host werden Python 3.13, Node.js 22.19.0 und npm 11.6.2 verwendet. Direkte Abhängigkeiten sind in den Requirements-Dateien beziehungsweise `package.json` festgelegt; `package-lock.json` fixiert den Frontend-Abhängigkeitsbaum.

Backend-Tests aus dem Repository-Stamm in PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest
```

Frontend-Tests und Produktionsbuild, ebenfalls ausgehend vom Repository-Stamm:

```powershell
cd frontend
npm.cmd install --global npm@11.6.2
npm.cmd ci
npm.cmd test
npm.cmd run build
```

Die CI prüft Backend, Frontend und den Compose-Stack einschließlich Health- und Login-Route. Erfolgreiche Builds auf `main` veröffentlichen die Tags `latest`, `main` und `sha-<vollständiger-Commit>` für:

- `ghcr.io/midniqhtvibes/semaphore-porter-backend`
- `ghcr.io/midniqhtvibes/semaphore-porter-frontend`

Release-Tags im Format `vX.Y.Z` erzeugen zusätzlich versionierte Images. Die veröffentlichten Images verwenden die Plattform `linux/amd64`.

## Dokumentation

- [Architektur und Sicherheitsmodell](docs/ARCHITECTURE.md)
- [Projektverwaltung und Tenant-Assistent](docs/PROJECT_MANAGEMENT.md)
- [Berechtigungen und Benutzerverwaltung](docs/PERMISSIONS.md)
- [Vault-Integration](docs/VAULT_IMPLEMENTIERUNG.md)
- [Designs und Unternehmensfarben](docs/DESIGNS.md)
- [Abnahmetestplan für die eigene Umgebung](docs/ABNAHMETESTS.md)
