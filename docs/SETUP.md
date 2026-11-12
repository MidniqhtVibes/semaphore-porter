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

Ein Reverse-Proxy auf dem Host erreicht das Frontend standardmäßig unter `http://127.0.0.1:8080`. Die Adresse ist über `PORTAL_BIND_ADDRESS` und `PORTAL_PUBLIC_PORT` konfigurierbar. Der Proxy muss den ursprünglichen `Host` einschließlich eines gegebenenfalls verwendeten Ports sowie `X-Forwarded-Proto: https` weiterreichen. Die Live-Taskansicht verwendet kurze, regelmäßig wiederholte API-Anfragen. Für zusätzliche Clients des SSE-Endpunkts sind Streaming ohne Proxy-Buffering und ausreichend lange Timeouts erforderlich.

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

## Task-Berichte, Live-Ausgabe und Tenant-Bereinigung

### Mailbericht

Bei einem Task mit `send_deployment_mail` setzt das Backend beim ausgewählten Mailbericht `mail_user` auf die Login-E-Mail der startenden Person. Alte feste Empfänger aus einer kopierten Policy und vom Browser mitgesendete Empfänger werden dabei ignoriert. Die Adresse ist im Startformular sichtbar, aber nicht bearbeitbar. Eine ungültige Konto-Adresse verhindert den Start mit Mailbericht.

Die Empfängerzuordnung steuert den Mailversand. Die Erreichbarkeit der verlinkten Testanwendung hängt zusätzlich von deren Laufzeit, veröffentlichter Adresse, Port und den Netz-/Proxyregeln der aufrufenden Person ab. Der Ansible-Stack erzeugt den Link aus seiner Deployment-Konfiguration. Bei einer Ablehnung durch den Firmenproxy den konkreten Link während der Laufzeit von den betroffenen Arbeitsplätzen prüfen und den Zugriffsweg mit den Netzwerkverantwortlichen abstimmen.

Der bestehende Semaphore-/Ansible-Stack übernimmt weiterhin den eigentlichen Versand. SMTP und Mail-Playbook müssen dort eingerichtet sein; Semaporter führt keinen zusätzlichen Maildienst ein. Diese Regel gilt auch für bestehende Tenants und deren alte Policies.

### Live-Ausgabe

Die Task-Detailansicht liest Status und vollständige Ausgabe alle zwei Sekunden, solange der Task wartet, läuft oder sein Zustand unbekannt ist. Vorübergehende Verbindungsfehler werden erneut versucht. Eine leere Semaphore-Antwort `null` bedeutet zunächst „noch keine Ausgabe“. Abgelaufene Sitzungen oder entzogene Zugriffe beenden die Anzeige. Auch der vorhandene SSE-Endpunkt behandelt leere Ausgaben und vorübergehende Fehler, die Oberfläche benötigt für ihre Live-Anzeige aber kein dauerhaftes Proxy-Streaming mehr.

Die Task-Ausgabe scrollt beim Öffnen und bei neuen Zeilen automatisch nach unten. Manuelles Hochscrollen pausiert das Folgen. Mit **Zum neuesten Eintrag** oder durch manuelles Scrollen bis zum Ende wird es wieder aktiviert. Dabei bewegt sich nur der Ausgabebereich.

**Laufende Tasks** fragt alle für das angemeldete Konto sichtbaren, über Semaporter gestarteten Ausführungen alle fünf Sekunden ab. Die Begrenzung der Historie auf die letzten 200 sichtbaren Ausführungen gilt für diese aktive Ansicht nicht. Abgeschlossene Tasks wechseln nach dem Statusabgleich in die Historie. Nicht bestätigte Zustände bleiben als **Status unbekannt** sichtbar; ein Abruffehler wird ausdrücklich angezeigt. Über **Aktualisieren** lässt sich die Liste erneut laden. Laufzeiten verwenden die von Semaphore gelieferten Start-/Endzeiten; reine Wartezeit und unbekannte Zustände erhalten keine scheinbare Ausführungslaufzeit.

Diese Taskliste benötigt den optionalen Host-Collector nicht. Ein abgeschlossener Ansible-Task kann ein weiterhin laufendes Docker-Deployment hinterlassen; dessen Lebensdauer und TTL gehören ins **Deployment-Monitoring**.

### Tenant entfernen

Als Systemadmin **Administration → Tenants → Tenant öffnen → Löschvorschau öffnen** wählen.

