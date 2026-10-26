# Doom Easter Egg

Das Easter Egg ist standardmäßig **nicht Bestandteil des Builds**. Ein
Frontend-Image mit dem Spiel wird aus dem Repository-Stamm so gebaut:

```powershell
docker build --build-arg PORTAL_BUILD_IDDQD=1 -t semaporter-local-frontend:dev ./frontend
```

Ohne Flag oder mit `PORTAL_BUILD_IDDQD=0` fehlen Trigger, Route, Spiel-Chunks,
WASM, Quellcodearchiv und Lizenzdateien im fertigen Frontend. Der Pfad
`/arcade/` liefert im Container dann 404; die WebAssembly-Ausnahme der CSP
wird ebenfalls nicht eingebunden. Die Build-Flag akzeptiert nur `0` oder `1`.
Sie ist kein Zugangsschutz oder vertrauliches Geheimnis. Ein Eintrag unter
`environment:` im laufenden Container kann sie nicht nachträglich aktivieren.
Die normalen veröffentlichten CI-Images enthalten das Spiel nicht.

Im angemeldeten Portal `IDDQD` tippen, während kein Eingabefeld fokussiert
ist. Die versteckte Route `/portal/iddqd` öffnet eine eigene Spielansicht.
**E1M1 starten** lädt die Doom-Shareware und startet **E1M1: Hangar** auf
der normalen Schwierigkeitsstufe *Hurt Me Plenty*. Die Portalnavigation
enthält keinen Spieleintrag.

## Bedienung

| Taste | Funktion |
| --- | --- |
| WASD / Pfeile hoch und runter | Bewegen |
| Pfeile links und rechts | Drehen |
| Leertaste / Strg | Schießen |
| E | Benutzen / Türen öffnen |
| Umschalt | Rennen |
| Tab | Karte |
| 1–7 | Waffe wechseln |
| P | Pausieren |
| Esc / Enter | Originalmenü / Auswahl bestätigen |

Bei Touch-Geräten stehen Bildschirmtasten bereit. Fensterwechsel und
Fokusverlust pausieren das Spiel und geben gedrückte Tasten frei. Es gibt
einen Vollbildmodus und einen Rückweg zur vorherigen Portalseite.
Spielstände aus dem Originalmenü bleiben nur in der laufenden Sitzung
erhalten. Neustart und Verlassen löschen sie. Der Browser-Port hat keine
Tonausgabe.

## Einbindung

- Die React-Seite wird erst beim Aufruf der Route geladen. Engine und
  Spieldaten werden erst nach dem Startknopf angefordert.
- Die optionalen Laufzeitdateien liegen unter `frontend/arcade/`. Vite
  kopiert sie nur beim aktivierten Build nach `dist/arcade/`. Das Spiel
  benötigt keine externen Server, CDNs oder zusätzlichen npm-Pakete.
- Die Engine läuft in einem Web Worker innerhalb eines separaten lokalen
  iframe-Dokuments. Beim Verlassen wird der Worker beendet.
- Nginx erlaubt WebAssembly-Kompilierung mit `wasm-unsafe-eval` nur unter
  `/arcade/`. Die CSP des übrigen Portals bleibt bestehen. Der Spielpfad
  erlaubt die Einbettung durch denselben Ursprung.
- Die Portalroute erfordert eine Anmeldung. Die statischen Engine-Dateien
  und Lizenzhinweise sind bei aktiviertem Build wie die übrigen
  Frontenddateien öffentlich abrufbar.

Direkter Vite-Build mit aktivierter Flag in PowerShell, im Repository-Stamm:

```powershell
$env:PORTAL_BUILD_IDDQD = '1'
try { npm.cmd --prefix frontend run build } finally { Remove-Item Env:PORTAL_BUILD_IDDQD }
```

Für den Entwicklungsserver gilt dieselbe Umgebungsvariable. Die CI prüft
Tests und Builds mit ausgeschalteter und aktivierter Flag.

## Ressourcenbedarf

Lokaler Vergleich vom 18.10.2026 mit identischen Portalquellen und
Node-/Vite-Versionen. MB bezeichnet hier 1.000.000 Bytes, MiB 1.048.576 Bytes.
Die Zahlen sind eine Momentaufnahme des isolierten Easter-Egg-Vergleichs;
weitere Änderungen an der Portaloberfläche verändern die absoluten Buildgrößen.

| Messwert | Standardbuild | Build mit Spiel |
| --- | ---: | ---: |
| Gesamte Frontenddateien | 823.941 Bytes | 7.811.606 Bytes |
| Haupt-JavaScript, gzip | 144.461 Bytes | 144.926 Bytes |
| Lokale Docker-Größenangabe | 22.789.148 Bytes | 27.104.816 Bytes |

