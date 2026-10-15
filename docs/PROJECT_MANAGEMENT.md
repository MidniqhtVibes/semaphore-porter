# Direkte Semaphore-Verwaltung

Die Web-App verwaltet unter **Administration → Semaphore-Projekte** die tatsächlichen Projekte der konfigurierten Semaphore-Instanz. Alle externen Schreiboperationen laufen über das Backend und benötigen die Portalrolle `system_admin`. Die Portal-Mitgliedschaft `tenant_admin` ersetzt diese Systemberechtigung nicht.

## Vorhandenes Projekt bearbeiten

1. Unter **Semaphore** Server-URL und Service-Token prüfen und speichern.
2. Unter **Semaphore-Projekte** das Projekt öffnen.
3. Variablengruppen, Repositories, Inventories, Task Templates und SSH-/Login-Zugänge öffnen oder hinzufügen. Die Ressourcenlisten zeigen ihre Semaphore-IDs für die Zuordnung in Templates und Inventories.
4. Änderungen prüfen und anschließend in Semaphore speichern. Ressourcen werden einzeln gespeichert; es gibt keine Transaktion über mehrere externe Änderungen.

Variablengruppen bieten separate Felder für `tenant_slug` und `runtime_scope_id`. Beide stehen ausschließlich im Extra-Variables-JSON der Gruppe `Semaphore-Defaults`; die Schreibweise `Semaphore-Default` wird ebenfalls erkannt. Sie dürfen weder in anderen Gruppen noch als Survey- oder Secret-Override gesetzt werden. Beim Ändern eines verknüpften Portal-Tenants wird dessen lokale Tenant-Kennung mitgeführt.

Eine Änderung dieser Kennungen migriert keine bereits laufenden Deployments, Docker-Ressourcen oder Vault-Daten. Insbesondere bleibt die bisherige Ownership alter Deployments erhalten.

Die übrigen Variablen und Ressourcen lassen sich als JSON bearbeiten. Bei Task Templates werden mehrere Gruppen über `environment_ids` zugeordnet. Nach Änderungen eines bereits im Portal registrierten Templates wird dessen Portal-Freigabe deaktiviert, bis die Policy geprüft und erneut gespeichert wurde. Neue Templates zunächst in der Tenant-Detailansicht synchronisieren.

## Neuen Tenant aus einer Projektkopie anlegen

1. Quellprojekt öffnen und **Als neuen Tenant duplizieren** wählen. Dabei wird eine unveränderte Projektvorlage gespeichert.
2. Im Wizard neuen Projektnamen, Tenant-ID und Runtime-Scope ausdrücklich festlegen. Tenant-ID und Scope müssen sich von den Werten der Quell-Defaults unterscheiden.
3. Im Ressourcenschritt Variablengruppen, Repository/Branch, Inventories und Template-Zuordnungen auf der Kopie bearbeiten. **Ressourcen übernehmen** anklicken und danach die Auswahl prüfen.
4. Presets und Portalzugriffe zuweisen, validieren und die Projektanlage bestätigen.
5. Im erstellten Projekt SSH-/Vault-Zugänge neu setzen, die Zuordnungen und Policies prüfen und den Portal-Tenant anschließend aktivieren.

Der Kopiervorgang schreibt beide Kennungen in eine einzelne Defaults-Gruppe, entfernt kopierte Kennungen aus anderen Gruppen sowie aus Surveys und ordnet Defaults den ausgewählten Tasks zu. Nicht ausgewählte Variablengruppen werden entfernt, auch bei vollständig leerer Auswahl. Zeitpläne, Webhooks, Autorun und eingebettete Cron-Werte werden deaktiviert. Das Quellprojekt bleibt unverändert.

Gespeicherte Entwürfe können auf der ersten Wizard-Seite fortgesetzt werden. Ein Vorlagenwechsel beginnt einen neuen Vorgang. Nach einem unklaren Restore wird zunächst nach dem exakten Projektnamen gesucht; ein erneuter Restore bei nachgewiesenem Fehlen benötigt eine separate Bestätigung. Während eines noch laufenden Restore-Aufrufs ist keine sofortige Wiederholung erlaubt. Gleichnamige Projekte nach einem Timeout müssen vor der Übernahme auch betrieblich eindeutig dem Vorgang zugeordnet sein.

