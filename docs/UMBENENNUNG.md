# Umbenennung zu Semaporter

Stand: 26.10.2026.

Die Anwendung heißt **Semaporter**. Oberfläche, Anmeldemaske, Browser-Titel, App-Manifest, Backend-API-Titel, HTTP-Clientkennung, npm-Paket, Dokumentation und Präsentation verwenden diesen Namen. Neue Images heißen `semaporter-backend` und `semaporter-frontend`; lokale Builds verwenden beispielsweise `semaporter-local-backend:dev` und `semaporter-local-frontend:dev`.

## Bestehende Daten erhalten

`COMPOSE_PROJECT_NAME` in `.env` legt fest, welcher Stack und welche zugehörigen Volumes angesprochen werden. In der vorhandenen lokalen Installation bleibt dafür `semaphore-porter-local` erhalten. Neue Installationen können `semaporter` beziehungsweise `semaporter-local` verwenden. Die Service-Namen, Volume-Schlüssel und Datenbanktabellen werden durch die Produktumbenennung nicht geändert.

Bei bestehenden Installationen auch `POSTGRES_DB`, `POSTGRES_USER`, Passwörter und Anwendungsschlüssel beibehalten. Die neuen Datenbanknamen in `.env.example` sind Vorgaben für Neuinstallationen. Die lokale Umstellung ändert keine Benutzerkonten oder Datenbankinhalte.

Die Anleitungen verwenden deshalb `docker compose` ohne fest eingebauten Projektnamen. Der passende Name kommt aus `.env`, auch wenn sich später der Verzeichnisname ändert. Ein ausdrücklich angegebenes `-p` hat weiterhin Vorrang und muss zu diesem bestehenden Stack passen.

## Browser-Einstellungen

Neue Speicherwerte verwenden die Präfixe `semaporter.designs.v1` und `semaporter.navigation.v1`. Die Anwendung liest bisherige Schlüssel weiter als Rückfall, damit Designwahl, eigene Designs und aufgeklappte Kategorien erhalten bleiben. Alte Standard-Produkttexte in eigenen Designs werden aktualisiert. Individuelle Firmenbezeichnungen, Logos und rechtliche Texte bleiben erhalten; lediglich der frühere Standard-Footer wird zum neuen Produktnamen geändert.

## GitHub, Images und Verzeichnis

Die GitHub-Adresse und der geöffnete Workspace-Ordner behalten ihren bisherigen technischen Namen. Das Remote-Repository wird durch diese lokale Änderung nicht umbenannt. Es erfolgt kein Push. Ein Umbenennen des geöffneten Ordners während der Arbeit würde die Workspace-Pfade ändern; der Produktname ist davon unabhängig.

Der CI-Workflow veröffentlicht bei den bereits vorgesehenen Release-Auslösern unter `ghcr.io/<owner>/semaporter-backend` und `ghcr.io/<owner>/semaporter-frontend`. Das funktioniert auch bei einem abweichenden GitHub-Repositorynamen. Vor dem ersten Pull müssen diese neuen Images für den gewählten Tag tatsächlich veröffentlicht sein. Für Bestandsinstallationen kann `PORTAL_IMAGE_REGISTRY` bis dahin die bisherige Adresse behalten.

Semaphore UI und die Semaphore-API behalten ihren eigenen Produktnamen. Das benachbarte Repository `azubiorga-semaphore-git` gehört zum Deployment-Stack und wird durch diese Umbenennung nicht verändert.
