# Zentrale SSH-Zugangsprofile

Semaporter kann einen vorhandenen Deployment-Schlüssel in mehreren neuen Tenant-Projekten wiederverwenden. Vault bleibt die Quelle der privaten Schlüssel. Semaporter speichert Profile, geprüfte Versionen, öffentliche Fingerprints und Projektzuordnungen. Die benötigten Kopien liegen nach der Übertragung im Semaphore-Key-Store.

Unter **Einstellungen → Zugangsprofile** werden ein eigener Vault-Lesezugang und die Profile eingerichtet. Die vorhandene Vault-Konfiguration für neue Tenant-Anwendungssecrets bleibt davon unabhängig. Eine Semaphore-Pro-Lizenz und eine Änderung der Zielhosts sind für die Wiederverwendung eines dort bereits autorisierten Schlüssels nicht erforderlich.

## Voraussetzungen und Update

- Backend und Frontend aus demselben aktuellen Stand verwenden. Die Backend-Startmigration `20261029_0006` ergänzt Tabellen und optionale Felder; vorhandene Benutzer, Tenants und Jobs bleiben erhalten.
- Bestehenden `PORTAL_FERNET_KEY` erhalten und zusammen mit der Datenbank sichern. Damit werden auch die Zugangsdaten des neuen Profil-Lesezugangs geschützt.
- Vault muss vom Backend mit gültiger TLS-Zertifikatskette erreichbar sein. Für die neue Verbindung gelten ebenfalls `VAULT_CA_BUNDLE` und `VAULT_REQUEST_TIMEOUT_SECONDS`.
- Benötigte Proxy-Ausnahmen und CA-Dateien administrativ bereitstellen. Die Profilverwaltung ändert keine Server-, Runner- oder Pipeline-Konfiguration.
- Den ursprünglichen privaten SSH-Schlüssel kennen. Ein öffentlicher Schlüssel oder eine maskierte Anzeige in Semaphore genügt nicht.

## 1. Schlüssel in der Vault-GUI hinterlegen

Im vorhandenen KV-v2-Mount, beispielsweise `kv`, ein Objekt anlegen:

```text
automation-credentials/ssh/testhost
```

Felder:

| Schlüssel | Wert |
|---|---|
| `private_key` | Vollständiger privater OpenSSH-/PEM-Schlüssel mit echten Zeilenumbrüchen einschließlich BEGIN-/END-Zeilen |
| `passphrase` | Passphrase, falls benötigt; sonst leer oder Feld weglassen |

Die neue Version merken, zunächst üblicherweise `1`. Unterstützt werden Ed25519, RSA ab 2048 Bit und ECDSA. Der SSH-Benutzer wird im Profil festgelegt.

Ein getrenntes Objekt für lesenden Git-Zugriff kann beispielsweise `automation-credentials/git/deployment-read` heißen. Dieselben privaten Schlüssel für verschiedene Zwecke sind nicht erforderlich. Host- und Git-Profile werden getrennt zugeordnet.

Die Objekte liegen außerhalb von `semaphore/*`. Die bestehende breite Semaphore-Leserolle erhält dadurch keinen zusätzlichen Zugriff auf Infrastruktur-Schlüssel.

## 2. Eigene Profil-Leserolle in Vault einrichten

Die bisherigen Rollen für Tenant-Anlage und Anwendungssecrets behalten ihre Rechte. Ein Vault-Administrator erstellt eine zusätzliche Policy, beispielsweise `semaporter-profile-reader`, unter **Policies → ACL Policies → Create ACL Policy**:

```hcl
path "kv/data/automation-credentials/ssh/testhost" {
  capabilities = ["read"]
}

path "kv/data/automation-credentials/git/deployment-read" {
  capabilities = ["read"]
}
```

Nur tatsächlich benötigte Pfade freigeben. Der Zugriff auf eine konkrete KV-Version erfolgt über denselben Datenpfad. Die Profil-Leserolle benötigt weder Schreiben noch `list` oder Metadatenzugriff.

Im vorhandenen AppRole-Mount, hier beispielhaft `semaphore-ansible`, die Rollen zuerst in der Vault-Browserkonsole anzeigen:

```text
list auth/semaphore-ansible/role
```

Nur wenn der Rollenname unbenutzt ist, eine eigene Rolle erstellen. Dieses Beispiel verwendet eine wiederholt nutzbare Secret-ID mit 30 Tagen Laufzeit; den Wert an eure Betriebsvorgaben anpassen:

