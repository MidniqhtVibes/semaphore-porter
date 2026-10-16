# Vereinbartes Zielbild und Arbeitsauftrag: Vault-Integration

Stand: 16.10.2026. Diese Spezifikation hält die im Gespräch vereinbarten
Anforderungen fest. Der tatsächliche Implementierungs- und Prüfstand wird am
Ende dieser Datei nachgeführt. Die frühere `VAULT_BEWERTUNG.md` bleibt als
Recherche erhalten; bei abweichenden Vorschlägen gilt diese Vereinbarung.

## Auftrag und Grenzen

- Den bestehenden Semaphore-Porter um das automatische Anlegen der benötigten
  Vault-KV-v2-Objekte beim Erstellen eines Tenants erweitern.
- Bestehende Web-Funktionen, Designs, Benutzerverwaltung und Task-Freigaben
  erhalten. Die Integration darf bei nicht konfiguriertem Vault weiterhin die
  bisherige Tenant-Anlage erlauben.
- Ausschließlich KV-Objekte neu anlegen. Keine Vault-Policies, AppRoles oder
  Secret-IDs automatisch verwalten, keine Rotation, Löschung oder Änderung
  bestehender Objekte.
- Das benachbarte Repository `azubiorga-semaphore-git` zur Ermittlung der
  Verträge lesen. Seine Deployment-Implementierung nicht verändern.
- Nicht selbstständig pushen. Keine echten Tenant- oder Vault-Objekte als
  automatisierte Tests anlegen. Tests arbeiten mit nachgebildeten APIs.

## Identitäten und Zugriff

Der bestehende Semaphore-Lesezugang bleibt bestehen. Seine AppRole darf aktuell
`semaphore/*` lesen. Neue Tenant-Projekte verwenden dieselbe AppRole und deren
bisherige Rechte; die Rechteverwaltung erfolgt außerhalb des Porter.

Die vorhandene Secret-ID ist in Semaphore im Bereich **Secrets** gespeichert.
Ein normaler API-Aufruf oder Projektbackup liefert ihren Inhalt nicht zurück.
Deshalb werden Role-ID und eine gültige Secret-ID einmalig geschützt im Porter
hinterlegt. Falls die bisherige Secret-ID nicht mehr bekannt ist, kann ein
Vault-Administrator eine weitere Secret-ID derselben AppRole ausstellen. Die
vorhandene Secret-ID wird dabei nicht widerrufen.

Der Porter kopiert die öffentliche `Vault-Access`-Konfiguration und ergänzt im
neuen Projekt die zentral hinterlegten Lese-Credentials als Semaphore-Secrets:

- `vault_approle_role_id`: geschützte Extra Variable;
- `ANSIBLE_HASHI_VAULT_SECRET_ID`: geschützte Prozessvariable.

Für das Schreiben nach Vault wird eine separat konfigurierte AppRole verwendet.
Sie benötigt die Anlage neuer KV-v2-Datenobjekte und das Lesen ihrer Metadaten.
Zieladresse, Mounts, Namespace und Tenantwurzel werden administrativ festgelegt.
TLS-Zertifikate werden geprüft; eine Unternehmens-CA kann serverseitig angegeben
werden. Browser dürfen keine frei wählbaren Provisionierungsziele übermitteln.

## Tenant, Anwendung und Runtime-Scope

`tenant_slug` und `runtime_scope_id` bleiben feste Werte in `Semaphore-Default`
beziehungsweise `Semaphore-Defaults`. Beide sind getrennt einzutragen und dürfen
nicht über eine Task-Survey überschrieben werden.

`runtime_scope_id` steuert Shared-Pool-Identität, Ressourcennamen, Docker-Labels,
Ownership, Claims und Cleanup. Ein Shared-Pool wird durch die Kombination
`runtime_scope_id + application_id + database_type + provider_id` identifiziert.
Unterschiedliche Tenant-Scopes trennen die Pools auf demselben Docker-Host.

Die Runtime-Scope-ID ist kein Bestandteil des Vault-Pfads. Ohne explizite
Zuordnungen lautet dieser:

