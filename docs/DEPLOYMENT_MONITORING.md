# Live-Deployments und Restlaufzeit

Unter **Arbeitsbereich → Überwachung** stehen jetzt Live-Deployments und die bisherige Portal-Task-Historie. Die Ansicht ist Systemadmins vorbehalten.

## Datenquelle und Umfang

Der Semaphore-Stack schreibt pro Deployment auf dem **Deployment-Zielhost** unter `/opt/semaphore-deployments/<deployment_id>/`:

- `state.json` (Schema 7): Anwendung, Release, Tenant, Runtime-Scope, Provider, Dataset, Endpoint und Lifecycle-Zeiten.
- `metadata.env`: ältere Metadaten und beispielsweise den Quell-Git-Commit.
- `status.env`: aktuelle Lifecycle-Phase und gegebenenfalls aktualisierte Ablaufzeit.

Ein lokaler **Status-Exporter** liest diese Dateien und die Containerliste. Er schreibt ausschließlich die vorgesehenen Metadaten und Containerzahlen atomar in eine lokale JSON-Datei. Ein separater **Sender** unter einem eingeschränkten Dienstkonto liest nur diese Statusdatei und überträgt sie an Semaporter. Dadurch werden auch Deployments sichtbar, die direkt in Semaphore gestartet wurden oder schon vor der Einrichtung bestanden. Ein lokaler Portal-TaskRun ist nicht erforderlich. Ein Paar aus Exporter und Sender pro Zielhost deckt dessen Projekte und Tenants gemeinsam ab.

Die Restlaufzeit ist **Deployment-TTL**, keine Schätzung der Dauer eines Ansible-Tasks. Im vorhandenen Stack beginnt sie erst nach erfolgreicher Readiness. Eine noch nicht gesetzte Ablaufzeit bleibt unbekannt. Die Ablaufzeit aus `status.env` hat Vorrang vor `state.json` und `metadata.env`.

Die Erfassung setzt Lifecycle-Dateien dieses Stacks und Docker Compose-Projektlabels voraus. Beliebige andere Semaphore-Playbooks ohne diesen Vertrag werden nicht automatisch als Deployments erkannt. Erfasst werden die angebundenen Zielhosts, nicht automatisch alle Hosts eines Inventories. Noch wartende Semaphore-Tasks haben noch kein Deployment-Verzeichnis.

## Rechteaufteilung

| Bestandteil | Rechte und Aufgabe |
| --- | --- |
| `semaporter-exporter.py` | Lokale, einmalige Erfassung als root. Ausschließlich lesender Docker-Befehl `ps --all` am lokalen Unix-Socket. Schreibt die bereinigte Statusdatei, besitzt keinen Token und überträgt nichts. |
| Statusdatei | Eigentümer root, Gruppe des Dienstkontos, Modus `0640`; übergeordnetes Verzeichnis root-eigen, ohne Schreibrecht für Gruppe/andere, beispielsweise `0750` oder `2750`. |
| `semaporter-collector.py` | Sender als Dienstkonto ohne root, Docker-Gruppe, Socket-ACL, sudo oder interaktive Anmeldung. Liest nur den Export und seinen Token; überträgt zum bestehenden Semaporter-Endpunkt. |

Die Skripte und ihre Verzeichnisse müssen root gehören und dürfen vom Dienstkonto nicht veränderbar sein. **Keine Docker-Gruppenmitgliedschaft, keine allgemeinen Docker-sudo-Regeln und keine ACL auf den Docker-Socket für das Senderkonto einrichten.** Ebenso keine Leserechte auf Deployment-Verzeichnisse oder App-`.env` vergeben. Ein Unix-Socket wird durch einen `:ro`-Bind-Mount nicht zu einer Docker-API mit ausschließlich lesenden Operationen.

Das ist eine Aufteilung der Berechtigungen, keine vollständige Beseitigung des Risikos: Der kleine lokale Exporter besitzt weiterhin privilegierten Docker-Zugriff. Er muss als vertrauenswürdiger Code behandelt werden. Seine Dienstkonfiguration sollte Netzwerkverbindungen über `AF_INET`/`AF_INET6` sperren, nur `AF_UNIX` für Docker erlauben und ihm nur die Statusablage schreibbar machen. Der Sender benötigt dagegen Netzwerk, aber keinen Zugriff auf Hostverwaltungs-Sockets oder andere Anwendungsverzeichnisse. CPU-/Speicherlimits und `NoNewPrivileges` ergänzen diese Grenzen. Diese Betriebssystem-Grenzen müssen bei der Einrichtung auf dem Zielhost konfiguriert und geprüft werden; Python-Code allein richtet sie nicht ein.

