# Semaporter

**Das zentrale Portal für Ihre Semaphore-Automatisierung.**

Semaporter verbindet Projektverwaltung, kontrollierte Task-Ausführung und zentrale Zugriffsverwaltung in einer gemeinsamen Weboberfläche. Teams erhalten einen übersichtlichen Zugang zu ihren Automatisierungsaufgaben. Administratoren verwalten Mandanten, Vorlagen und Integrationen in der eigenen Infrastruktur.

[Installation](#installation) · [Setup und Betrieb](docs/SETUP.md) · [Konfiguration](.env.example)

## Funktionen

| Bereich | Umfang |
| --- | --- |
| Projekte und Mandanten | Zentrale Verwaltung von Semaphore-Projekten, Mandanten und wiederverwendbaren Projektvorlagen |
| Automatisierung | Freigegebene Tasks mit validierten Parametern, Live-Ausgaben und Ausführungshistorie |
| Benutzer und Teams | Nachträglich bearbeitbare Portalrollen, Gruppen, Personenprofile und gezielte Projekt- und Task-Freigaben |
| Programmpakete | Paketverwaltung mit Validierung, GitLab-Anbindung und versionierten Anwendungskatalogen |
| Zugangsdaten | Vault-Integration sowie zentrale SSH- und Registry-Zugangsprofile |
| Überwachung | Task-Status und optionale Deployment-Übersicht angebundener Zielhosts |
| Container-Verwaltung | Optionaler eigener Docker-Agent für bestehende Container: Status, Logs, Messwerte und bestätigte Verwaltungsaktionen |
| Nachvollziehbarkeit | Audit-Log für Verwaltungsaktionen und dokumentierte Task-Ausführungen |
| Designstudio | Farben, Logos, Bilder/GIF-Hintergründe mit Verdunkelung, Milchglas und Unschärfe, Live-Vorschau sowie Import/Export |

## Integrationen

**Semaphore UI** stellt die Automatisierungsumgebung bereit. Portalbenutzer benötigen für ihre freigegebenen Tasks keinen eigenen Semaphore-Login.

**Vault** ergänzt die zentrale Verwaltung von Secrets und Zugangsprofilen. **GitLab** verbindet Programmpakete mit Repository, Review und CI. Beide Integrationen sind optional und werden über die Administration konfiguriert.

Der [eigene Docker-Agent](agent/README.md) ist eine zusätzliche optionale Integration, unabhängig vom Deployment-Monitoring und ohne Portainer. Seine Images können gebaut werden, bevor der Dienst eingerichtet oder gestartet wird. Im normalen Portal ist die Container-Verwaltung standardmäßig ausgeschaltet. Einrichtung unter **Einstellungen → Verbindungen → Docker-Agenten**; Aktivierung und Schreibaktionen sind getrennte Freigaben. HTTPS ist erforderlich, gegenseitiges TLS mit Client-Zertifikat ist zusätzlich möglich. Konkrete Server-Compose und CI-Anpassungen werden separat abgestimmt.

## Installation

Vorausgesetzt werden Docker mit Linux-Containern, Docker Compose ab **2.33.1** und eine erreichbare Semaphore-UI-Instanz. Die bereitgestellten Anwendungsimages verwenden **Linux/amd64**.

Die Bereitstellung erfolgt mit [docker-compose.yml](docker-compose.yml) und einer lokalen Konfigurationsdatei:

```bash
cp .env.example .env
chmod 600 .env
```

Ersetzen Sie alle `CHANGE_ME`-Werte und hinterlegen Sie die Administrator-Zugangsdaten sowie den öffentlichen Hostnamen. [Konfiguration und Schlüsselerzeugung](docs/SETUP.md#konfiguration) beschreiben die erforderlichen Einstellungen.

Für den Betrieb mit integriertem HTTPS-Gateway:

```bash
docker compose --profile tls pull
docker compose --profile tls up -d --wait
```

Das Portal ist anschließend unter `https://<PORTAL_DOMAIN>` erreichbar. Der Domainname muss auf den Server zeigen; die Ports 80 und 443 müssen für das Gateway verfügbar sein. Beim ersten Login wird ein Passwortwechsel verlangt.

Alternativen und Betriebsregeln stehen in der [Setup-Anleitung](docs/SETUP.md): vorhandener Reverse-Proxy, lokaler Build, optionale Integrationen, Updates und Datensicherung.

## Demo

Unter `/demo/` steht eine integrierte Umgebung mit Beispieldaten und simulierten Anbindungen zur Verfügung. Sie verwendet einen separaten Daten- und Sitzungskontext und benötigt keine externen Testsysteme.

## Betrieb und Sicherheit

Semaporter besteht aus React-Frontend, FastAPI-Backend und PostgreSQL. Die Compose-Konfiguration trennt die Dienste über eigene Netzwerke und persistiert die Datenbank in einem benannten Volume. Backend und Datenbank veröffentlichen keine Host-Ports.

Rollenbasierte Berechtigungen, serverseitige Sitzungen, CSRF-Schutz, Argon2-Passwort-Hashes und verschlüsselte Integrationszugänge bilden die Grundlage der Zugriffskontrolle. Für den regulären Betrieb sind HTTPS, geschützte Konfigurationsdateien und regelmäßige Sicherungen vorgesehen.

Status und Logs lassen sich mit Docker Compose prüfen:

```bash
docker compose --profile tls ps
docker compose --profile tls logs --tail=100 backend frontend gateway
```

Die API-Dokumentation ist unter `/api/docs` erreichbar. Weitere Hinweise zu [Updates, Sicherungen und Diagnose](docs/SETUP.md#betrieb) enthält die Setup-Anleitung.

<!-- Optionales Easter Egg, standardmäßig nicht enthalten:
docker build --build-arg PORTAL_BUILD_IDDQD=1 -t semaporter-local-frontend:dev ./frontend
Aktivierung nur beim Build; im angemeldeten Portal außerhalb von Eingabefeldern IDDQD tippen.
-->
