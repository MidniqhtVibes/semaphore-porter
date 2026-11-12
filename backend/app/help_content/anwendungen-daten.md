## Auswahl und Wirkung

Der Tenant-Ersteller unterstützt mehrere Anwendungen sowie mehrere freigegebene Datenbankprovider und Testdatensätze. Die Projektvorlage und der Katalog bestimmen, welche Werte angeboten und kombiniert werden dürfen.

Die Auswahl legt erlaubte Werte und eine Vorgabe in der Tenant-Konfiguration fest. Die tatsächliche Bereitstellung und ein möglicher Testdatenimport werden durch einen späteren Task ausgelöst.

## Vorgehen

1. Die benötigten Anwendungen auswählen.
2. Die von diesen Anwendungen unterstützten Provider wählen. Der aktuelle Stack umfasst beispielsweise AzubiOrga mit PostgreSQL sowie WordPress mit passenden MySQL-/MariaDB-Providern.
3. Katalogisierte Datensätze für die jeweilige Kombination auswählen und die gewünschte Vorgabe prüfen.
4. Beim Taskstart die tatsächlich gewählte Kombination kontrollieren.

`none` ist eine technische Auswahl für einen Ablauf ohne Dataset, sofern der jeweilige Katalog sie anbietet. Dieser Wert ist kein Datenbankprovider.

## Voraussetzungen für neue Pakete

Eine neue Anwendung benötigt einen unterstützten Paketvertrag mit Manifest, Providerzuordnung und gegebenenfalls Dataset-Definitionen. Ein weiterer Name im Formular stellt noch kein lauffähiges Programmpaket bereit.

Bei einer Meldung über einen nicht unterstützten Provider zunächst die konkrete Anwendung und den verwendeten Katalogstand abgleichen. Vorlagen und freigegebene Pakete müssen denselben Vertrag verwenden.