## Einrichtung und Funktionsprüfung

1. Backend und Frontend aktualisieren. Der vorhandene Backend-Start wendet die additive Migration `20261029_0007` an; für die Aufteilung ist keine weitere Migration nötig.
2. Unter **Überwachung → Monitoring-Quellen und Einrichtung** pro Zielhost eine Quelle anlegen und den einmal angezeigten Token sichern. Bestehende Quellen/Tokens können weiterverwendet werden. Einen alten kombinierten Collector vor der Umstellung stoppen, damit nur ein Sender pro Quelle meldet.
3. **Status-Exporter herunterladen** und **Sender herunterladen** wählen. Beide Downloads sind administrativ geschützt, enthalten keinen Token und funktionieren eigenständig mit Python 3.10 oder neuer, ohne Zusatzpakete. Quellcode: `backend/app/integrations/deployment_exporter.py` und `deployment_collector.py`.
4. Auf dem Zielhost ein separates Dienstkonto ohne Anmeldung und ohne zusätzliche privilegierte Gruppen verwenden. Die Installationsdateien bleiben root-eigen. Die Statusablage ist root-eigen; nur ihre Gruppe erlaubt dem Sender Lesen/Betreten. Der Sender bekommt keine Schreibrechte auf diese Ablage.
5. Den Exporter mit einer festen absoluten Ausgabe-Datei einmal als root starten. `--root` bezeichnet die vorhandenen Lifecycle-Dateien, `--output` eine vorbereitete geschützte Statusablage. `--docker-bin` ist optional; Standard `/usr/bin/docker`, vor Ort mit `command -v docker` abgleichen. Der Exporter erwartet weder URL noch Token und lehnt diese Konfiguration ausdrücklich ab. Er verwendet eine feste, bereinigte Umgebung für den Docker-Unterprozess.

```text
python3 -I semaporter-exporter.py --root /PFAD/ZU/DEPLOYMENTS --output /STATUSABLAGE/snapshot.json
```

Die Großbuchstaben-Pfade sind Platzhalter, keine automatisch angelegten Verzeichnisse. Der vorhandene Deployment-Root ist normalerweise `/opt/semaphore-deployments`. Erwartet wird `Snapshot written: ... complete=True`. Bei Erfassungsfehlern wird ein unvollständiger Snapshot mit Warncodes geschrieben, der keine Löschung bisheriger Einträge bestätigt.

6. Den Token als private Datei übergeben, vorzugsweise mit systemd `LoadCredential=`. Der Sender liest ihn über **`SEMAPORTER_MONITOR_TOKEN_FILE`**; die Datei muss root oder dem Dienstkonto gehören und `0400`/`0600` besitzen. Der Tokenwert selbst darf nicht mehr als `SEMAPORTER_MONITOR_TOKEN` in der Umgebung stehen. Die URL steht separat unter **`SEMAPORTER_URL`**. Diese Angaben gehören ausschließlich zum Sender auf dem Zielhost, nicht in GitLab oder die Semaporter-Compose.

```text
SEMAPORTER_URL=https://EURE-SEMAPORTER-ADRESSE
SEMAPORTER_MONITOR_TOKEN_FILE=/GESCHUETZTE-CREDENTIAL-DATEI
```

7. Unter dem Dienstkonto einmalig testen:

```text
python3 -I semaporter-collector.py --snapshot /STATUSABLAGE/snapshot.json --once
```

Der Export muss jünger als 90 Sekunden sein. Erwartet wird `Snapshot accepted: ...`. Nach bereits akzeptiertem Export ist `already received or superseded` korrekt: HTTP 409 zählt als bereits bearbeitet, HTTP 401/403 bleiben Fehler. Der Sender verändert die Beobachtungszeit nie und sendet dieselbe Datei im laufenden Prozess nicht wiederholt.

8. Exporter regelmäßig als kurzen lokalen Dienst starten, Sender dauerhaft unter dem Dienstkonto betreiben. Für beide sind etwa 15 Sekunden vorgesehen; Sender mit `--interval 30` anpassbar, mindestens 10 Sekunden. Auch das Exportintervall muss zur Frischegrenze von 90 Sekunden passen. Erst nach erfolgreichem Funktionstest automatisch starten lassen. Die konkreten Serverbefehle und Dienstdateien werden entsprechend der Projektvorgabe ausschließlich im Chat bereitgestellt, nicht als Deployment-Artefakte im Repository abgelegt.

