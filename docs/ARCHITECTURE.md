# Architektur und Sicherheitsmodell

## Komponenten

`frontend` erzeugt eine statische React-SPA. Nginx liefert sie aus, leitet `/api/` an FastAPI weiter und deaktiviert für den Live-Run-Stream das Proxy-Buffering. `backend` enthält REST-API, Autorisierung, Policy Engine, Semaphore-Client, Audit und Creation-Job-Orchestrierung. `postgres` speichert Portalzustand, verschlüsselte Integrationsdaten und Historie.

Das interne Docker-Netz verbindet alle drei Dienste. Nur das Backend hängt zusätzlich am Egress-Netz, nur das Frontend am Edge-Netz. Damit ist PostgreSQL weder vom Host noch über das Egress-Netz erreichbar.

## Vertrauensgrenzen

Der Browser gilt als nicht vertrauenswürdig. Er erhält interne Portal-UUIDs, aber keine frei wählbaren Semaphore-Projekt- oder Template-IDs für schreibende Aufrufe. Jeder Tenant-, Task- und Run-Endpunkt lädt das Objekt serverseitig und prüft Benutzerstatus, Rolle, direkte beziehungsweise gruppenbasierte Mitgliedschaft und Task-Berechtigung erneut.

Die dynamischen Formulare sind Komfort, keine Sicherheitsgrenze. Vor jedem Semaphore-Task-Start validiert die Policy Engine:

1. ausschließlich bekannte Variablennamen,
2. exakten Datentyp und Wertebereich,
3. Enum-Mitgliedschaft, Länge und optionale Regex,
4. serverseitige Fixed/Hidden-Werte,
5. das Fehlen von clientseitigen Überschreibungsversuchen.

Erst das validierte Ergebnis wird als Semaphore-`environment` serialisiert.

## Authentifizierung

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

## Datenmodell

Zentrale Entitäten sind `users`, `roles`, `groups`, `tenants`, `semaphore_projects`, `task_templates`, `task_policies`, `variable_rules`, `task_permissions`, `task_runs`, `creation_jobs`, `project_templates`, `presets`, `portal_sessions` und `audit_events`. Fremdschlüssel und Unique-/Check-Constraints sichern die wichtigsten Invarianten zusätzlich zur Anwendungsschicht ab.

Schemaänderungen gehören ausschließlich in neue Alembic-Revisionsdateien. Das initiale Schema liegt unter `backend/alembic/versions/`.
