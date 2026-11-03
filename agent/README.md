# Semaporter Docker-Agent

Optionaler vierter Dienst zur Verwaltung bestehender Docker-Container. Das Image kann gebaut und veröffentlicht werden, bevor der Dienst eingerichtet oder gestartet wird. Ohne Agent und Aktivierung funktioniert das Portal einschließlich des Deployment-Monitorings weiter.

## Image und Tests

Vom Repository-Hauptverzeichnis:

```bash
docker build --target production -t semaporter-agent:local agent
```

Das startet keinen Container. Das Produktionsimage enthält keine Tests oder Testabhängigkeiten. Das Testtarget benötigt zusätzlich `agent/tests` und `agent/requirements-dev.txt`. Diese Dateien werden wegen der gewünschten Ignore-Regeln lokal gehalten und müssen für CI-Testpakete ausdrücklich enthalten sein.

## Laufzeit

Ein Agent je Docker-Zielhost; eine Instanz/ein Worker je Journal. Der Agent benötigt den lokalen Docker-Socket, eine nur lesbar eingebundene Policy, HTTPS-Zertifikate und eine persistente SQLite-Auftragsablage. Im Portal-Backend wird kein Docker-Socket eingebunden. Ein Docker-TCP-Listener oder Neustart des Docker-Daemons ist nicht erforderlich.

Das Image verwendet UID/GID `10001`. Socket-Gruppenrechte, Zertifikatsrechte und Journal-Verzeichnis müssen administrativ passend eingerichtet werden. Kein `privileged`, Host-PID-Namespace oder Host-Root-Mount. Docker-Socket-Zugriff bleibt trotzdem eine weitreichende Hostberechtigung.

Konkrete Compose-/Pipeline-Dateien, Serverpfade, Netze und Host-Ports werden gemäß Projektvorgabe ausschließlich im Chat abgestimmt. Der Agent lauscht im Container auf Port 8000; das veröffentlicht keinen Host-Port. Der Agent ist keine Startabhängigkeit der drei Portal-Dienste. Ein optionales Compose-Profil kann den Dienst bis zur Einrichtung ausgeschaltet lassen.

| Variable | Bedeutung |
| --- | --- |
| `AGENT_POLICY_FILE` | Policy; Standard `/etc/semaporter-agent/policy.json` |
| `AGENT_DOCKER_SOCKET` | Socket; Standard `/var/run/docker.sock` |
| `AGENT_JOURNAL_PATH` | Journal; Standard `/var/lib/semaporter-agent/operations.sqlite3` |
| `AGENT_TLS_CERT_FILE` | Pflicht: HTTPS-Zertifikatskette als PEM |
| `AGENT_TLS_KEY_FILE` | Pflicht: zugehöriger privater PEM-Schlüssel |
| `AGENT_CLIENT_CA_FILE` | Optional: Client-CA; aktiviert verpflichtendes mTLS |

## Einrichtung

1. **Einstellungen → Verbindungen → Docker-Agenten**: Verbindung hinzufügen, HTTPS-Adresse, Token und gegebenenfalls öffentliche Server-CA speichern. Agent und Integration dürfen deaktiviert bleiben.
2. Ein Token kann im Formular sicher erzeugt werden. Er wird verschlüsselt gespeichert und danach nicht zurückgegeben. **Policy-Vorlage herunterladen** liefert nur seinen SHA-256-Hash.
3. Die Vorlage administrativ prüfen und auf dem Zielhost nur lesbar einbinden. `projects` enthält exakte Compose-Projektnamen, `container_ids` alternativ vollständige Container-IDs. `allow_all` ist standardmäßig `false` und wird durch den Vorlagendownload niemals automatisch auf `true` gesetzt.
4. `credentials` enthält Token-Hashes mit maximal erlaubten Aktionen. Eine leere Aktionsliste bedeutet nur lesen. Mehrere Einträge erlauben kontrollierte Rotation. Die Policy ist nicht über die Agent-API veränderbar.
5. `protected_projects`, das Containerlabel `semaporter.management.protected=true`, erkannte Semaporter-Images und die eigene Agent-ID schützen Verwaltungskomponenten vor Aktionen.
6. Agent mit Zertifikaten, Journal und Socket-Rechten starten. **Gespeicherte Verbindung testen** prüft Anmeldung/Protokoll, noch keinen erfolgreichen Docker-Abruf. Danach gewünschten Umfang, Agent und Container-Verwaltung aktivieren.
7. Zunächst lesend prüfen. Schreibaktionen anschließend separat erlauben. Es gilt die Schnittmenge aus Portal-Freigaben, Agent-Policy, Token-Aktionen und Containerzustand. Der Portalzugriff ist zunächst Systemadministratoren vorbehalten.

