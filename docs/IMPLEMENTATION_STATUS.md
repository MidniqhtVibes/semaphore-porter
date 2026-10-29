# Implementierungs- und Abnahmestatus

Ergänzung 29.10.2026: Live-Deploymentüberwachung mit getrenntem lokalem Status-Exporter und Sender ohne Docker-Rechte, privaten Token-Dateien, echten Lifecycle-Ablaufzeiten, Containerzuständen und veralteten/teilweise erfassten Snapshots. Migration `20261029_0007`. Linux-Dateirechte und ein echter unprivilegierter Senderprozess wurden im isolierten lokalen Testcontainer geprüft. Einrichtung, systemd-Isolation und verbleibende Abnahme am echten Zielhost: [DEPLOYMENT_MONITORING.md](DEPLOYMENT_MONITORING.md). Keine Serverzugriffe vorgenommen. Ohne eingerichtete Quelle werden noch keine Host-Deployments angezeigt; die bisherige Portal-Task-Historie bleibt verfügbar.

Ergänzung 29.10.2026: Zentrale SSH-Zugangsprofile mit eigenem Vault-Lesezugang, Host-/Git-Zielprüfung, versionierter Wizard-Zuordnung, automatischer Übertragung nach dem Restore und bestätigter Rotation je Projekt. Einrichtung: [SSH_ZUGANGSPROFILE.md](SSH_ZUGANGSPROFILE.md). Private SSH-Inhalte werden nicht im Semaporter gespeichert; die benötigten Projektkopien liegen im Semaphore-Key-Store. Der bestehende Tenant-Vault-Schreibzugang bleibt unverändert.

Stand: 26.10.2026. Aktuelle Bedienungs- und Einrichtungsanleitungen stehen in der [README](../README.md), im [GitLab-Leitfaden](GITLAB.md), der [Vault-Vereinbarung](VAULT_IMPLEMENTIERUNG.md) und der [Projektverwaltung](PROJECT_MANAGEMENT.md). Frühere Zwischenstände sind im [Changelog](../CHANGELOG.md) und in der Git-Historie nachvollziehbar.

## Umgesetzt

- Web-App mit FastAPI, React/TypeScript, PostgreSQL, Nginx und optionalem Caddy-TLS-Gateway; alte WPF-/EXE-Quellen und deren Buildartefakte sind entfernt.
- Semaphore-Projekte und Ressourcen verwalten; Projektvorlagen importieren; Tenants über einen fortsetzbaren und bestätigten Backup-/Restore-Workflow erstellen.
- Mehrere Anwendungen, Provider und Datensätze je Tenant freigeben; `tenant_slug` und `runtime_scope_id` gemeinsam unter `Semaphore-Defaults` pflegen.
- Lokale Benutzer, Gruppen, Mitgliedschaften, Task-Rechte und serverseitige Parameter-Policies; Anmeldung mit Benutzername oder E-Mail; Task-Start, Status, Live-Ausgabe, Abbruch und Audit.
- Vault KV v2: zentrale verschlüsselte AppRole-/Registry-Zugänge, manuelle oder ausdrücklich generierte Werte, vollständiger Vorabcheck, ausschließlich `cas=0`, Wiederaufnahme und manuelle Prüfung unklarer Ergebnisse. AppRoles/Policies werden außerhalb des Portals verwaltet.
- GitLab-Projektverbindung mit verschlüsseltem Token unter **Einstellungen → Verbindungen → GitLab**. Bereich **Entwicklung** mit Paketen, Änderungen & Freigaben, Prüfungen und Versionen & Übernahme.
- Programmpakete erzeugen/kopieren, vollständige Manifest-/Dateibearbeitung, Dataset-Assistent mit SHA-256, lokale Vertragsprüfung aller angebotenen Kombinationen und Diff. Nur eigener Paketordner und eigener Katalogeintrag sind beschreibbar.
- Revisionsgebundene Branch-/Merge-Request-Übergabe mit expliziter Bestätigung, Ausführungssperre, optimistischen Entwurfsversionen und Wiederaufnahme nach unklaren Antworten. Review/Merge bleiben in GitLab; keine automatische Repository-Veröffentlichung durch den Agenten.
- Versionierte GitLab-Katalogstände mit exakter SHA-/Pipeline-Prüfung und atomarer Aktivierung gemeinsam mit einer separaten lokalen Projektvorlage. Rücknahme nur auf bereits aktivierte Stände; vorhandene Tenants werden nicht umgestellt. Der gebündelte Vault-Katalog bleibt der Rückfall ohne aktiven Snapshot.
- Baumnavigation mit Speicherung, Tastatursteuerung und mobiler Sidebar; Produktname Semaporter mit Übernahme bisheriger Browserdaten. Technische Bestandsnamen: [UMBENENNUNG.md](UMBENENNUNG.md).
- Designstudio einschließlich animierter GIFs als Logo und Anmeldehintergrund, separater Hintergrund-Unschärfe von 0–24 Pixeln, Import/Export und browserlokaler Speicherung. Formular und Logo bleiben scharf.
- Präsentationsordner mit Architektur, Codeabläufen, Docker-Erklärung, PowerPoint/PDF und Sprechernotizen. Die Folien dokumentieren den Stand vor der GitLab-Erweiterung; aktuelle GitLab-Details stehen im Leitfaden.

