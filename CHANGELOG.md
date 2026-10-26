# Änderungen

## GitLab-Integration und Bereinigung – 26.10.2026

- GitLab unter Einstellungen → Verbindungen und Entwicklung mit Programmpaketen, Änderungen & Freigaben, Prüfungen sowie Versionen & Übernahme.
- Verschlüsselte Projektverbindung, revisionsgebundene Paketentwürfe, vollständiger Manifest-/Dateieditor, Datensatz-Assistent mit SHA-256 und Stack-Vertragsprüfung.
- Bestätigte Batch-Commits/Merge Requests mit Ausführungssperre, Versionskonflikten und Wiederaufnahme nach unklaren API-Ergebnissen.
- Versionierte Vault-Kataloge mit Pipeline-/SHA-Prüfung, atomarer Aktivierung und separater Semaphore-Projektvorlage; Rücknahme auf bereits aktivierte Stände.
- Migration `20261026_0005`, reproduzierbares Backend-Testimage, gemeinsamer Katalogexporter und CI-Beispiel für das Stack-Projekt.
- Überholte GitLab-Planung und historische Vault-Vorstudie durch aktuelle Anleitungen ersetzt. Aktive Regressionstests, Migrationen, Präsentation und benötigte Lizenz-/Quellartefakte bleiben erhalten.
- Keine Live-Verbindung zur Firmeninstanz eingerichtet, kein GitLab-Commit durch den Agenten und kein Push dieses Repositories.

## GIF-Designs und GitLab-Planung – 26.10.2026

- Animierte GIFs als Logo und Anmeldehintergrund hochladen; unveränderte Bilddaten beim Speichern, Kopieren sowie JSON-Import und -Export erhalten.
- Hintergrund-Unschärfe zwischen 0 und 24 Pixeln mit gemeinsamer Darstellung in Vorschau und Anmeldung; Logo, Texte und Formular bleiben scharf.
- Bestehende Grenzen von 250 KB pro Bild und 1 MB pro Design-Datei beibehalten; ältere Designs bleiben gültig.
- Ursprüngliche GitLab-Planung für Menü, Paket-Assistent und Übernahme; inzwischen durch die [umgesetzte Integration](docs/GITLAB.md) ersetzt.
- 73 Frontend-Tests bestanden, drei variantenbedingt übersprungen; Produktionsbuild und lokale Browserprüfung erfolgreich. Kein Commit oder Push.

## Umbenennung zu Semaporter – 26.10.2026

- Einheitlicher Produktname in Oberfläche, Browser-Titel, App-Manifest, API-Titel, HTTP-Clientkennung, npm-Paket und Dokumentation.
- Neue lokale und veröffentlichbare Image-Namen; CI-Veröffentlichungsziel unabhängig vom GitHub-Repositorynamen.
- Bestehende Browser-Designs und Menüeinstellungen über bisherige Speicherschlüssel übernehmen; alte Standardtexte aktualisieren und individuelle Firmenbezeichnungen erhalten.
- Präsentation, PDF und Sprechernotizen auf Semaporter umgestellt und Dateien entsprechend benannt.
- Bestehendes Compose-Projekt in der lokalen Konfiguration festgeschrieben und auf neue Images aktualisiert; derselbe Datenbank-Container bleibt erhalten. GitHub-Adresse und geöffneter Workspace-Ordner bleiben unverändert.
- Einrichtungs- und Umstellungshinweise in [docs/UMBENENNUNG.md](docs/UMBENENNUNG.md). Kein Push und keine externe Veröffentlichung.

## Lokale Navigation und Präsentationsunterlagen – 26.10.2026

- Sidebar als aufklappbarer Baum mit eingerückten Einträgen und verschachtelten Verbindungen für Semaphore und Vault.
- Navigationszustand getrennt für Admin- und Benutzerportal merken; aktive Zweige automatisch öffnen, alle Kategorien gemeinsam schalten und Tastaturbedienung unterstützen.
- Vollständiger Seitenpfad und dieselbe Navigation in der Designvorschau; mobile geschlossene Sidebar aus der Fokusreihenfolge nehmen.
- Ungenutzte Backend-Definitionen, lokale Build-/Testcaches und temporäre Prüfarbeitsdateien bereinigen; Ignore-Regeln und Dokumentationsverweise aktualisieren.
- Ordner `präsentieren` mit Architektur, Code-Rundgang, Ablaufdiagrammen, Docker-Erklärung, Vorführungsleitfaden und Bereinigungsübersicht.
- Bearbeitbare PowerPoint-Präsentation mit 16 Folien, integrierten und separaten Sprechernotizen sowie einer PDF-Fassung.
- Keine Veröffentlichung, kein Commit und kein Push durchgeführt.

## Lokale Vault-Erweiterung – 16.10.2026

- Zentrale verschlüsselte AppRole- und Registry-Konfiguration im Menü **Vault**.
- Tenant-Wizard mit Manifestkatalog, konkreten KV-Zielen und Eingabe oder ausdrücklicher Generierung von Secret-Werten.
- Vorprüfung aller Ziele, Neuanlage ausschließlich mit `cas=0`, Fortschrittsbelege und Wiederaufnahme ohne Überschreiben oder Neugenerieren.
- Bestehenden Semaphore-Lesezugang geschützt in neue Tenant-Projekte eintragen; AppRoles und Policies bleiben extern verwaltet.
- Additive Migration `20261016_0004`, Fehlerfalltests, Einrichtungsanleitung und 14 weitere Abnahmefälle.
- Keine Veröffentlichung oder Push durchgeführt; Live-Abnahme gegen die Firmeninstanzen bleibt offen.

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
