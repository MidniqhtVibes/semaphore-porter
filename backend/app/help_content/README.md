# Redaktionelle Pflege der integrierten Hilfe

`catalog.json` enthält Kategorien, Artikel-Metadaten, Zielgruppen und Kontextzuordnungen. Jede Artikel-ID verweist ausschließlich auf die gleichnamige Markdown-Datei in diesem Verzeichnis. Inhalte werden vom Backend nach Anmeldung und Berechtigungsprüfung ausgeliefert; sie gehören nicht in den öffentlichen Frontend-Assetordner.

- `audience`: `all` für angemeldete Personen, `admin` nur für Systemadmins.
- `quick_steps`: kurze, vollständige Hilfeschritte für das Seitenpanel.
- `keywords`: Begriffe und bekannte Fehlermeldungen für die Suche.
- `contexts`: stabile Kontext-ID, Artikel-ID und optional ein vorhandener Abschnittsanker. Abweichende Kurztexte können pro Kontext angegeben werden.
- `content_version`: redaktioneller Stand; bei fachlichen Änderungen aktualisieren und mit der lokalen Implementierung abgleichen.

Markdown beginnt mit Überschriften der Ebene 2. Die Artikelseite stellt den Titel separat dar. Abschnittsanker werden aus den Überschriften abgeleitet; bestehende verlinkte Überschriften nicht ohne Aktualisierung der Kontextverweise ändern. Artikelverweise verwenden relative IDs, beispielsweise `[Registry-Zugänge](registry-profile)`. HTML, ausführbare Inhalte und externe Bildabrufe gehören nicht in die Hilfe. Vertrauliche Angaben und installationsspezifische Pipeline-/Serverdateien bleiben außerhalb der Artikel.

Nach Änderungen die Tests für Rollen, direkte Artikelaufrufe, Suche, Kontextanker und Querverweise ausführen. `help_service.library.cache_clear()` ist nur für Tests beziehungsweise Wartungswerkzeuge vorgesehen; im Betrieb wird ein neuer Inhaltsstand mit dem aktualisierten Backend ausgeliefert.
