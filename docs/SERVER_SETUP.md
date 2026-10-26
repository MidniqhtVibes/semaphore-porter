# Serverbereitstellung: offene Angaben und Ablauf

Stand: 26.10.2026. **Planung; keine Änderungen am Zielserver, DNS oder Nginx Proxy Manager ausgeführt.** Es werden keine neuen Netze angelegt. Bestehende Netze, Portbelegungen und Betriebsregeln werden zuerst vom Verantwortlichen benannt und bestätigt; Semaporter erhält keine vom Agenten ausgewählte Serveranbindung.

## Bereits bekannt

- Zielserver: CAYO, interne IP `10.233.129.123`; Linux mit vorhandenem Docker und Docker Compose.
- NPM-Container `nginxproxymanager` läuft auf demselben Server in `application` und `vault`. Semaphore verwendet `application` und `db`; der bestehende NPM-Upstream lautet `semaphore:3000`.
- Gewünschte interne Adresse: `https://semaporter.devops.kommunale.it`.
- Vorhandene Netze umfassen `application`, `db` und `vault`. 80/81/443 sind vom bestehenden NPM veröffentlicht. Die mehrfachen internen 8080-Ports sind keine automatisch kollidierenden Host-Portbelegungen.
- Commit/Push und Freigabe dieses Repositories erfolgen durch den Nutzer.

## Noch zu klären

| Angabe | Status |
|---|---|
| Servername und interne Server-IP | CAYO, `10.233.129.123` |
| Docker-/Compose-Version und laufende/gestoppte Projekte | vor Ort prüfen |
| NPM-Containername und dessen Netzwerkzuordnung | `nginxproxymanager`, `application` und `vault` |
| Freigegebene vorhandene Netze | Frontend: `application`; Backend: `application` + `db` + `vault`; PostgreSQL: `db` |
| Anbindung über bestehendes Netz oder Host-Port | Vorhandene Netze, keine veröffentlichten Host-Ports; vom Nutzer bestätigt |
| Bei Host-Port: gewünschte Bind-IP und Port | Entfällt für die bestätigte Variante |
| Dienstnamen und Proxyziel | `semaporter-web:80`, intern `semaporter-backend` und `semaporter-postgres`; bestätigt |
| Installationsverzeichnis und Compose-Projektname | `/server/semaporter`, `semaporter` vom Nutzer festgelegt |
| Neue Datenbank oder Übernahme vorhandener lokaler Daten | Neue leere Installation vom Nutzer festgelegt |
| Quellcode und Veröffentlichung | Neues eigenes GitLab-Projekt mit CI/CD gewünscht; Instanz, Projektpfad, Branch, Registry und Runnerdetails offen |
| Sicherungsziel und Aufbewahrung | offen |
| Zertifikat | `stern.devops.kommunale.it-2026` vom Nutzer genannt; Abdeckung der Domain vor Ort prüfen |
| Interner DNS-Eintrag und NPM Access List | Noch prüfen beziehungsweise benennen |

## Lesende Vorabprüfung auf dem Zielserver

```bash
docker version
docker compose version
docker compose ls
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
docker network ls
sudo ss -ltnp
df -h
free -h
```

Den tatsächlichen NPM-Containernamen einsetzen:

```bash
docker inspect --format '{{json .NetworkSettings.Networks}}' NPM_CONTAINERNAME
```

