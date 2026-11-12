## Voraussetzungen

Der Tenant-Ersteller ist für Systemadmins vorgesehen. Benötigt werden eine geeignete Projektvorlage und eine erreichbare Semaphore-Anbindung. Bei automatischer Secret- oder Schlüsselversorgung müssen die zugehörigen Zugänge eingerichtet sein.

Ein bestehendes Projekt kann als Ausgangspunkt für einen neuen Tenant dienen. Der neue Tenant benötigt eine eigene technische Zuordnung. Kopierte, maskierte Secrets ersetzen keine verfügbare Secret-Quelle.

## Vorlage

Eine passende Projektvorlage wählen. Enthaltene Tasks, Variablengruppen, Repositories, Inventories und Auswahlwerte bilden die Ausgangsbasis. Die Quellvorlage bleibt erhalten.

## Tenant

Projektnamen, Tenant-Slug, Runtime-Scope, Anzeigenamen und Beschreibung festlegen. Technische Kennungen bewusst wählen; `tenant_slug` und `runtime_scope_id` werden unter **Semaphore-Defaults** gespeichert und beeinflussen die Laufzeit- und Vault-Zuordnung.

## Anwendungen

Die unterstützten Anwendungen, Datenbankprovider und Testdatensätze auswählen. Bei mehreren Werten die gewünschte Vorgabe kontrollieren. Die Auswahl bereitet die Projektkonfiguration vor; ein Deployment oder Datenimport beginnt erst mit einem Task.

## Ressourcen

Benötigte Tasks und Variablengruppen auswählen sowie Repository und Inventory prüfen. Host- und Git-SSH-Profile nach ihrem jeweiligen Zweck zuordnen. Für repositorybasierte Datei-Inventories den angebotenen statischen Import prüfen; spätere Repository-Änderungen ändern eine statische Kopie nicht automatisch.

## Presets

Passende Variablenvorgaben ergänzen. Bei aktivierter Vault-Anlage je Anwendung ein Registry-Profil zuordnen. Vorhandene Anwendungs-Secrets bewusst eintragen; erlaubte neue Werte können erzeugt werden.

## Berechtigungen

Benutzer oder Gruppen zuordnen und die vorgesehenen Task-Policies kontrollieren. Bei optionaler Genehmigung einen anderen aktiven Portalbenutzer auswählen und Kosten-/Aufwandsklassen festlegen.

## Validieren

Die Konfiguration validieren und Fehler beheben. Warnungen, Vault-Zielobjekte und Schlüsselzuordnungen prüfen. Änderungen nach der Vorschau benötigen eine erneute Validierung. Die Validierung legt noch keine Tenant-Secrets an.

## Erstellen

**Projekt verbindlich erstellen** bestätigt die geplanten externen Änderungen. Vorhandene Vault-Objekte werden nicht überschrieben. Bei unklarem Schreibergebnis die tatsächlichen Objekte abgleichen und den gespeicherten Vorgang kontrolliert fortsetzen.

## Ergebnis prüfen

Semaphore-Projekt, Variablen, Taskfreigaben und belegte Vault-Objekte kontrollieren. Den Tenant erst nach einem geeigneten Testlauf als betriebsbereit einordnen.

Verwandte Anleitungen: [Anwendungen und Daten](anwendungen-daten), [SSH](ssh-profile), [Registry](registry-profile), [Vault](vault), [Bereinigung](tenant-bereinigen).
