# CODEX GOAL: Semaphore Tenant Portal

## 1. Auftrag und Endziel

Analysiere das bestehende Repository:

https://github.com/MidniqhtVibes/semaphore-porter.git

Dieses Repository enthält aktuell einen Windows-basierten Semaphore Tenant Configurator mit C#/WPF sowie ältere PowerShell-Versionen.

Entwickle daraus eine vollständige, moderne, Docker-basierte Webplattform mit dem Namen:

**Semaphore Tenant Portal**

Die Anwendung soll eine zentrale Verwaltungs- und Bedienoberfläche für Semaphore-Projekte, Mandanten, Anwendungen und automatisierte Testdeployments werden.

Das bisherige Projekt soll konzeptionell weiterentwickelt werden. Es ist ausdrücklich **NICHT** das Ziel, die vorhandene WPF-Oberfläche lediglich in HTML umzuschreiben.

Die neue Webplattform soll zwei strikt getrennte Funktionsbereiche besitzen:

1. Adminportal zur Konfiguration und Verwaltung.
2. Benutzerportal zum kontrollierten Starten und Überwachen freigegebener Semaphore-Tasks.

Der gesamte Stack muss mittels Docker Compose auf einem Linux-Server ausführbar sein.

Arbeite eigenständig und implementiere das Ziel möglichst vollständig. Verwende keine Platzhalter-Funktionen, die lediglich eine zukünftige Implementierung vortäuschen.

---

## 2. Verbindliche Architekturentscheidungen

Folgende Entscheidungen sind bereits getroffen und nicht erneut zu diskutieren:

- Ein Tenant entspricht genau einem eigenen Semaphore-Projekt.
- Die Benutzerverwaltung erfolgt zunächst lokal im Portal.
- Das initiale Deployment eines neuen Tenants erfolgt **NICHT automatisch**.
- Semaphore bleibt die eigentliche Automatisierungs-Engine.
- Normale Portalbenutzer erhalten keinen direkten Semaphore-API-Token.
- Die gesamte Plattform läuft in Docker.
- Das Adminportal und das Benutzerportal verwenden dasselbe einheitliche Designsystem.
- Die Anwendung wird in deutscher Sprache entwickelt.
- Die bisherige Windows-Anwendung wird als Legacy-Code erhalten, aber nicht mehr als primäre Anwendung weiterentwickelt.

### Vorgeschlagener Technologiestack

Frontend:

- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui oder vergleichbare hochwertige React-Komponenten
- TanStack Query
- React Hook Form
- Zod
- React Router

Backend:

- Python
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic
- PostgreSQL 17

Deployment:

- Docker
- Docker Compose
- Interne Docker-Netzwerke
- Nginx als Frontend-Webserver und API-Reverse-Proxy
- Externe HTTPS-Terminierung über einen vorhandenen Reverse Proxy

Wähle stabile, zueinander kompatible Versionen und dokumentiere die tatsächlich verwendeten Versionen.

Es soll keine Abhängigkeit zu einer lokal installierten Python-, Node.js- oder .NET-Umgebung für den regulären Docker-Betrieb bestehen.

---

## 3. Repository-Analyse und Migration

Untersuche vor der Implementierung den tatsächlichen Inhalt des Repositories.

Prüfe insbesondere:

- Vorhandenen C#/WPF-Konfigurator
- Semaphore-API-Integration
- Projektbackup- und Restore-Logik
- Behandlung von Projektlisten
- Tenant-Erstellung
- Variablengruppen
- Presets
- Task Templates
- Survey-Variablen
- Proxy-Verhalten
- Sicherheitsmaßnahmen
- Bestehende Tests
- README und Dokumentation

Identifiziere, welche fachlichen Konzepte weiterverwendet werden können.

Der vorhandene Quellcode soll nicht gelöscht werden.

Verschiebe Legacy-Code bei Bedarf in einen nachvollziehbaren Bereich wie:

