## Status und Aktualisierung

**Laufende Tasks** erfasst die für Sie sichtbaren, über Semaporter gestarteten Ausführungen. Die aktive Liste wird alle fünf Sekunden abgefragt. In der Detailansicht werden Status und Ausgabe während aktiver oder unbekannter Zustände alle zwei Sekunden aktualisiert.

| Anzeige | Bedeutung |
| --- | --- |
| Wartet | Semaphore hat den Auftrag angenommen; die Ausführung wartet noch. |
| Läuft | Die zuletzt bestätigte Semaphore-Meldung beschreibt eine aktive Ausführung. |
| Erfolgreich / Fehlgeschlagen / Abgebrochen | Der bestätigte Endzustand der Ausführung. |
| Status unbekannt | Ein aktueller Zustand konnte nicht bestätigt werden. |

Abgeschlossene Tasks wechseln nach dem Abgleich in die Historie. Die Historie enthält höchstens die letzten 200 sichtbaren Ausführungen; ältere aktive Tasks bleiben in der aktiven Ansicht berücksichtigt.

## Automatisches Scrollen

Die Ausgabe öffnet am Ende und folgt neuen Zeilen. Wenn Sie nach oben scrollen, pausiert das automatische Folgen. **Zum neuesten Eintrag** oder manuelles Scrollen bis zum Ende aktiviert es erneut. Dabei bewegt sich nur der Ausgabebereich.

## Laufzeit und Verbindungsfehler

Laufzeiten verwenden verfügbare Semaphore-Start- und Endzeiten. Wartezeit oder ein unbestätigter Zustand werden nicht als gesicherte Ausführungslaufzeit dargestellt.

Bei einem vorübergehenden Abruffehler versucht die Ansicht die Aktualisierung erneut. Eine Fehlermeldung oder ein unbekannter Status bedeutet nicht, dass der Task beendet oder ein Deployment entfernt wurde.

Weitere Informationen: [Task und Deployment unterscheiden](laufzeiten).
