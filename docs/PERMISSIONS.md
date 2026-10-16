# Benutzerverwaltung und Berechtigungsmatrix

Systemadmins können Portal-Konten anlegen und deaktivieren, Passwörter zurücksetzen, Gruppen und Mandantenfreigaben verwalten und Mandanten-Tasks in der Web-App auslösen. Benutzer benötigen dafür keinen eigenen Semaphore-Login. Die App verwendet serverseitig das hinterlegte Semaphore-Service-Token; dessen Rechte begrenzen alle API-Operationen.

## Einrichtung

1. Unter **Benutzer & Gruppen** Portal-Konten anlegen, aktivieren/deaktivieren und Passwörter zurücksetzen; Gruppen anlegen und ihre Mitglieder pflegen. Nach einem Passwortreset sind bisherige Sitzungen ungültig.
2. Unter **Tenants → Tenant öffnen → Zuweisen** Benutzer oder Gruppe dem Mandanten zuordnen.
3. Unter **Berechtigungsmatrix** den Tenant und sein Task Template auswählen. Dem Benutzer oder der Gruppe **Nur sehen** oder **Sehen, starten, abbrechen** zuweisen.
4. Im Tenant die Task-Policy prüfen. Die Policy bestimmt die erlaubten Variablen, Werte, Standardwerte und Laufzeitgrenzen. Tenant, Task-Freigabe und Policy müssen aktiv sein.
5. Im **Benutzerportal → Meine Projekte → Projekt → Task** die Werte auswählen und starten. Status, Live-Logs und Abbruch sind im Portal verfügbar; die Historie zeigt die im Portal registrierten Ausführungen.

Schritt 6 des Tenant-Wizards kann Tenant-Zuordnungen und die Task-Rechte initial gemeinsam als Operator-Freigabe anlegen. Eine spätere Tenant-Zuordnung außerhalb des Wizards vergibt allein noch keine Task-Rechte.

## Welche Rechte wirken?

| Ebene | Wirkung |
|---|---|
| Aktives Konto | Grundvoraussetzung für eine Anmeldung und API-Zugriff |
| `system_admin` | Zugriff auf die Verwaltungsseiten; Tenant- und Task-Rechte werden automatisch gewährt |
| Tenant-Zuordnung | Benutzer oder Gruppe darf auf diesen Mandanten zugreifen |
| Task-Recht `sehen` | Task, Formular, Status und Logs sind sichtbar |
| Task-Recht `starten` | Eine Ausführung darf mit durch die Policy erlaubten Variablen gestartet werden |
| Task-Recht `abbrechen` | Eine zugängliche Ausführung dieses Templates darf abgebrochen werden, auch wenn sie ein anderer Benutzer gestartet hat |
| Aktiver Tenant und aktive Task-Policy | Zusätzlich erforderlich für Formular und Task-Start, auch für Systemadmins |

Benötigte Rechte können direkt oder über Gruppen kommen und addieren sich. Es gibt keine expliziten Verbote. Wird eine direkte Freigabe entfernt, kann eine Gruppenfreigabe weiterhin Zugriff erlauben. Ohne Tenant-Zuordnung reichen Task-Rechte allein nicht aus. Auch globale Rollen wie `operator` ersetzen keine Tenant-Zuordnung oder Task-Freigabe.

`viewer`, `operator` und `tenant_admin` sind als Rollen vorhanden. Bei der initialen Wizard-Vergabe erhalten Viewer Leserechte und Operatoren/Tenant-Admins zusätzlich Start-/Abbruchrechte. Im laufenden Betrieb entscheiden die gespeicherten einzelnen Task-Freigaben. Die Rolle **Tenant Admin** hat derzeit keine eigene delegierte Verwaltungsoberfläche; die Admin-API verlangt `system_admin`.

## Abgrenzung zu Semaphore und Anwendungen

Portal-Konten sind keine Semaphore-Konten. Eine Synchronisierung von Semaphore-Benutzern, dessen Teams/SSO oder Benutzerkonten innerhalb von AzubiOrga/WordPress ist nicht implementiert. Solche Konten bleiben unabhängig. Ebenso zeigt die Portal-Historie keine automatisch importierte Gesamthistorie aller direkt in Semaphore gestarteten Tasks.

Ein Bearbeitungsdialog für Anzeigename und globale Portalrollen bestehender Benutzer fehlt noch; dafür existiert bereits die Admin-API. Konten werden über die Oberfläche deaktiviert, nicht endgültig gelöscht. E-Mail-Adressen lassen sich derzeit nicht nachträglich ändern.

Die Matrix steuert den Zugriff auf Tasks. Welche Anwendungen, Provider und Testdaten ein Task verwenden darf, steuert seine Variablen-Policy. Der Deployment-Stack prüft anschließend die fachliche Kompatibilität der gewählten Kombination.