```text
write auth/semaphore-ansible/role/semaporter-profile-reader bind_secret_id=true token_policies=semaporter-profile-reader secret_id_ttl=720h secret_id_num_uses=0 token_ttl=1h token_max_ttl=4h token_num_uses=0
```

Role-ID auslesen und eine Secret-ID erzeugen:

```text
read auth/semaphore-ansible/role/semaporter-profile-reader/role-id
```

```text
write -force auth/semaphore-ansible/role/semaporter-profile-reader/secret-id
```

`role_id` und `secret_id` geschützt übernehmen, nicht den `secret_id_accessor`. Jede Ausführung des zweiten Befehls erzeugt eine zusätzliche Secret-ID. Semaporter erneuert diese nicht automatisch; rechtzeitig eine gültige ID nachtragen. Eine vorhandene Rolle nicht ungeprüft mit dem Beispiel überschreiben.

## 3. Verbindung in Semaporter konfigurieren

Unter **Einstellungen → Zugangsprofile → Vault-Lesezugang für SSH-Profile**:

| Feld | Beispiel |
|---|---|
| Vault-URL des Schlüsselspeichers | `https://vault.example.internal` ohne `/v1` |
| Vault-Namespace | leer, sofern nicht verwendet |
| KV-v2-Mount für SSH-Profile | `kv` |
| AppRole-Auth-Mount | `semaphore-ansible` ohne `auth/` und ohne Rollenname |
| Profil-Lesezugang: Role-ID | Role-ID der eigenen Profil-Leserolle |
| Profil-Lesezugang: Secret-ID | Gültige Secret-ID derselben Rolle |

**Lesezugang speichern**, anschließend **Gespeicherten Lesezugang testen**. Der Verbindungstest meldet die Rolle an. Ein Profiltest prüft zusätzlich Secret-Leserechte, Version, Schlüssel und Passphrase.

Leere Zugangsfelder behalten vorhandene Werte. Die Werte werden nicht zurückgegeben. Nach erster Projektverwendung bleiben Serveradresse, Namespace und Mounts fest; Role-ID und Secret-ID können weiterhin ersetzt werden.

## 4. Hostprofil anlegen

**Profil hinzufügen** auswählen:

| Feld | Beispiel |
|---|---|
| Profilname | Testhost – Deployment |
| Verwendungszweck | SSH zum Zielhost |
| SSH-Benutzer | Der tatsächlich auf dem Ziel verwendete technische Benutzer |
| Vault-Version | `1` |
| Logischer Vault-Pfad | `automation-credentials/ssh/testhost` |
| Freigegebene Ziele | Konkrete IP oder DNS-Name je Zeile |

Wenn das Inventory einen Alias mit `ansible_host=10.0.0.10` enthält, gehört `10.0.0.10` in die Liste. Statische INI- und YAML-Inventories werden geprüft; Hostbereiche, dynamische Inventories und nicht auflösbare Vorlagenvariablen benötigen eine manuelle Einrichtung. Ein expliziter SSH-Benutzer im Inventory muss zum Profil passen.

Speichern und **Profil prüfen** anklicken. Nach erfolgreicher Prüfung zeigt Semaporter den öffentlichen Schlüssel und Fingerprint. Der private Inhalt wird nicht angezeigt. Ein erfolgreicher Profiltest bestätigt noch keinen tatsächlichen SSH-Zugriff auf den Zielhost.

Für Git ein eigenes Profil mit Zweck **Git-Repository über SSH** erstellen. Als freigegebene Ziele vollständige SSH-Repository-URLs angeben, beispielsweise `git@git.example:gruppe/deployment.git`. Der öffentliche Schlüssel benötigt dort eine passende, üblicherweise lesende Deploy-Key-Freigabe. HTTPS-Repository-Zugänge mit Benutzer/Token sind keine SSH-Profile.

## 5. Neues Tenant-Projekt erstellen

Im Tenant-Assistenten unter **Schritt 4 → Zentrale SSH-Zugangsprofile**:

1. Bei jedem betreffenden Inventory das Hostprofil wählen.
2. Bei einem SSH-Repository das Git-Profil wählen.
3. Sonstige Zugänge ausdrücklich manuell konfigurieren, insbesondere Become-Passwörter und HTTPS-Git-Zugänge.
4. Weitergehen und validieren. Die Vorschau zeigt Profile, Vault-Versionen, Fingerprints und Ziele. Die Validierung schreibt keine Schlüssel nach Semaphore.
5. **Projekt verbindlich erstellen**. Nach dem Projekt-Restore werden die Schlüssel in dessen vorgesehene Key-Store-Einträge geschrieben und die tatsächlichen Ressourcen-Zuordnungen erneut geprüft.