`legacy/windows-configurator/`

Erstelle die neue Webplattform in einer klar strukturierten Projektarchitektur.

Dokumentiere den Übergang von der bisherigen Anwendung zur neuen Webplattform.

---

## 4. Grundlegendes Mandantenmodell

Jeder Tenant besitzt genau ein eigenes Semaphore-Projekt.

Ein Tenant muss mindestens folgende Eigenschaften besitzen:

- Interne Tenant-ID
- Technische Kennung `tenant_slug`
- Anzeigename
- Beschreibung
- Semaphore-Projekt-ID
- Semaphore-Projektname
- Anwendung beziehungsweise Anwendungskatalog-Zuordnung
- Aktivierungsstatus
- Erstellungsdatum
- Änderungsdatum
- Zugeordnete Benutzer
- Zugeordnete Benutzergruppen
- Freigegebene Task Templates
- Zugehörige Task Policies

Verwende die Semaphore-Projekt-ID als technische Referenz.

Berechtigungen dürfen niemals ausschließlich über den Projektnamen aufgelöst werden.

Die Umbenennung eines Semaphore-Projekts darf keine Berechtigungen zerstören.

Ein Tenant darf erst für normale Benutzer freigegeben werden, wenn die dafür erforderliche Konfiguration abgeschlossen ist.

---

## 5. Adminportal

Entwickle einen vollständigen Administrationsbereich mit eigener Navigation.

Mindestens folgende Seiten sind erforderlich:

### 5.1 Admin Dashboard

Zeige:

- Anzahl verwalteter Tenants
- Anzahl aktiver Benutzer
- Anzahl zugeordneter Semaphore-Projekte
- Laufende Tasks
- Fehlgeschlagene Tasks
- Letzte administrative Änderungen
- Verbindungsstatus zu Semaphore
- Projekte mit unvollständiger Konfiguration

Alle Kennzahlen müssen aus tatsächlichen Daten stammen.

### 5.2 Tenant erstellen

Implementiere einen echten mehrstufigen Wizard.

Der Wizard soll folgende Schritte besitzen:

1. Projektvorlage auswählen.
2. Tenant konfigurieren.
3. Anwendung und Testdaten auswählen.
4. Task Templates und Ressourcen auswählen.
5. Variablengruppen und Presets konfigurieren.
6. Benutzer und Berechtigungen zuweisen.
7. Konfiguration validieren.
8. Neues Semaphore-Projekt erstellen.

Der Admin muss zwischen den Schritten navigieren können, ohne bereits eingegebene Daten zu verlieren.

Speichere unfertige Konfigurationen als Entwurf, damit sie später fortgesetzt werden können.

### 5.3 Vorlagen auswählen

Unterstütze:

- Bestehende Semaphore-Projekte
- Hochgeladene Projektbackup-JSON-Dateien
- Bereits gespeicherte Portal-Projektvorlagen

Verwende die funktionierende Semaphore-Backup-/Restore-Logik als fachliche Grundlage.

Das originale Semaphore-Projekt darf beim Duplizieren nicht verändert werden.

### 5.4 Tenants verwalten

Implementiere eine Tabellen- und Detailansicht aller Tenants.

Funktionen:

- Tenant anzeigen
- Tenant umbenennen
- Beschreibung ändern
- Zugeordnete Benutzer verwalten
- Berechtigungen verändern
- Task Policies bearbeiten
- Freigegebene Tasks ändern
- Tenant deaktivieren
- Konfiguration exportieren
- Semaphore-Verbindung prüfen

Löschen muss ausdrücklich bestätigt werden.

Ein gelöschter Portal-Tenant darf niemals versehentlich andere Semaphore-Projekte oder Docker-Ressourcen entfernen.

### 5.5 Anwendungskatalog

Unterstütze vorhandene Anwendungen aus dem Semaphore-Projektbackup.

