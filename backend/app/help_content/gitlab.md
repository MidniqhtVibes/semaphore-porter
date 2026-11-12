## Geltungsbereich

Die GitLab-Anbindung verbindet Semaporter mit dem Projekt, das den Deployment-Stack und die Programmpakete enthält. Dieses Projekt ist vom Repository des Semaporter-Anwendungscodes zu unterscheiden.

## Vorgehen

1. **Einstellungen → Verbindungen → GitLab** öffnen.
2. GitLab-Adresse, numerische Projekt-ID, Basisbranch und den vorgesehenen API-Zugang eintragen.
3. Verbindung und Branchschutz prüfen. Den Schreibmodus erst für den freigegebenen Arbeitsablauf aktivieren.
4. Unter **Entwicklung → Programmpakete** ein Paket nach dem unterstützten Manifestvertrag vorbereiten und validieren.
5. Die Änderung über den vorgesehenen Review-Ablauf einreichen.
6. Merge und erfolgreiche Pipeline für den tatsächlichen Basisbranch-Commit abwarten.
7. Unter **Versionen & Übernahme** den geprüften Stand ausdrücklich übernehmen.

## Paketvertrag

Ein Paket muss Anwendung, unterstützte Provider, benötigte Dateien, Eingaben und gegebenenfalls Datensätze nachvollziehbar deklarieren. Ein Image-Name allein liefert keine vollständige Bereitstellungsdefinition.

Registry-Pull-Zugang, GitLab-API-Token und Git-SSH-Schlüssel erfüllen unterschiedliche Aufgaben. Jeder Zugang benötigt die Rechte für seinen konkreten Verwendungszweck.

## Ergebnis prüfen

Commit, Merge Request, Pipeline und übernommener Katalogstand müssen zusammenpassen. Anschließend den Tenant-Ersteller und einen geeigneten Deployment-Test gegen den übernommenen Stand prüfen. Die Semaporter-CI/CD-Pipeline bleibt ein separat administrierter Betriebsprozess.
