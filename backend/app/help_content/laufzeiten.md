## Drei unterschiedliche Zustände

| Ebene | Aussage |
| --- | --- |
| Task | Status und Dauer des Automatisierungslaufs in Semaphore. |
| Deployment | Bereitgestellte Umgebung mit eigener Identität und gegebenenfalls Ablaufzeit. |
| Container | Einzelner Prozess beziehungsweise Dienst innerhalb dieser Umgebung. |

Ein Task kann nach der erfolgreichen Bereitstellung abgeschlossen sein, während seine Container weiterlaufen. Die Tasklaufzeit ist deshalb keine Restlaufzeit des bereitgestellten Programms.

## TTL und Cleanup

Die TTL begrenzt die Lebensdauer eines temporären Deployments. Ein Countdown zeigt die verbleibende Zeit anhand der gemeldeten Ablaufzeit. Nach Ablauf erledigt der Deployment-Stack den vorgesehenen Cleanup.

Ein abgelaufener Countdown bestätigt noch keine tatsächliche Löschung. Ein frischer Hostzustand oder eine gezielte administrative Prüfung liefert diesen Nachweis.

## Datenqualität beachten

Veraltete oder unvollständige Monitoring-Meldungen sind entsprechend gekennzeichnet. Ohne frische Daten kann der aktuelle Zustand nicht zuverlässig bestätigt werden. Laufende Container beweisen außerdem nicht automatisch, dass die Anwendung vom Arbeitsplatz aus erreichbar ist.

Die Taskliste funktioniert unabhängig vom optionalen Host-Monitoring. Weitere Informationen: [Task-Feed](task-feed) und [Mail-Link öffnen](mail-link).