Lese aus den Survey-Feldern insbesondere:

- `application_id`
- `database_type`
- `dataset_id`
- `ttl_minutes`

Bereite zusätzlich eine modulare Anbindung an den generalisierten GitLab-Programmkatalog vor.

Die Anwendungskonfiguration soll später aus vorhandenen Programmdefinitionen und Testdatenkatalogen gelesen werden können.

Erfinde keine vermeintlich vorhandenen GitLab-Dateien oder Programmdefinitionen.

Wenn der tatsächliche Katalog nicht verfügbar ist, verwende zunächst ausschließlich die vorhandenen Semaphore-Survey-Werte.

### 5.6 Vorlagen und Presets

Erstelle eine zentrale Preset-Verwaltung.

Unterstütze wiederverwendbare Variablengruppen für:

- Deployment
- Container Registry
- PostgreSQL
- MariaDB
- MySQL
- Vault
- SMTP
- Anwendungsspezifische Einstellungen

Admins sollen eigene Presets erstellen, bearbeiten, versionieren und wiederverwenden können.

Presets dürfen keine Klartext-Zugangsdaten enthalten.

### 5.7 Benutzerverwaltung

Administratoren müssen Benutzer erstellen und verwalten können.

Funktionen:

- Benutzer erstellen
- Benutzer deaktivieren
- Passwort zurücksetzen
- Rolle vergeben
- Projektzugriffe vergeben
- Benutzergruppen verwalten
- Task-Berechtigungen vergeben
- Zugriffe entziehen

Ein deaktivierter Benutzer darf keine neuen Tasks ausführen.

### 5.8 Berechtigungsverwaltung

Entwickle eine zentrale Berechtigungsmatrix.

Admins sollen direkt festlegen können:

- Welcher Benutzer welchen Tenant sehen darf.
- Welcher Benutzer welche Tasks sehen darf.
- Welcher Benutzer welche Tasks starten darf.
- Welche Variablen verändert werden dürfen.
- Welche Variablen fest vorgegeben sind.
- Welche Werte für einzelne Variablen erlaubt sind.

### 5.9 Task-Überwachung

Zeige die aktuellen und historischen Task-Ausführungen.

Administratoren können alle vom Portal verwalteten Task-Ausführungen sehen.

### 5.10 Audit-Log

Protokolliere wichtige Aktionen:

- Anmeldung
- Fehlgeschlagene Anmeldung
- Tenant erstellt
- Projekt importiert
- Berechtigung geändert
- Benutzer erstellt/deaktiviert
- Task gestartet
- Task abgebrochen
- Task Policy verändert

Speichere keine Tokens oder geheimen Variablenwerte im Audit-Log.

---

## 6. Benutzerportal

Entwickle ein separates Benutzerportal.

Normale Benutzer dürfen ausschließlich ihre freigegebenen Ressourcen sehen.

Folgende Seiten sind erforderlich:

1. Dashboard
2. Meine Projekte
3. Projektübersicht
4. Task starten
5. Laufende Tasks
6. Task-Historie
7. Mein Konto

Das Benutzerportal darf keine administrativen API-Endpunkte verwenden können.

Admins dürfen optional in die normale Benutzeransicht wechseln.

---

## 7. Zentrale Funktion: Mandantenspezifische Task Policies

Dieser Teil ist besonders wichtig.

Der Administrator soll für jeden Tenant und jedes freigegebene Task Template eine eigene Policy definieren können.

Die Policy legt fest, welche Survey-Variablen ein normaler Benutzer verändern darf.

Unterstütze mindestens diese Policy-Typen:

### Fixed

Die Variable wird fest vorgegeben. Der Benutzer darf sie nicht ändern.

Beispiel: `tenant_slug = kunde-a`

### Enum

Der Benutzer darf aus einer vorgegebenen Whitelist auswählen.

Beispiel `dataset_id`: `none`, `smoke-v1`, `public-v1`.