```text
<Tenantwurzel>/<tenant_slug>/<Anwendungsprofil>
<Tenantwurzel>/<tenant_slug>/providers/<Providerprofil>
```

Beispiel mit `vault_kv_mount=kv` und `vault_tenant_secret_root=semaphore/tenants`:

```text
semaphore/tenants/kundenmanagement/azubiorga
semaphore/tenants/kundenmanagement/providers/postgresql-v1
```

`kv` und das API-Segment `data/` sind keine Bestandteile dieser logischen Pfade.
Explizite Quellprojekt-Zuordnungen dürfen nicht unbemerkt auf fremde oder alte
Tenantpfade führen. Der Plan zeigt die neuen Ziele; die neue Konfiguration muss
dieselben Pfade verwenden wie die Provisionierung.

## Kataloge und unterstützte Kombinationen

Grundlage sind die Manifeste, Provider-Driver und Dataset-Kataloge des lokalen
Stack-Stands `182007c`. Ein versionierter, validierter Katalog im Porter enthält
die daraus abgeleiteten Profile, Schlüssel, Anforderungen und Kompatibilitäten.
Eine dokumentierte Exportmöglichkeit soll spätere Stack-Erweiterungen übernehmen,
ohne Geheimnisse oder ausführbare Paketdateien zu importieren.

| Anwendung | Datenbank | Datasets zusätzlich zu `none` |
|---|---|---|
| AzubiOrga | PostgreSQL / `postgresql-v1` | `smoke-v1`, `public-v1` |
| WordPress | MariaDB / `mariadb-v1` | `mariadb-smoke-v1` |
| WordPress | MySQL / `mysql-v1` | `mysql-smoke-v1` |

Keine Unterstützung für weitere Kombinationen behaupten, nur weil ein Provider
global vorhanden ist. Mehrfachauswahl im Tenant bedeutet Freigabe dieser
Anwendungen, Provider und Datasets; ein einzelner Deployment-Task wählt weiterhin
eine dazu passende Kombination.

Ein neues Programmpaket benötigt Manifest, Compose/Konfiguration, Dataset-Katalog,
Eintrag in `programs/catalog.yml`, neu gerenderte Survey-Enums und Vertrags- sowie
Lifecycle-Tests. Ein vorhandener Provider muss im Anwendungsmanifest ausdrücklich
freigegeben werden. Ein vollständig neuer Provider benötigt zusätzlich Driver,
Provider-Tasks, statische Dispatcher und gegebenenfalls den Pool-Helper-Zweig.
Danach den Porter-Katalog neu exportieren und die neue Version prüfen.

## Secret-Felder und Eingabe

| Profil | Schlüssel | Herkunft |
|---|---|---|
| `azubiorga` | `registry_password` | zentral pro Anwendung hinterlegter gültiger Registry-Zugang |
| `azubiorga` | `crypto_secret`, `crypto_salt` | vorhandene Werte eingeben oder ausdrücklich generieren lassen |
| `wordpress` | `registry_password` | zentral pro Anwendung hinterlegter gültiger Registry-Zugang |
| `postgresql-v1` | `postgres_password` | eingeben oder generieren |
| `mariadb-v1` | `mariadb_password` | eingeben oder generieren |
| `mysql-v1` | `mysql_password` | eingeben oder generieren; im Stack ein Runtime-Credential-Seed |

Imageabhängig vorgegebene Crypto-Werte sind exakt zu übernehmen. Manuelle Eingabe
ist für AzubiOrga-Crypto-Werte die Voreinstellung. Eine Generierung bestätigt
nicht automatisch die Eignung für jedes Image. `crypto_salt` muss dem Manifest
entsprechen: Hex, gerade Länge, mindestens 16 Zeichen, kein Whitespace.
Providerwerte müssen 10–256 Zeichen lang sein und dürfen keine CR/LF enthalten.
Passwörter und Crypto-Werte nicht durch Trimmen verändern.

