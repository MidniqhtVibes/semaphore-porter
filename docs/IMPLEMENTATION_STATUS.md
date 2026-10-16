# Implementierungs- und Abnahmestatus

## SIT-Marke und Website-Symbole vom 16.10.2026

SIT Hell und SIT Dunkel zeigen die vom Betreiber bereitgestellte transparente weiße PNG-Marke in Navigation und Anmeldung. Die Datei wird bytegenau unverändert lokal ausgeliefert. GitHub Black bleibt neutral. Unter **Designs → Website-Symbol** lassen sich Portal-Tor, Mandanten-Verbund und SP-Monogramm unabhängig vom Farbschema auswählen; die Auswahl bleibt im Browser erhalten.

Enthalten sind SVG- und ICO-Favicons, Touch-Icons sowie 192-/512-Pixel-App-Symbole mit drei Manifesten für Edge-/Windows-App-Verknüpfungen. Die Windows-App-Installation ist eine Benutzeraktion; es wurde keine App auf dem Rechner installiert oder angeheftet.

Prüfung: **26 Frontend-Tests bestanden**, TypeScript/Vite- und Docker-Build erfolgreich. Logoanzeige, mobile Darstellung, Anmeldung und alle drei Manifest-Wechsel wurden in Edge mit Testdaten geprüft; keine CSP-Verstöße und keine horizontalen Überläufe. Details zu Symbolwahl und Taskleiste stehen in [DESIGNS.md](DESIGNS.md).

## Designauswahl vom 16.10.2026

Administration und Benutzerportal enthalten den Menüpunkt **Designs**. GitHub Black bleibt die Voreinstellung; zusätzlich sind SIT Hell und SIT Dunkel nach der bereitgestellten Richtlinie mit lokal ausgelieferter Sora-Schrift wählbar. Die browserlokale Auswahl gilt auch auf der Anmeldeseite. Eigene Varianten lassen sich über ein versioniertes JSON-Format mit Vorlage, Schema, Kontrastprüfung sowie Import/Export verwenden. Details und Betriebsgrenzen stehen in [DESIGNS.md](DESIGNS.md).

Prüfung: **23 Frontend-Tests bestanden**, TypeScript/Vite- und Docker-Build erfolgreich. Beide SIT-Varianten, mobile Darstellung und die helle Anmeldung wurden in Edge mit Testdaten visuell geprüft; keine horizontale Überbreite und keine CSP-Verstöße. Backend und Datenmodell wurden für die Designauswahl nicht geändert.

Das aktualisierte Frontend läuft im lokalen Stack auf Port 18092. Design-Seite, JSON-Vorlage, Schema und lokale Schrift antworten erfolgreich; alle Dienste sind gesund. Die bereitgestellte PDF und die daraus erzeugten temporären Prüfbilder wurden nach der Umsetzung wie gewünscht entfernt.

## Erweiterung vom 16.10.2026

Schritt 3 des Tenant-Wizards unterstützt mehrere Anwendungen, Datenbankprovider und Testdatensätze einschließlich „Alle auswählen“ und separater Vorgaben. Die Freigabelisten werden im Tenant gespeichert, schränken die Surveys der Projektkopie ein und begrenzen die Initial-Policies im Portal. Ansible erhält weiterhin einzelne Werte je Task-Ausführung. Die Auswahl startet keine Deployments oder Datenimporte; die Kompatibilität der Kombinationen prüft der Stack.

Besuchte Wizard-Schritte und der gespeicherte Fortschritt bleiben beim Zurückgehen erhalten. Änderungen verwerfen die angezeigte Validierung; der Weg zurück zur Erstellung prüft den aktuellen Entwurf neu. Außerdem ist ein React-Hook-Fehler beim Laden des Policy-Editors korrigiert. Die Berechtigungsmatrix enthält eine Erläuterung; Details und aktuelle Grenzen der Benutzerverwaltung stehen in [PERMISSIONS.md](PERMISSIONS.md).

Lokale Prüfung: **45 Backend-Tests und 8 Frontend-Tests bestanden**, TypeScript/Vite-Build und beide Docker-Builds erfolgreich. Die additive Alembic-Migration `20261016_0002` wurde im vorhandenen lokalen PostgreSQL-Stack erfolgreich angewendet. Alle drei Dienste sind gesund; Webseite auf Port 18092 antwortet mit HTTP 200 und `/api/health` mit `status: ok`. Die Semaphore-Integration wurde automatisiert mit simulierten API-Antworten geprüft; es wurde kein echtes Deployment gestartet.