### Integer Range

Der Benutzer darf eine Zahl innerhalb eines erlaubten Bereichs wählen.

Beispiel `ttl_minutes`: Minimum 15, Maximum 180, Standardwert 60.

### String

Ein freigegebenes Textfeld mit serverseitiger Validierung.

### Boolean

Ein freigegebenes Ja/Nein-Feld.

### Hidden

Ein Wert wird automatisch übertragen, aber nicht im Benutzerformular angezeigt.

---

## 8. Konkretes Beispiel einer Tenant Policy

Tenant: `kunde-a`

Semaphore-Projekt: `AzubiOrga – Kunde A`

Freigegebenes Task Template: `deploy-timed-demo`

Die Konfiguration soll ungefähr folgende fachliche Bedeutung besitzen:

```yaml
tenant_slug:
  type: fixed
  value: kunde-a

application_id:
  type: enum
  allowed_values:
    - azubiorga

database_type:
  type: enum
  allowed_values:
    - postgresql

dataset_id:
  type: enum
  allowed_values:
    - none
    - smoke-v1
    - public-v1

ttl_minutes:
  type: integer_range
  minimum: 15
  maximum: 180
  default: 60

host_port:
  type: fixed
  value: 0
```

Der Benutzer darf dadurch beispielsweise den Testdatensatz und die Laufzeit auswählen.

Er darf aber weder die Tenant-ID noch die Anwendung auf einen anderen Mandanten umstellen.

Die Policy muss vollständig serverseitig durchgesetzt werden.

---

## 9. Task-Ausführung über Semaphore

Beim Start eines Tasks muss der folgende Ablauf stattfinden:

1. Benutzer authentifizieren.
2. Benutzerstatus prüfen.
3. Tenant-Zugriff prüfen.
4. Task-Berechtigung prüfen.
5. Task Policy laden.
6. Übermittelte Variablen validieren.
7. Nicht freigegebene Variablen ablehnen.
8. Feste und versteckte Variablen serverseitig ergänzen.
9. Erlaubte Survey-Daten erzeugen.
10. Semaphore-Task über die API starten.
11. Semaphore-Task-ID speichern.
12. Ausführenden Portalbenutzer protokollieren.
13. Task-Status und Ausgabe verfügbar machen.

Das Backend darf nicht einfach alle vom Browser übermittelten Variablen ungeprüft an Semaphore durchreichen.

Verwende die dokumentierte Task-Ausführungs-API der tatsächlich angebundenen Semaphore-Version.

Wenn ein API-Endpoint oder Payload-Format nicht eindeutig ist, prüfe die vorhandene Implementierung oder die passende API-Dokumentation, statt einen Endpoint zu erfinden.

---

## 10. Task-Formulare

Erzeuge Task-Formulare dynamisch aus der Kombination von:

- Semaphore-Survey
- Tenant-Konfiguration
- Task Policy

Die Benutzeroberfläche soll abhängig vom Variablentyp automatisch passende Steuerelemente anzeigen.

Beispiele:

- Enum → Dropdown
- Integer Range → Zahlenfeld mit Grenzen
- Boolean → Checkbox
- String → Textfeld
- Fixed/Hidden → Kein veränderbares Benutzerfeld

Zeige zu jedem Feld einen verständlichen Hilfetext.

Validiere die Eingaben sowohl im Frontend als auch im Backend.

Die Backend-Validierung ist verbindlich.

---

## 11. Benutzergruppen und Rollen

Implementiere mindestens folgende Rollen:

- System Admin
- Tenant Admin
- Operator
- Viewer

Unterstütze direkte Benutzerfreigaben und gruppenbasierte Freigaben.

Eine Berechtigung muss sich mindestens auf folgende Beziehungen beziehen können:

Benutzer/Gruppe → Tenant → Task Template → erlaubte Aktionen

Implementiere serverseitige Autorisierung für jeden relevanten API-Endpunkt.

