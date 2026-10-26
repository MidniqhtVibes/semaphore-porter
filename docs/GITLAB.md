# GitLab und Programmpakete

Die Integration ist im Adminbereich implementiert. Sie verbindet genau ein Stack-Projekt pro Portalinstallation. Ein GitLab-Projekt ist das Quellrepository; Semaphore-Projekte bleiben die Ausführungsumgebungen der Tenants. Die GitHub-Verbindung dieses Semaporter-Repositories wird dadurch nicht verändert.

## Menü und Einrichtung

- **Einstellungen → Verbindungen → GitLab:** Instanz, numerische Projekt-ID, Basisbranch, Token und Schreibmodus.
- **Entwicklung → Programmpakete:** Repository-Pakete, neue Pakete, Kopien und gespeicherte Entwürfe.
- **Entwicklung → Änderungen & Freigaben:** Branches, Merge Requests und Wiederaufnahme.
- **Entwicklung → Prüfungen:** CI-Status der gespeicherten Commit-SHA.
- **Entwicklung → Versionen & Übernahme:** Katalogstände und neue, revisionsgebundene Projektvorlagen.

Alle APIs erfordern `system_admin`; schreibende Portal-Anfragen benötigen zusätzlich Session und CSRF. Tenant-Mitgliedschaften berechtigen nicht zur Änderung gemeinsam verwendeten Deployment-Codes.