Die Registry-Konfiguration bleibt zentral pro Anwendung; gültige Tokens werden
nicht frei generiert. Das Schreiben nach KV legt keine Registry-/DB-Benutzer an
und importiert keine bereits bestehende Software oder Datenbank.

Geheimnisse gehören in passwortgeschützte Eingabefelder und werden weder in
Wizard-Entwürfen, Presets, Browser-Speicher, Auditdaten, API-Antworten noch im
validierten Projektbackup abgelegt. Zentrale Zugangsdaten und für Wiederaufnahme
benötigte Ausführungswerte werden ausschließlich serverseitig verschlüsselt
gespeichert. Job-Payloads nach erfolgreichem Abschluss entfernen.

## Ablauf, Konflikte und Wiederaufnahme

1. Anwendungen, Provider, Datasets, Tenant und Scope auswählen; öffentliche
   Projektkonfiguration und die konkrete Liste benötigter KV-Objekte validieren.
2. Secret-Felder je Profil ausfüllen oder bewusst die Generierung auswählen.
3. Vor Beginn alle konkret geplanten KV-Objekte über Metadaten auf Existenz
   prüfen. Andere Geschwisterobjekte unter demselben Tenant sind zulässig.
4. Existiert eines der geplanten Objekte, auch mit Löschhistorie, die Neuanlage
   insgesamt vor dem ersten Schreibvorgang abbrechen. Fehler, fehlende Rechte
   und unklare Antworten gelten nicht als bestätigte Abwesenheit.
5. Neue Objekte ausschließlich mit KV-v2 `options.cas=0` schreiben. Das verhindert
   Überschreiben auch bei einem Rennen nach der Vorprüfung. Vault bietet keine
   Transaktion über mehrere KV-Objekte; Fortschritt nach jedem Schritt sichern.
6. Das Semaphore-Projekt aus der vorbereiteten Vorlage anlegen, die geschützten
   Lese-Credentials eintragen und `Vault-Access` an die gewählten Tasks binden.
   Keine automatischen Deployments oder kopierten Zeitpläne starten.
7. Tenant erst nach vollständigem Abschluss als fertig behandeln. Ein Fehler
   lässt den Vorgang unvollständig und wiederaufnehmbar.

Bereits angelegte eigene Objekte bleiben bei Teilfehlern erhalten. Keine
automatische Löschung, Überschreibung oder erneute Generierung. Wiederaufnahme
verwendet den gespeicherten Plan und dieselben Werte. Ein vorhandenes Objekt darf
nur dann als eigener Fortschritt gelten, wenn die Zuordnung zum Job zuverlässig
nachgewiesen ist. Bei unklarem Schreibergebnis ist manuelle Prüfung erforderlich;
die bloße Existenz eines Pfads beweist keinen Besitz.

## Verifikation und Dokumentation

- Backend: AppRole-Login, URL/TLS/Namespace, Metadatenprüfung aller Ziele vor
  dem ersten Write, CAS-Konflikte, keine Änderungen vorhandener Objekte.
- Katalog: korrekte Anwendungs-/Provider-/Dataset-Kombinationen, genaue Schlüssel
  und Feldvalidierung, Erweiterung aus Manifesten.
- Orchestrierung: Teilfehler, Wiederaufnahme, unsicheres Timeout, konkurrierende
  Ausführung, keine doppelten Projekte oder neuen Secret-Werte bei Wiederholung.
- Credentials: geschützte Übergabe an Semaphore, keine Rückgabe im Browser oder
  Audit, verschlüsselte Persistenz, Zugriff nur für Systemadministratoren.
- Frontend: Secret-Eingabe/Generierung, Plananzeige, Konfiguration und Fehler,
  Vor-/Zurück-Navigation ohne versehentliche Regenerierung.
- Bestehende Tests ausführen, Produktionsbuild prüfen und Migration testen.
- README, Abnahmetests und Implementierungsstatus aktualisieren. Den Live-Test
  mit der Firmeninstanz gesondert als noch durchzuführende Abnahme ausweisen.

## Einrichtung und Bedienung

### 1. Portal aktualisieren

