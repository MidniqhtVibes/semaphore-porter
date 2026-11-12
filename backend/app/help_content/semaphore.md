## Voraussetzungen

Das Backend benötigt eine erreichbare Semaphore-API und einen geeigneten Service-Token. Portalbenutzer führen Tasks über diesen Backend-Zugang aus; es wird dadurch kein eigenes Semaphore-Konto für jede Person angelegt.

## Vorgehen

1. **Einstellungen → Verbindungen → Semaphore-Verbindung** öffnen.
2. Die vollständige HTTP(S)-Basisadresse und den Service-Token eintragen.
3. Einen Firmenproxy nur für den tatsächlich vorgesehenen Backend-Zugriffsweg konfigurieren.
4. Die Verbindung prüfen und speichern.
5. Projekte importieren beziehungsweise zuordnen und einen freigegebenen Task abnehmen.

Der Verbindungsnachweis bestätigt die API-Anbindung. Git-, SSH-, sudo-, Vault- und Registry-Rechte des späteren Deployments benötigen eigene Prüfungen.

## Fehlerbehebung

- **HTTP 401:** Token und die Berechtigung seines Semaphore-Kontos prüfen.
- **Connection refused / nicht erreichbar:** Adresse, Zielport, DNS und den expliziten Backend-Proxy abgleichen.
- **HTTP 500 beim Taskstart:** Den Zeitpunkt und die IDs mit dem Semaphore-Serverlog abgleichen. Dort kann beispielsweise ein nicht nutzbarer Schlüssel benannt sein.
- **HTML statt JSON:** Basisadresse und Weiterleitung des Reverse-Proxys kontrollieren.

WebSocket-Fehler eines Semaphore-Browserfensters sind getrennt von der eigentlichen Taskstart-Fehlermeldung zu bewerten. Die Semaporter-Taskansicht verwendet regelmäßige API-Abfragen.