Der Sender verweigert root, Mitgliedschaft in einer sichtbaren Docker-Gruppe und erkennbaren Schreibzugriff auf den lokalen Docker-Socket. Das ersetzt keine Prüfung der tatsächlichen Host-Gruppen, ACLs, sudo-Regeln oder alternativer Verwaltungszugänge. Beim Lesen prüft er root-eigene, nicht von anderen beschreibbare Pfade, geschützte reguläre Dateien, Größe, Schema, erlaubte Felder und Zeit. Symlinks, Hardlinks, FIFOs, zusätzliche Felder und widersprüchliche Metadaten werden abgelehnt. Der Exporter ersetzt die Statusdatei atomar mit `0640` und der Gruppe des Ablageverzeichnisses.

Für einen ausdrücklich unverschlüsselten internen HTTP-Test benötigt der Sender `--allow-http`. Dabei wird auch der Token unverschlüsselt übertragen. Regulär HTTPS verwenden; TLS-Prüfung bleibt aktiv und Redirects werden abgewiesen. Der Sender berücksichtigt die Proxy-Umgebung von Python/urllib; interne Ziele gegebenenfalls gezielt in `NO_PROXY`/`no_proxy` aufnehmen. Eine Firmen-CA muss im Vertrauensspeicher des Senderprozesses hinterlegt sein. Der Exporter benötigt keine Proxy-Konfiguration.

Es werden keine zusätzlichen Serverports, Docker-Netze, SSH-Logins aus dem Backend oder Docker-Socket-Mounts in Semaporter benötigt. Es wurden keine Benutzer oder Dienste auf CAYO angelegt und keine CAYO-/Pipeline-Konfigurationsdateien im Repository ergänzt.

## Anzeige und Bedeutung

| Anzeige | Bedeutung |
| --- | --- |
| Läuft | Alle gefundenen Container des Compose-Projekts laufen; keiner meldet `unhealthy` oder einen startenden Healthcheck. Ohne Healthcheck ist dies keine Bestätigung der Anwendungserreichbarkeit. |
| Wird vorbereitet | Lifecycle meldet eine Vorbereitungsphase; TTL kann noch fehlen. |
| Container starten | Mindestens ein laufender Container meldet einen startenden Healthcheck. |
| Gestört | Container ausgefallen oder `unhealthy`. |
| Gestoppt / Container fehlen | Keine laufenden beziehungsweise keine zugeordneten Container gefunden. |
| TTL abgelaufen | Gespeicherte Ablaufzeit erreicht; Cleanup kann noch ausstehen. |
| Cleanup ausstehend | Der Stack meldet `cleanup_pending`. |
| Unbekannt / veraltet | Fehlende, unvollständige oder über 90 Sekunden alte Zustandsmeldung. |

Die Web-App fragt alle zehn Sekunden ab und aktualisiert den Countdown jede Sekunde anhand der Serverzeit. Der Zustand ist damit eine regelmäßig aktualisierte Momentaufnahme. Die Host- und Serveruhren müssen synchron laufen. Mehr als fünf Minuten alte oder mehr als eine Minute in der Zukunft liegende Meldungen werden abgelehnt. Doppelte beziehungsweise ältere Snapshots ersetzen keinen neueren Stand.

Filter: Tenant, Runtime-Scope, Anwendung, Host, Deployment-ID und Status. In den Details stehen außerdem Release, Datenbanktyp, Provider, DB-Modus, Dataset, Commit, URL, Port sowie Erstellungs-, Readiness-, Ablauf- und Beobachtungszeit. Ein bekanntes lokales Tenant-Slug wird mit Tenantname und dessen Semaphore-Projekt verknüpft. Diese Zuordnung ist keine aus dem Tasklog abgeleitete Start-Task-ID.

Fehlen Einträge bei einem **vollständigen** neuen Scan, verschwinden sie aus der aktuellen Übersicht. Bei einem **unvollständigen** Scan bleiben nicht erneut lesbare Einträge mit ihren letzten Metadaten erhalten und werden als unbekannt markiert. Ein abgelaufener Countdown allein entfernt nichts. Es gibt kein dauerhaftes Deployment-Archiv; gespeichert wird der letzte Zustand je Quelle, der auch einen Backend-Neustart übersteht.

## Token und Schnittstelle

Die Administration und Anzeige sind nur für Systemadmins zugänglich. Collector-Tokens werden einmal ausgegeben und nur als SHA-256-Hash gespeichert. Ein Token darf ausschließlich `POST /api/monitoring/report` für seine eigene Quelle verwenden, weder Daten lesen noch Tasks starten oder Konfiguration ändern. Token-Erneuerung sperrt den alten Token sofort; der neue muss auf dem Zielhost hinterlegt werden. Entfernen einer Quelle widerruft ihren Token und entfernt deren gespeicherten Snapshot, lässt die Deployments bestehen.

