# Abnahmetests für den Web-App-Zwischenstand

Stand: 26.10.2026. Dieser Plan enthält **80 Abnahmetestfälle** einschließlich 14 Vault-, 12 GitLab- und zwei GIF-Fällen. Alle hier beschriebenen manuellen und integrierten Prüfungen haben zunächst den Status **offen**. Die bestandenen automatisierten Tests sind unten separat zugeordnet; sie ersetzen keine Abnahme der echten GitLab-/Semaphore-/Vault-/Deployment-Umgebung.

## Durchführung und Nachweise

P0 kennzeichnet einen Freigabeblocker: Ohne bestandenen Test keine Produktivfreigabe. P1 muss ebenfalls geprüft werden; eine Abweichung benötigt eine dokumentierte Entscheidung des Verantwortlichen. Nicht verfügbare Infrastruktur ergibt **blockiert**, nicht **bestanden**. Mögliche Ergebnisse: offen, bestanden, fehlgeschlagen, blockiert oder begründet nicht anwendbar.

Für jeden Test erfassen: Test-ID, Datum, Prüfer, Commit/Image-Tag, Umgebung, konkrete Testdaten und Objekt-IDs, tatsächliches Ergebnis, Status sowie Ticket oder Nachweis. Screenshots und API-Protokolle enthalten keine Passwörter, Tokens, Cookies, privaten Schlüssel oder vollständigen Secret-Werte. Beim API-Test Session-Cookie und CSRF-Header verwenden, ohne diese im Nachweis zu veröffentlichen.

Projektlöschungen, Datenimporte, gestörte Verbindungen und Restore-Tests ausschließlich in einer dafür bestimmten Testumgebung durchführen. Dieser Plan führt selbst keine Änderungen an Semaphore, Vault oder Zielhosts aus.

## Voraussetzungen und Testdaten

