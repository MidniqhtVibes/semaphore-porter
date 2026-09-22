"""Offline-Strukturprüfung; ersetzt NICHT den Windows-.NET-Build."""
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
source = root / 'src'
for name in ('App.xaml', 'MainWindow.xaml'):
    doc = ET.parse(source / name)
    print(f'PASS: XML syntaktisch gültig: {name}, {len(list(doc.iter()))} Elemente')
code = (source / 'MainWindow.xaml.cs').read_text(encoding='utf-8')
xaml = (source / 'MainWindow.xaml').read_text(encoding='utf-8')
methods = set(re.findall(r'\b(?:private|public)\s+(?:async\s+)?(?:void|Task(?:<[^>]+>)?)\s+(\w+)\s*\(', code))
events = re.findall(r'\b(?:Click|TextChanged|SelectionChanged)="([A-Za-z_][A-Za-z0-9_]*)"', xaml)
missing = [handler for handler in events if handler not in methods]
assert not missing, f'XAML-Eventhandler fehlen: {missing}'
print(f'PASS: {len(events)} XAML-Ereignisse verweisen auf vorhandene Methoden')
assert len(re.findall(r'new\("0[1-7]', code)) == 7
assert 'ProjectDocument.Prepare' in code and 'ParseProjectList(string raw)' in (source / 'Services/SemaphoreApi.cs').read_text()
print('PASS: 7 Wizard-Schritte, Projektvorbereitung und eigener Projektlistenparser vorhanden')
test = (root / 'tests/Program.cs').read_text(encoding='utf-8')
fixture = test.split('var source = ProjectDocument.ParseBackup("""', 1)[1].split('""");', 1)[0].strip()
assert json.loads(fixture)['meta']['name'] == 'Demo'
print('PASS: C#-Testfixture gültiges JSON')
assert (root / 'BUILD-WINDOWS.ps1').is_file() and (root / '.github/workflows/build-windows.yml').is_file()
print('PASS: Windows-Build und CI-Konfiguration vorhanden')
print('HINWEIS: Keine C#-Kompilierung oder Windows-GUI-Ausführung durchgeführt.')
