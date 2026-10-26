# Architektur und Sicherheitsmodell

## Komponenten

`gateway` ist ein optionales Caddy-TLS-Gateway innerhalb derselben Compose-Datei. `frontend` enthält die statische React-SPA; Nginx liefert sie aus, leitet `/api/` an FastAPI weiter und deaktiviert für den Live-Run-Stream das Proxy-Buffering. `backend` enthält REST-API, Autorisierung, Policy Engine, Semaphore-Client, Audit und Creation-Job-Orchestrierung. `postgres` speichert Portalzustand, verschlüsselte Integrationsdaten und Historie.

Die Dienste sind über getrennte Docker-Netze gekoppelt:

- `portal_edge`: ausschließlich Gateway und Frontend
- `portal_application`: ausschließlich Frontend und Backend
- `portal_database`: ausschließlich Backend und PostgreSQL
- `portal_backend_egress`: externer Zugriff nur für das Backend, insbesondere zur Semaphore API
- `portal_gateway_egress`: externer Zugriff nur für Caddy, insbesondere für ACME
- `portal_frontend_ingress`: separate nicht-interne Bridge für die Host-Portfreigabe des Frontends (standardmäßig Loopback); ermöglicht auch ausgehenden Netzwerkzugriff, besitzt jedoch keine Verbindung zur Datenbank

Die drei internen Netze besitzen keinen externen Egress. PostgreSQL und Backend veröffentlichen keine Host-Ports. Das Frontend bindet für die Anbindung eines vorhandenen Host-Reverse-Proxys nur an Loopback; bei aktiviertem TLS-Profil ist Caddy der öffentliche Einstiegspunkt.

Die zusätzliche Frontend-Bridge ist für die Host-Portveröffentlichung erforderlich: Auf der lokal geprüften Docker Engine 29.5.3 wurde die angeforderte Portbindung bei ausschließlich internen Netzen nicht eingerichtet. Datenbank- und Anwendungsnetz bleiben intern.

## Build- und Deployment-Grenze

GitHub Actions testet Backend und Frontend vor dem Image-Build. Nur erfolgreiche Pushes auf `main` beziehungsweise Versionstags veröffentlichen die Images nach GHCR. Die produktive Compose-Datei enthält für die Anwendung ausschließlich `image:`-Referenzen und keine `build:`-Kontexte. Deshalb benötigt der Zielserver weder Quellcode noch Python-, Node- oder .NET-Toolchains.

Beide Anwendungsimages verwenden denselben Release- oder Commit-Tag. Damit wird verhindert, dass Frontend und Backend versehentlich aus unterschiedlichen Revisionen kombiniert werden. PostgreSQL-Daten, Caddy-Zertifikate und Caddy-Zustand liegen in benannten Volumes; die Portal-Konfiguration und Secrets liegen in der nur lokal vorhandenen `.env`.

## Vertrauensgrenzen

Der Browser gilt als nicht vertrauenswürdig. Das Benutzerportal verwendet interne Portal-UUIDs und keine frei wählbaren Semaphore-Projekt- oder Template-IDs für Taskstarts. Jeder Tenant-, Task- und Run-Endpunkt lädt das Objekt serverseitig und prüft Benutzerstatus, Rolle, direkte beziehungsweise gruppenbasierte Mitgliedschaft und Task-Berechtigung erneut.

Die direkte Projektverwaltung unter `/api/admin/semaphore/projects` verwendet hingegen die tatsächlichen Semaphore-Ressourcen-IDs und ist ausschließlich Systemadministratoren zugänglich. Ressourcentypen und schreibbare Felder sind serverseitig begrenzt. Vor einer Änderung wird die geladene Revision geprüft; eine Projektlöschung benötigt zusätzlich den exakten Projektnamen. Details stehen in [PROJECT_MANAGEMENT.md](PROJECT_MANAGEMENT.md).

Die dynamischen Formulare sind Komfort, keine Sicherheitsgrenze. Vor jedem Semaphore-Task-Start validiert die Policy Engine:

1. ausschließlich bekannte Variablennamen,
2. exakten Datentyp und Wertebereich,
3. Enum-Mitgliedschaft, Länge und optionale Regex,
4. serverseitige Fixed/Hidden-Werte,
5. das Fehlen von clientseitigen Überschreibungsversuchen.

Erst das validierte Ergebnis wird als Semaphore-`environment` serialisiert.

## Authentifizierung

Die GitLab-Integration ergänzt ausschließlich Admin-APIs. Projektbezogene Tokens liegen verschlüsselt in PostgreSQL. Paketentwürfe frieren Basis-SHA und Dateisnapshot ein; Versionen und persistierte Sperren schützen die Übergabe. Repository-Code wird nicht im Backend ausgeführt. Ein lokaler, geprüfter Compiler validiert deklarative Verträge. GitLab-CI und menschlicher Review gehen der ausdrücklichen Aktivierung eines Katalogstandes voraus. Diese erzeugt eine separate Projektvorlage mit fester Git-SHA; bestehende Tenants bleiben unverändert. Ablauf und Grenzen: [GitLab](GITLAB.md).