## Automatisiert geprüft

- **101 bestehende Backend-Tests und 42 GitLab-/Paketfälle bestanden** mit Python 3.13 im isolierten Testcontainer. Eine DeprecationWarning der vorhandenen Starlette-Testclient-Abhängigkeit.
- **80 Frontend-Tests bestanden**, drei weitere sind für die andere Build-Variante vorgesehen und wurden übersprungen.
- TypeScript-/Vite-Produktionsbuild und beide Produktionsimages erfolgreich; GitLab-Seiten werden getrennt geladen. Alle sechs neuen Seiten wurden auf Desktop und Mobilgerät in einem isolierten Edge-Profil mit simulierten Admin-/API-Daten geprüft: sichtbarer GitLab-Menüeintrag, keine horizontalen Überläufe und keine JavaScript-Ausnahmen.
- Tatsächlicher benachbarter Stack offline mit dem mitgelieferten Compiler geprüft: **59 Dateien, 17 Kombinationen**, AzubiOrga und WordPress. Repository-Python, Shell, SQL, Compose und Playbooks wurden dabei nicht ausgeführt.
- Migration `20261026_0005` auf Datenerhalt und Rücknahme mit SQLite geprüft. Der Backend-Dockerfile besitzt ein separates Testtarget; das Standardimage enthält keine Tests/Testabhängigkeiten.
- GIF-Anmeldung mit isoliertem Edge-Profil auf 1440 und 390 Pixeln geprüft: Animation läuft, Hintergrundfilter aktiv, Formular ungefiltert, kein horizontaler Überlauf und keine JavaScript-Ausnahmen. Temporäres Profil entfernt.

Die Tests verwenden simulierte GitLab-/Semaphore-/Vault-Antworten. Sie belegen keine Erreichbarkeit oder Rechte der Firmeninstanzen.

## Lokaler Betrieb und Bereinigung

Der bestehende Stack verwendet Port **18092** und seinen bisherigen Compose-Projekt-/Datenbanknamen. `.env`, Fernet-Schlüssel, Zugangswerte und Volumes bleiben erhalten. Frontend und Backend sind lokal aktualisiert, alle drei Dienste gesund. PostgreSQL wurde nicht neu erstellt. Migration `20261026_0005` ist angewendet; Hash-Vergleiche bestätigen unveränderte bestehende Benutzer, Tenants, Vorlagen, Erstellungsvorgänge und Integrationsdaten. Eine vorherige Datenbanksicherung liegt im ignorierten lokalen Sicherungsordner. Die neuen APIs sind im OpenAPI-Schema vorhanden und ohne Anmeldung gesperrt.

Überholte GitLab-Planung und die historische Vault-Vorstudie wurden durch aktuelle Anleitungen ersetzt; der doppelte Katalogexport ist in einem gemeinsamen Modul zusammengeführt. Temporäre Prüfskripte, Browserprofile und erzeugte Anwendungscaches sind entfernt. Aktive Regressionstests, Migrationen, lokale Sicherungen, Entwicklungsumgebungen, Präsentationsunterlagen und tatsächlich verwendete optionale Arcade-/Lizenzdateien bleiben erhalten. Es gibt keine ungenutzten EXE-/DLL-Artefakte im versionierten Stand.

## Vor Produktivfreigabe offen

Der [Abnahmetestplan](ABNAHMETESTS.md) enthält **80 Fälle** einschließlich GitLab, Vault und GIFs. Die manuellen Live-Fälle sind offen:

- GitLab-Instanz, numerische Projekt-ID, Tokenrolle/-Scopes, geschützter Basisbranch, Firmen-CA und echte Commit-/MR-/Timeout-Abläufe abnehmen.
- GitLab-CI im Stack-Projekt einrichten: [Beispiel](examples/gitlab-ci.yml). Eine erfolgreiche Pipeline ist Voraussetzung für die Übernahme. Statische Prüfungen allein ersetzen keine isolierten Lifecycle-/Import-/Readiness-/TTL-/Claim-/Cleanup-Tests.
- Menschlichen Review und Freigabeprozess in GitLab organisatorisch und durch passende Branch-/Reviewregeln absichern. Die Portalbestätigung behauptet keine zusätzliche GitLab-Approval-Durchsetzung.
- Neue Katalogrevision zusammen mit passender Projektvorlage aktivieren; reale Semaphore-Backup-/Survey-Struktur und Registry-Vorgaben prüfen.
- Vault-ACLs, Secret-Verwendung, Tenant-Zuordnung und Deployment-Zielhosts Ende zu Ende testen.
- Produktive TLS-/DNS-/ACME-Wege, Secure-Cookies, erlaubte Hostnamen sowie Backup/Restore mit unverändertem Fernet-Key prüfen.

Kein Commit oder Push dieses Repositories, keine Live-GitLab-Verbindung eingerichtet und keine produktiven Semaphore-/Vault-/GitLab-Objekte durch den Agenten geschrieben.