## Zertifikate

Am Unix-Socket gelten Dateirechte; TLS-Zertifikate werden dort nicht ausgewertet. HTTPS sichert die Verbindung zwischen Backend und Agent. Bei `AGENT_CLIENT_CA_FILE` verlangt der Agent zusätzlich ein gültiges Client-Zertifikat. Eine dafür vorgesehene Client-CA und Zertifikate mit Client-Auth-Verwendungszweck verwenden.

Im Portal im mTLS-Bereich das Client-Zertifikat und den zugehörigen unverschlüsselten PEM-Schlüssel speichern. Der Schlüssel wird verschlüsselt abgelegt, nicht zurückgegeben und nur zum Laden des TLS-Kontexts kurz in einem privaten temporären Verzeichnis verarbeitet. Diese Dateien werden vor dem HTTP-Request entfernt.

Hostname und Zertifikatskette werden geprüft; diese Prüfung lässt sich nicht ausschalten. Keine privaten CA-Schlüssel im Portal hinterlegen. Bei TLS-terminierenden Proxys muss die gegenseitige Prüfung zum Agenten erhalten bleiben; bevorzugt direkt vom Backend zum Agenten verbinden. Zertifikate ergänzen Token-/Ressourcenprüfungen und beseitigen nicht das Risiko eines kompromittierten Agenten mit Socket-Zugriff.

## Umfang und Fehlerfälle

Containerliste mit Suche/Filter, Status und Healthchecks, Details, Compose-Gruppen, verwendete Images/Volumes/Netzwerke, begrenzte Logs und aktuelle CPU/RAM/Netzwerk-/Datenträgerzähler. Die Übersicht aktualisiert alle 15 Sekunden, Logs und Messwerte des geöffneten Containers alle fünf Sekunden; abschaltbar. Antwortgrößen, Parallelität und Laufzeiten sind begrenzt. Gestoppte Container haben unbekannte Messwerte. Netzwerk-/Datenträgerwerte sind kumulativ; keine gespeicherte Langzeithistorie.

Einzeln freigebbar: Start, Stopp, Neustart, Pause, Fortsetzen und Entfernen gestoppter/noch nicht gestarteter Container. Entfernen verwendet weder `force` noch Volume-Löschung. Konsole, beliebige Containererstellung, Compose-Bearbeitung, Image-Pull und Ressourcenbereinigung gehören nicht zu dieser ersten Ausbaustufe.

Jeder Auftrag enthält eine UUID, kurze Gültigkeit und den bestätigten Containerstand. Das persistente Journal erkennt dieselbe Kennung auch nach Neustarts wieder. Unklare/parallele Aufträge sperren den betroffenen Container. **Ereignisse → Am Agenten abgleichen** fragt nur den vorhandenen Auftrag ab und wiederholt keine Aktion. Erst nach tatsächlicher Zustandsprüfung kann ein Administrator frühestens nach zwei Minuten die manuelle Prüfung bestätigen. Ein verlorenes oder wiederhergestelltes Journal beweist nicht, dass eine Aktion nie ausgeführt wurde.

Portal-Datenbank/Fernet-Key und Agent-Journal sichern; Policy und Zertifikatsrotation administrativ verwalten. Agent-Updates dürfen das Journal nicht verwerfen. Die integrierte Demo simuliert den Agenten ohne zusätzlichen Dienst oder Socket-Zugriff und enthält das Szenario einer verlorenen Antwort nach ausgeführter Aktion.

## Protokoll und Abnahme

Agent-Protokoll v1 bietet ausschließlich feste Routen unter `/v1`: Info, Inventar, Containerdetails, Logs, Stats, Aktionen und Auftragsabgleich/-prüfung. Keine generische Weiterleitung beliebiger Docker-Pfade. Docker-API v1.41 bis v1.45 wird anhand der Engine-Version gewählt; höhere Mindestversionen werden ausdrücklich abgewiesen.

Lokale Tests verwenden Mocktransporte/ASGI und temporäre Datenbanken, ohne Docker-Socket, Listener oder Serververbindung. Vor Produktivnutzung am freigegebenen Zielhost nachweisen: Zertifikate/gegebenenfalls mTLS, Dateirechte, Scope-Grenzen, jede freigegebene Aktion an Testobjekten, Journal-Neustart, unklare Ergebnisse und unveränderte fremde Anwendungen.

Grundlagen: [Docker Engine API](https://docs.docker.com/reference/api/engine/), [Docker-Sicherheit](https://docs.docker.com/engine/security/), [HTTPX-Transporte](https://www.python-httpx.org/advanced/transports/).
