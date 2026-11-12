## Voraussetzungen

Sie benötigen Zugriff auf den Tenant und das Startrecht für einen aktiven Task. Seine Policy legt fest, welche Parameter bearbeitet werden können. Fixed- und Hidden-Werte ergänzt das Backend.

## Vorgehen

1. Unter **Meine Projekte** den Tenant und den gewünschten Task öffnen.
2. Die angebotenen Werte kontrollieren. Bei Provider und Dataset eine für die Anwendung freigegebene Kombination wählen.
3. Bei Bedarf den **Mailbericht** aktivieren. Der angezeigte Empfänger entspricht der Login-E-Mail Ihres Kontos und wird serverseitig gesetzt.
4. **Task jetzt starten** wählen. Ist eine Genehmigung erforderlich, stattdessen einen begründeten Antrag stellen.
5. In der Task-Detailansicht den Status und die Ausgabe verfolgen.

> Ein freigegebener Task kann echte Änderungen auf dem Zielsystem ausführen. Die beschriebene Wirkung und die gewählte Umgebung vor dem Start prüfen.

## Ergebnis prüfen

Ein erfolgreicher Start liefert eine Semaphore-Task-ID. Das spätere Ergebnis steht in der Ausgabe und in der Historie. Ein erfolgreicher Ansible-Abschluss kann ein weiterhin laufendes Deployment hinterlassen.

Bei unklarem Startresultat zuerst kontrollieren lassen, ob Semaphore bereits eine Ausführung angelegt hat. Ein erneuter Klick ist kein geeigneter Ersatz für diesen Abgleich.

## Fehlerbehebung

Bei abgelehnten Parametern die markierten Felder korrigieren. Bei API- oder SSH-Fehlern Task-ID, Zeitpunkt und bereinigte Fehlermeldung an die Administration weitergeben. Keine Tokens oder privaten Schlüssel mitsenden.

Weitere Informationen: [Genehmigungen](genehmigungen), [Task-Feed](task-feed), [Mail-Link öffnen](mail-link).