1. Temporäre Deployments regulär auslaufen lassen. Dauerhafte Deployments auf allen betroffenen Zielservern bewusst beenden. Die Bereinigung stoppt keine Container und startet keine Cleanup-Playbooks.
2. Bekannte Hostmeldungen dürfen keine laufenden Deployments mehr enthalten. Temporäre Einträge blockieren auch nach ihrem Ablaufzeitpunkt, bis die Hostmeldung die tatsächlich erfolgte Bereinigung bestätigt. Bei deaktivierter Überwachung die Zielserver selbst prüfen. Aktive Semaphore-Tasks ebenfalls abschließen lassen.
3. Die Vorschau prüfen: Portal-Zugriffe, Task-Freigaben und Ausführungen; das durch einen Erstellungsvorgang belegte Semaphore-Projekt; exakt die durch Vault-Anlagebelege nachgewiesenen Secret-Pfade.
4. Die Prüfung der Deployments bestätigen und die Tenant-Kennung exakt eingeben. Erst **Tenant endgültig entfernen** führt externe Löschungen aus.

Semaphore entfernt mit dem Projekt seine projektgebundenen Variablengruppen, Schlüssel, Inventories, Repositories und Task-Historie. Vault entfernt an den aufgeführten KV-v2-Pfaden alle Versionen und Metadaten dauerhaft. Semaporter entfernt danach Tenant, Mitgliedschaften, Freigaben, Policies, Ausführungen, Erstellungsvorgänge, SSH-Verwendungsbelege und tenantbezogene Audit-Ereignisse. Aus den vorhandenen Host-Snapshots werden die zugehörigen Einträge entfernt; die Host-Quelle bleibt bestehen.

Gemeinsame Konten, Gruppen, SSH-/Registry-Profile, globale Vorlagen und GitLab-Projekte/Images bleiben erhalten. Ein extern zugeordnetes Semaphore-Projekt ohne Semaporter-Anlagebeleg wird ausdrücklich in der Vorschau als erhalten angezeigt. Nicht belegte Vault-Pfade werden weder gesucht noch pauschal unter einem gemeinsamen Wurzelpfad gelöscht. Vorhandene Serverdateien, Datenträger, Backups oder externe Zugriffslogs werden nicht bereinigt. Die manuelle Stilllegung von Deployments gehört zum vorherigen Betriebsschritt.

Ein geänderter Vault-Pfad, fehlender Anlagebeleg, ein inzwischen neu angelegtes Secret oder eine unklare frühere Anlage verhindert die automatische Löschung. Auf global verwendete Profile verweisende Secret-Pfade werden ebenfalls geschützt. Während der Bereinigung diese Tenant-Secrets nicht parallel bearbeiten: Vault bietet für das Löschen der Metadaten keinen CAS-Abgleich. Für alte Erstellungsvorgänge wird die öffentliche Vault-Verbindung aus den gespeicherten Semaphore-Defaults verwendet; zukünftige Vorgänge speichern diese Zuordnung zusätzlich direkt im Anlageplan.

### Zusätzliche Vault-Berechtigung

Für die Einrichtung der Schreib-AppRole besteht bereits ein Betreiberzugang zu Vault. In der Vault-GUI unter **Policies → ACL Policies** die Policy der Semaporter-Schreibrolle um die folgenden Rechte ergänzen. Mount `kv` und Wurzel `semaphore/tenants` an die tatsächliche Semaporter-Konfiguration anpassen. Bei einer bereits vorhandenen Regel für denselben Pfad `delete` zu ihren Fähigkeiten hinzufügen; bestehende Regeln für Anlage und Metadatenprüfung beibehalten.

```hcl
# Nur die Tenant-Secrets, keine zentralen SSH-/Registry-Profile.
path "kv/metadata/semaphore/tenants/*" {
  capabilities = ["read", "delete"]
}

# Vor der ersten externen Löschung werden die Rechte geprüft.
path "sys/capabilities-self" {
  capabilities = ["update"]
}
```

Die Policy gehört zur **Semaporter-Schreibrolle**, nicht zur Semaphore-Leserolle. Der bereits verwendete Auth-Mount bleibt bestehen, beispielsweise `auth/semaphore-ansible/role/<SCHREIBROLLENNAME>`. Über die Vault-GUI-Konsole lässt sich die Zuordnung ohne Ausgabe von Zugangsdaten kontrollieren:

```text
read auth/semaphore-ansible/role/<SCHREIBROLLENNAME>
```

Unter `token_policies` muss die angepasste Policy enthalten sein. Keine neue Role-ID oder Secret-ID ist nötig, wenn lediglich die bereits zugeordnete Policy ergänzt wird. Semaporter meldet sich für einen Löschversuch neu an. Die Lese-AppRole benötigt keine Löschrechte.