Damit kommen bei aktiviertem Build rund **6,99 MB statische Dateien**
hinzu; die lokale Docker-Größenangabe wächst um **4,32 MB**. Der Standardbuild
hat gegenüber dem Portalstand vor dem Easter Egg nur 14 zusätzliche Bytes
im Hauptbundle. Er enthält keine Spiel-Chunks oder Spieldateien.
Die optionalen Quelldateien im Repository bleiben unabhängig von der Flag
vorhanden und belegen zusammen rund 7 MB. Buildcache und lokale Testimages
sind von diesen Angaben zum ausgelieferten Frontend getrennt zu betrachten.

Im aktivierten Build lädt der normale Portalaufruf nur etwa **465 zusätzliche
gzip-Bytes** im Hauptbundle. Der erste Spielstart lädt rund **4,58 MB**
einschließlich der 4,56-MB-WASM-Datei. Das 2,38-MB-Quellcodearchiv wird erst
über den entsprechenden Download-Link angefordert. Der Testserver lieferte
die Spieldateien ohne HTTP-Kompression aus. Während des Spiels sind keine
weiteren Spielanfragen an Backend, Datenbank oder einen externen Dienst nötig.

In einem lokalen Headless-Edge-Kurztest mit jeweils fünf Sekunden pro
Zustand wurden folgende Werte gemessen:

- Zusätzlicher Browser-Arbeitsspeicher beim Spielen: etwa **60–120 MiB**,
  abhängig von Speicherbereinigung und Zustand. Der WASM-Speicher selbst
  belegte **15,5 MiB**; Browsercode, Canvas und Bildpuffer kommen hinzu.
- CPU-Zeit des Rendererprozesses beim Spielen: etwa **15–16 % eines Kerns**.
  Der Browser-Grafikprozess benötigte zusätzlich etwa **7 % eines Kerns**
  CPU-Zeit. Das ist keine Messung der Hardware-GPU-Auslastung.
- Vor dem Spielstart und in Pause lag die gemessene CPU-Zeit jeweils nahe
  null. Pause hält Spielzustand und Speicher für die Fortsetzung vor.
- Beim Verlassen wird der Worker beendet. Wann der Browser übrige Caches
  und Speicher an das Betriebssystem zurückgibt, entscheidet der Browser.

Diese Zahlen sind Richtwerte dieses Rechners, keine garantierten Grenzwerte
für andere Geräte. Die Engine zeichnet mit 640 × 400 Pixeln und zielt auf
35 Bilder pro Sekunde. Die Spielberechnung läuft vollständig im Browser;
auf dem Server werden keine zusätzlichen Spielprozesse oder Datenbankobjekte
angelegt. Die Standard-aus-Flag hält reguläre Installationen praktisch frei
von zusätzlicher Größe und Laufzeitlast.

## Herkunft und Lizenzen

Die Engine ist das unveränderte Binary aus
[doom.wasm](https://github.com/jacobenget/doom.wasm/tree/25ea598859a7dba4e2f86ea0354d583e1b3f5ecd),
Revision `25ea598859a7dba4e2f86ea0354d583e1b3f5ecd`,
`examples/browser/assets/doom.wasm`.

| Datei | Prüfsumme |
| --- | --- |
| `doom-25ea5988.wasm` | SHA-256 `8edfe49a7583fd975199969302d8e9adcf8e714d0af72bf3e672f991fd810faa` |
| Eingebettete `DOOM1.WAD` | MD5 `f0cefca49926d00903cf57551d901abe` |

Die Engine steht unter der GPL-2.0; einzelne Quelldateien erlauben spätere
Versionen. Der mitgelieferte Quellcode umfasst den vollständigen
Engine-Quelltext derselben Revision und die Buildskripte. Ausgelassen sind
die fremden Test-WADs, Screenshots und die doppelte fertige WASM-Datei.
Die unveränderte Shareware-WAD ist für den Build unter `build/DOOM1.WAD`
beigefügt. Die Buildanleitung steht im enthaltenen Upstream-README.
Die beiden lokalen JavaScript-Adapter stehen unter GPL-2.0-or-later.

Die Spieldaten unterliegen der eigenen Shareware-Lizenz. Die ursprünglichen
Bedingungen samt archivierter Weitergabefreigabe sind in
`SHAREWARE-LICENSE.txt` enthalten. E1M1 wird über das Originalmenü gestartet;
die WAD wird weder verändert noch auf ein einzelnes Level gekürzt.

Credits, Lizenztexte und der Download des vollständigen Engine-Quellcodes
sind direkt in der Spielansicht unter **Credits & Lizenzen** erreichbar.