Den bestehenden Datenbankstand und `.env` mit demselben Fernet-Key sichern. Beim
lokalen Stack die Images bauen und denselben Compose-Projektnamen verwenden:

```powershell
docker build -t semaphore-portal-local-backend:dev ./backend
docker build -t semaphore-portal-local-frontend:dev ./frontend
docker compose -p semaphore-porter-local up -d --wait --force-recreate backend frontend
```

Beim Backend-Start wird die additive Migration `20261016_0004` ausgeführt.
Bestehende Benutzer, Tenants, Jobs und die Semaphore-Verbindung bleiben erhalten.
Für Serverinstallationen gelten die Image-/Update-Befehle der README.

### 2. Vault-Zugänge vorbereiten

Ein Vault-Administrator stellt den Porter-Schreibzugang bereit. Bei `kv` und
`semaphore/tenants` genügt für den beschriebenen Objektvertrag eine passende
Policy wie diese; sie wird außerhalb des Porter eingerichtet:

```hcl
path "kv/data/semaphore/tenants/*" {
  capabilities = ["create"]
}
path "kv/metadata/semaphore/tenants/*" {
  capabilities = ["read"]
}
```

Die konkreten Mounts und Pfade an die Installation anpassen. Kein `list`, kein
Lesen von Secret-Inhalten und kein Update-/Delete-/Destroy-Zugriff für diesen
Ablauf erforderlich. Der Porter erzeugt keine AppRole und keine Secret-ID.

Für den Semaphore-Lesezugang dieselbe bestehende AppRole verwenden. Die Role-ID
ist mit administrativen Rechten abrufbar. Die Secret-ID ist nur verwendbar,
wenn ihr Wert noch bekannt ist oder ein Administrator eine zusätzliche Secret-ID
derselben AppRole ausstellt. Die Ausgabe nur in das geschützte Porter-Feld
übertragen; nicht im Chat, einer Projektvorlage oder Dokumentation speichern.
TTL, Nutzungszahl und mögliche Netzwerkbindungen müssen spätere Anmeldungen vom
Semaphore-Runner ermöglichen. Der Porter erneuert solche Credentials nicht selbst.

### 3. Unter Administration → Vault konfigurieren

| Feld | Einzutragender Wert |
|---|---|
| Vault Server-URL | z. B. `https://vault.intern.example:8200`, ohne `/v1` oder weitere Pfade |
| Vault Namespace | nur bei entsprechender Vault-Installation, sonst leer |
| KV-v2-Mount | z. B. `kv`, ohne `data/` oder `metadata/` |
| Tenantwurzel | z. B. `semaphore/tenants` |
| Auth-Mount des Schreibzugangs | tatsächlicher AppRole-Mount des Porter, z. B. `approle` |
| Auth-Mount des Semaphore-Lesezugangs | bestehender Mount, im Stack-Beispiel `semaphore-ansible` |
| Schreibzugang: Role-ID / Secret-ID | Zugang der extern bereitgestellten Porter-AppRole |
| Semaphore-Lesezugang: Role-ID / Secret-ID | Zugang der bereits bestehenden Semaphore-AppRole |
| Registry-Passwort je Anwendung | gültiges Passwort/Token zu deren Host, Benutzer und Images |

**Vault-Anlage im Tenant-Assistenten anbieten** aktivieren und speichern. Alle
vier Zugangswerte müssen dafür hinterlegt sein. Leere Passwortfelder behalten
bereits gespeicherte Werte. Der Verbindungstest prüft Erreichbarkeit und die
Anmeldung der Schreib-AppRole, ohne Testsecrets anzulegen. Er bestätigt keine
Schreibrechte und keine erfolgreiche spätere Semaphore-Anmeldung.

Host, Registry-Benutzer, Image-Repositories, Anwendungsversion und weitere
öffentliche Programmvariablen weiterhin in der Projektvorlage beziehungsweise
im Ressourceneditor pflegen. Im aktuellen Stack sind z. B.
`azubiorga_registry_host`/`azubiorga_registry_username` und
`wordpress_registry_host`/`wordpress_registry_username` getrennte Variablen.