Eine manipulierte Projekt-ID, Task-ID oder Tenant-ID darf niemals Zugriff auf fremde Ressourcen ermöglichen.

---

## 12. Authentifizierung und Sicherheit

Implementiere lokale Benutzerkonten.

Anforderungen:

- Sichere Passwort-Hashes
- Sichere Sitzungen
- HttpOnly-Cookies
- CSRF-Schutz für zustandsändernde Cookie-authentifizierte Requests
- Login-Rate-Limiting
- Benutzerdeaktivierung
- Passwortänderung
- Geschützte Admin-Routen
- Serverseitige Berechtigungsprüfung
- Keine Tokens im Frontend
- Keine Zugangsdaten in Logs
- Keine Secrets in Presets
- Keine deaktivierte TLS-Prüfung

Der Semaphore-Service-Token wird ausschließlich im Backend verwaltet.

Das Portal darf keine beliebigen Semaphore-API-Aufrufe von normalen Benutzern durchreichen.

Besonders wichtig:

Eine Änderung der Browser-Requests darf weder zusätzliche Task-Variablen noch andere Task Templates oder fremde Projekte freischalten.

---

## 13. Semaphore-Integration

Implementiere einen eigenständigen Semaphore-API-Client im Backend.

Funktionen:

- Verbindung testen
- Projektliste abrufen
- Projektbackup abrufen
- Projekt wiederherstellen
- Task Templates lesen
- Tasks starten
- Task-Status lesen
- Task-Ausgaben lesen
- Task-Historie abrufen, soweit die angebundene API sie bereitstellt

Beachte die bisherigen Erfahrungen mit der Windows-Anwendung:

- Projektlisten können unterschiedlich strukturiert zurückkommen.
- JSON-Arrays müssen korrekt verarbeitet werden.
- Reverse-Proxy-Weiterleitungen können auftreten.
- Bearer-Tokens dürfen nicht an fremde Hosts weitergegeben werden.
- POST-Anfragen dürfen bei unklaren Netzwerkfehlern nicht blind wiederholt werden.
- HTTP-Fehler müssen verständlich diagnostiziert werden.

Unterstütze eine konfigurierbare Firmenproxy-Anbindung, falls erforderlich.

Sichere den Semaphore-Service-Token serverseitig.

---

## 14. Sichere Tenant-Erstellung

Der Tenant-Wizard muss eine Importvorschau erzeugen.

Vor dem tatsächlichen Restore müssen alle Einstellungen validiert werden.

Insbesondere:

- Projektname
- Tenant-ID
- Task Templates
- Variablengruppen
- Referenzen
- Repository
- Inventory
- Survey-Werte
- Task Policies
- Benutzerberechtigungen

Zeitpläne und Webhooks sollen bei neuen Tenant-Projekten standardmäßig nicht übernommen werden.

Der Administrator kann die Projektanlage ausdrücklich bestätigen.

Nach erfolgreichem Restore wird die neue Semaphore-Projekt-ID in PostgreSQL registriert.

Behandle teilweise fehlgeschlagene Vorgänge sicher.

Beispiel: Semaphore erstellt das Projekt erfolgreich, aber das Speichern in PostgreSQL schlägt fehl.

In diesem Fall darf ein erneuter Klick nicht versehentlich ein weiteres Projekt erzeugen.

Implementiere eine nachvollziehbare Zustandsverwaltung für den Erstellungsprozess.

---

## 15. Live-Task-Ausgabe

Das Benutzerportal soll laufende Semaphore-Tasks anzeigen.

Mindestens erforderlich:

- Task-ID
- Tenant
- Task Template
- Ausführender Benutzer
- Startzeit
- Status
- Laufzeit
- Task-Ausgabe
- Abschlussstatus

Nutze eine geeignete Echtzeitübertragung, beispielsweise Server-Sent Events.

