## Host- und Git-Zugang

Ein Host-Schlüssel dient der SSH-Anmeldung am Deployment-Ziel. Ein Git-Schlüssel ermöglicht das Lesen des Stack-Repositories. Eine SSH-Verbindung für die Semaporter-CI/CD-Pipeline ist wiederum ein eigener Verwendungszweck.

Der ausgewählte private Schlüssel muss zum öffentlichen Schlüssel passen, der beim tatsächlichen Zielkonto beziehungsweise Git-Projekt freigegeben ist. Eine Änderung des Benutzernamens im Formular erteilt keine neuen Serverrechte.

## Vorgehen

1. Einen freigegebenen privaten Schlüssel und gegebenenfalls seine Passphrase im vorgesehenen Vault-Objekt hinterlegen.
2. Unter **Einstellungen → Zugangsprofile** den eigenen Vault-Lesezugang konfigurieren.
3. Ein Profil mit Zweck **Host** oder **Git**, dem richtigen SSH-Benutzernamen, der festen Secret-Version und den erlaubten Zielen anlegen.
4. Das Profil prüfen und im Tenant-Ersteller den passenden Ressourcen zuordnen.
5. Repository, Inventory und tatsächlichen Tasklauf gemeinsam testen.

Der öffentliche Git-Schlüssel gehört zum Projekt mit den Ansible-Playbooks. Ein in GitLab gemeldeter bereits vorhandener Fingerprint weist auf eine bestehende Zuordnung hin; vorhandene Schlüssel nicht ungeprüft entfernen.

## Inventory und sudo

Das Inventory kann den SSH-Benutzernamen vorgeben. Bei Datei-Inventories den vorgesehenen Import in eine statische INI-/YAML-Kopie prüfen. Dynamische Inventories benötigen eine manuelle fachliche Prüfung.

`Permission denied (publickey)` betrifft die Anmeldung. Eine erfolgreiche Anmeldung bestätigt noch keine sudo-Rechte. Ein Playbook mit `become` benötigt zusätzlich den vorgesehenen, administrativ freigegebenen Rechteumfang.

## Fehlerbehebung

Bei einem ungültigen Schlüssel Format und Passphrase prüfen; unterstützt werden geeignete Ed25519-, RSA- und ECDSA-Schlüssel. Maskierte Secret-Felder liefern keinen auslesbaren alten privaten Schlüssel. Falls die Quelle fehlt, ist ein neuer, gezielt freigegebener Schlüssel erforderlich.