- Separater Portal-Stack mit PostgreSQL; lokal entsprechend der [README](../README.md#lokaler-test). Für TLS-Tests zusätzlich eine Testdomain mit gültigem Zertifikat.
- Semaphore-Testinstanz mit Service-Token, einer freigegebenen Projektvorlage, Test-Registry und einem entbehrlichen Linux-/Docker-Zielhost. Für Netzwerkfehler eine kontrollierbare Testverbindung verwenden.
- Zwei Portal-Tenants `qa-a` und `qa-b` mit getrennten Semaphore-Projekten und Runtime-Scopes `qa-scope-a` und `qa-scope-b`.
- Konten für Systemadmin, Viewer, Operator, globalen Tenant Admin sowie ein Konto ohne Tenant-Zuordnung. Für Login-Limitierung ein separates entbehrliches Konto verwenden.
- Gruppe `qa-operators`, eine lesende Task-Freigabe und eine Start-/Abbruchfreigabe. Bestehende Quellvorlage vor Kopiertests anhand ihrer nicht geheimen Konfiguration dokumentieren.
- Für echte Deployments gültige Test-Vault-Zugänge und benötigte KV-Objekte. Im automatischen Onboarding richtet ein Administrator Schreib-AppRole, bestehenden Semaphore-Lesezugang und Registry-Zugänge im Semaporter ein; neue Test-KV-Objekte legt dann der Wizard an. AppRoles/Policies werden weiterhin außerhalb des Semaporter verwaltet. Der vereinbarte gemeinsame Leser darf aktuell `semaphore/*` lesen; die Tests behaupten dafür keine Trennung durch Vault-ACLs. Siehe [Vault-Implementierung](VAULT_IMPLEMENTIERUNG.md).
- Eine deaktivierte Policy, ein deaktivierter Tenant, ein absichtlich fehlschlagender Test-Task und ein ausreichend lange laufender, gefahrlos abbrechbarer Task.
- Für Migrations- und Restore-Prüfungen eine Kopie einer älteren Portal-Datenbank und die zugehörige `.env`/Fernet-Konfiguration. Die laufende Testdatenbank wird hierfür nicht überschrieben.

### Deployment-Matrix

Die folgenden Kombinationen stammen aus den lokalen Manifesten in `azubiorga-semaphore-git`, Stand `182007c`. Vor Durchführung mit dem tatsächlich in Semaphore ausgecheckten Stack-Commit und dessen Surveys abgleichen. Jede gültige Zeile ist als eigener Durchlauf von T01/T02 zu protokollieren. Ausgewählte Freigabelisten bedeuten nicht, dass jedes kartesische Produkt daraus unterstützt ist.

| Anwendung | Provider | Datensatz | Erwartung |
|---|---|---|---|
| AzubiOrga | PostgreSQL | `none` | Deployment ohne Testdatenimport; sonstige Anwendungsvoraussetzungen beachten |
| AzubiOrga | PostgreSQL | `smoke-v1` | Technischer Importtest; keine fachlichen Testdaten zugesichert |
| AzubiOrga | PostgreSQL | `public-v1` | Import des katalogisierten Schemas und der fachlichen Testdaten |
| WordPress | MariaDB | `none` | Deployment ohne Testdatenimport |
| WordPress | MariaDB | `mariadb-smoke-v1` | Technischer Importtest; WordPress wird dadurch nicht vorinstalliert |
| WordPress | MySQL | `none` | Deployment ohne Testdatenimport |
| WordPress | MySQL | `mysql-smoke-v1` | Technischer Importtest; WordPress wird dadurch nicht vorinstalliert |
| AzubiOrga | MariaDB oder MySQL | beliebig | Aktuell im Anwendungsmanifest nicht unterstützt; Ablehnung vor Deployment |
| WordPress | PostgreSQL | beliebig | Aktuell im Anwendungsmanifest nicht unterstützt; Ablehnung vor Deployment |
| WordPress | MariaDB | `mysql-smoke-v1` | Unpassender Datensatz; Ablehnung vor Deployment |

Eine fehlende freigegebene Survey-Option zunächst in der Testvorlage ergänzen und die Vorlage neu importieren. Die Portal-Validierung prüft Survey-Freigaben; im Vault-Modus prüft sie zusätzlich den exportierten Manifestkatalog. Die konkrete Deployment-Kombination prüft der Stack erneut.

## B – Installation, Update und Wiederanlauf

| ID | Prio | Prüfschritte | Erwartetes Ergebnis |
|---|---|---|---|
| B01 | P0 | Neuen Test-Stack mit gültiger `.env` und dem vorgesehenen Image-Tag starten. Startprotokoll, Dienste, `/`, `/api/health` und `/api/docs` prüfen. | Backend, Frontend und PostgreSQL gesund; Migrationen und Bootstrap erfolgreich; Seite/Schema erreichbar, Health meldet `ok`. |
| B02 | P0 | In einem separaten frischen Stack `PORTAL_FERNET_KEY` ungültig setzen bzw. eine erforderliche Compose-Variable entfernen; danach gültige Testkonfiguration herstellen. | Start scheitert erkennbar; kein scheinbar gesunder Portalbetrieb mit ungültiger Konfiguration. Nach Korrektur normaler Start. |
| B03 | P0 | Benutzer, Gruppe, Tenant-Zuordnung und Designauswahl anlegen. Stack stoppen und mit identischem Projektnamen/Volume starten; danach einmal Container neu erstellen. | Portal-Daten bleiben erhalten, kein zweiter Bootstrap-Admin; Design bleibt im selben Browser erhalten. Der Neustart benötigt keinen Image-Neubau. |
| B04 | P0 | Kopie einer Datenbank vor `20261016_0002`/`0003` aktualisieren. Konten mit gleichem E-Mail-Lokalteil, bestehende Rollen und eine alte skalare Anwendungsauswahl einbeziehen. | Anwendungen werden übernommen; Benutzernamen eindeutig und gültig ergänzt. IDs, E-Mails, Passwort-Hashes, Rollen und Aktivierungszustände bleiben erhalten; E-Mail-Login funktioniert. |
| B05 | P0 | PostgreSQL-Backup und zugehörige Konfiguration in einen separaten Restore-Stack einspielen. Anmeldung, Datenbestand und verschlüsselte Semaphore-Verbindung prüfen. | Wiederherstellung vollständig; gespeichertes Service-Token mit demselben Fernet-Key verwendbar. Keine Ersetzung des Schlüssels zur vermeintlichen Reparatur. |
| B06 | P0 | Testinstallation über vorgesehenes HTTPS-Gateway bzw. Host-Reverse-Proxy aufrufen; Session-Cookie, erlaubten Host und absichtlich falschen Host prüfen. | HTTPS und Weiterleitung funktionieren; Cookie mit `Secure`, `HttpOnly`, `SameSite=Lax`; fremder Host abgelehnt. Lokaler HTTP-Test verwendet ausdrücklich `PORTAL_COOKIE_SECURE=false`. |

## A – Anmeldung und Benutzerverwaltung

| ID | Prio | Prüfschritte | Erwartetes Ergebnis |
|---|---|---|---|
| A01 | P0 | Neu angelegten Bootstrap-Admin anmelden; vor dem Passwortwechsel direkt eine Admin-API aufrufen. Passwort wechseln, ab- und erneut anmelden. | Passwortwechsel wird auch API-seitig erzwungen. Neues Passwort gilt; der Bootstrap setzt das Konto beim Neustart nicht zurück. |
| A02 | P0 | Dasselbe Konto mit E-Mail und Benutzername anmelden, zusätzlich Groß-/Kleinschreibung und umgebende Leerzeichen prüfen. Falsches Passwort und unbekannten Namen testen. | Beide gültigen Kennungen führen zum selben Konto und denselben Rechten. Ungültige Anmeldung ergibt eine allgemeine Fehlermeldung, keine Sitzung. |
| A03 | P0 | Konto mit explizitem und Konto mit automatisch vergebenem Benutzernamen anlegen. Namen ändern; doppelte Namen mit anderer Großschreibung sowie ungültige Zeichen/Längen versuchen. | Eindeutige Namen; Änderungen in der Liste sichtbar. Unzulässige Eingaben abgelehnt. Neuer Name und E-Mail funktionieren; alter Benutzername nicht mehr. |
| A04 | P0 | Zwei Sitzungen desselben Kontos öffnen und das Passwort in einer ändern. Anschließend per Admin Passwortreset durchführen. | Passwortwechsel beendet die andere Sitzung. Admin-Reset beendet alle bisherigen Sitzungen und erzwingt den vorgesehenen Passwortwechsel beim nächsten Login. |
| A05 | P0 | Aktives Nicht-Admin-Konto anmelden, dann deaktivieren; mit bestehender Sitzung lesen/schreiben und erneut anmelden. Anschließend reaktivieren. | Deaktiviertes Konto hat keinen Zugriff und kann sich über keine der beiden Kennungen anmelden. Reaktivierung erhält Zuordnungen, erzeugt aber keine neuen Freigaben. |
| A06 | P0 | Mit dem separaten Login-Testkonto acht Fehlversuche innerhalb von 15 Minuten abwechselnd über Name/E-Mail durchführen. Danach korrekte Anmeldung versuchen; nach Ablauf des Fensters wiederholen. | Begrenzung mit HTTP 429; kein Umgehen durch Wechsel der Kennung. Auch die IP-Grenze wird separat geprüft. Nach Ablauf ist korrekte Anmeldung wieder möglich. |
| A07 | P0 | Angemeldete schreibende Anfrage ohne/falschen CSRF-Header senden; Login mit fremdem Origin testen. Danach regulär abmelden und alten Session-Cookie erneut benutzen. | Unzulässige Anfragen abgelehnt, keine externe Änderung. Regulärer Logout macht die Sitzung ungültig. Passwörter und Sessionwerte erscheinen nicht im Audit. |

## S – Semaphore-Verbindung und direkte Projektverwaltung

| ID | Prio | Prüfschritte | Erwartetes Ergebnis |
|---|---|---|---|
| S01 | P0 | Gültige Test-URL/Token speichern und Verbindung testen. Falsches Token, unerreichbaren Host, ungültige CA und gegebenenfalls vorgesehenen Proxy prüfen. | Gültige Verbindung nutzbar; Fehler sichtbar, kein Abschalten der TLS-Prüfung. Gespeichertes Token wird weder beim erneuten Laden noch im Audit ausgegeben. |
| S02 | P0 | Testprojekt erstellen, auflisten, öffnen und umbenennen; Ergebnis direkt in Semaphore vergleichen. | Änderungen am richtigen Remote-Projekt sichtbar; tatsächliche Semaphore-ID wird verwendet. Keine Änderung eines anderen Projekts. |
| S03 | P0 | Variablengruppe, Repository, Inventory, Key-Store-Eintrag und Task Template anlegen/bearbeiten. Mehrere Variablengruppen zu einem Template zuordnen. | Ressourcen und Referenzen in Semaphore korrekt; Mehrfachzuordnung bleibt erhalten. Keine Verwechslung von Portal-UUIDs und Semaphore-IDs. |
| S04 | P0 | Beide Tenant-Kennungen in `Semaphore-Defaults` ändern; zugleich einen anderen öffentlichen Wert erhalten. Kennung in fremder Gruppe, Survey und geschütztem Override einschleusen. | Beide Kennungen nur in Defaults; andere Werte bleiben erhalten. Unzulässige Ablagen abgelehnt; lokale Tenant-Kennung wird nach erfolgreicher Änderung mitgeführt. Bestehende Deployments/Vault-Pfade werden nicht umbenannt. |
| S05 | P0 | In `Vault-Access` eine Test-Role-ID als geschützte Extra Variable und eine Test-Secret-ID als geschützte Prozessvariable setzen. Danach nur eine normale Variable ändern und Ressourcen neu laden. SSH-Key gesondert testen. | Geschützte Werte bleiben erhalten und werden nicht zurückgegeben. Secret-Typen stimmen; private Schlüssel/Passwörter nicht in Audit, Entwurf oder Vorschau. Tatsächliche Verwendung mit T01 prüfen. |
| S06 | P0 | Dasselbe Projekt bzw. dieselbe Ressource in zwei Browser-Tabs öffnen. In Tab 1 speichern, dann aus Tab 2 mit alter Revision speichern bzw. löschen. | Veraltete Revision ergibt Konflikt, kein stilles Überschreiben. Nach Neuladen ist die aktuelle Konfiguration sichtbar. |
| S07 | P0 | Entbehrliches Testprojekt zunächst mit falschem, dann mit exakt richtigem Bestätigungsnamen löschen. Projektliste und verknüpften Portal-Tenant prüfen. | Falsche Bestätigung blockiert. Richtige Bestätigung löscht nur dieses Remote-Projekt; Portal-Tenant wird deaktiviert. Laufende Zielhost-Deployments und Vault-Daten bleiben bestehen. |

## W – Tenant-Wizard und Duplizieren

| ID | Prio | Prüfschritte | Erwartetes Ergebnis |
|---|---|---|---|
| W01 | P0 | Wizard ohne Vorlage fortsetzen; anschließend eine Vorlage wählen. Tenant-/Scope-Werte der Quelle unverändert übernehmen bzw. leer lassen. | Ohne Vorlage kein Fortschritt. Neue, gültige und von der Quelle verschiedene Tenant-/Scope-Kennungen erforderlich. Keine Remote-Anlage bei ungültigem Entwurf. |
| W02 | P0 | In Schritt 3 mindestens zwei Anwendungen, mehrere Provider und mehrere Datensätze wählen; „Alle auswählen“ und Abwahl prüfen. Pro Liste eine Vorgabe festlegen. | Jede Auswahl und Vorgabe bleibt gespeichert; keine Beschränkung auf einen Listeneintrag. Vorgabe muss Teil ihrer Freigabeliste sein. |
| W03 | P0 | Erstellung aus W02 abschließen. Portal-Tenant, kopierte Semaphore-Surveys, Defaults und Initial-Policies vergleichen. | Freigabelisten beschränken Surveys und Policies. Defaults enthalten einzelne Werte; Task-Start übergibt später einzelne Werte statt Listen. Die Erstellung selbst startet keinen Deployment-/Import-Task. |
| W04 | P0 | Explizit leere Freigabeliste, unbekannte Option und ausgewähltes Task Template ohne gemeinsame Survey-Option testen; zusätzliche nicht erlaubte Daten im Request senden. | Validierung blockiert unbrauchbare Freigaben; keine automatische Erweiterung auf alle Werte. Fehler benennen das betroffene Feld/Template. |
| W05 | P1 | Mehrere Schritte vorwärts, zurück und erneut vorwärts wechseln. Entwurf speichern, Seite neu laden und auf der Einstiegsseite fortsetzen. | Aktueller und bereits besuchter Schritt korrekt markiert; besuchte Schritte zugänglich; gespeicherte Mehrfachauswahl, Kennungen und Fortschritt erhalten. |
| W06 | P0 | Validierten Entwurf ändern und erneut zur Erstellung wechseln. Danach zur ersten Seite gehen und eine andere Vorlage auswählen. | Alte Validierung wird verworfen und aktueller Entwurf neu geprüft. Vorlagenwechsel beginnt einen neuen Creation Job und übernimmt keinen alten Restore-Zustand. |
| W07 | P0 | Task-/Gruppenauswahl reduzieren, zusätzlich vollständig leere Gruppenauswahl prüfen. Repository/Branch und Ressourcen auf der Kopie bearbeiten. | Nur ausgewählte Ressourcen plus erforderliche `Semaphore-Defaults` übernommen; Referenzen konsistent. Nicht gewählte Quellgruppen bleiben entfernt. Quelle unverändert. |
| W08 | P0 | Vorlage mit Quell-Credentials, Zeitplan, Webhook und Autorun duplizieren. Neue Kennungen und explizite Vault-Pfad-Overrides jeweils ohne und mit Vault-Anlage prüfen. | Quell-Credentials/private Schlüssel nicht kopiert; automatische Trigger deaktiviert. Kennungen nur in Defaults. Ohne Vault-Anlage Quellpfade ausdrücklich ersetzen. Im Vault-Modus verwendet die Kopie die angezeigten neuen Tenant-/Profilpfade und erhält nur die zentral eingerichteten Lese-Credentials. |
| W09 | P0 | Erstellen doppelt auslösen bzw. denselben abgeschlossenen Job erneut aufrufen. In einer getrennten Störungsprüfung die Antwort nach erfolgreichem Restore unterbrechen. | Ein Projekt und ein Tenant pro Job. Unklares Ergebnis führt zu Verifikationszustand; vorhandenes Projekt wird geprüft, kein blindes zweites Restore. Ein erneuter Restore bei nachgewiesenem Fehlen erfordert Bestätigung. |
| W10 | P0 | Initial-Policies/Zugriffe einmal aktivieren und einmal abwählen. Im angelegten Projekt einen Remote-Survey ändern und synchronisieren bzw. Template über den Projekteditor ändern. | Zugewiesene Zugriffe entsprechen dem Entwurf. Ohne gültige Policy kein Task-Start. Geänderte, zuvor freigegebene Templates bleiben bis zur erneuten Policy-Prüfung deaktiviert; kein zusätzlicher Zugriff durch globale Operatorrolle allein. |

## R – Berechtigungen und Variablen-Policies

| ID | Prio | Prüfschritte | Erwartetes Ergebnis |
|---|---|---|---|
| R01 | P0 | Konto ohne Tenant-Zuordnung anmelden; bekannte Tenant-, Task- und Run-IDs direkt per API aufrufen. | Kein Zugriff allein aufgrund bekannter IDs oder einer globalen Viewer-/Operatorrolle; keine fremden Metadaten oder Logs. |
| R02 | P0 | Viewer einem Tenant und dessen Task nur lesend zuweisen. Task anzeigen und per UI/API starten bzw. einen zugänglichen Lauf abbrechen versuchen. | Nur erlaubte Ansicht; Start und Abbruch auch serverseitig abgelehnt. Tenant-Zuordnung allein ersetzt keine Task-Freigabe. |
| R03 | P0 | Operator mit Tenant-Zuordnung sowie Sicht-/Start-/Abbruchrecht anmelden. Zugriff auf erlaubten Task und die Admin-API prüfen. | Erlaubte Task-Aktionen nutzbar; Admin-API weiterhin gesperrt. Ein globaler `tenant_admin` erhält ebenfalls keine Systemadmin-Oberfläche. |
| R04 | P0 | Direkte Freigabe und Gruppenfreigabe parallel erteilen. Direkte Freigabe entfernen, danach Gruppenfreigabe bzw. Mitgliedschaft entfernen. | Rechte addieren sich. Solange Gruppenfreigabe gilt, bleibt der Zugriff erhalten; nach Entzug aller passenden Freigaben kein Zugriff mehr. |
| R05 | P0 | Mit Konto von `qa-a` IDs von `qa-b` in Projekt-, Formular-, Start-, Run-, Stop- und Log-Anfragen einsetzen. | Alle fremden Ressourcen bleiben gesperrt; keine Task-Ausführung und kein Datenabfluss zwischen Mandanten. |
| R06 | P0 | Policy mit Enum, Integer-Grenze, String-Regel, Boolean, Fixed/Hidden anlegen. Unbekannte Felder, `tenant_slug`-/Scope-Override, fremden Datensatz und falsche Typen direkt senden. | Validierung vor Semaphore-Aufruf; Fixed/Hidden nicht manipulierbar. Für Initial-TTL-Grenzen 5/1440 gültig, 4/1441 ungültig; bei eigener Policy deren Grenzen verwenden. |
| R07 | P0 | Tenant inaktiv setzen; separat ein durch Template-Änderung deaktiviertes Task Template und eine inaktive Policy prüfen. Als Operator und Systemadmin jeweils Start versuchen. | Start bleibt bei inaktiver Konfiguration gesperrt. Systemadmin-Rechte umgehen weder aktive Tenant-/Policy-Anforderungen noch die Variablenvalidierung. |

## T – Tatsächliche Deployments, Daten und Laufzustand

| ID | Prio | Prüfschritte | Erwartetes Ergebnis |
|---|---|---|---|
| T01 | P0 | Jede gültige Zeile der Deployment-Matrix aus dem Portal starten. Semaphore-Parameter, Zielhost-Ressourcen, Readiness und Anwendungsadresse prüfen. | Richtige Anwendung/Provider/Tenant/Scope; tatsächlich erreichbare Instanz. Bei `host_port=0` konfliktfreie Portvergabe durch den Stack. Portal-Task-Erfolg wird mit realer Funktionsprüfung bestätigt. |
| T02 | P0 | Datensatz-Durchläufe aus T01 anhand eines vorab festgelegten, nicht geheimen Datenmerkmals prüfen; zusätzlich `none` und jede ungültige Matrixzeile testen. | Vorgesehener Import nachweisbar; `none` löst keinen Testdatenimport aus. Unpassende Kombination vor Deployment abgelehnt; Quelle und bestehende Daten unverändert. |
| T03 | P0 | Je einen erfolgreichen, fehlschlagenden und lange laufenden Task starten. Laufübersicht ohne Detailöffnung aktualisieren, Logs öffnen und abbrechbaren Task stoppen. | Status/Fehler/Ende werden aktualisiert; Logs dem richtigen Lauf zugeordnet. Stop wirkt auf richtigen Semaphore-Task, benötigt Abbruchrecht und wird in der Historie nachvollziehbar. |
| T04 | P0 | Für `qa-a` und `qa-b` parallel deployen; getrennte Scopes und mehrere Instanzen im selben vorgesehenen Pool prüfen. Nur Instanz A stoppen/ablaufen lassen. | Port-, Netzwerk-, Datenbank- und Ownership-Trennung stimmen. B bleibt nutzbar; ein geteilter Provider wird nicht vorzeitig entfernt. Ressourcen bleiben anhand IDs zuordenbar. |
| T05 | P0 | In Test-Vault ein Pflichtfeld entfernen bzw. AppRole-Leserecht entziehen; getrennt eine abgelaufene Secret-ID und ein ungültiges CA-Zertifikat prüfen. Danach korrekt wiederherstellen. | Kontrollierter Fehler ohne Secret-Ausgabe und ohne neues Deployment. Mit korrigierten Voraussetzungen funktioniert ein neuer Lauf. Bereits vorhandene unvollständige Objekte repariert der Semaporter nicht automatisch; die Vault-Anlage betrifft neue Tenant-Objekte beim Onboarding. |
| T06 | P0 | Kürzeste freigegebene TTL verwenden; anschließend Zielhost-Cleanup und Portal-/Semaphore-Laufhistorie getrennt prüfen. | Deployment gemäß Stack-Cleanup entfernt, fremde oder noch aktive Instanzen erhalten. Abgelaufene Deployment-Ressourcen bedeuten nicht automatisch einen nachträglichen anderen Semaphore-Taskstatus. |
| T07 | P1 | Optionalen Mailversand mit freigegebener Testadresse an/aus ausführen; Image-/Release-Auswahl und voreingestellte Variablen im tatsächlich gestarteten Task prüfen. | Nur ausgewählte freigegebene Werte verwendet. Mailverhalten entspricht Schalter; Mail-/Registry-Ausfall sichtbar und ohne Veröffentlichung von Credentials. |

## D – Designs und Bedienoberfläche

| ID | Prio | Prüfschritte | Erwartetes Ergebnis |
|---|---|---|---|
| D01 | P1 | GitHub Black, SIT Hell und SIT Dunkel auswählen; Administration, Benutzerportal und Anmeldung prüfen; Browser neu laden. | Auswahl bleibt für dieselbe Browser-Origin bestehen. SIT-Logo dunkel im hellen und weiß im dunklen Design, ohne farbige Fläche; GitHub Black mit neutraler Marke. |
| D02 | P1 | Anmeldung in beiden SIT-Varianten öffnen; Tab-/Favoritensymbol und gegebenenfalls eine installierte Test-App prüfen. Alten lokalen Symbolwert simulieren. | Portal-Tor fest eingestellt, keine Symbolauswahl. Die drei entfernten Werbetexte fehlen. Verantwortlichen-Hinweis klein und lesbar; alte Symbolwerte ändern das Portal-Tor nicht. |
| D03 | P1 | Design exportieren und wieder importieren; mitgelieferte Vorlage anpassen. Ungültige Farbe, zu geringe Kontraste, fremde Felder und übergroße Datei importieren. | Gültiges Design übernimmt freigegebene Werte; ungültiger Import abgelehnt, aktive Variante erhalten. Keine Ausführung beliebiger CSS-/Script-/URL-Inhalte. |
| D04 | P1 | Eigenes Design entfernen, Browser-Speicher sperren bzw. absichtlich ungültige gespeicherte Konfiguration laden. Zweiten Browser mit leerem Speicher öffnen. | Aktive entfernte/ungültige Variante fällt auf GitHub Black zurück. Bei gesperrtem Speicher Hinweis und nutzbare Sitzung. Keine behauptete geräte- oder kontoweite Synchronisierung. |
| D05 | P1 | Anmeldung, Navigation, Wizard, Tabellen und Dialoge bei Desktop- und Mobilbreite sowie nur per Tastatur bedienen; Konsole/Netzwerk prüfen. | Bedienelemente erreichbar, kein Seitenüberlauf; erforderliche Felder/Fehler erkennbar. Schrift/Logo lokal geladen; keine blockierenden UI-Fehler oder CSP-Verstöße. |

## O – Audit, Betriebsgrenzen und Abschluss

| ID | Prio | Prüfschritte | Erwartetes Ergebnis |
|---|---|---|---|
| O01 | P0 | Für Anmeldung, Fehlversuch, Benutzer-/Gruppenänderung, Projektschreibvorgang, Tenant-Anlage und Task-Start passende Ereignisse prüfen. Auch Fehlerprotokolle und Browser-Netzwerkantworten sichten. | Aktionen mit Benutzer/Ziel nachvollziehbar. Keine Secret-Inhalte, Vault-/Semaphore-Tokens oder privaten Schlüssel in Audit/Antworten/Logs; Portal-Session und CSRF nur im vorgesehenen Anmeldeprotokoll. Nicht jede Debug-Ausgabe des externen Stacks ist automatisch bereinigt: Secret-Fund als Blocker behandeln. |
| O02 | P0 | Portal-Tenant entfernen und separat Remote-Projekt löschen; Zustand von Vault-Objekten, Zielhost-Deployments und direkt in Semaphore gestarteten Tasks dokumentieren. | Lokales Entfernen löscht kein Remote-Projekt. Remote-Projektlöschung löscht keine Vault-/Docker-Daten. Portal-Historie verspricht keinen vollständigen Import direkt in Semaphore gestarteter Läufe. |
| O03 | P0 | Finale Commit-/Image-Tags und erfolgreichen Portal-CI-Lauf erfassen; Testresultate, Restore-Nachweis, offene Fehler und vorgenommene Testdatenbereinigung prüfen. | Verwendete Backend-/Frontend-Version eindeutig; alle P0 bestanden, P1 geprüft und Abweichungen entschieden. Offene Live-Prüfungen nicht als erledigt markiert; Freigabe durch Verantwortlichen dokumentiert. |

## V – Vault-Anlage und geschützte Übergabe

Diese Fälle ausschließlich mit entbehrlichen Testpfaden durchführen. Bei absichtlichen Timeouts oder Rennen alle beteiligten Objekte anschließend anhand des Vault-Audits prüfen. Die zentrale AppRole bleibt entsprechend der Vereinbarung ein gemeinsam genutzter Leser.

| ID | Prio | Prüfschritte | Erwartetes Ergebnis |
|---|---|---|---|
| V01 | P0 | Als Systemadmin Vault-Verbindung und vier AppRole-Werte sowie Registry-Zugänge speichern; Seite neu laden. Dasselbe als Operator versuchen. | Werte verschlüsselt gespeichert, nur Belegt-Flags zurückgegeben, Passwortfelder leer. Leer lassen erhält vorhandene Werte. Operator und fehlender CSRF-Header blockiert. |
| V02 | P0 | Schreibzugang mit gültiger und ungültiger Secret-ID testen; Unternehmens-CA und Namespace einbeziehen. | Gültige Anmeldung erfolgreich; falsche Werte/TLS erkennbar abgelehnt. Kein Testsecret angelegt. Verbindungstest bestätigt nur Anmeldung, keine Schreibrechte oder Runner-Anmeldung. |
| V03 | P0 | AzubiOrga/PostgreSQL mit vorgegebenem Crypto-Secret/Salt und manuellem DB-Wert anlegen; auf Testinstanz kontrolliert vergleichen. | Genau zwei korrekte KV-Objekte mit den erwarteten Schlüsseln. Vorgegebene Werte einschließlich zulässiger Leerzeichen bytegetreu; neue Semaphore-Defaults tragen Tenant und unabhängigen Scope. |
| V04 | P0 | WordPress mit MariaDB und MySQL freigeben, passende Datasets und Generierung der Providerwerte wählen. | Ein WordPress-Objekt und zwei getrennte Providerobjekte. Keine Crypto-Felder für WordPress, keine Registry-Token-Generierung; Providerwerte entsprechen den Grenzen. |
| V05 | P0 | Beide Anwendungen, alle drei gültigen Provider und mehrere passende Datasets freigeben. | Genau fünf eindeutige neue Objekte; kein Objekt je Dataset und kein doppeltes Objekt je Task. Der Stack wählt pro Lauf eine gültige Kombination. |
| V06 | P0 | Je einen Durchlauf mit vorhandenem, unvollständigem, weich gelöschtem und zerstörtem letzten Zielobjekt ausführen. | Die gesamte Vorprüfung stoppt vor dem ersten Write. Keine bestehenden Inhalte oder Versionen geändert; kein neues Semaphore-Projekt. |
| V07 | P0 | Unter demselben Tenant einen unabhängigen Geschwisterpfad vorhalten; alle geplanten Objekte fehlen. | Anlage zulässig; ausschließlich geplante Objekte angelegt, Geschwisterpfad unverändert. |
| V08 | P0 | Zwischen Vorprüfung und Write ein Zielobjekt durch einen kontrollierten zweiten Vorgang anlegen lassen. | `cas=0` verhindert Überschreiben. Kein automatisches Übernehmen fremder Objekte; bereits eigene Anlagen bleiben nachvollziehbar erhalten. |
| V09 | P0 | Metadaten-Leserecht für ein Ziel entziehen, 5xx beziehungsweise ungültige Antworten simulieren. | Kein Fehler gilt als Abwesenheit. Keine folgenden Writes und kein Restore; API-/Auditfehler enthalten keine Secret-Payload oder fremde Serverantwort. |
| V10 | P0 | Write-Timeout einmal vor und einmal nach tatsächlicher Anlage simulieren. | Vorgang angehalten; Wiederholung würfelt keine Werte neu. Zuordnung nur nach ausdrücklicher Prüfung, Metadatenabgleich und auditierter Bestätigung von eigener Anlage oder Abwesenheit. |
| V11 | P0 | Nach dem ersten Objekt Schreibrecht/Verbindung für das zweite unterbrechen, dann wiederherstellen und fortsetzen. Zusätzlich ein bestätigtes Objekt durch ein fremdes neu erzeugtes Objekt ersetzen. | Wiederaufnahme behält Werte, prüft Version und Erstellungszeit, schreibt nur ausstehende Objekte. Ersetztes oder verändertes Objekt wird abgelehnt. |
| V12 | P0 | Geschützte Eintragung in Semaphore nach erfolgreichem Restore scheitern lassen; anschließend fortsetzen. | Tenant bleibt unvollständig. Keine zweite Projektanlage; Role-ID als `var`, Secret-ID als `env`. Bereits vorhandene Secret-Einträge werden aktualisiert, Werte niemals zurückgegeben. |
| V13 | P0 | Ungültige App-/Provider-/Dataset-Vorgaben, zu kurzen DB-Wert und ungültigen Salt prüfen. Im Wizard zurück/vor navigieren und Entwurf speichern. | Ungültige Eingaben vor Writes abgelehnt. Generierung ausdrücklich gewählt; vorhandene Crypto-Werte bleiben erhalten. Secret-Inhalte weder im Entwurf noch Browser-Speicher oder Fehlerantwort. |
| V14 | P0 | Bestehenden Portal-Stand aktualisieren; offenen Vorgang nach Container-Neustart und aktualisierten AppRole-Credentials fortsetzen. Parallelen Execute-Aufruf testen. | Migration erhält Bestandsdaten. Gleicher Job wird nicht parallel ausgeführt; Ziele und KV-Werte bleiben stabil. Abschluss entfernt die verschlüsselte temporäre Payload. Keine Vault-Policy-/AppRole-/Secret-ID-Verwaltungsaufrufe. |

## GitLab und Programmpakete

Zusätzlich erforderlich: separates GitLab-Testprojekt mit der aktuellen Stack-Struktur, geschütztem Basisbranch, Test-Bot-Token und isoliertem CI-Runner; eine dazu passende Portal-Projektvorlage. Änderungen an Testbranches und Merge Requests sind ausdrücklich Teil dieser manuellen Abnahme. Einrichtung und CI-Vorlage: [GITLAB.md](GITLAB.md).

| ID | Prio | Prüfschritte | Erwartetes Ergebnis |
|---|---|---|---|
| G01 | P0 | Instanz, Projekt-ID, Basisbranch und Token speichern; Token leer lassen, rotieren und ablaufen lassen. | Keine Secret-Rückgabe; Rotation bei gleichem Projekt erhält Entwürfe. Ungültige Verbindung liefert verständlichen Fehler ohne Token/Antwortbody. |
| G02 | P0 | GitLab- und Paket-APIs als Viewer/Operator sowie ohne Session/CSRF aufrufen. Lesemodus mit Übergabe versuchen. | Admin- und CSRF-Grenzen greifen; Lesemodus erzeugt keinen Commit/MR. |
| G03 | P0 | Neue HTTP-Anwendung erzeugen und WordPress mit neuer ID kopieren; vor/zurück navigieren, speichern und neu laden. | Neue IDs/Profiles passen, Dateien und Entwurf bleiben erhalten. Noch kein GitLab-Schreibzugriff. |
| G04 | P0 | Fremden Programmkatalogeintrag, Providerdatei, Traversal, Symlink, privilegierten Compose-Service und Docker-Socket-Mount einbringen. | Serverseitige Ablehnung; keine Änderung fremder Dateien oder Ausführung im Backend. |
| G05 | P0 | SQL-Dataset hinzufügen, Hash/File/Provider/Engine absichtlich verändern und erneut prüfen. | SHA wird berechnet; unpassende Kombinationen/Hashes werden abgewiesen. Ein zulässiger Import wird zusätzlich in isolierter CI geprüft. |
| G06 | P0 | Entwurf parallel öffnen; in einer Sitzung ändern, in der anderen speichern/übergeben. | Versionskonflikt; Änderungen werden nicht überschrieben, alte Prüfung berechtigt nicht zur Übergabe. |
| G07 | P0 | Nach bestätigtem Commit und nach MR-Anlage jeweils Antwortverlust simulieren; Übergabe wiederholen. | Branch, Commit und MR werden abgeglichen; kein zweiter Commit/MR. Fremdänderungen blockieren. |
| G08 | P0 | Basisbranch nach Entwurfsanlage ändern, Branchschutz entfernen und zwei Übergaben gleichzeitig auslösen. | Abweichende Basis/fehlender Schutz/zweite Ausführung werden blockiert; kein Force-Push. |
| G09 | P0 | MR-Status aktualisieren; Pipelines mit falscher SHA, falschem Ref, pending/skipped/failed und success testen. | Angezeigte Pipeline ist revisionsgebunden. Nur die neueste erfolgreiche Basisbranch-Pipeline erlaubt die Übernahme. |
| G10 | P0 | Nach Review/Merge Snapshot vorbereiten, Diff prüfen, passende Vorlage/Repository wählen und aktivieren; parallele Aktivierung versuchen. | Neue Vorlage auf vollständiger SHA und aktiver Vault-Katalog werden atomar gespeichert. Quellvorlage/Bestandstenants bleiben unverändert; paralleler Wechsel ergibt Konflikt. |
| G11 | P0 | Auf einen früher aktivierten Snapshot zurücknehmen; unbestätigten historischen Snapshot als Rücknahme versuchen. | Nur bereits aktivierte Stände sind für die ausdrückliche Rücknahme zulässig; eigene Vorlage mit alter SHA, kein Git-/Tenant-Rollback. |
| G12 | P0 | Neue Vorlage im Tenant-Assistenten auswählen, neue Anwendung/Provider/Dataset freigeben, Registry-/Secret-Werte hinterlegen, bereitstellen und bereinigen. Alte oder manipulierte Git-SHA im Vault-Onboarding versuchen. | Katalog und Vorlage stimmen überein. Neues Paket funktioniert Ende zu Ende; alte/manipulierte Revision wird abgewiesen. Readiness, zwei parallele Deployments, TTL/Claims und vollständiges Cleanup protokollieren. |

## GIF-Hintergründe

| ID | Prio | Prüfschritte | Erwartetes Ergebnis |
|---|---|---|---|
| GIF01 | P1 | Animiertes GIF als Logo und Anmeldehintergrund hochladen; kopieren, speichern, exportieren/importieren und Seite neu laden. | Animation bleibt erhalten, eingebettete Bytes und Designauswahl werden übernommen; Größenlimits gelten. |
| GIF02 | P1 | Hintergrund-Unschärfe auf 0, 12 und 24 Pixel stellen; Desktop-/Mobilvorschau und tatsächliche Anmeldung prüfen. | Nur Hintergrund wird unscharf; Texte, Logo und Formular bleiben scharf und bedienbar. Kein horizontaler Überlauf. |

## Automatisierte Zuordnung

`backend/tests/test_gitlab.py` prüft Konfiguration, Kopien, Revisionen, Dateigrenzen, Compiler, Konflikte, Timeout-Wiederaufnahme, Hostzugriff, Pipeline-Gates, Aktivierung/Rücknahme und Migration. `frontend/src/test/GitLab.test.tsx` prüft Menükontext, Tokenformular, fehlende Verbindung, Paketworkflow, Konflikterhalt und Übernahmebestätigung. GIF-Fälle werden in `themes.test.ts`, `DesignCreator.test.tsx` und `App.test.tsx` geprüft. Aktuelle Laufzahlen: [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

Die Vault-Erweiterung ergänzt automatisierte Fehlerfall-, Migrations- und Oberflächentests. Die endgültigen Laufzahlen stehen im aktuellen [Implementierungsstand](VAULT_IMPLEMENTIERUNG.md#implementierungsstand). Ein Release-Kandidat benötigt einen protokollierten Testlauf; die simulierten Prüfungen ersetzen keine Live-Abnahme.

| Prüfdateien | Bereits automatisiert abgedeckte Ausschnitte |
|---|---|
| `backend/tests/test_auth.py`, `test_migrations.py` | Benutzername/E-Mail, Eindeutigkeit, Aktivierungsstatus, gemeinsames Login-Limit, CSRF, additive Datenübernahme |
| `backend/tests/test_projects.py` | Admin-Grenze, Projektoperationen, Defaults, Revisionen, Secret-Erhalt/Redaktion, SSH-Schreibvorgang, Passwortzwang und Sitzungswiderruf |
| `backend/tests/test_project_backup.py`, `test_creation_jobs.py` | Quellschutz, entfernte Trigger/Credentials, Defaults, Mehrfachfreigaben, skalare Vorgaben, Wiederholung und unklarer Restore |
| `backend/tests/test_policy.py`, `test_task_authorization.py` | Policy-Typen, manipulierte Werte/IDs, Startberechtigung und Statusaktualisierung |
| `backend/tests/test_semaphore_client.py` | Antwortformate, Redirect-Grenzen und validierte Task-Payload |
| `backend/tests/test_vault.py`, `test_migrations.py` | Verschlüsselung/Redaktion, Zielkonflikte und Löschhistorie, CAS-Rennen, Teilfehler, Timeout-Zuordnung, Credential-Übergabe/-Aktualisierung, Kataloggrenzen und additive Vault-Migration |
| `frontend/src/test/Vault.test.tsx` | Explizite Generierung, geschützte zentrale Eingaben, Wiederaufnahme, manuelle Timeout-Prüfung und Vor-/Zurück-Navigation ohne Secrets im Entwurf |
| `frontend/src/test/App.test.tsx`, `themes.test.ts` | Login, Benutzername ändern, Wizard-Auswahl/Fortschritt, Defaults-Editor, Löschbestätigung, Designwechsel/Import und festes Symbol |
| `.github/workflows/portal-ci.yml` | Backend-/Frontend-Suites, Produktionsbuild, Compose mit PostgreSQL/Caddy, Health und Login vor Image-Veröffentlichung |

Semaphore-Aufrufe in den Backend-Tests sind simuliert. Echte Secret-Verwendung, Quellinstanz-Version, Datenbankimporte, Mandantentrennung auf dem Zielhost, Vault-ACLs, TTL-Cleanup und produktive TLS-/Netzwerkwege bleiben integrierte Abnahmefälle.

Die Ausführungsbefehle stehen unter [Entwicklung](../README.md#entwicklung). Nach Code-/Konfigurationsänderungen die betroffenen automatisierten Tests und die zugehörigen P0-/P1-Abnahmefälle erneut ausführen.

## Protokollvorlage

```text
Test-ID:
Prüfer / Datum:
Portal-Commit und Backend-/Frontend-Image-Tags:
Semaphore-/Vault-/Stack-Version:
Umgebung und Testobjekt-IDs:
Verwendete Auswahl / Voraussetzungen:
Tatsächliches Ergebnis:
Status: offen | bestanden | fehlgeschlagen | blockiert | nicht anwendbar
Nachweis / Ticket / Begründung:
Aufräumarbeiten abgeschlossen:
```
