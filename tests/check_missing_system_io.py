"""Regression check for the CS0103 missing-System.IO issue of v2.0.1."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
expected = {
    'src/Services/AppSettings.cs': ('Path', 'Directory', 'File'),
    'src/Services/Presets.cs': ('Path', 'Directory', 'File', 'IOException'),
    'src/MainWindow.xaml.cs': ('File',),
}
for relative, tokens in expected.items():
    src = (root / relative).read_text(encoding='utf-8')
    assert 'using System.IO;' in src, f'{relative} fehlt using System.IO;'
    assert all(token in src for token in tokens), f'{relative}: IO references missing'
    print(f'PASS: {relative} imports System.IO')