- Passwörter: Argon2 über `pwdlib`
- Session: kryptografisch zufälliger, opaker Wert; nur SHA-256-Hash in der Datenbank
- Cookie: `HttpOnly`, `SameSite=Lax`, in Produktion `Secure`
- schreibende Requests: sitzungsgebundenes CSRF-Token im Header
- Login: Origin-Prüfung und datenbankgestützte Limitierung fehlgeschlagener Versuche
- Passwortwechsel: widerruft andere aktive Sitzungen

## Secrets

Der Semaphore-Service-Token wird mit Fernet verschlüsselt. Der Schlüssel liegt ausschließlich in der Laufzeitkonfiguration. Token, Sessionwerte und secret-verdächtige Felder werden nicht in API-Antworten oder Auditdetails aufgenommen. Presets mit typischen Secret-Schlüsseln werden abgelehnt.

Der Fernet-Key muss bei Backup, Restore und Update erhalten bleiben. Eine Rotation erfordert eine kontrollierte Neuverschlüsselung des gespeicherten Tokens; bloßes Ersetzen des Keys macht den bestehenden Ciphertext unlesbar.

## Semaphore-Client

- TLS-Verifikation bleibt aktiv.
- Bearer-Token wird nur an die konfigurierte Semaphore-Origin gesendet.
- Nur GET darf begrenzt sicheren, gleich-originigen Redirects folgen.
- POST wird bei Redirects oder unklarem Transportfehler nicht automatisch wiederholt.
- Timeouts und optionaler HTTP(S)-Proxy sind konfigurierbar.
- Projektlisten werden sowohl als Array als auch in den bekannten umschließenden Antwortformen tolerant gelesen.

Die verwendeten API-Operationen entsprechen dem offiziellen Semaphore-UI-OpenAPI-Schema: Projekt-Backup/Restore, Projekt-Templates, Task-Start, Task-Status, Ausgabe und Stop.

## Restore und Idempotenz

Vor dem externen Restore wird der Creation Job mit Idempotency-Key persistiert. Nach einem eindeutigen Erfolg wird die stabile Semaphore-Projekt-ID gespeichert. Bei einem Timeout oder nicht eindeutigem Ergebnis wechselt der Job in `verification_required`; ein weiterer Restore wird erst nach exakter Projektnamensuche und bewusster Bestätigung zugelassen. So wird ein blindes POST-Retry vermieden.

Die gespeicherte Projektvorlage bleibt unverändert. Tenant-spezifische Anpassungen erfolgen auf einer tiefen Kopie und werden vor dem Restore strukturell validiert.

## Vault-Provisionierung

Die optionale Integration verwendet einen separaten create-only-KV-v2-Client und einen aus Stack-Manifesten exportierten Katalog. Nur Systemadministratoren können die Verbindung, AppRole-Zugänge und zentralen Registry-Passwörter verwalten. `vault_settings` speichert die gesamte Konfiguration verschlüsselt mit dem vorhandenen Fernet-Key. API-Antworten enthalten nur öffentliche Konfiguration und Belegt-Flags.

Creation Jobs speichern den öffentlichen Zielplan, Metadatenbelege und eine temporäre verschlüsselte Ausführungspayload. Eine Datenbank-Lease sperrt parallele Ausführungen desselben Jobs auch über Commit-Grenzen hinweg. Sämtliche Zielmetadaten werden vor dem ersten Write geprüft; `cas=0` verhindert Überschreiben bei konkurrierender Anlage. Vault und Semaphore bilden keine gemeinsame Transaktion. Bei unklaren Ergebnissen bleibt der Job angehalten, bis ein Administrator den tatsächlichen Ausgang geprüft hat. Nach vollständiger Anlage und Credential-Übergabe wird die Job-Payload gelöscht.

Der Vault-Client folgt keinen Redirects, prüft TLS und schreibt keine Payloads oder Serverantworten in Fehlermeldungen. FastAPI-Validierungsfehler geben abgewiesene Eingabewerte nicht zurück. Vault-Policies, AppRoles und Secret-IDs werden vom Portal nicht erzeugt oder geändert. Details stehen in [VAULT_IMPLEMENTIERUNG.md](VAULT_IMPLEMENTIERUNG.md).

## Datenmodell

Zentrale Entitäten sind `users`, `roles`, `groups`, `tenants`, `semaphore_projects`, `task_templates`, `task_policies`, `variable_rules`, `task_permissions`, `task_runs`, `creation_jobs`, `project_templates`, `presets`, `portal_sessions` und `audit_events`. Fremdschlüssel und Unique-/Check-Constraints sichern die wichtigsten Invarianten zusätzlich zur Anwendungsschicht ab.

Schemaänderungen gehören ausschließlich in neue Alembic-Revisionsdateien. Das initiale Schema liegt unter `backend/alembic/versions/`.