Der Report-Endpunkt nutzt ausschließlich `Authorization: Bearer …`, keine Sitzungscookies. Nur dieser Maschinen-Endpunkt ist von der Session-CSRF-Prüfung ausgenommen. Normale Administrationsänderungen benötigen weiterhin Anmeldung und CSRF-Token. Unbekannte Reportfelder, URL-Zugangsdaten, Queryparameter, doppelte IDs und widersprüchliche Containerzahlen werden abgewiesen. Grenzen: 2 MB und 1.000 Deployments pro Quelle. App-`.env`, Compose-Dateien, private Schlüssel, Vault-Secrets und Taskausgaben werden vom Collector nicht gelesen oder übertragen.

## Abnahmetest auf einem Testhost

1. Quelle anlegen, Exporter als lokalen Einmallauf und danach Sender mit `--once` unter dem Dienstkonto ausführen. Vollständige aktuelle Meldung und richtigen Hostnamen prüfen.
2. Ein Deployment direkt in Semaphore mit kurzer TTL starten: ohne Portal-TaskRun muss es erscheinen. Tenant, Anwendung, Scope, Dataset, URL und Port mit den Lifecycle-Dateien vergleichen.
3. Ablaufzeit und Countdown gegen `status.env` prüfen. Während der Vorbereitung darf keine erfundene Restlaufzeit erscheinen.
4. Beim natürlichen Ablauf zunächst `TTL abgelaufen` beziehungsweise `Cleanup ausstehend`, nach erfolgreichem Cleanup und vollständigem Scan keinen aktuellen Eintrag mehr erwarten.
5. Nur den Exporter für mehr als 90 Sekunden anhalten, Sender weiterlaufen lassen: alte Datei wird nicht als frischer Status gemeldet. Anzeige wird unbekannt. Nach Wiederanlauf müssen neue Metadaten erscheinen. Ebenso einen Ausfall nur des Senders prüfen.
6. Auf einem isolierten Testhost Containerzustände `starting`, `unhealthy` oder gestoppt prüfen. Keine fremden produktiven Container dafür verändern.
7. Fehlenden Root oder nicht lesbare Metadaten mit separater Testquelle prüfen: kein vollständiger leerer Scan, bestehende Einträge bleiben als letzter bekannter Stand erhalten.
8. Token erneuern: alter Token erhält 401, neuer Token funktioniert. Operator darf Monitoring weder lesen noch Quellen verwalten.
9. Unter dem Dienstkonto muss Lesen der Statusdatei funktionieren; Ändern/Ersetzen der Datei, Lesen einer fremden privaten App-Datei sowie Docker-/sudo-Zugriff müssen scheitern. Keine fremden Produktionsdateien dafür verändern. Gruppen und ACLs mitprüfen; die Ablehnung durch das Python-Programm allein belegt keine Betriebssystem-Isolation.
10. Exporter-Dienst mit der Betriebssystem-Konfiguration auf fehlenden IPv4-/IPv6-Netzwerkzugriff prüfen; der lokale Unix-Socket zu Docker muss weiter funktionieren. Dienstkonto, schreibbare Pfade und Ressourcenlimits des Senderdienstes kontrollieren. Diese Prüfungen sind auf CAYO noch offen.

Die automatisierten Sicherheitstests `test_monitoring_isolation.py` prüfen auch einen echten unprivilegierten Senderprozess gegen die API und Linux-Dateirechte. Die Tests, die root zum anschließenden Privilegienentzug benötigen, nur als root in einem isolierten Testcontainer **ohne Host-Docker-Socket und mit schreibgeschützten Quellen** ausführen; bei unprivilegiertem Testlauf sind diese Fälle ausdrücklich übersprungen. Kein Test erfordert root auf dem Deployment-Zielhost.

Implementierungsgrundlagen: [Docker-Containerliste](https://docs.docker.com/reference/cli/docker/container/ls/), [Docker-Berechtigungen](https://docs.docker.com/engine/security/), [Python urllib.request](https://docs.python.org/3/library/urllib.request.html) und [systemd: Dienstrechte und Credentials](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html). Der fachliche Metadatenvertrag stammt aus den lokal geprüften Playbooks `write-deployment-state.yml`, `deploy-program.yml` und dem bestehenden TTL-Cleanup des Semaphore-Stacks.