Mehrere Projekte dürfen dasselbe Profil verwenden. Auf dem Zielserver genügt weiterhin dessen bereits autorisierter öffentlicher Schlüssel. Semaporter verteilt keine `authorized_keys`, verändert keine SSH-Konten und startet durch die Projektanlage keinen Deployment-Task.

Ohne Profilauswahl bleibt der bisherige manuelle Ablauf möglich. Bestehende Projekte mit manuell gesetzten Schlüsseln werden nicht automatisch erfasst oder übernommen.

## 6. Wiederaufnahme und Rotation

Ein gestarteter Vorgang behält seine geprüfte Version. Bei einem Übertragungsfehler wird derselbe bekannte Key-Store-Eintrag erneut per PUT gesetzt; kein zusätzliches Projekt oder Schlüsselpaar wird erzeugt. Der Vorgang bleibt bis zum erfolgreichen Abschluss unvollständig. Eine gesperrte Profilfreigabe oder ein nicht mehr erlaubtes Ziel blockiert die Wiederaufnahme. Benötigte alte Vault-Versionen bis zum Abschluss offener Vorgänge erhalten.

Für eine Rotation:

1. Neuen Schlüssel als neue Vault-Version hinterlegen und den öffentlichen Schlüssel auf den Zielen zusätzlich autorisieren.
2. Im Profil die gewünschte Vault-Version speichern und **Profil prüfen** ausführen.
3. Unter **Projektverwendungen und Rotation** die betroffenen Projekte prüfen. Es erfolgt keine automatische Verteilung durch das Speichern des Profils.
4. Je Projekt **Version übernehmen** und die konkrete Änderung bestätigen. Die verwaltete Schlüssel-ID bleibt erhalten. Geänderte Ressourcen oder Zuordnungen werden nicht still überschrieben.
5. Den Zugriff über einen geeigneten, unschädlichen Semaphore-Prüftask kontrollieren. Eine erfolgreiche API-Übertragung allein bestätigt keine SSH-Anmeldung.
6. Erst nach vollständiger Umstellung den alten öffentlichen Schlüssel von Zielhosts beziehungsweise GitLab entfernen. Andere, außerhalb dieser Verwaltung liegende Verwendungen ebenfalls berücksichtigen.

Die Profilverbindung und die Zuordnung zum Vault-Objekt bleiben bei verwendeten Profilen fest. Zum Wechsel von Benutzer, Zweck oder Vault-Pfad ein neues Profil anlegen. Eine Zuordnung gehört außerdem zur ursprünglichen Semaphore-Instanz; nach Änderung ihrer Server-URL wird die Schlüsselverteilung blockiert. Zentrale Schlüssel können nicht über den normalen Projekteditor überschrieben werden. Profilverwaltung und Rotation sind Systemadministratoren vorbehalten.

Das Sperren eines Profils verhindert neue Zuordnungen, Wiederaufnahmen und Aktualisierungen. Es widerruft bereits kopierte SSH-Zugänge nicht und stoppt keine laufenden Tasks. Zur wirksamen Sperrung den öffentlichen Schlüssel am Ziel entfernen und gegebenenfalls betroffene Tasks beziehungsweise Tenant-Freigaben deaktivieren.

## Prüfungen

- Mehrere neue Projekte erhalten denselben ausgewählten Schlüssel, jeweils unter ihren eigenen Semaphore-Key-IDs.
- Fremde Ziele, falsche SSH-Benutzer, falscher Profilzweck und nicht verfügbare Vault-Versionen werden abgelehnt.
- Private Schlüssel und Passphrasen erscheinen nicht in API-Antworten, Entwürfen, Datenbankprofilen, Projektvorlagen oder Auditdaten.
- Ein Fehler nach dem Restore ist ohne zweiten Restore und ohne Versionswechsel wiederaufnehmbar.
- Rotation benötigt Bestätigung, aktualisiert einen bekannten Eintrag und wird bei veränderter Zielzuordnung blockiert.
- Anmeldung in Vault, Lesen/Prüfen eines Schlüssels, Übertragung nach Semaphore und tatsächlicher SSH-Zugriff werden getrennt überprüft.
