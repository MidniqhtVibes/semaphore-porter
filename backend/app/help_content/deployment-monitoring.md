## Aufbau

Das optionale Deployment-Monitoring besteht aus einer Portal-Quelle, einem lokalen Exporter und einem eingeschränkten Sender. Der Exporter erfasst die vorgesehenen Lifecycle-Metadaten und Containerzustände in einer geschützten Datei. Der Sender liest diese Datei und übermittelt einen Snapshot über HTTPS.

Der Sender benötigt weder Docker-Rechte noch sudo. Die administrative Einrichtung des Exporters und der Dateiberechtigungen bleibt eine gesonderte Hostaufgabe.

## Vorgehen

1. Unter **Deployment-Monitoring → Monitoring-Quellen und Einrichtung** pro Zielhost eine Quelle anlegen.
2. Den einmalig angezeigten Collector-Token als geschützte Datei ablegen.
3. Exporter und Sender über die vorgesehenen Downloads bereitstellen.
4. Dienstkonto, Statusablage, Berechtigungen und Dienstdateien nach dem freigegebenen Hostkonzept einrichten.
5. `SEMAPORTER_URL` und `SEMAPORTER_MONITOR_TOKEN_FILE` in der tatsächlichen Sender-Umgebung setzen.
6. Eine frische Meldung und ein konkretes Testdeployment kontrollieren.

## Aktualisierung und Ergebnis

Hostmeldungen sind im vorgesehenen Ablauf alle 15 Sekunden geplant. Die Ansicht fragt alle 10 Sekunden ab; der Countdown aktualisiert sich jede Sekunde. Nach mehr als 90 Sekunden ohne frischen Snapshot wird der Zustand als veraltet eingeordnet.

Ein erfolgreich angenommener Snapshot bestätigt zunächst die Übertragung. Tenant, Anwendung, Runtime-Scope, Containerzahl und Ablaufzeit müssen zusätzlich zum tatsächlichen Deployment passen.

## Dienstkonfiguration prüfen

Auf älteren systemd-Versionen kann der `%d`-Bezeichner für ein Credential-Verzeichnis fehlen. Dann den freigegebenen konkreten Credential-Dateipfad verwenden und die Dienstdateien mit `systemd-analyze verify` prüfen lassen. Tokenwerte bleiben außerhalb von Logs und Anleitungen.

Ein deaktiviertes Host-Monitoring verhindert keine normalen Portal-Taskstarts. Seine Aktivierung führt auch keine automatische Container-Bereinigung aus.