Keine `.env` und keine vollständigen Container-Inspect-Ausgaben weitergeben. Die gefilterten Befehle enthalten keine Environment-Zugangswerte. Compose mindestens 2.33.1 entsprechend der [README](../README.md#voraussetzungen).

Falls eine Host-Portanbindung vorgegeben wird, auch reservierte Ports gestoppter Container prüfen:

```bash
for container_id in $(docker ps -aq); do
  docker inspect --format '{{.Name}} {{json .HostConfig.PortBindings}}' "$container_id"
done
```

Ein Port gilt erst nach Prüfung der Listener, sämtlicher Docker-Portreservierungen und der gewünschten Bind-Adresse als Kandidat. Direkt nach dem späteren Start die tatsächliche Belegung erneut kontrollieren. Andere Anwendungen dafür nicht stoppen, umkonfigurieren oder entfernen.

8080-Einträge sind vor der Bewertung zuzuordnen: Ein Container-Port kann in unterschiedlichen Containern vorkommen; ein veröffentlichter Host-Port hängt zusätzlich von Bind-IP und Protokoll ab. Auch ein NPM-Upstream auf 8080 belegt nicht automatisch den Host-Port 8080. Ohne die Bestandsangaben wird weder 8080 noch ein anderer Port ausgewählt. [Docker-Portfreigaben](https://docs.docker.com/engine/network/port-publishing/)

Ein vorhandenes gemeinsames Proxy-Netz kann eine Anbindung per Container-DNS ermöglichen. Welches Netz dafür freigegeben ist und welcher Alias/Port verwendet werden darf, entscheidet der Verantwortliche. NPMs eigenes `127.0.0.1` bezeichnet innerhalb eines Containers diesen Container. [NPM-Netzwerkanbindung](https://nginxproxymanager.com/advanced-config/#best-practice-use-a-docker-network)

## Geplanter Ablauf nach Klärung

1. Bestandsaufnahme auswerten und ausschließlich die vom Verantwortlichen ausgewählte Netz-/Portvariante dokumentieren. Bei Konflikten nachfragen, keine automatische Ausweichwahl.
2. Freigegebenes Release, Installationspfad, Projektname, Datenübernahme und Sicherungsverfahren festhalten. Geheimnisse lokal auf dem Server erzeugen beziehungsweise kontrolliert übernehmen; Fernet-Key bei Datenübernahme erhalten.
3. Konkrete Compose-/`.env`-Werte zur Prüfung bereitstellen. Keine neuen Netze oder globalen Docker-/Firewalländerungen ohne einen separat vereinbarten Umfang. Die bestehende Compose-Datei definiert eigene Netze; für den Zielserver müssen daher vor einem Start **alle** Dienstverbindungen gemäß der bestätigten Zuordnung auf die vorhandenen Netze abgebildet und auf Namenskonflikte geprüft werden. Bis dahin keinen Server-`up`-Befehl ausführen.
4. Geprüfte Konfiguration zunächst mit `docker compose ... config --quiet` validieren; keine aufgelösten Secrets in gemeinsame Protokolle kopieren. Danach nur den eigenen Stack im vereinbarten Umfang starten und vorhandene Anwendungen vergleichen.
5. Internen DNS-Eintrag und das vorgegebene Zertifikat/CA-Vertrauen für `semaporter.devops.kommunale.it` prüfen.
6. Im vorhandenen NPM per GUI **Hosts → Proxy Hosts → Add Proxy Host** einen Eintrag vorbereiten. Alle noch offenen Felder zuvor erfragen:

| NPM-Feld | Festzulegender Wert |
|---|---|
| Domain Names | `semaporter.devops.kommunale.it` |
| Scheme | `http` für den bestätigten internen Upstream |
| Forward Hostname / IP | `semaporter-web` |
| Forward Port | `80` innerhalb des Frontend-Containers; kein Host-Port |
| SSL Certificate / Force SSL | `stern.devops.kommunale.it-2026`; Domainabdeckung prüfen, HTTPS erzwingen nach Zertifikatsprüfung |
| Access List | ausdrücklich vorgegebene interne/VPN-Regel |
| Cache / Websocket / Advanced | passend zu Semaporter abstimmen; Task-Logs verwenden SSE |

7. Ursprünglichen Hostnamen und `X-Forwarded-Proto` durch die reale Proxykonfiguration prüfen. Uploadlimit und Timeouts für Paketdateien sowie lange Taskausgaben abstimmen. Semaporter verwendet bis 48 MB HTTP-Bodylimit für Base64-Pakete und bis 1900 Sekunden Read-Timeout in den betroffenen internen Nginx-Routen; der vorgeschaltete Proxy muss die vorgesehenen Anwendungsfälle ermöglichen.
8. HTTPS, Zertifikat, Login/CSRF, Rollen, Datei-Upload, Live-Logs und Verbindungen zu Semaphore/GitLab/Vault testen. Abschließend auch die bestehenden Anwendungen und Portzuordnungen prüfen.

Der Plan ersetzt keine Bestandsprüfung. Es wurde kein Host-Port als frei bestätigt und kein Proxy-Host angelegt. Die oben dokumentierte Zuordnung vorhandener Netze wurde vom Nutzer bestätigt; zusätzliche Netze werden nicht erstellt. Die bisherige lokale Entwicklungsinstallation auf Port 18092 ist hiervon getrennt.

## Vereinbarter Plan für GitLab-CI/CD

Ein neues eigenes GitLab-Projekt enthält **Semaporter selbst**. Das Stack-Projekt für Programmpakete bleibt davon getrennt. Ziel ist ein automatisches Deployment nach erfolgreicher Pipeline des noch festzulegenden Branches; Quellcode-Pushes führt der Nutzer aus.

Geplante Reihenfolge:

1. Backend- und Frontend-Tests sowie Produktionsbuild ausführen.
2. Backend- und Frontend-Images aus derselben Commit-SHA bauen und in die freigegebene Registry schreiben. Feste SHA-Tags für Deployment und Rückverfolgung verwenden; kein unkontrolliertes `latest`-Pull durch andere Dienste.
3. Einen exklusiven Deploymentjob auf CAYO ausführen. Vorab prüfen, ob der vorhandene Runner den vereinbarten Docker-Zugang besitzt; keine Daemon-/Runneränderung selbstständig vornehmen.
4. Ausschließlich `/server/semaporter` und Compose-Projekt `semaporter` verwalten. Neue Server-`.env` mit neuen DB-/Bootstrap-Zugängen anlegen und dauerhaft erhalten; CI darf sie bei normalen Releases nicht mit Testwerten überschreiben.
5. Vor einer Migration eine Datenbanksicherung am noch festzulegenden Ziel erzeugen. Beide neuen Images auf denselben SHA-Stand bringen und nur die eigenen Dienste aktualisieren.
6. Dienste, Migration und Health prüfen; bei Fehlern stoppen und den dokumentierten Wiederherstellungspfad verwenden. Ein altes Image allein ist nach einer nicht rückwärtskompatiblen Datenbankmigration kein ausreichender Rollback.
7. In NPM den bestätigten Proxy-Host mit `semaporter-web:80`, der Domain und dem benannten Zertifikat konfigurieren; Access List noch erfragen. DNS, HTTPS, Login, Uploads und Live-Logs sowie bestehende Anwendungen abnehmen.

**Vor diesem Deployment muss ein eigenes Server-Compose-Profil fertiggestellt und geprüft werden.** Die allgemeine `docker-compose.yml` erstellt eigene Netze und darf deshalb nicht unverändert auf CAYO gestartet werden. Das Serverprofil muss ausschließlich vorhandene `external`-Netze verwenden. Interne Ziele müssen eindeutige Semaporter-Namen erhalten: Die jetzige allgemeine Nginx-Konfiguration verwendet `backend:8000`; auf einem gemeinsam genutzten Netz ist das vor dem Serverbetrieb auf `semaporter-backend:8000` konfigurierbar zu machen. Der DB-Host muss entsprechend `semaporter-postgres` lauten. Diese Anpassung ist Bestandteil der folgenden konkreten Server-/CI-Konfiguration, nicht bereits auf dem Server umgesetzt.

Noch erforderlich: GitLab-Instanz und Projektpfad, Deploymentbranch, Runner-Tags/Executor/Docker-Zugang, Registry, Sicherungsziel/-aufbewahrung und NPM Access List. Ohne diese Angaben wird keine ausführbare Deploymentpipeline mit geratenen Werten bereitgestellt.