Die Berechtigungen müssen vor dem Zugriff auf Status und Logs geprüft werden.

Ein Benutzer darf keine Logs eines fremden Projekts abrufen.

Erfinde keine erfolgreiche Task-Ausführung, wenn Semaphore keine entsprechende Bestätigung zurückliefert.

---

## 16. Webdesign

Entwickle eine hochwertige, professionelle Dark-Mode-Oberfläche.

Orientierung: GitHub Dark / GitHub Black.

Farbpalette:

| Element | Farbe |
|---|---|
| Background | `#0D1117` |
| Surface | `#161B22` |
| Surface Alt | `#21262D` |
| Border | `#30363D` |
| Primary Text | `#E6EDF3` |
| Muted Text | `#9DA7B3` |
| Accent | `#2F81F7` |
| Success | `#3FB950` |
| Warning | `#D29922` |

Die Oberfläche soll vollständig dunkel sein.

Vermeide weiße Formulare, weiße Dropdown-Menüs oder ungestylte Browser-Standardkomponenten.

Anforderungen:

- Konsistentes Designsystem
- Wiederverwendbare Komponenten
- Gut lesbare Schriftgrößen
- Großzügige Abstände
- Responsives Layout
- Klare Navigation
- Moderne Tabellen
- Hochwertige Dialogfenster
- Einheitliche Buttons
- Icons
- Tooltips
- Kontextbezogene Hilfefunktionen
- Ladezustände
- Leere Zustände
- Verständliche Fehlermeldungen
- Bestätigungsdialoge bei kritischen Aktionen

Benutze für Adminportal und Benutzerportal dasselbe Designsystem.

Der Tenant-Wizard soll als nachvollziehbarer Schritt-für-Schritt-Prozess umgesetzt werden.

---

## 17. Docker-Deployment

Erstelle eine vollständige Docker-Compose-Konfiguration.

Mindestens folgende Dienste:

- frontend
- backend
- postgres

PostgreSQL darf keinen öffentlich freigegebenen Port erhalten.

Backend und PostgreSQL kommunizieren über ein internes Docker-Netzwerk.

Verwende persistente Volumes für PostgreSQL.

Erstelle:

- Dockerfiles
- `docker-compose.yml`
- `.env.example`
- `.gitignore`
- Healthchecks
- Datenbankmigrationen
- Initialen Admin-Bootstrap
- README mit Installationsanleitung

Die Anwendung soll mit einem dokumentierten Ablauf gestartet werden können.

Beispiel:

```bash
docker compose up -d --build
```

Verwende sichere Konfigurationsstandards.

Speichere keine produktiven Tokens oder Passwörter im Repository.

---

## 18. Datenbankmodell

Entwickle ein nachvollziehbares relationales Datenmodell.

Berücksichtige mindestens:

- users
- roles
- groups
- group_memberships
- tenants
- tenant_memberships
- semaphore_projects
- task_templates
- task_permissions
- task_policies
- variable_rules
- presets
- project_templates
- task_runs
- audit_events
- creation_jobs

Nutze Alembic-Migrationen.

Verwende eindeutige Constraints und Foreign Keys, wo fachlich notwendig.

Berücksichtige Projektumbenennungen, deaktivierte Benutzer und gelöschte Ressourcen.

---

## 19. Tests

Implementiere automatisierte Tests für die kritischen Geschäftsprozesse.

Backend:

- Authentifizierung
- Berechtigungen
- Tenant-Erstellung
- Projektzuordnung
- Policy-Validierung
- Task-Start
- Manipulierte Projekt-IDs
- Manipulierte Task-IDs
- Nicht freigegebene Variablen
- Fehlerhafte Semaphore-Antworten
- Wiederaufnahme fehlgeschlagener Erstellungsvorgänge

Frontend:

- Login
- Adminnavigation
- Tenant-Wizard
- Benutzerverwaltung
- Task-Formulare
- Berechtigungsanzeigen
- Lade- und Fehlerzustände

