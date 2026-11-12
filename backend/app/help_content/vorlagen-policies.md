## Projektvorlagen

Eine Basisvorlage enthält eine geprüfte Projektstruktur mit Repositories, Inventories, Variablengruppen und Task-Templates. Verwenden Sie eine nachvollziehbare Quelle, deren Anwendungs-, Provider- und Dataset-Auswahl zum Katalog passt.

Die Vorlage dient als Ausgangspunkt für neue Tenants. Projektspezifische Kennungen und Secrets sind vor der Verwendung als Vorlage zu überprüfen. Maskierte Secret-Felder können nicht als wiederhergestellte Geheimnisse betrachtet werden.

## Presets

Presets ergänzen wiederverwendbare Variablenvorgaben, beispielsweise für Laufzeit oder öffentliche Anwendungseinstellungen. Ihre tatsächliche Wirkung ergibt sich aus dem gebundenen Deployment-Stack und der abschließenden Vorschau.

## Task-Policies

Eine aktive Policy beschreibt die zulässigen Parameter eines freigegebenen Tasks. Geeignete Regeln umfassen erlaubte Auswahlwerte, Zahlenbereiche, boolesche Werte und begrenzte Texte. Fixed- und Hidden-Werte werden serverseitig ergänzt.

Nach Änderungen am Semaphore-Survey den importierten Formularstand und die Regeln gemeinsam prüfen. Ein sichtbares Feld ohne passende Freigabe ist kein Ersatz für eine serverseitige Policy.

## Ergebnis prüfen

Mit einem vorgesehenen Operator-Konto den erlaubten Ablauf ausführen. Unzulässige Werte, zusätzliche Parameter und entzogene Startrechte müssen abgewiesen werden. Bei aktiviertem Genehmigungsworkflow auch die administrative Kosten-/Aufwandsklasse prüfen.
