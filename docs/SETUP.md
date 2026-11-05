# Setup und Betrieb

Allgemeine Voraussetzungen und Konfigurationsregeln für eine selbst gehostete Semaporter-Installation. Die Shell-Beispiele verwenden Bash und werden im Verzeichnis der Compose-Datei ausgeführt.

## Voraussetzungen

- Docker mit Linux-Containern und Docker Compose ab Version 2.33.1.
- Linux/amd64 für die bereitgestellten Anwendungsimages.
- Zugriff auf die in `.env` konfigurierte Container-Registry; für private Images ist eine Registry-Anmeldung erforderlich.
- Eine vom Backend erreichbare Semaphore-UI-Instanz mit Service-Token und passenden Projekt- und Task-Rechten.
- Für HTTPS ein gültiger DNS-Name sowie ein Reverse-Proxy oder das integrierte TLS-Gateway.

Der Betrieb mit fertigen Images benötigt `docker-compose.yml` und `.env`. Python und Node.js müssen auf dem Portal-Host nicht installiert sein.

## Konfiguration

Die vollständige Vorlage steht in [.env.example](../.env.example). Kopieren Sie sie nach `.env`, ersetzen Sie sämtliche Platzhalter und beschränken Sie den Dateizugriff auf den Betreiber.

| Einstellung | Anforderung |
| --- | --- |
| `COMPOSE_PROJECT_NAME` | Stabiler Installationsname; bei bestehenden Installationen beibehalten, damit dieselben Volumes verwendet werden |
| `PORTAL_IMAGE_REGISTRY` | Gemeinsamer Image-Präfix für Backend und Frontend |
| `PORTAL_IMAGE_TAG` | Derselbe veröffentlichte Release- oder vollständige `sha-…`-Tag für beide Anwendungsimages |
| `POSTGRES_DB`, `POSTGRES_USER` | Datenbankname und Benutzer |
| `POSTGRES_PASSWORD` | Eigenes zufälliges Passwort aus URL-sicheren Zeichen |
| `PORTAL_SECRET_KEY` | Eigener zufälliger Anwendungsschlüssel mit mindestens 32 Zeichen |
| `PORTAL_FERNET_KEY` | URL-safe Base64 eines zufälligen 32-Byte-Schlüssels für gespeicherte Integrationszugänge |
| `PORTAL_BOOTSTRAP_ADMIN_EMAIL` | E-Mail-Adresse des ersten Administrators |
| `PORTAL_BOOTSTRAP_ADMIN_PASSWORD` | Eigenes starkes Initialpasswort mit mindestens 12 Zeichen |
| `PORTAL_ALLOWED_HOSTS` | Kommagetrennte erlaubte Hostnamen ohne Schema, Port oder Pfad |
| `PORTAL_COOKIE_SECURE` | `true` für HTTPS; `false` ausschließlich bei lokalem HTTP-Test |
| `PORTAL_DOMAIN` | Öffentlicher DNS-Name für das integrierte TLS-Gateway |

### Schlüssel erzeugen

Führen Sie diesen Befehl für Datenbankpasswort und Anwendungsschlüssel jeweils separat aus:

```bash
docker run --rm python:3.13.7-slim python -c "import secrets; print(secrets.token_hex(48))"
```

Den Fernet-Schlüssel erzeugen Sie separat:

