## Zusammenspiel der Freigaben

Die Portalrolle beschreibt die grundsätzliche Zuständigkeit. Für konkrete Ausführungen kommen die Tenant-Zuordnung, die Task-Rechte und eine aktive Variablen-Policy hinzu.

| Portalrolle | Einordnung |
| --- | --- |
| Systemadmin | Verwaltet die Installation und besitzt die administrativen Portalrechte. |
| Tenant-Admin | Kennzeichnet die Verwaltung eines zugeordneten Tenants; die einzelnen Verwaltungsoberflächen können weiterhin Systemadmins vorbehalten sein. |
| Operator | Führt ausdrücklich freigegebene Aufgaben aus. |
| Viewer | Nutzt ausdrücklich freigegebene lesende Ansichten. |

Eine Rollenbezeichnung allein garantiert keinen Zugriff auf einen bestimmten Tenant oder Task. Direkte Freigaben und Gruppenfreigaben ergänzen sich. Ein entzogener direkter Zugriff kann über eine weiterhin bestehende Gruppe erhalten bleiben.

## Rechte prüfen

1. Prüfen lassen, ob das Konto aktiv und dem richtigen Tenant zugeordnet ist.
2. Für den betroffenen Task die Rechte **sehen**, **starten** und gegebenenfalls **abbrechen** kontrollieren lassen.
3. Den Aktivierungszustand von Tenant, Task und Policy prüfen lassen.
4. Bei einer angeforderten Genehmigung deren Status beachten. Eine Zustimmung erweitert die allgemeinen Rechte nicht.

Die Portal-Anmeldung, der Semaphore-Service-Token, eine SSH-Anmeldung am Zielhost und eine Vault-AppRole sind getrennte Zugänge. Ein erfolgreiches Portal-Login bestätigt keine Rechte in den anderen Systemen.