## Ausbau der Projektverwaltung

Die direkte Verwaltung tatsächlicher Semaphore-Projekte ist ergänzt: Erstellen, Umbenennen, bestätigtes Remote-Löschen, Bearbeiten/Hinzufügen von Variablengruppen, Repositories, Inventories, Templates und Zugangsdaten sowie Duplizieren über den reparierten Tenant-Wizard. `tenant_slug` und `runtime_scope_id` werden gemeinsam in `Semaphore-Defaults` gepflegt und nicht als Survey-Variablen erzeugt. Details, Ablauf und Betriebsgrenzen stehen in [PROJECT_MANAGEMENT.md](PROJECT_MANAGEMENT.md).

Zusätzlich korrigiert: Entwurfswiederaufnahme, Vorlagenwechsel, vollständig leere Gruppenauswahl, initiale Policies für den aktuellen Stack, Statusaktualisierung der Tasklisten, API-seitiger Passwortwechselzwang, Sitzungswiderruf nach Passwortreset und Bedienung von Gruppenmitgliedschaften/Zugriffsentzug.

Lokale Prüfung am 15.10.2026: **39 Backend-Tests und 7 Frontend-Tests bestanden**, TypeScript/Vite-Produktionsbuild erfolgreich, `npm audit` mit **0 bekannten Schwachstellen**. Backend-Prüfung mit SQLite und simulierten Semaphore-Antworten unter WSL; diese Ergebnisse ersetzen weder den PostgreSQL-/Compose-Smoke-Test noch die Live-Abnahme. Frontend-Build und CI verwenden npm 11.6.2; Router, Vite und Vitest wurden mit aktualisierter Lockdatei auf korrigierte Versionen angehoben.

## Implementiert

- Docker-Architektur mit React/Nginx, FastAPI und PostgreSQL
- Datenmodell und initiale Alembic-Migration
- Authentifizierung, Rollen, Gruppen, Tenant- und Task-Berechtigungen
- Semaphore-Verbindung, Backup-Katalog und Restore-basierter Wizard
- idempotente Creation Jobs und Wiederanlauf nach unklarem Restore
- Survey-Synchronisierung und serverseitige Policy Engine
- Benutzerportal, Task-Start, Status, Live-Logs, Stop und Historie
- Administration für Tenants, Benutzer, Gruppen, Vorlagen, Presets, Runs und Audit
- automatisierte Backend-/Frontend-Tests und produktionsnaher Compose-Smoke-Test vor der Image-Veröffentlichung
- reproduzierbarer Frontend-Build und testabhängiger Docker-Image-Build
- Veröffentlichung von Backend und Frontend als GHCR-Packages mit Release- und Commit-Tags
- produktive Pull-only-Compose-Datei ohne lokale App-Builds, mit getrennten internen Netzen und optional integriertem Caddy-TLS-Gateway

## Noch vor Produktivfreigabe abzunehmen

Ein Live-End-to-End-Test gegen die konkrete Firmeninstanz von Semaphore ist ohne deren URL und Service-Token nicht Bestandteil des lokalen Tests. Vor Produktivfreigabe sind deshalb mindestens folgende Punkte in einer Testumgebung zu bestätigen:

- Unternehmens-CA, DNS und optionaler Proxy aus dem Backend-Container
- Rechteumfang des Service-Tokens
- reale Backup-Struktur der verwendeten Projektvorlage
- Restore, exakte Projekt-ID-Zuordnung und Template-Synchronisierung
- Task-Start mit den realen Survey-Typen sowie Live-Ausgabe und Stop
- öffentlicher DNS-/ACME-Durchlauf beziehungsweise Einbindung in den vorhandenen Host-Reverse-Proxy, Secure-Cookie und erlaubte Hostnamen
- Datenbank-Backup und Wiederherstellung zusammen mit demselben Fernet-Key
- erfolgreicher erneuter Lauf beider GitHub-Workflows nach dem Push dieser Änderungen und Pull der veröffentlichten Images auf dem Zielserver

Das Portal schreibt weder in GitLab noch in Vault und kopiert keine privaten Schlüssel. Solche Integrationen benötigen einen eigenen, explizit autorisierten Ausbau.
