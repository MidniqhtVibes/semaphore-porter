## Ziel

Ein Registry-Profil ist ein wiederverwendbarer Pull-Zugang für genau eine Anwendung. Es enthält den Registry-Host, den tatsächlichen Benutzer und eine Passwort- beziehungsweise Tokenquelle. Mehrere Container derselben Anwendung teilen diesen Zugang. Verschiedene Anwendungen können verschiedene Registries verwenden.

Das Profil setzt einen gültigen Zugang beim Registry-Anbieter voraus. Beim Anlegen des Profils werden dort weder Server noch Projekte, Konten oder Tokens erzeugt.

## Passwortquelle

| Quelle | Verwendung |
| --- | --- |
| Verschlüsselt in Semaporter | Einen bereits gültigen Pull-Token beziehungsweise ein Passwort eingeben. Der Wert wird verschlüsselt gespeichert und nicht über Profilabfragen zurückgegeben. |
| Feste Vault-Version | Auf dem Profil den relativen Secret-Pfad, eine konkrete Version und das Passwortfeld referenzieren. Der Registry-Lesezugang wird auf derselben Verwaltungsseite eingerichtet. |

Eine Vault-Referenz enthält den Pfad relativ zum KV-Mount, ohne `/data/`. Eine spätere Secret-Version wird erst nach bewusster Profiländerung verwendet. Host und Benutzer werden weiterhin im Profil gepflegt.

## Vorgehen

1. **Einstellungen → Registry-Zugänge** öffnen.
2. Profilname, Anwendung, Host ohne Protokoll/Pfad und Benutzer eintragen.
3. Die gültige Passwortquelle auswählen und speichern.
4. Im Tenant-Ersteller bei aktivierter Vault-Anlage je Anwendung das Profil zuordnen.
5. Quelle und Zielpfad in der Vorschau kontrollieren und die Erstellung bestätigen.

Ein direkt im Assistenten angelegtes Profil wird sofort gespeichert. Ein späterer Abbruch des Assistenten entfernt dieses gemeinsam nutzbare Profil nicht.

## Wirkung im Tenant

Bei der Erstellung werden `registry_password`, `registry_host` und `registry_username` in das neue Vault-Anwendungsobjekt kopiert. Host und Benutzer werden zusätzlich in die passenden öffentlichen Variablen unter **Semaphore-Defaults** übernommen.

Eine Profiländerung rotiert die Kopien bestehender Tenants nicht automatisch. Eine abweichende, fest vorgegebene Registry muss zuvor im freigegebenen Stack beziehungsweise in der Vorlage abgeglichen werden.

## Ergebnis prüfen

Die Quellprüfung bestätigt den Lesezugang und den verfügbaren Wert. Ein tatsächlicher Docker-Login oder Image-Pull findet dabei nicht statt. Die Pull-Berechtigung wird mit einem geeigneten Testdeployment nachgewiesen.
