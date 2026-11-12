## Voraussetzungen

Die Bereinigung ist eine administrative, dauerhafte Aktion. Temporäre Deployments regulär auslaufen lassen. Dauerhafte Deployments müssen zuvor bewusst stillgelegt werden. Ungeklärte genehmigte Startversuche sind zuerst mit Semaphore abzugleichen.

## Löschumfang

Die Vorschau zeigt die belegten eigenen Ressourcen: Tenant-Daten, zugehörige Freigaben, Policies, Ausführungen, Genehmigungen, Logo und tenantbezogene Audit-Ereignisse. Ein belegtes eigenes Semaphore-Projekt und die belegten tenantbezogenen Vault-Objekte werden ebenfalls bereinigt.

Gemeinsam genutzte Benutzer, Gruppen, SSH-/Registry-Profile und GitLab-Quellprojekte bleiben erhalten. Nicht belegte externe Ressourcen und beliebige Serverdateien werden nicht pauschal gesucht oder entfernt.

> Beim Löschen der Vault-Metadaten werden alle Versionen des konkreten KV-v2-Objekts dauerhaft entfernt. Die Vorschau und den freigegebenen Pfadbereich sorgfältig kontrollieren.

## Vorgehen

1. Unter **Tenants** den Tenant öffnen und die Löschvorschau anfordern.
2. Blockierende Deployments und unklare Startversuche klären.
3. Den genauen Tenant-Slug und die bewusste Deployment-Prüfung bestätigen.
4. Die Bereinigung ausführen und ihr Ergebnis kontrollieren.

## Rechte und Wiederaufnahme

Der Vault-Schreiber benötigt zusätzlich die vorgesehenen Löschrechte auf den konkreten Tenant-Metadatenpfaden. Gemeinsame Secret-Bereiche gehören nicht zu dieser Freigabe.

Bei einem Fehler bleiben erledigte Schritte im laufenden Vorgang gespeichert. Die Vorschau erneut prüfen und **Bereinigung fortsetzen** verwenden. Nach einem Timeout zuerst den tatsächlichen Zustand abgleichen. Der erfolgreiche Abschluss entfernt entsprechend dem gewählten Umfang auch den tenantbezogenen Verlauf.
