# Designs und eigene Unternehmensfarben

Der Menüpunkt **Designs** steht in Administration und Benutzerportal zur Verfügung. Die allgemeine Grundlage bilden **Neutral Dunkel** und **Neutral Hell** mit Systemschrift, neutralem Symbol und blauen Akzenten. **GitHub Black**, **SIT Hell** und **SIT Dunkel** stehen daneben als gleichwertige Varianten zur Verfügung. Alle Varianten verwenden dasselbe Format und dieselben Funktionen zum Auswählen, Kopieren, Exportieren und Entfernen.

Logos werden in Navigation, Anmeldung, Designkarten und Vorschau über eine gemeinsame Komponente dargestellt. Design-Daten können eine mitgelieferte Logo-Vorlage oder ein hochgeladenes Bild sowie Originalfarben oder eine dunkle Darstellung wählen. Die SIT-Varianten enthalten dafür reguläre Logo-Metadaten; es gibt keine markenabhängigen Regeln in den Ansichten. Mitgelieferte Logo-Dateien bleiben unverändert.

Die Schrift liegt lokal unter `frontend/public/fonts/Sora-Variable.ttf`; Browser laden keine Schrift von Google nach. Quelle: [Google Fonts – Sora](https://github.com/google/fonts/tree/main/ofl/sora), Lizenz: `frontend/public/fonts/OFL-Sora.txt`.

## Auswahl und Speicherung

**Design verwenden** aktiviert die gewählte Variante unmittelbar. Sie gilt anschließend für Anmeldung, Administration und Benutzerportal auf derselben Browser-Origin. Auswahl und eigene Designs liegen im lokalen Browser-Speicher; sie ändern keine Server-Konfiguration und werden nicht zwischen Geräten oder Benutzerkonten synchronisiert. Bei gesperrtem Browser-Speicher bleibt die Darstellung für die aktuelle Sitzung aktiv. Ohne gespeicherte Auswahl und bei ungültigen gespeicherten Daten wird Neutral Dunkel verwendet. Vorhandene gültige Designauswahlen bleiben erhalten. Neue Studioentwürfe starten auf neutraler Basis; **Als Vorlage** übernimmt gezielt die jeweilige Variante.

## Website-Symbol und Windows-Taskleiste

Das **Portal-Tor** ist fest als Symbol für Browser-Tabs, Favoriten und App-Verknüpfungen hinterlegt. Die frühere Symbolauswahl entfällt; alte gespeicherte Auswahlen werden ignoriert, ohne das gewählte Design zu ändern. SVG- und ICO-Favicons sowie Touch-Icons liegen unter `frontend/public/icons/`; die ICO-Datei enthält 16-, 32- und 48-Pixel-Varianten. Zusätzlich sind PNG-Dateien mit 180, 192 und 512 Pixeln enthalten. `/favicon.ico` verwendet ebenfalls das Portal-Tor.

Für eine eigene Windows-App-Verknüpfung in Edge **Einstellungen und mehr → Weitere Tools → Apps → Diese Website als App installieren** verwenden und die App an die Taskleiste anheften. Je nach Edge-Version ist **Apps** direkt im Hauptmenü verfügbar. Das Manifest liegt unter `/manifests/portal.webmanifest`. Bereits installierte Verknüpfungen können ein früheres Symbol zwischenspeichern und müssen gegebenenfalls neu installiert werden. Die App benötigt weiterhin eine Verbindung zum Portal; es wird kein Offline-Modus ergänzt.

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
  "base": "neutral-dark",
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

Nicht angegebene Werte werden aus `base` übernommen. Zulässig sind `neutral-dark`, `neutral-light`, `github-dark`, `sit-light` und `sit-dark`. `font` erlaubt die lokale Sora-Schrift oder die vorhandene Systemschrift. `radius` ist eine ganze Zahl von 0 bis 16 Pixeln. Der Import akzeptiert höchstens 1 MB und speichert maximal 20 eigene Varianten. Beim Entfernen der aktiven Variante wird das erste verbleibende Design aktiviert.

Eigene Design-Dateien verwenden standardmäßig das neutrale Symbol. `logo` enthält ein hochgeladenes Bild; alternativ verweist `logoAsset` auf eine freigegebene lokale Logo-Vorlage. `logoTone` wählt `original` oder `dark`, unabhängig vom Bild und der Farbbasis. Ältere Dateien mit `branding` werden beim Import in diese allgemeinen Logo-Felder überführt. Das feste Website-Symbol ist kein Bestandteil der Design-Datei.

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

## Visueller Design-Creator

Unter **Designs → Design erstellen** öffnet sich eine eigene Studioseite ohne die normale Portalnavigation. **Als Vorlage** öffnet eine Kopie einer mitgelieferten Variante; **Bearbeiten** öffnet ein vorhandenes eigenes Design. Die Routen sind `/admin/designs/studio` und `/portal/designs/studio`. Erst **Speichern und aktivieren** übernimmt den Entwurf und führt zurück zur Designauswahl. **Zurück zu Designs** verlässt den Entwurf ohne Änderungen am aktiven Design.

Anpassbar sind sämtliche Farben (zusätzliche Zustände unter **Weitere Farben und Zustände**), Hell-/Dunkelbasis, Schrift und Eckenradius. Portalname, Untertitel und die Texte der Anmeldung erscheinen nach dem Speichern auch in Navigation und Anmeldung. Die Farbprüfung verhindert das Speichern unzureichender Textkontraste. **Änderungen zurücksetzen** stellt den Stand beim Öffnen des Editors wieder her.

Eigene Logos und ein optionales Hintergrundbild der Anmeldung können als PNG, JPEG oder WebP mit jeweils bis zu 250 KB hochgeladen und wieder entfernt werden. Sie werden in die Design-Datei eingebettet, ohne externe Bildaufrufe. Die Logobreite lässt sich zwischen 32 und 120 Pixeln einstellen. Ein Logo mit transparentem Hintergrund eignet sich für wechselnde Flächen. JSON-Importe erlauben bis zu 1 MB inklusive Bildern und Texten. Die optionalen Felder `copy`, `logo`, `logoWidth`, `loginBackground` und `legal` ergänzen Formatversion 1; vorhandene Dateien bleiben gültig. Export und Import übertragen die vollständige Gestaltung. Speicherung und Auswahl gelten weiterhin nur im jeweiligen Browser.

Alle eigenen und mitgelieferten Designs erscheinen gemeinsam unter **Verfügbare Designs**. Jede Karte bietet Auswahl, Bearbeitung beziehungsweise Kopie und Entfernen. Das Entfernen eines aktiven Designs aktiviert die erste verbleibende Variante. Mindestens ein Design bleibt erhalten. Entfernte Standarddesigns bleiben in diesem Browser ausgeblendet, bis **Standarddesigns wiederherstellen** gewählt wird; eigene Designs werden beim Entfernen aus dem Browser-Speicher gelöscht.

### Interaktive Live-Vorschau

Die Vorschau füllt die verfügbare Fläche neben einer schmalen Werkzeugleiste. Unter **Farben** stehen ausschließlich Farbwähler zur Verfügung; Hex-Eingaben entfallen. Transparente Farben haben zusätzlich einen Deckkraftregler. **Texte & Bilder** öffnet die übrigen Einstellungen. Die Ansichten **Anmeldung**, **Portal**, **Elemente**, **Impressum** und **Datenschutz** zeigen alle Änderungen unmittelbar. **Elemente** demonstriert Aktionen, Fokus, Hover, Eingaben und Statusmeldungen; Portalaktionen arbeiten ausschließlich mit Beispieldaten. Desktop- und Mobilansicht, eine vergrößerte Vorschau sowie **Vergleichen** mit dem Stand beim Öffnen erleichtern die Beurteilung. Auf kleinen Bildschirmen liegt die kompakte Farbpalette unter der Vorschau; beide Bereiche scrollen unabhängig. Farbstimmungen für Ozean, Iris, Wald und Terrakotta passen zusammengehörige Akzent- und Aktionsfarben gemeinsam an.

Das Studio öffnet direkt die **Portal**-Vorschau mit dem vollständigen Hauptmenü. **Menüvorschau** wechselt zwischen Administration und Benutzerportal. Die Menüpunkte und Symbole stammen aus derselben Definition wie die tatsächliche Portalnavigation. Auf schmalen Vorschauflächen lässt sich das Hauptmenü über die Menütaste öffnen und schließen. Menüaktionen verändern nur die Beispielansicht.

Unter **Footer und Rechtliches** stehen ein Footertext bis 160 Zeichen sowie Impressum und Datenschutzhinweise mit jeweils bis zu 12.000 Zeichen zur Verfügung. Zeilenumbrüche und Absätze bleiben erhalten; HTML wird als Text angezeigt. Das Bearbeiten der Rechtstexte öffnet automatisch die entsprechende Vorschau. Nach dem Speichern verlinkt der Footer ausgefüllte Texte unter `/impressum` beziehungsweise `/datenschutz`; diese Ansichten sind auch ohne Anmeldung zugänglich. Auch diese Inhalte gelten für das Design im jeweiligen Browser und sind keine serverweite Betreiberkonfiguration.
