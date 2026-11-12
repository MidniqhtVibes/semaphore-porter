## Zusammengehöriger Betriebsstand

Frontend und Backend müssen zum selben freigegebenen Stand gehören. Veränderliche Tags wie `latest` allein sind kein eindeutiger Versionsnachweis; nummerierten Tag beziehungsweise Image-Digest und den zugehörigen Quellstand festhalten.

Die tatsächliche Server-Compose und ihre Umgebungswerte werden nach dem lokalen Betriebskonzept verwaltet. Beispiele für andere Installationen müssen vor einer Übernahme mit den vorhandenen Netzen, Namen und Ports abgeglichen werden.

## Datensicherung

Die Datenbank enthält Benutzer, Freigaben, Profile, Konfigurationen und verschlüsselte Integrationszugänge. Den zugehörigen `PORTAL_FERNET_KEY` geschützt mit sichern. Ohne den passenden Schlüssel sind verschlüsselte Werte nach einer Wiederherstellung nicht nutzbar.

Auch den Anwendungsschlüssel und die erforderliche Betriebskonfiguration nach dem vorgesehenen Sicherungskonzept schützen. Bei aktiviertem Docker-Agenten dessen Journal und erforderliche Konfiguration berücksichtigen.

## Update und Prüfung

1. Ausgangsstand, Sicherung und geeigneten Rückweg dokumentieren.
2. Zusammengehörige Images bereitstellen und nur den vorgesehenen Stack aktualisieren.
3. Datenbankmigrationen beim Backend-Start und Dienstzustände kontrollieren.
4. Anmeldung, Rechte und einen vollständigen Tenant-/Taskablauf prüfen.
5. Version und Ergebnisse der Abnahme festhalten.

Eine ältere Anwendungsversion passt nach einer Schemaänderung nicht automatisch zur migrierten Datenbank. Wiederherstellung und Rückweg benötigen deshalb eine eigene Prüfung in einer freigegebenen Testumgebung.

Eine lesende Übersicht des passenden Compose-Projekts kann im vorgesehenen Arbeitsverzeichnis beispielsweise so erfolgen:

```bash
docker compose ps
```

Bei einer abweichenden Compose-Datei deren vorgesehenen Dateinamen angeben. Der Befehl zeigt den Zustand; er führt kein Update und keine Bereinigung aus.

## Inhaltliche Pflege der Hilfe

Die Artikel werden als Markdown im Anwendungspaket gepflegt. Der angezeigte Inhaltsstand bezeichnet den redaktionellen Stand. Er ersetzt weder einen Nachweis der tatsächlich laufenden Images noch eine Betriebsabnahme Ihrer Umgebung.