Ohne ausreichende Rechte erfolgt keine externe Löschung. Die Fähigkeit wird für die konkreten geplanten Pfade geprüft. Die Policy selbst kann enger gefasst werden, wenn nur bestimmte Tenant-Pfade entfernt werden dürfen. Technische Referenz: [Vault KV-v2: Metadaten und alle Versionen löschen](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2#delete-metadata-and-all-versions).

### Fehler und Fortsetzung

Sobald die Ausführung beginnt, wird der Tenant deaktiviert. Neue Portal-Tasks sind dann gesperrt. Bei einem Fehler die Detailansicht erneut öffnen, die Löschvorschau prüfen und **Bereinigung fortsetzen** wählen. Bereits erledigte Schritte werden gespeichert. Ein Timeout gilt nicht als Nachweis, dass nichts gelöscht wurde; ein weiterer Versuch prüft den tatsächlichen Zustand erneut. Wieder angelegte Objekte werden nicht nochmals automatisch entfernt.

Vor dem ersten externen Löschversuch lässt sich ein begonnener Vorgang mit **Bereinigung verwerfen** zurücknehmen. Ein bereits deaktivierter Tenant wird dabei nicht automatisch aktiviert; das ist eine bewusste Aktion unter **Bearbeiten**. Nach einem externen Löschversuch ist die Fortsetzung erforderlich. Parallel gestartete Ausführungen sind gesperrt; eine nach einem Backend-Abbruch verwaiste Sperre läuft nach 15 Minuten aus.

Der erfolgreiche Abschluss entfernt auch den internen Löschvorgang selbst. Es bleibt entsprechend der gewählten Vorgabe kein tenantbezogenes Löschprotokoll in der Anwendung zurück.

## Integrierte Hilfe und Dokumentation

Nach Anmeldung ist **Hilfe & Dokumentation** unten in der Sidebar erreichbar. Die gemeinsame Oberfläche steht unter `/admin/hilfe` beziehungsweise `/portal/hilfe` bereit und verwendet das gewählte Design einschließlich Schriftarten, Farben und Hintergrundgestaltung. Suche und Themenbereiche berücksichtigen die verfügbaren Artikel des angemeldeten Kontos. Administrationsartikel sind auch bei direktem API-Aufruf nur für Systemadmins zugänglich.

Fragezeichen öffnen ein Seitenpanel mit einer kurzen Erklärung. Im Tenant-Assistenten passt sich die Hilfe dem jeweiligen Schritt an. Der Link zur vollständigen Anleitung öffnet einen neuen Tab; der Assistent und seine Eingaben bleiben erhalten. Native Dialogbedienung unterstützt Schließen per Escape und die Rückkehr zum auslösenden Element.

Markdown-Dateien, Artikel-Metadaten und Kontextzuordnungen liegen unter `backend/app/help_content/`. Die dortige README beschreibt die redaktionelle Pflege. Inhalte werden mit dem Backend aktualisiert; der angezeigte Inhaltsstand bezeichnet die redaktionelle Version. Zusätzliche Container, Datenbankmigrationen, Host-Ports oder externe Suchdienste werden für die Dokumentation nicht benötigt. Frontend und Backend für diese Erweiterung gemeinsam aktualisieren. Die integrierte Demo verwendet dieselben Artikel und ihre eigenen Sitzungen sowie Rollen.

## Projektlogos und optionale Task-Genehmigungen

### Projektlogos

Unter **Arbeitsbereich → Tenants → Tenant öffnen → Projektlogo** zwischen automatischer Zuordnung, mitgelieferten Logos, eigenem Upload und keiner Darstellung wählen. Mitgeliefert sind Doxis, PostgreSQL und WordPress; mehrere dieser Logos können kombiniert werden. Eigene PNG-, JPEG-, WebP- und GIF-Dateien sind bis 5 MB und 1024 × 1024 Pixel möglich. Animationen und transparente Hintergründe bleiben erhalten. Hochgeladene SVGs sind nicht erlaubt. Die Logos erscheinen rechts auf den Projektkacheln unter **Meine Projekte** und blenden zur Mitte aus.

Uploads werden in der vorhandenen Portal-Datenbank gespeichert und nur angemeldeten, berechtigten Benutzern ausgeliefert. Sie gehören zur Datenbanksicherung und werden bei vollständiger Tenant-Löschung mit entfernt. Die Projektlisten enthalten keine Bilddaten. Mitgelieferte Logos liegen lokal im Frontend; ihre Quellen stehen in `frontend/public/branding/projects/SOURCES.md`.

### Genehmigungsworkflow

Der Workflow ist für bestehende Tenants standardmäßig ausgeschaltet. Im **Tenant-Ersteller → Berechtigungen** optional aktivieren, einen aktiven Portalbenutzer als Vorgesetzten auswählen und die Grenze **niedrig**, **mittel** oder **hoch** festlegen. Pro freigegebenem Task Kosten und Aufwand administrativ einstufen. Die höhere der beiden Klassen löst ab einschließlich der Grenze eine Genehmigung aus. Die Einstufung ist eine organisatorische Vorgabe, keine Messung oder automatische Euro-/Stundenberechnung.

Bestehende Tenants lassen sich unter **Tenantdetails → Genehmigungsworkflow** umstellen; ihre Task-Klassen werden unter **Policy bearbeiten** gepflegt. Bei aktivierter Genehmigung sind nicht eingestufte Tasks bis zur Einstufung gesperrt. Unterhalb der Grenze bleibt der normale Taskstart möglich.

1. Der Antragsteller füllt das Taskformular aus und wählt **Genehmigung anfordern** mit einer Begründung. Es wird noch kein Semaphore-Task gestartet.
2. Der zugeordnete Vorgesetzte entscheidet unter **Arbeitsbereich → Task-Genehmigungen**. Dafür reicht das ausgewählte aktive Portal-Konto; die Zuordnung vergibt keine allgemeinen Tenant-/Task-Rechte. Selbstfreigaben und Entscheidungen anderer Administratoren anstelle des zugeordneten Vorgesetzten sind gesperrt.
3. Nach Zustimmung startet ausschließlich der Antragsteller unter **Task-Genehmigungen** mit **Genehmigten Task einmalig starten**. Die Parameter sind festgelegt und die Freigabe ist einmalig. Anfragen gelten insgesamt 24 Stunden ab Erstellung.
4. Aktueller Benutzerstatus, Tenant-/Taskrechte, aktive Policy, Vorgesetzter, Klassifizierung, Semaphore-Zuordnung und Parameter werden erneut geprüft. Änderungen der Konfiguration oder des Mailbericht-Empfängers verlangen eine neue Anfrage. Antragsteller können offene/genehmigte Anfragen zurückziehen.

Die Sperre gilt für Taskstarts **über Semaporter**, einschließlich direkter Aufrufe seiner Start-API und Systemadmins. Direkte Starts in Semaphore unterliegen weiterhin dessen eigener Berechtigungsverwaltung. Der Workflow benötigt keine weiteren Container, Ports oder Hintergrunddienste.

Genehmigungsparameter werden verschlüsselt gespeichert. Die Oberfläche zeigt weder Fixed-/Hidden-Werte noch erkannte Secrets. Audit-Ereignisse protokollieren Antrag und Entscheidung ohne Variablenwerte. Bei vollständiger Tenant-Bereinigung werden Anfragen, Bilddaten und tenantbezogene Genehmigungsereignisse ebenfalls entfernt.

Ein unklarer Semaphore-Startversuch verbraucht die Freigabe vorsorglich. Nicht blind erneut beantragen: Semaphore auf einen tatsächlich angelegten Task prüfen. Ein Systemadmin kann eine unklare Anfrage frühestens nach 15 Minuten und ausdrücklicher Bestätigung der manuellen Prüfung schließen. Dies startet oder stoppt keinen Task und stellt die Freigabe nicht wieder her. Solche ungeklärten Starts blockieren die Tenant-Bereinigung bis zum Abgleich.

### Optionale Mail-Hinweise

Die Entscheidung erfolgt immer angemeldet in Semaporter. Ohne SMTP funktionieren Antrag und Genehmigung vollständig in der Weboberfläche. Ein optionaler Hinweis an den Vorgesetzten sowie eine Entscheidungsnachricht an den Antragsteller können im Tenant eingeschaltet werden, sobald der Backend-Mailversand eingerichtet ist.

Folgende Werte gehören ausschließlich zur tatsächlichen Backend-Umgebung; eine unreferenzierte Zeile in einer Compose-`.env` reicht nicht. Konkrete Server-/Compose-Dateien werden weiterhin separat im Chat abgestimmt:

| Variable | Bedeutung |
| --- | --- |
| `APPROVAL_SMTP_HOST` | Freigegebener SMTP-Server |
| `APPROVAL_SMTP_PORT` | Port, Standard 587 |
| `APPROVAL_SMTP_SECURITY` | `starttls` (Standard) oder `tls`; keine unverschlüsselte Übertragung |
| `APPROVAL_SMTP_FROM` | Erlaubte Absenderadresse |
| `APPROVAL_SMTP_USERNAME` | Optionaler SMTP-Benutzer |
| `APPROVAL_SMTP_PASSWORD` | Optionales SMTP-Passwort; als Geheimnis behandeln |
| `APPROVAL_PORTAL_URL` | HTTPS-Basisadresse des Portals für Links |

Die Nachrichten enthalten keine Task-Parameter, Schlüssel oder Genehmigungstokens. Ein Mailfehler lässt die Anfrage in Semaporter bestehen und wird dort angezeigt. Es gibt keine automatische Mail-Wiederholung. Die Demo übernimmt keine produktiven SMTP-Einstellungen und versendet keine echten Mails.
