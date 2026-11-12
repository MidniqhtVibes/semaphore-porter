## Optionaler Betrieb

Die Container-Verwaltung verwendet einen eigenen optionalen Docker-Agenten. Ohne eingerichteten und aktivierten Agenten bleibt der reguläre Portalbetrieb nutzbar. Ein gebautes Agent-Image startet noch keinen Dienst.

## Voraussetzungen

Der Agent benötigt den administrativ freigegebenen Docker-Zugriff, eine begrenzte Host-Policy, einen Token, geeignetes HTTPS und ein persistentes Auftragsjournal. Gegenseitiges TLS kann den Zugriff zusätzlich über ein Client-Zertifikat absichern.

## Vorgehen

1. Host-Policy und erlaubte Projekte beziehungsweise Aktionen festlegen.
2. Dienst, Token, Zertifikate und Journal nach dem freigegebenen Betriebskonzept bereitstellen.
3. Unter **Einstellungen → Verbindungen → Docker-Agenten** die Verbindung konfigurieren und testen.
4. Zunächst nur lesend aktivieren und sichtbare Container, Logs und Messwerte prüfen.
5. Gewünschte Schreibaktionen separat freigeben und an entbehrlichen Testcontainern abnehmen.

> Docker-Zugriff ist eine administrative Berechtigung. Die auf dem Host gesetzten Grenzen müssen fremde Projekte und geschützte Semaporter-Komponenten ausschließen.

## Aktionen und Abgleich

Die Oberfläche bietet nur die freigegebenen Verwaltungsaktionen. Eine Aktion benötigt die aktuelle Vorschau und eine bewusste Bestätigung. Bei einem unklaren Ergebnis zuerst den vorhandenen Auftrag abgleichen, statt einen weiteren Auftrag anzulegen.

Die Integration ist vom Deployment-Monitoring unabhängig. Die Betreuung temporärer Deployments und ihrer TTL verbleibt im bestehenden Lifecycle des Deployment-Stacks.
