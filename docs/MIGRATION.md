# Migration vom Windows-Konfigurator

Der bisherige WPF-Konfigurator und seine Tests bleiben in `src/` und `tests/` erhalten. Er ist kein Laufzeitbestandteil des Portals. Das Portal übernimmt die bewährten fachlichen Regeln, nicht die lokale Desktop-Konfiguration.

## Übernommene Konzepte

- tolerantes Einlesen verschiedener Semaphore-Projektlisten
- Projekt-Backup als unveränderte Vorlage und Restore als Erstellmechanismus
- sichere GET-Redirects ohne automatisches POST-Retry
- Survey-Auswertung für dynamische Task-Eingaben
- Erkennung secret-verdächtiger Preset-Schlüssel
- Validierung vor externen Schreiboperationen
- geführter, bestätigter Tenant-Workflow

## Bewusst nicht automatisch importiert

- lokal per Windows-DPAPI geschützte Tokens
- Desktop-Einstellungen unter dem Windows-Benutzerprofil
- freie lokale Preset-Dateien ohne serverseitige Validierung
- UI-Zustand oder Verlauf der Desktop-Anwendung

DPAPI-Ciphertexte sind an den Windows-Benutzer und Rechnerkontext gebunden. Der Service-Token muss deshalb einmal im Adminbereich neu hinterlegt werden und wird danach mit dem Portal-Fernet-Key verschlüsselt.

## Empfohlener Umstieg

1. Bestehende Semaphore-Projekte und ihre verwendeten Task Templates dokumentieren.
2. Portal installieren, ersten Admin anmelden und Semaphore-Verbindung testen.
3. Geeignete bestehende Projekte als Projektvorlagen in das Portal aufnehmen.
4. Benutzer und Gruppen anlegen; keine alten lokalen Zugangsdaten kopieren.
5. Einen nicht produktiven Tenant über den Wizard erstellen.
6. Synchronisierte Survey-Felder und generierte Policies fachlich prüfen.
7. Task-Ausführung, Live-Ausgabe, Abbruch und Audit gegen die echte Semaphore-Instanz abnehmen.
8. Erst danach produktive Tenants migrieren und den Desktop-Konfigurator nur noch als Archiv verwenden.

Bestehende Semaphore-Projekte werden nicht automatisch zu Portal-Tenants erklärt. Diese explizite Zuordnung verhindert, dass Benutzer aufgrund eines Namensmusters versehentlich Zugriff auf fremde Projekte erhalten.