Integration:

Simuliere Semaphore über einen Testserver beziehungsweise API-Mocks.

Teste insbesondere die Projektlisten-Verarbeitung, Projektbackups und Task-Ausführung.

Die Tests dürfen keine produktiven Semaphore-Tasks auslösen.

---

## 20. Dokumentation

Erstelle eine ausführliche README auf Deutsch.

Sie soll mindestens enthalten:

- Architektur
- Voraussetzungen
- Installation
- Docker-Konfiguration
- Erster Admin
- Semaphore-Anbindung
- Projektvorlagen
- Tenant-Erstellung
- Benutzerverwaltung
- Task Policies
- Benutzerportal
- Task-Ausführung
- Sicherheit
- Backup und Restore
- Fehlerbehebung
- Aktualisierung der Plattform

Ergänze eine verständliche Architekturübersicht.

Dokumentiere außerdem die Migration vom bisherigen Windows-Konfigurator.

---

## 21. Arbeitsweise

Arbeite die Implementierung in sinnvollen Phasen ab:

**Phase 1:** Repository-Analyse, Architektur, Docker-Grundgerüst, Datenbank, Authentifizierung.

**Phase 2:** Semaphore-API, Adminportal und Tenant-Verwaltung.

**Phase 3:** Tenant-Wizard, Projektvorlagen, Anwendungskatalog und Presets.

**Phase 4:** Benutzerverwaltung, Gruppen, Rollen und Berechtigungen.

**Phase 5:** Task Policies, Task-Ausführung und Benutzerportal.

**Phase 6:** Live-Logs, Audit-Log, Integrationstests und Dokumentation.

Arbeite nach Möglichkeit selbstständig weiter, solange der Auftrag und das Repository genügend Informationen liefern.

Unterbrich nicht nach jeder einzelnen Datei, um nach Bestätigung zu fragen.

Bewahre die Funktionsfähigkeit bereits implementierter Bereiche.

Wenn eine Phase noch nicht vollständig implementiert wurde, kennzeichne sie ausdrücklich.

Behaupte keine erfolgreichen Tests, die nicht tatsächlich ausgeführt wurden.

---

## 22. Verbindliche Abnahmekriterien

Die Umsetzung ist erst abgeschlossen, wenn folgende End-to-End-Abläufe funktionieren:

1. Ein Administrator kann sich anmelden.
2. Der Administrator kann Semaphore verbinden.
3. Der Administrator kann ein bestehendes Semaphore-Projekt als Vorlage auswählen.
4. Der Administrator kann daraus einen neuen Tenant erstellen.
5. Der neue Tenant besitzt ein eigenes Semaphore-Projekt.
6. Der Administrator kann Benutzer erstellen.
7. Der Administrator kann Benutzern Zugriff auf einzelne Tenants geben.
8. Der Administrator kann einzelne Task Templates freigeben.
9. Der Administrator kann erlaubte Survey-Variablen und Werte einschränken.
10. Ein normaler Benutzer sieht nur seine freigegebenen Projekte.
11. Der Benutzer kann ausschließlich freigegebene Tasks starten.
12. Der Benutzer kann nur erlaubte Variablen verändern.
13. Das Backend weist manipulierte oder unerlaubte Eingaben zurück.
14. Semaphore erhält ausschließlich die validierten Task-Parameter.
15. Der Benutzer kann den Task-Status und erlaubte Logs sehen.
16. Der Administrator kann nachvollziehen, welcher Benutzer welchen Task gestartet hat.
17. Das gesamte Projekt ist mit Docker Compose startbar.
18. Es existieren funktionierende Tests und eine vollständige Dokumentation.

**Das Endziel ist keine Demo-Oberfläche, sondern eine tatsächlich nutzbare, nachvollziehbar abgesicherte Verwaltungsplattform für mandantenspezifische Semaphore-Deployments.**