## Stack-Variablen

Die Initial-Policies berücksichtigen die Surveys des Projekts:

- `application_id`, `database_type`, `existing_environment_policy` und `dataset_id`: erlaubte Werte aus dem jeweiligen Survey.
- `ttl_minutes`: 5–1440 Minuten entsprechend dem aktuellen Deployment-Stack.
- `host_port`: automatisch `0` zur Portvergabe durch den Stack.
- `application_release_id`, `pdf_api_release_id`: Survey-Enums oder validierte Image-Tags.
- `send_deployment_mail`, `mail_user`: Mail-Schalter und Empfängeradresse.

Anwendung und Datenbanktyp werden nicht mehr pauschal auf eine einzelne Anwendung fixiert. Die Kombinationen aus Programm, Provider und Datensatz prüft weiterhin der Plan-Compiler des Deployment-Stacks; die Semaphore-Surveys allein enthalten keinen vollständigen relationalen Programmkatalog.

Vault-Pfade wie `vault_tenant_secret_root`, `vault_provider_secret_paths`, `vault_program_secret_paths` und `vault_tenant_secret_paths` bleiben editierbar. Für neue Mandanten müssen bestehende explizite Pfad-Overrides ebenfalls auf den neuen Mandanten angepasst werden.

## Zugangsdaten und Löschung

Bestehende geschützte Werte werden nicht an den Browser zurückgegeben. Änderungen normaler Variablen behalten bestehende geheime Werte bei. Neue Geheimnisse werden über separate Eingaben direkt an Semaphore geschrieben; Entwürfe und Auditdetails enthalten diese Werte nicht. Beim Duplizieren werden Vault-Bootstrap-Zugangsdaten und private Key-Inhalte nicht kopiert und müssen für den neuen Mandanten neu gesetzt werden. Vault-AppRoles, Vault-Inhalte und Zielhosts müssen bereits bereitgestellt sein; ihre externe Provisionierung erfolgt nicht über die Semaphore-API.

Für den vorliegenden Stack in `Vault-Access` die AppRole Role ID als geschützte Extra Variable `vault_approle_role_id` (Typ `var`) und die Secret ID als geschützte Prozessvariable `ANSIBLE_HASHI_VAULT_SECRET_ID` (Typ `env`) setzen. Adresse, Mounts und Tenantwurzel bleiben normale editierbare Variablen.

**Semaphore-Projekt endgültig löschen** löscht tatsächlich das Remote-Projekt und erfordert dessen exakten Namen. Ein verknüpfter Portal-Tenant wird deaktiviert. Bereits gestartete Docker-Deployments werden dadurch nicht gelöscht. Die bisherige Funktion **Portal-Tenant entfernen** entfernt dagegen weiterhin nur die lokale Portalzuordnung.

Der Editor prüft vor dem Schreiben, ob sich die geladene Remote-Konfiguration geändert hat. Diese Prüfung reduziert Konflikte; die Semaphore-API stellt dafür keine atomare bedingte Änderung über mehrere Aufrufe bereit. Bei einem unklaren Schreibfehler zuerst neu laden und den tatsächlichen Zustand prüfen.

## Abnahme

Automatisierte Tests nutzen simulierte Semaphore-Antworten. Vor Produktivbetrieb sind Backup-/Restore-Format, Mehrfachzuordnung von Variablengruppen, Secret-Operationen, SSH-Zugänge und Projektlöschung gegen die eingesetzte Semaphore-Version in einer Testinstanz zu prüfen. Die Implementierung orientiert sich an der offiziellen Semaphore-API und unterstützt moderne `environment_ids` sowie vorhandene Backup-Referenzen über Namen.

API-Referenz: [Semaphore OpenAPI](https://github.com/semaphoreui/semaphore/blob/develop/api-docs.yml).
