# Semaphore Tenant Configurator v2 (Windows)

**Ziel:** Geführter Konfigurator zum Erstellen neuer Semaphore-Projekte für Mandanten/Tenants. Kein JSON-Handeditieren und keine bloß kosmetische Neuauflage der WinForms-App.

## Warum C# / WPF / .NET 10?

WPF stellt Layout-Grids, Data Binding, Scrollbereiche, wiederverwendbare Styles und echte Windows-Dialoge bereit. Der asynchrone API-Client blockiert nicht die Oberfläche, und `dotnet publish` erzeugt eine eigenständige `win-x64`-EXE. Die bisherige PowerShell-App (v1.6) liegt unverändert im Archiv als **Legacy-v1.6.zip**. Der API-Code wurde semantisch neu umgesetzt: getrennte JSON-Projektliste, sichere GET-Redirects, kein POST-Retry, Proxy mit Windows-Konto, DPAPI-Token-Ablage.

## WICHTIG: Stand der ausgelieferten Datei

Hier ist **Quellcode mit einem Windows-Buildskript** enthalten. Aus dieser Linux-Arbeitsumgebung konnte keine Windows/WPF-EXE kompiliert oder gestartet werden. Die App ist daher **noch nicht als Windows-Release verifiziert**. Bitte nicht als getestete EXE behandeln. Ein Windows-Rechner oder der beigefügte GitHub-Actions-Workflow kompiliert die EXE.

## Einmalig bauen

1. .NET **10 SDK** für Windows installieren: https://dotnet.microsoft.com/download/dotnet/10.0 (Firmenrichtlinien beachten).
2. `BUILD-WINDOWS.cmd` doppelklicken. Die CMD ruft `dotnet publish` jetzt direkt auf, ohne PowerShell-Execution-Policy. Sie sucht auch das vorhandene x86-SDK unter `C:\Program Files (x86)\dotnet`. Internet/NuGet kann beim ersten Restore notwendig sein.
3. Danach **`dist\SemaphoreTenantConfigurator.exe` direkt starten**, kein `.bat` nötig. Das SDK wird nur zum Bauen benötigt; die resultierende EXE bündelt .NET selbst.
4. Alternativ Repository nach GitHub hochladen und Workflow **Build Windows EXE** starten. Die EXE steht als Workflow-Artefakt bereit; GitHub-Actions-Berechtigungen und Firmenrichtlinien beachten.

Die EXE ist **nicht signiert**. Windows SmartScreen, AppLocker oder WDAC können sie auf Firmenrechnern blockieren. Keine Umgehung dieser Richtlinien vorgesehen; im Zweifel Freigabe/Signierung über IT.

## Wizard

1. **Verbindung:** Server-URL, Bearer-Token, Firmenproxy; System-Windows-SSO oder manueller Proxy. Lokale JSON-Quelle ist offline möglich. Bekannte v1.6-DPAPI-Datei und settings.json werden übernommen.
2. **Vorlage:** Liste vom Server (`GET /api/projects`) oder lokale `.json`/`.backup`, Backup wird per `GET /api/project/{id}/backup` geladen. Original bleibt unangetastet.
3. **Tenant:** Neuer Projektname, technische Tenant-ID (`tenant_slug`), optionale Anwendung, Datenbanktyp, Testdaten, TTL. Auswahlvorschläge stammen aus vorhandenen Survey-Dropdowns der Vorlage, nicht aus erfundenen Werten.
4. **Inhalte:** Task Templates und Variablengruppen auswählen, Git-URL/Branch des ersten Repositories ggf. ändern, Tenant-Gruppe zuweisen; Zeitpläne und Webhooks standardmäßig entfernen.
5. **Presets:** Vorlagen PostgreSQL/MariaDB/MySQL/Registry/Vault/SMTP/Deployment; eigene v1.6-Presets werden gelesen; Gruppenwerte editierbar (`Text`, `Zahl`, `Bool`, `JSON`). Keine Geheimnisse speichern.
6. **Prüfen:** Strukturvalidierung, Hinweise zu Keys, Vorschau als JSON exportieren, bewusste Bestätigung und erst dann `POST /api/projects/restore`.
7. **Fertig:** Hinweise zum Key Store und zum manuellen Test-Deployment.

## Was der Wizard bewusst NICHT macht

- Er startet **keinen Ansible-Task** und legt keine Datenbank auf dem Zielhost an. Ein neues Semaphore-Projekt zu erstellen ist nicht dasselbe wie eine neue Laufzeitumgebung zu provisionieren.
- Kein automatisches Kopieren von SSH-Privatkeys, Vault-Secrets oder Registry-Passwörtern; diese müssen nach dem Restore geprüft bzw. neu hinterlegt werden.
- Kein Editieren des GitLab-Repositories oder seiner application.yml-Dateien. Die Anwendung kann nur Variablen und Konfigurationsbezüge in einem Semaphore-Projektbackup anpassen.
- Kein In-Place-Update eines bestehenden Projekts; Restore erzeugt eine neue Projektkopie.
- Bei jeder Änderung der Gruppen im Wizard sollen Referenzen zu übernommenen Gruppen passen. Vor dem Import Fehlerausgabe beachten.

## Datenschutz/Sicherheit

- Token im Windows-Benutzerprofil per DPAPI verschlüsselt, kompatibel mit bestehender v1.6-Ablage. Einstellungen: `%LOCALAPPDATA%\SemaphoreProjectManager\settings.json`, Token: `credentials.dat`, eigene Presets: `Presets\`.
- Keine TLS-Zertifikatsprüfung abgeschaltet. Bearer-Token nur zu demselben Host und demselben API-Pfad bei GET-Redirects; POST wird nie automatisch wiederholt.
- Manuelle Proxy-Passwörter bleiben nur in der laufenden Anwendung und sind nicht persistent.
- Projekt-Backup/JSON-Vorschau *kann Konfigurationen mit sensiblen Werten enthalten*: nur an vertrauenswürdigem Ort speichern und vor Weitergabe prüfen.

## Technische Grenzen / nächste Ausbaustufe

- Aktuell 7-Schritt-Wizard mit generischen Presets; spezifische Mandanten-Backend-Operationen außerhalb von Semaphore (DNS, eigene DBs, GitLab, Vault, Jobausführung) benötigen zuvor eine explizite Berechtigung und eine getrennte, abgesicherte API-Anbindung.
- Repository-Übersteuerung wirkt auf das **erste** Repository im Backup. Bei Projekten mit mehreren Repositories die JSON-Vorschau prüfen. Inventories bleiben referenziert, aber ihre Inhalte werden hier noch nicht grafisch bearbeitet.
- Windows-Build und Firmenproxy bitte am Zielgerät testen. Im Gegensatz zur bestehenden PowerShell-Version wurde dieser neue Client **noch nicht live gegen euren Server getestet**.

## Tests

Auf einem Windows-Rechner mit .NET 10 SDK:

```powershell
dotnet run --project tests/TenantConfigurator.Tests.csproj -c Release
```

Zusätzlich baut und testet der Workflow unter `.github/workflows/build-windows.yml` auf Windows.