Für eine Unternehmens-CA `VAULT_CA_BUNDLE` auf einen lesbaren Pfad **im
Backend-Container** setzen. Die Datei zusätzlich über einen Compose-Override
einbinden, zum Beispiel `compose.vault-ca.yml`:

```yaml
services:
  backend:
    volumes:
      - ./certs/company-ca.pem:/etc/portal/company-ca.pem:ro
```

In `.env` dann `VAULT_CA_BUNDLE=/etc/portal/company-ca.pem` setzen. Den Override
bei allen zugehörigen Compose-Aufrufen mitführen, beispielsweise:

```powershell
docker compose -p semaphore-porter-local -f docker-compose.yml -f compose.vault-ca.yml up -d --wait backend
```

Der Semaphore-Runner benötigt unabhängig davon sein eigenes Vertrauen in die
Vault-Zertifikatskette. `VAULT_REQUEST_TIMEOUT_SECONDS` steuert die einzelnen
Backend-Anfragen; Standard sind 30 Sekunden.

### 4. Tenant erstellen

1. Vorlage wählen, neue `tenant_slug` und eigene `runtime_scope_id` eintragen.
2. Anwendungen, Provider und erlaubte Datasets auswählen. Die jeweils erste
   Auswahl bildet die Vorgabe; diese Kombination muss ebenfalls gültig sein.
3. Tasks, Gruppen, Presets und Benutzerrechte prüfen. In Schritt 5 ist die
   Vault-Anlage bei neuen Vorlagen nach Aktivierung vorbelegt und abwählbar.
4. Schritt 7 validiert den Plan und zeigt die exakten KV-Objekte. Secret-Werte
   eingeben oder je Feld ausdrücklich Generierung auswählen. Vorgegebene
   AzubiOrga-Crypto-Werte manuell eingeben. Die übrigen eingegebenen Werte bleiben
   beim Vor-/Zurückgehen im geöffneten Assistenten erhalten, werden aber nicht
   mit dem Entwurf gespeichert.
5. **Projekt verbindlich erstellen** führt Metadatenprüfung, Vault-Anlage,
   Semaphore-Restore und Credential-Übergabe aus. Der Vorgang ist anschließend
   gespeichert wiederholbar. Deployments starten erst durch einen Task.

Ein Browser-Neuladen vor der ersten Ausführung verwirft ungespeicherte
Secret-Eingaben; diese dann erneut eingeben. Nach Beginn der Vault-Anlage wird
die Ausführungspayload verschlüsselt gespeichert. Ab dann sind Zielplan und
KV-Werte für diesen Job fest; die Oberfläche zeigt ihre Inhalte nicht mehr an.

### 5. Fehler und Wiederaufnahme

- **Objekt bereits vorhanden:** kein Überschreiben, auch nicht bei leerem,
  unvollständigem, weich gelöschtem oder zerstörtem Inhalt. Bei einem Konflikt
  nach bereits erfolgten eigenen Writes bleiben diese erhalten; den Konflikt
  außerhalb des Porter prüfen. Keine automatische Bereinigung.
- **Teilweise angelegt:** gespeicherten Vorgang fortsetzen. Eigene unveränderte
  Objekte werden anhand bestätigter Version und Erstellungszeit wiedererkannt;
  nur noch ausstehende Objekte werden angelegt.
- **Schreibergebnis unklar:** in Vault den tatsächlichen Ausgang prüfen. Im
  betroffenen Objekt des Assistenten die Prüfung bestätigen und ausdrücklich
  eigene Anlage oder vollständige Abwesenheit zuordnen. Der Porter prüft dazu
  erneut Metadaten. Ein fremdes Objekt niemals als eigene Anlage bestätigen.
- **Abgelaufene Zugangsdaten:** ein Administrator hinterlegt gültige Werte unter
  Vault. Bei unveränderter Server-/Namespace-/Mount-Zuordnung übernimmt die
  Wiederaufnahme die aktualisierten Zugänge. Zielpfade, Registry-/Crypto-/DB-Werte
  bleiben die bereits bestätigten Werte des Jobs.
