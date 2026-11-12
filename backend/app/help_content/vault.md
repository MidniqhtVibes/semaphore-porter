## Mounts und Pfade

Der KV-v2-Mount bezeichnet die Secret-Engine. Der Secret-Pfad liegt innerhalb dieses Mounts. Der AppRole-Auth-Mount ist davon unabhängig und wird ohne `auth/` oder `/login` angegeben. Ein vorhandener Mount kann beispielsweise `semaphore-ansible` heißen; `approle` ist kein zwingender Name.

## Schreib- und Leseaufgaben

| Zugang | Aufgabe |
| --- | --- |
| Tenant-Schreiber | Zielobjekte prüfen und neue Tenant-Secrets mit Create-only-Verhalten anlegen; bei Bereinigung belegte Tenant-Objekte löschen. |
| Semaphore-Leser | Die vom Deployment-Stack benötigten Tenant-Secrets lesen. |
| SSH-Leser | Die freigegebenen versionierten SSH-Secret-Quellen lesen. |
| Registry-Leser | Die freigegebenen versionierten Registry-Secret-Quellen lesen. |

Die Zugänge werden an den jeweiligen Konfigurationsstellen getrennt hinterlegt. Vault-Policies und AppRoles werden durch die zuständigen Vault-Verantwortlichen verwaltet. Semaporter vergibt keine neuen Vault-Berechtigungen.

## Vorgehen

1. **Einstellungen → Verbindungen → Vault** öffnen.
2. Basisadresse, gegebenenfalls Namespace, KV-v2-Mount und die vorgesehenen Tenant-Pfadbereiche kontrollieren.
3. Die AppRole-Auth-Mounts und die Role-/Secret-IDs für Schreiber und Semaphore-Leser zuordnen.
4. Verbindung prüfen und die automatische Anlage bei Bedarf aktivieren.
5. Im Tenant-Ersteller den Vault-Plan kontrollieren. Vorhandene Anwendungswerte eintragen oder geeignete neue Werte generieren lassen.

Vor dem ersten Schreiben müssen sämtliche geplanten Zielobjekte nachweislich fehlen. KV-v2-`cas=0` verhindert das Überschreiben vorhandener Objekte. Bei unklaren Schreibergebnissen die tatsächlichen Zielobjekte zuerst prüfen und den gespeicherten Vorgang kontrolliert fortsetzen.

## Bereinigung und Rechte

Für die vollständige Tenant-Bereinigung benötigt der Schreiber die vorgesehenen Löschrechte auf den konkreten KV-v2-Metadatenpfaden. Dadurch werden alle Versionen dieser Objekte entfernt. Gemeinsame SSH- und Registry-Quellpfade gehören nicht in die Tenant-Löschfreigabe.

## Fehlerbehebung

Bei `no handler for route` den tatsächlich aktivierten Auth-Mount prüfen. Bei einer CSRF-Meldung zunächst die Semaporter-Sitzung und den verwendeten HTTP-/HTTPS-Ursprung kontrollieren. Die Sperre liegt dann vor dem eigentlichen Vault-Schreibzugriff.

Weitere Informationen: [SSH-Profile](ssh-profile), [Registry-Profile](registry-profile), [Tenant-Bereinigung](tenant-bereinigen).
