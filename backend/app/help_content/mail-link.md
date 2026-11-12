## Voraussetzungen

Die Testanwendung muss noch laufen. Verwenden Sie den Link aus dem Bericht der konkreten Ausführung; verschiedene Deployments können unterschiedliche Ports erhalten.

## Vorgehen

1. Schema, Host und Port im Mail-Link kontrollieren.
2. Die Deployment-Laufzeit und gegebenenfalls den zuletzt gemeldeten Hostzustand prüfen lassen.
3. Bei einer Proxy-Fehlerseite den genauen Ablehnungsgrund, die Adresse und den Zeitpunkt festhalten.
4. Den Zugriff mit der zuständigen Netzwerk- oder Systemadministration abgleichen.

Die Empfängeradresse steuert den Mailversand. Sie erteilt keine personenbezogene Freigabe am Browserproxy. Unterschiedliche Systemproxy-, PAC- oder Browser-Erweiterungseinstellungen können deshalb zu unterschiedlichen Ergebnissen führen.

## Weiterleitungen verstehen

Eine Weiterleitung auf einen Anmeldepfad derselben Anwendung kann zum normalen Ablauf gehören. Wechselt das Ziel auf einen unerwarteten Host, ein anderes Schema oder einen falschen Port, muss die veröffentlichte Basisadresse geprüft werden.

Eine erfolgreiche TCP-Verbindung bestätigt zunächst den erreichbaren Port. Eine HTTP-Antwort und die tatsächlich nutzbare Anwendungsseite sind zusätzliche Prüfschritte.

## Dauerhafter Zugriffsweg

Die zuständige Stelle legt eine gezielte Proxy-Freigabe beziehungsweise eine freigegebene direkte Route fest. Bei wechselnden Deployment-Ports ist der vorgesehene Testportbereich einzubeziehen. Die Proxy-Einstellung der Semaphore-Verbindung betrifft den Backend-Zugriff und steuert diesen Browserzugriff nicht.