- **Semaphore-Zugangseintragung fehlgeschlagen:** der Tenant bleibt unvollständig;
  Wiederaufnahme aktualisiert vorhandene Secret-Einträge anstatt neue Einträge
  oder ein weiteres Projekt zu erzeugen.
- **Vorgang läuft noch:** parallele Ausführung wird blockiert. Nach einem
  Prozessabbruch kann eine seit 15 Minuten nicht aktualisierte Sperre wieder
  übernommen werden; ein unklarer Vault-Write benötigt weiterhin die Prüfung.

Tenant-/Projektlöschung entfernt keine Vault-Objekte. Zentrale Einstellungen und
offene Job-Payloads sind verschlüsselte Datenbankinhalte; Backups benötigen den
unveränderten Fernet-Key. Ein abgeschlossener Job löscht seine temporäre
Secret-Payload; noch offene Jobs behalten sie zur Wiederaufnahme.

### 6. Katalog nach Stack-Erweiterungen aktualisieren

Im Entwickler-Python mit installierten Backend-Abhängigkeiten zusätzlich PyYAML
installieren. Danach aus dem Porter-Stamm ausführen:

```powershell
python -m pip install PyYAML
python tools/export_vault_catalog.py --stack-root ../azubiorga-semaphore-git
```

Das Werkzeug liest ausschließlich YAML-Verträge, keine Secret-Inhalte, Compose-
Ausführung oder fremde Taskdateien. Es schreibt den validierten Katalog nach
`backend/app/vault_catalog.json` und vermerkt den Stack-Commit. Unbekannte
Validierungsregeln müssen vor dem Export im Porter ergänzt werden. Neuartige
Secret-Felder sind standardmäßig nur manuell eingebbar; Generierung benötigt
einen unterstützten Vertrag. Exportierte Änderungen prüfen, Tests ausführen
und das Backend-Image neu bauen. Ein Katalogexport implementiert keinen neuen
Provider im Stack; dafür gilt zuerst dessen Paket-/Providerablauf oben.

## Implementierungsstand

- Spezifikation, Backend-/Frontend-Integration und additive Migration umgesetzt.
- Prüfung: **101 Backend-Tests und 33 Frontend-Tests bestanden**; TypeScript-/Vite-
  Produktionsbuild und beide Docker-Image-Builds erfolgreich. Katalogexport mit
  den Stack-Manifesten verglichen, lokale Dokumentationslinks geprüft.
- Lokaler Compose-Stack unter `http://127.0.0.1:18092` gesund; Migration
  `20261016_0004` angewendet. Vorheriges Datenbank-Backup unter
  `.tools/backups/portal-before-vault-20261016.dump` gesichert. Vergleichswerte
  bestätigen unveränderte IDs, E-Mail-Adressen, Benutzernamen, Passwort-Hashes,
  Aktivierungszustände und Rollen der zwei Konten sowie unveränderte Tenant-Daten.
- Webseite, Vault-Seitenroute, Health und OpenAPI antworten erfolgreich;
  unauthentifizierter Vault-API-Zugriff wird abgelehnt. Keine Zugangsdaten
  zurückgesetzt oder neue Vault-Verbindungen im lokalen Bestand aktiviert.
- Automatisierte Prüfung verwendet nachgebildete Vault-/Semaphore-APIs. Die
  konkrete Firmeninstanz und ihre Rechte bleiben als Live-Abnahme offen.
- Es wurden bisher keine Live-Vault-Objekte angelegt oder verändert.

## Quellen

- Stack: `guides/MANDANTENFAEHIGKEIT.md`, `guides/PROGRAMMPAKETE.md`,
  `SETUPGUIDE.md`, `playbooks/tasks/resolve-program-runtime.yml`,
  `programs/*/program.yml`, `database-types/*/driver.yml` und Dataset-Kataloge.
- [Vault KV v2](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2)
- [Vault AppRole](https://developer.hashicorp.com/vault/api-docs/auth/approle)
- [Semaphore-Variablengruppen-API](https://github.com/semaphoreui/semaphore/blob/develop/api/projects/environment.go)