1. GitLab muss aus dem Backend erreichbar sein. Instanz-URL ohne Zugangsdaten oder `/api/v4` eintragen; ein Installations-Unterpfad ist erlaubt.
2. Numerische Projekt-ID und Basisbranch, beispielsweise `main`, eintragen. Das Repository benötigt die Verzeichnisse `programs`, `database-types` und `mail` mit den Verträgen des vorhandenen Stacks.
3. Administrativ bereitgestellten Project Access Token hinterlegen. Für Lesen ist `read_api` vorgesehen. Für API-Commits und Merge Requests wird `api` mit geeigneter Projektrolle benötigt; `write_repository` allein ersetzt keinen API-Schreibzugang. [GitLab Token-Scopes](https://docs.gitlab.com/security/tokens/access_token_scopes/)
4. Speichern prüft Projekt-ID und Basisbranch, ohne Repository-Dateien zu ändern. Der Token wird Fernet-verschlüsselt gespeichert und nie zurückgegeben. Ein leeres Tokenfeld erhält den bisherigen Token nur bei gleicher Instanz, Projekt-ID und gleichem Basisbranch. Tokenrotation erhält bestehende Entwürfe; ein anderes Projekt bekommt eine neue Verbindungsidentität.
5. Für die Übergabe den Schreibmodus ausdrücklich aktivieren. Der Basisbranch muss in GitLab geschützt sein. Den Bot so berechtigen, dass er Paketbranches schreiben und Merge Requests vorbereiten, aber den geschützten Branch nicht selbst freigeben kann.

Für eine Firmen-CA `GITLAB_CA_BUNDLE` auf einen lesbaren PEM-Pfad **im Backend-Container** setzen und die Datei per Compose-Override schreibgeschützt mounten. `GITLAB_REQUEST_TIMEOUT_SECONDS` begrenzt einzelne Anfragen, Standard 30 Sekunden. Zertifikatsprüfung bleibt aktiv; Redirects und automatisch übernommene Proxyvariablen sind deaktiviert. Nur explizit konfigurierte GitLab-Ziele erhalten den Token. GitLab-Weblinks werden auf dieselbe Instanz begrenzt.

## Programmpaket erstellen und bearbeiten

Ein Programmpaket beschreibt die Bereitstellung eines vorhandenen Container-Images; es entwickelt oder baut keine neue Anwendungssoftware.

1. **Programmpaket erstellen** öffnen. Entweder eine vorhandene SQL-Anwendung als Vorlage wählen oder eine HTTP-Anwendung ohne Datenbank erzeugen. Bei einer Kopie Provider, Services und Konfiguration fachlich an die neue Anwendung anpassen.
2. Technische ID, Anzeigename, Image-Repository und Release angeben. IDs sind 1–63 Kleinbuchstaben, Ziffern oder Bindestriche. Bei einer Kopie werden Vault-Profil und zum alten Programmnamen gehörende Repository-/Registry-Variablennamen auf die neue ID geändert. Die bestehenden Services und Compose-Umgebungsnamen bleiben untereinander konsistent.
3. Unter **Stammdaten** den Namen, das Release und das Vault-Profil bearbeiten.
4. Unter **Provider & Konfiguration** das vollständige Manifest als JSON bearbeiten. Gespeichert wird weiterhin `program.yml`. Dazu gehören Provider-IDs, Policies, Compose-Modi, Image-/Variable-Mappings, Konfigurationsdateien, erwartete Services, Endpoint, Runtime-Allowlist, Secret-Vertrag und Readiness. Im Dateieditor die zugehörigen Compose-/Konfigurations-/Testdateien ändern oder hinzufügen. Provider müssen bereits im Stack implementiert sein.
5. Unter **Secrets & Testdaten** ausschließlich Secret-Schlüsselnamen und Validierungsregeln prüfen. Passwörter und Tokens gehören nicht in Paketdateien. Ein neuer Datensatz enthält Beschreibung, Typ, Provider-ID, Format, Engine-Hauptversion und Datei; der Assistent berechnet SHA-256. Er setzt `contains_schema: true`, die Datei muss also tatsächlich das Schema enthalten. Metadaten können im Dataset-JSON angepasst werden. Standardpfad des Assistenten ist `testdata/`; bei einem abweichenden Katalogpfad die Datei im Dateieditor passend ablegen.
6. **Entwurf speichern**, dann unter **Prüfen & Übergeben** die gespeicherte Version prüfen. Alle angebotenen Provider-/Policy-/Dataset-Kombinationen werden mit dem lokal mitgelieferten Stack-Vertrag kompiliert. Compose-Service-Namen, Dateigrenzen, Hashes und Secret-Profilkompatibilität werden geprüft. Der Anzeigename des eigenen Programmkatalogeintrags wird beim Speichern mitgeführt.
7. Den vollständigen Diff prüfen und **Branch und Merge Request erstellen** bestätigen. Erst jetzt erfolgt ein GitLab-Schreibzugriff. Ein Paketexport enthält die gespeicherten Dateien als JSON mit Base64-Inhalten; vor einem Export Änderungen speichern.

Das Manifest ist absichtlich vollständig zugänglich. Ein generischer Assistent kann die Kompatibilität einer beliebigen Software mit einem Datenbankprovider nicht erfinden. Neue Provider, große frei programmierte Mehrservice-Architekturen und globale Lifecycle-Änderungen erfolgen im Stack-Repository und durch dessen Entwicklungsprozess.

## Prüfungen und Grenzen

- Ein Schreibvorgang darf ausschließlich `programs/catalog.yml` und Dateien unter `programs/<eigene-id>/` verändern. Einträge anderer Anwendungen bleiben unverändert. Programm-ID und Dateipfade werden serverseitig geprüft.
- Der lesende Snapshot umfasst nur `programs/`, `database-types/` und `mail/`. Symlinks, Submodule und spezielle Dateien werden abgewiesen. `.gitkeep` wird als reguläre Paketdatei unterstützt.
- Maximal 10 MB je Datei, 32 MB decodierte Daten und 400 Dateien pro Katalog; maximal 100 Dateien pro Entwurf und 300 geprüfte Kombinationen. Größere Pakete benötigen eine bewusst erweiterte Materialisierungs-/Speicherstrategie. Git LFS-Zeiger ersetzen keine regulären Datensatzdateien.
- YAML benötigt sichere Typen und eindeutige Schlüssel. Tiefe, Größe, rekursive Aliase und Python-Tags werden begrenzt beziehungsweise abgewiesen.
- Compose darf keine privilegierten Container, Hostnetz-/PID-/IPC-Zugriffe, Geräte, zusätzliche Capabilities, Docker-Socket-/Hostmounts, Builds oder fremde Includes verwenden. Zulässig sind eigene benannte Volumes und einfache lokale Konfigurationsdateien. Statische Secret-Werte in Compose-Umgebungsfeldern werden abgewiesen.
- Das Backend führt weder Repository-Python, Shell, SQL, Compose noch Playbooks aus. Die Portalprüfung ist eine **Struktur-/Vertragsprüfung**. Provider-Validatoren, tatsächliche Imports, Readiness, Claims, TTL, parallele Runtimes und Cleanup müssen in isolierter CI-/Deployment-Testinfrastruktur geprüft werden.

Der Compiler in `backend/app/package_contract.py` ist eine lokal geprüfte Kopie des vorhandenen Stack-Compilers vom 26.10.2026, ohne dessen CLI. SHA-256 der ursprünglichen Datei: `987765cdbdb203508963ff407637eb144ebc7523d4d272b7b5135a3450143ba6`. Änderungen an Manifest-/Providerverträgen benötigen eine koordinierte Aktualisierung und Tests in beiden Projekten. Semaporter lädt niemals einen neuen Compiler aus GitLab nach.

## Branch, Merge Request und Wiederaufnahme

Die Übergabe verwendet einen eindeutigen Branch `semaporter/programs/<id>/<entwurfs-id>`, einen Batch-Commit auf der gespeicherten Basis-SHA und anschließend einen Merge Request. Der geschützte Basisbranch wird nicht direkt beschrieben; erzwungene History-Änderungen sind deaktiviert. [Commits API](https://docs.gitlab.com/api/commits/), [Merge requests API](https://docs.gitlab.com/api/merge_requests/)

Entwürfe besitzen eine Versionsnummer gegen paralleles Überschreiben. Die persistierte Ausführungssperre verhindert gleichzeitige Übergaben. Ist eine Ausführung nach 15 Minuten noch gesperrt, kann sie erneut abgeglichen werden. Der alte Worker darf eine inzwischen übernommene Sperre nicht freigeben.

Bei Timeout **Übergabe abgleichen / fortsetzen** verwenden. Semaporter prüft zunächst den bekannten Branch, Commit-Eltern, die Entwurfskennung und den vollständigen Kataloginhalt. Einen vorhandenen Commit oder Merge Request legt es nicht nochmals an. Fremde Änderungen blockieren die Fortsetzung. Bereits übergebene Entwürfe sind unveränderlich und bleiben als Nachweis gespeichert; neue Änderungen beginnen vom aktuellen Basisbranch. Nur lokale, noch nicht zur Übergabe festgeschriebene Entwürfe können gelöscht werden.

Ein zwischenzeitlich geänderter Basisbranch blockiert eine neue Übergabe. Einen neuen Entwurf vom aktuellen Stand öffnen und die eigene Änderung anhand des Diffs übertragen. Semaporter überschreibt oder rebasiert keine fremden Änderungen automatisch.

Unter **Änderungen & Freigaben** beziehungsweise im Entwurf Review/CI manuell aktualisieren. Der Portalstatus ersetzt kein GitLab-Review. Mergen erfolgt in GitLab unter den dort administrierten Rechten und Reviewregeln; Semaporter stellt keine Branchschutz-/Approvalregeln eigenmächtig um.

## CI und Übernahme in den Betrieb

Im bestehenden lokalen Stack-Repository ist noch keine GitLab-CI vorgegeben. [examples/gitlab-ci.yml](examples/gitlab-ci.yml) ist eine konkrete Ausgangsvorlage für das Stack-Projekt. Sie wird nicht automatisch dorthin geschrieben.

1. Ein freigegebenes Semaporter-Backend-Image mit festem Digest als CI-Variable `SEMAPORTER_VALIDATION_IMAGE` bereitstellen. Private Registry-Leserechte für den Runner getrennt einrichten. `SEMAPORTER_BASE_BRANCH` muss dem Portal-Basisbranch entsprechen.
2. Die Beispiel-CI im Stack-Projekt mit bestehender CI zusammenführen. Der erste Job verwendet den mitgelieferten, vertrauenswürdigen Validator über `python -m app.package_check`. Der zweite führt die bestehenden Stack-Vertragstests aus. Runner haben keine produktiven Vault-/SSH-Zugänge und keinen produktiven Docker-Socket.
3. Eigene isolierte Lifecycle-/Import-/Cleanup-Tests und den menschlichen Review als verbindlichen Freigabeprozess einrichten. Die statische Beispiel-CI allein beweist keine erfolgreiche Bereitstellung einer neuen Anwendung. Die tatsächliche GitLab-Version, Tokenrechte und Reviewregeln einmal gegen die Firmeninstanz abnehmen.
4. Nach Review und Merge muss die neueste Pipeline der **exakten SHA auf dem konfigurierten Basisbranch** erfolgreich sein. Laufende, fehlende, übersprungene, manuelle und fehlgeschlagene Pipelines reichen nicht. [Pipelines API](https://docs.gitlab.com/api/pipelines/)
5. **Versionen & Übernahme → Aktuellen Basisstand prüfen und vorbereiten** verwenden. Das Backend prüft alle Pakete und exportiert mit demselben Exporter wie das lokale Werkzeug einen unveränderlichen Vault-Katalog.
6. Unterschiede anzeigen, eine vorhandene Projektvorlage und ihr Stack-Repository auswählen und den Review bestätigen. Die Clone-URL muss exakt einer von GitLab bestätigten HTTP-/SSH-Clone-URL entsprechen. Die Grundlage muss Deployment-Tasks am gewählten Repository mit `application_id`, `database_type` und `dataset_id` als Surveys besitzen.
7. Die Aktivierung prüft Revision, Pipeline und Herkunft erneut. Sie legt **atomar** den aktiven Katalog und eine **separate Projektvorlage** fest: Repository auf vollständige SHA pinnen, Survey-Auswahlwerte aus dem geprüften Katalog übernehmen. Die Quellvorlage und bestehende Tenants bleiben unverändert. Im nächsten Tenant-Assistenten diese neue Vorlage verwenden.
8. Für neue Programme gegebenenfalls gültige Registry-Zugänge unter Vault und benötigte öffentliche Anwendungsvariablen ergänzen. Eine Katalogaktivierung legt noch keine Secrets, Benutzer, Registry-Credentials oder Deployments an.

Beim nächsten Vault-Onboarding müssen aktive Katalogrevision und Projektvorlage zusammenpassen. Bereits vorbereitete Vault-Ausführungen behalten ihren eingefrorenen Plan. Solange kein GitLab-Katalog aktiv ist, bleibt der gebündelte `vault_catalog.json` der Rückfall; der lokale Export über `tools/export_vault_catalog.py` bleibt unterstützt.

**Rücknahme:** Einen früher bereits aktivierten Snapshot auswählen, „Rücknahme auf einen früher bereits aktivierten Stand“ und Review bestätigen. Auch dabei wird eine separate Projektvorlage mit der alten SHA erzeugt. Die Rücknahme verändert keine laufenden Tenants, Vault-Objekte oder Git-Historie. Eine parallele Änderung am aktiven Katalog führt zu einem Konflikt; danach neu laden.

## Technische Zuordnung und Prüfung

| Bereich | Code |
|---|---|
| Konfiguration und HTTP | `app/gitlab_client.py`, `app/gitlab_service.py`, `app/gitlab_schemas.py` |
| Pakete und Verträge | `app/package_validation.py`, `app/package_contract.py`, `app/package_check.py` |
| Katalogexport | `app/catalog_export.py`, `app/vault_catalog.py`, `tools/export_vault_catalog.py` |
| API und Speicherung | `app/routers/gitlab.py`, Modelle und Migration `20261026_0005` |
| Oberfläche | `frontend/src/pages/admin/GitLab*.tsx`, `ProgramPackage*.tsx`, `frontend/src/gitlab.ts` |
| Automatisierte Prüfung | `backend/tests/test_gitlab.py`, `frontend/src/test/GitLab.test.tsx` |

Backend-Tests reproduzierbar ohne lokale Python-Umgebung: `docker build --target test -t semaporter-backend-test ./backend`, danach `docker run --rm --network none semaporter-backend-test`. Der Standard-Docker-Build erzeugt weiterhin das Produktionsimage ohne Testdateien und Testabhängigkeiten. Live-Abnahme und aktuelle Nachweise stehen in [ABNAHMETESTS.md](ABNAHMETESTS.md) und [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).