```bash
docker run --rm python:3.13.7-slim python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Die `.env` enthält vertrauliche Werte und gehört nicht in die Versionsverwaltung. Bewahren Sie den Fernet-Schlüssel geschützt zusammen mit den zugehörigen Datenbanksicherungen auf. Er muss bei Neustarts, Updates und Wiederherstellungen erhalten bleiben; ein bloßer Austausch macht vorhandene verschlüsselte Zugänge unlesbar.

### Erstes Administratorkonto

Die Bootstrap-Einstellungen legen ein noch nicht vorhandenes Konto an. Bestehende Konten und Passwörter werden nicht überschrieben. Nach dem ersten Login und Passwortwechsel können `PORTAL_BOOTSTRAP_ADMIN_EMAIL` und `PORTAL_BOOTSTRAP_ADMIN_PASSWORD` geleert werden. Übernehmen Sie die Änderung mit:

```bash
docker compose up -d --no-deps backend
```

## HTTPS und Reverse-Proxy

### Integriertes TLS-Gateway

Setzen Sie `PORTAL_DOMAIN` und nehmen Sie denselben Hostnamen in `PORTAL_ALLOWED_HOSTS` auf. DNS und eingehende TCP-Ports 80 und 443 müssen zum Gateway führen. Caddy übernimmt die Zertifikatsverwaltung.

```bash
docker compose --profile tls pull
docker compose --profile tls up -d --wait
```

`PORTAL_COOKIE_SECURE=true` bleibt gesetzt. Die Gateway-Ports und deren Bind-Adresse lassen sich über die entsprechenden Variablen in `.env.example` anpassen.

### Vorhandener Reverse-Proxy

Starten Sie den Stack ohne TLS-Profil:

```bash
docker compose pull
docker compose up -d --wait
```

Ein Reverse-Proxy auf dem Host erreicht das Frontend standardmäßig unter `http://127.0.0.1:8080`. Die Adresse ist über `PORTAL_BIND_ADDRESS` und `PORTAL_PUBLIC_PORT` konfigurierbar. Der Proxy muss den ursprünglichen `Host` einschließlich eines gegebenenfalls verwendeten Ports sowie `X-Forwarded-Proto: https` weiterreichen. Für Live-Ausgaben sind Streaming ohne Proxy-Buffering und ausreichend lange Timeouts erforderlich.

Für einen Proxy in einem eigenen Container richten Sie eine gemeinsame Netzwerkverbindung mit einem eindeutigen Frontend-Alias ein. `127.0.0.1` bezeichnet dort den Proxy-Container. Lassen Sie die internen Anwendungs- und Datenbanknetze getrennt und beschränken Sie den direkten Frontend-Zugriff auf den vorgesehenen Proxy.

Der öffentliche Hostname gehört in `PORTAL_ALLOWED_HOSTS`; `PORTAL_COOKIE_SECURE=true` bleibt aktiv. `PORTAL_DOMAIN` wird nur vom integrierten Gateway verwendet.

## Lokaler Build

Für einen Build aus dem Quellcode benötigen Sie das vollständige Repository. Verwenden Sie in `.env` für eine neue lokale Installation beispielsweise:

```dotenv
COMPOSE_PROJECT_NAME=semaporter-local
PORTAL_IMAGE_REGISTRY=semaporter-local
PORTAL_IMAGE_TAG=dev
PORTAL_PULL_POLICY=missing
PORTAL_COOKIE_SECURE=false
PORTAL_BIND_ADDRESS=127.0.0.1
PORTAL_PUBLIC_PORT=8080
PORTAL_ALLOWED_HOSTS=localhost,127.0.0.1
```

Bei einem bestehenden Stack bleibt dessen bisheriger `COMPOSE_PROJECT_NAME` erhalten. Alle erforderlichen Schlüssel und Bootstrap-Werte müssen auch lokal gesetzt sein.

```bash
docker build -t semaporter-local-backend:dev ./backend
docker build -t semaporter-local-frontend:dev ./frontend
docker compose up -d --wait
```

Das Portal ist unter `http://127.0.0.1:8080` erreichbar. Nach Quellcodeänderungen bauen Sie die betroffenen Images erneut und führen denselben `up`-Befehl aus.

## Optionale Integrationen

Die Verbindungen werden in der Administration eingerichtet. Die Dienste müssen aus dem Backend-Container erreichbar sein; DNS, Firewall und Zertifikatsvertrauen sind entsprechend bereitzustellen.

