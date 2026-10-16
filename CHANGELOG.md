# Änderungen

## Release-Zwischenstand – 16.10.2026

Das Repository wird ausschließlich als Web-App weitergeführt. Dieser Zwischenstand bündelt die bisherige Migration; die Abnahme gegen die konkrete Semaphore-Instanz steht noch aus.

### Web-App

- Semaphore-Projekte erstellen, bearbeiten, bestätigt löschen und über den Tenant-Wizard duplizieren.
- `tenant_slug` und `runtime_scope_id` gemeinsam in `Semaphore-Defaults` pflegen.
- Mehrere Anwendungen, Datenbankprovider und Testdatensätze pro Tenant auswählen; Freigaben und Initial-Policies übernehmen.
- Benutzer, Gruppen, Tenant-/Task-Rechte sowie Task-Start, Status, Logs und Abbruch verwalten.
- Anmeldung mit Benutzername oder E-Mail-Adresse am selben Konto; Benutzernamen vergeben und ändern.
- GitHub Black, SIT Hell/Dunkel sowie eigene JSON-Designs mit Import und Export verwenden.
- Einfarbige SIT-Marke, festes Portal-Tor als Website-/App-Symbol und reduzierte Anmeldung mit Verantwortlichen-Hinweis.

### Repository und Betrieb

- Alte Windows/WPF-Anwendung, zugehörige Tests, Bauskripte und Windows-Workflow entfernt.
- Sämtliche eingecheckten EXE-/DLL-Dateien und Desktop-Build-Zwischendateien entfernt.
- Überholte Symbolvarianten und lokale temporäre Prüfdateien bereinigt; Ignore-Regeln für Konfiguration, Caches und Build-Ausgaben erweitert.
- Web-App-Tests und Docker-Workflow bleiben erhalten. Der lokale Stack ist unter `http://127.0.0.1:18092` geprüft.

### Prüfung und verbleibende Abnahme

59 Backend- und 28 Frontend-Tests sowie Produktions- und Docker-Builds wurden erfolgreich ausgeführt. Die Migration für Benutzernamen ist im vorhandenen lokalen PostgreSQL-Stack angewendet. Eine vollständige Prüfung realer Semaphore-Deployments, Unternehmensnetzwerk und produktiver TLS-Anbindung folgt vor der Produktivfreigabe; siehe [Implementierungsstatus](docs/IMPLEMENTATION_STATUS.md).
