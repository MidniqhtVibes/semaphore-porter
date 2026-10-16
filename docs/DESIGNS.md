# Designs und eigene Unternehmensfarben

Der Menüpunkt **Designs** steht in Administration und Benutzerportal zur Verfügung. Enthalten sind **GitHub Black** als bisherige Voreinstellung sowie **SIT Hell** und **SIT Dunkel**. Die SIT-Varianten orientieren sich an der bereitgestellten Look-&-Feel-Richtlinie vom 10.09.2025: Anthrazit `#414146`, Hellgrau `#ececec`, Grün `#50be46` beziehungsweise Hellgrün `#9bd78c` und Sora in Regular, Medium und SemiBold. Für lesbare Bedienelemente und Statushinweise werden ergänzend abgestufte Kontrastfarben verwendet.

In beiden SIT-Varianten erscheint die vom Betreiber bereitgestellte transparente weiße PNG-Marke in Navigation und Anmeldung. Die Datei wird unverändert aus `frontend/public/branding/sit-logo.png` geladen und auf einem grünen beziehungsweise hellgrünen Feld dargestellt. Die ursprüngliche `sit-logo.png` im Repository bleibt erhalten. GitHub Black verwendet weiterhin die neutrale Schlüsselmarke.

Die Schrift liegt lokal unter `frontend/public/fonts/Sora-Variable.ttf`; Browser laden keine Schrift von Google nach. Quelle: [Google Fonts – Sora](https://github.com/google/fonts/tree/main/ofl/sora), Lizenz: `frontend/public/fonts/OFL-Sora.txt`.

## Auswahl und Speicherung

**Design verwenden** aktiviert die gewählte Variante unmittelbar. Sie gilt anschließend für Anmeldung, Administration und Benutzerportal auf derselben Browser-Origin. Auswahl und eigene Designs liegen im lokalen Browser-Speicher; sie ändern keine Server-Konfiguration und werden nicht zwischen Geräten oder Benutzerkonten synchronisiert. Bei gesperrtem Browser-Speicher bleibt die Darstellung für die aktuelle Sitzung aktiv. Ohne gespeicherte Auswahl und bei ungültigen gespeicherten Daten wird GitHub Black verwendet.

## Website-Symbole und Windows-Taskleiste

Unter **Designs → Website-Symbol** sind drei neutrale Vorschläge auswählbar:

| Vorschlag | Idee |
|---|---|
| Portal-Tor (Voreinstellung und Empfehlung) | Ein Eingang mit Pfeil als zentraler Zugang zu Projekten und Tasks |
| Mandanten-Verbund | Verbundene Bausteine für die Mandantenverwaltung |
| SP-Monogramm | Die Initialen von Semaphore Porter |

Die Auswahl ist unabhängig vom Farbschema und bleibt im Browser gespeichert. SVG- und ICO-Favicons sowie Touch-Icons wechseln mit. Die originalen SVG-Entwürfe liegen in `frontend/public/icons/`; ICO-Dateien enthalten 16-, 32- und 48-Pixel-Varianten. Zusätzlich sind PNG-Dateien mit 180, 192 und 512 Pixeln enthalten. `/favicon.ico` ist die statische Portal-Tor-Rückfallvariante.

Für eine eigene Windows-App-Verknüpfung zuerst das gewünschte Website-Symbol wählen. In Edge anschließend **Einstellungen und mehr → Weitere Tools → Apps → Diese Website als App installieren** verwenden und die App an die Taskleiste anheften. Je nach Edge-Version ist **Apps** direkt im Hauptmenü verfügbar. Die zugehörigen Manifeste liegen unter `/manifests/` und verwenden eine gemeinsame App-ID; die Symbolauswahl erzeugt keine andere Anwendungsidentität. Bereits installierte Verknüpfungen können das frühere Symbol zwischenspeichern und müssen gegebenenfalls neu installiert werden. Die App benötigt weiterhin eine Verbindung zum Portal; es wird kein Offline-Modus ergänzt.

Die Installation und Taskleistenverwaltung beschreibt auch [Microsoft Support](https://support.microsoft.com/de-de/edge/install-manage-or-uninstall-apps-in-microsoft-edge). Symbole und Manifeste werden lokal ausgeliefert; zur Laufzeit werden keine Markenressourcen von externen Webseiten geladen.

## Eigene Designs ohne Codeänderung

1. Unter **Designs → JSON-Vorlage** eine Datei herunterladen oder das aktive Design exportieren.
2. ID, Namen und Farben anpassen.
3. Die Datei unter **Eigenes Design verwenden** importieren. Sie wird als eigene Variante gespeichert und sofort aktiviert. Derselbe `id` aktualisiert einen vorhandenen Import.
4. Die JSON-Datei kann an andere Installationen oder Kollegen verteilt und dort importiert werden.

Beispiel:

```json
{
  "schema_version": 1,
  "id": "meine-firma",
  "name": "Meine Firma",
  "base": "github-dark",
  "font": "system",
  "radius": 6,
  "colors": {
    "accent": "#b6a4ff",
    "accent-hover": "#d2c6ff",
    "nav-indicator": "#b6a4ff",
    "primary": "#b6a4ff",
    "on-primary": "#161b22"
  }
}
```

Nicht angegebene Werte werden aus `base` übernommen. Zulässig sind `github-dark`, `sit-light` und `sit-dark`. `font` erlaubt die lokale Sora-Schrift oder die vorhandene Systemschrift. `radius` ist eine ganze Zahl von 0 bis 16 Pixeln. Der Import akzeptiert höchstens 50 KB und speichert maximal 20 eigene Varianten. Eigene Designs können entfernt werden; beim Entfernen der aktiven Variante wird GitHub Black aktiviert.

Eigene Design-Dateien verwenden standardmäßig die neutrale Bildmarke, auch bei einer SIT-Farbbasis. Das optionale Feld `branding` erlaubt ausdrücklich `neutral` oder `sit`. Beim Export einer eingebauten SIT-Variante wird `branding: "sit"` mitgeführt; für eine andere Unternehmensidentität auf `neutral` setzen. Die Website-Symbolwahl ist eine unabhängige Browser-Einstellung und kein Bestandteil der Design-Datei.

Das maschinenlesbare [JSON-Schema](../frontend/public/themes/theme.schema.json) beschreibt alle Felder. Es wird zusammen mit der [Beispieldatei](../frontend/public/themes/example.theme.json) unter `/themes/` ausgeliefert. Die Formatversion ist `schema_version: 1`.

Wichtige Farbschlüssel:

| Schlüssel | Verwendung |
|---|---|
| `bg`, `header`, `surface`, `surface-alt`, `surface-soft` | Seiten-, Navigations-, Karten- und Eingabeflächen |
| `text`, `muted` | Haupt- und Begleittexte |
| `accent`, `accent-hover`, `accent-soft`, `accent-border` | Links, Fokus und Hervorhebungen |
| `nav-indicator` | Markierung des aktiven Menüpunkts |
| `primary`, `primary-hover`, `primary-border`, `on-primary` | Primäre Aktion und ihre Textfarbe |
| `success`, `warning`, `danger` und jeweilige `-soft`/`-border`-Werte | Status- und Fehlerrückmeldungen |
| `border`, `border-soft`, `hover`, `overlay` | Trennlinien, Interaktion und Dialoghintergrund |

Farben müssen Hex-Werte sein. Transparenz ist nur für die im Schema ausgewiesenen Hinweisflächen und Rahmen erlaubt. Für Haupttext, Begleittext und die primäre Schaltfläche prüft der Import einen Mindestkontrast von 4,5:1. Die Prüfung ersetzt keine vollständige Barrierefreiheitsprüfung aller Zustände. Beliebiges CSS, externe Ressourcen und Skripte werden nicht importiert.

Für zusätzliche fest mitgelieferte Designs können Entwickler die zentrale Liste in `frontend/src/designs/themes.ts` ergänzen und das Frontend neu bauen. Eine globale Unternehmensvorgabe über die Serververwaltung ist derzeit nicht vorgesehen.