| Integration | Voraussetzungen |
| --- | --- |
| Vault | KV-v2-Mount und administrativ bereitgestellte AppRole-Zugänge; getrennte Schreib- und Lesezugänge mit auf die vorgesehenen Pfade begrenzten Policies |
| SSH-Zugangsprofile | Eigener Vault-Lesezugang, versionierte private SSH-Schlüssel und bereits auf den Zielhosts beziehungsweise Git-Repositories autorisierte öffentliche Schlüssel |
| Registry-Zugänge | Gültiger Registry-Host und Zugangsdaten; bei Vault-Referenzen zusätzlich ein eigener Lesezugang und eine konkrete Secret-Version |
| GitLab | Instanz-URL, numerische Projekt-ID, Basisbranch und Token; `read_api` zum Lesen, `api` und passende Projektrolle für API-Schreibzugriffe |

Vault-Policies, AppRoles, Hostberechtigungen und Registry-Infrastruktur werden durch die jeweiligen Betreiber bereitgestellt. GitLab-Schreibzugriffe benötigen einen geschützten Basisbranch und gesondert freigeschalteten Schreibmodus. Für die Übernahme eines Katalogstandes ist eine erfolgreiche Pipeline für den aktuellen Commit des konfigurierten Basisbranches erforderlich. Repository und Pakete müssen zum unterstützten Paketvertrag passen.

### Datei-Inventories mit SSH-Profilen

Die automatische SSH-Zuordnung prüft konkrete Hosts und SSH-Benutzer in statischen INI-/YAML-Inventories. Ein Datei-Inventory wie `inventory/inventory.ini` enthält in der Semaphore-Vorlage nur den Pfad, nicht die Hostliste.

Im Tenant-Assistenten unter **Schritt 4 → Ressourcen** zuerst das Host-SSH-Profil für das Inventory auswählen. Danach bei **Kopie vor dem Restore bearbeiten** die betreffende INI-/YAML-Datei hochladen oder ihren vollständigen Inhalt einfügen. **Hostliste prüfen** gleicht Benutzer und Ziele mit dem Profil ab. Mit **Als statisches Inventory übernehmen** wird nur die Projektkopie umgestellt; Repository, Quellprojekt und Datei bleiben bestehen. Die Tenant-Validierung und Schlüsselübertragung prüfen die Zuordnung anschließend erneut.

Die Kopie folgt späteren Änderungen der Repository-Datei nicht automatisch. Änderungen an Hosts und Benutzern deshalb im Tenant-Inventory pflegen beziehungsweise erneut übernehmen. Passwörter und private Schlüssel gehören nicht in die Hostliste. Der Import führt keine Inventory-Skripte aus und baut keine SSH-Verbindung auf. Eine erfolgreiche Ausführung eines vorgesehenen Diagnose-Tasks prüft danach die tatsächlichen Zugriffe.

### Interne Zertifikate

Für Vault und GitLab können `VAULT_CA_BUNDLE` und `GITLAB_CA_BUNDLE` auf eine vertrauenswürdige PEM-Datei **innerhalb des Backend-Containers** zeigen. Binden Sie diese über eine Compose-Override-Datei schreibgeschützt ein. Ein Host-Dateipfad allein stellt die Datei dem Container nicht bereit. Die TLS-Prüfung bleibt aktiv.

### Deployment-Monitoring

Die optionale Deployment-Übersicht benötigt je Zielhost eine Monitoring-Quelle sowie den über die Administration herunterladbaren Status-Exporter und Sender. Voraussetzung sind Python ab 3.10 und unterstützte Lifecycle-Metadaten im Deployment-Verzeichnis, üblicherweise `/opt/semaphore-deployments`.

- Der lokale Exporter benötigt privilegierten Zugriff auf Docker und die Lifecycle-Dateien. Er schreibt einen bereinigten Snapshot und erhält weder Token noch Netzwerkzugang.
- Der Sender läuft unter einem eigenen Dienstkonto ohne Docker-Rechte. Er liest die root-eigene Statusablage und eine private Token-Datei mit Modus `0400` oder `0600` und meldet den Snapshot über HTTPS.
- Besitzer, Dateirechte und Dienstbeschränkungen werden auf dem Zielhost eingerichtet. Die Statusablage darf für den Sender nur lesbar sein. Netzwerkbeschränkungen des Exporters sind über die Dienstkonfiguration durchzusetzen.

Die beiden folgenden Werte gehören ausschließlich zur Umgebung des Senders auf dem Zielhost:

```dotenv
SEMAPORTER_URL=https://portal.example.com
SEMAPORTER_MONITOR_TOKEN_FILE=/geschuetzter/pfad/collector-token
```

Exporter und Sender sollten etwa alle 15 Sekunden aktualisieren beziehungsweise übertragen. Snapshots müssen jünger als 90 Sekunden sein; die Hostuhren müssen synchron laufen. Das Portal benötigt dafür keinen Docker-Socket und keinen zusätzlichen öffentlichen Port.

### Gestaltung

Eigene Designs einschließlich Bildern und rechtlichen Texten werden im jeweiligen Browser gespeichert. Sie sind keine zentrale Betreiberkonfiguration. Verwenden Sie den Design-Export und -Import zur Übertragung zwischen Browsern.

## Betrieb

Die Beispiele verwenden das integrierte TLS-Gateway. Bei einem vorhandenen Reverse-Proxy entfällt `--profile tls`.

### Status und Diagnose

```bash
docker compose --profile tls ps
docker compose --profile tls logs --tail=200 backend frontend gateway
curl --fail https://portal.example.com/api/health
```

`/api/health` prüft die Backend-Datenbankverbindung. `/healthz` prüft die Erreichbarkeit des Frontend-Webservers. Die API-Dokumentation steht unter `/api/docs`, das Schema unter `/api/openapi.json`. Die Healthchecks ersetzen keine Prüfung der externen Integrationen.

`PORTAL_LOG_MAX_SIZE` und `PORTAL_LOG_MAX_FILES` begrenzen die Docker-Logs pro Container. `docker compose stop` stoppt den Stack unter Erhalt der Daten. `docker compose down --volumes` löscht die zugehörigen benannten Volumes einschließlich der Portal-Datenbank.

### Updates

Sichern Sie Datenbank und `.env` und setzen Sie `PORTAL_IMAGE_TAG` auf den gewünschten veröffentlichten Stand. Verwenden Sie für Backend und Frontend denselben Tag.

```bash
docker compose --profile tls pull
docker compose --profile tls up -d --wait
```

Datenbankmigrationen laufen beim Backend-Start automatisch. Ein Rückwechsel kann neben den vorherigen Images eine zum älteren Schema passende Datenbanksicherung erfordern. Behalten Sie Installationsname, Datenbankkonfiguration und Verschlüsselungsschlüssel bei.

### Datensicherung

Eine Sicherung im PostgreSQL-Custom-Format erstellen:

```bash
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > portal.dump
```

Bewahren Sie Sicherung und zugehörige `.env` geschützt außerhalb des Hosts auf und prüfen Sie die Wiederherstellung regelmäßig. Bei Verwendung des integrierten Gateways sollten auch dessen Zertifikats- und Konfigurationsvolumes in das Sicherungskonzept aufgenommen werden.

Eine Wiederherstellung ersetzt Daten in der Zieldatenbank und gehört in ein Wartungsfenster:

```bash
docker compose stop frontend backend
docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --exit-on-error' < portal.dump
docker compose --profile tls up -d --wait
```

### Häufige Konfigurationsfehler

| Symptom | Prüfen |
| --- | --- |
| Backend bleibt `unhealthy` | Backend-Logs, `.env`-Platzhalter, Schlüssel und Datenbankzugang |
| Image-Pull schlägt fehl | Registry-Adresse, vorhandener Tag und Registry-Anmeldung |
| Lokale HTTP-Anmeldung funktioniert nicht | `PORTAL_COOKIE_SECURE=false` für den lokalen Test |
| Hostname wird abgelehnt | Öffentlicher Hostname in `PORTAL_ALLOWED_HOSTS`, anschließend Backend-Konfiguration übernehmen |
| HTTPS-Gateway startet nicht korrekt | DNS, Portbelegung, Erreichbarkeit und Gateway-Logs |
| Externe Verbindung schlägt fehl | DNS, Netzwerkzugang, Zugangsdaten und Zertifikatsvertrauen im Backend-Container |

[Zur Projektübersicht](../README.md)
