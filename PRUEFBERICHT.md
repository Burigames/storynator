# Prüfung der Version 0.3 · 21. Oktober 2026

Lokal: **13 Integrationstests bestanden**. Die Windows-EXE wird erst nach denselben Tests auf Windows und einem Starttest der fertig gepackten Datei veröffentlicht.

Neue Prüfungen:

- Tatsächlicher Editorfont und Formatleistenwerte stimmen beim Öffnen überein. Ein Verweis und der Text danach behalten 19 pt, fett, kursiv, Unterstreichung und eine eigene Textfarbe nach ZIP-Speicherung und erneutem Laden. Dabei wird die stabile ID weiterhin verwendet.
- Vier Listen-/Tabellenzeilen liegen innerhalb des tatsächlichen Viewports; Verknüpfungsfelder besitzen keine beschränkende Ein-Zeilen-Maximalhöhe.
- Druckerlayout Letter/Querformat mit eigenen Rändern und Kapitelauswahl wird gespeichert und wieder geladen. Kapiteltitel erscheinen auch im erzeugten PDF-Text. Die Titel können abgeschaltet werden.
- Einstellungen für Dark Mode, Akzent Ozean und Sprache Englisch werden gespeichert. Die englische Oberfläche startet mit übersetzten Bedienelementen und belässt den benutzerdefinierten Projektnamen unverändert. Ein Themewechsel verändert den Dokumentinhalt nicht.
- Klick auf die rechte Fläche einer Navigationszeile öffnet das Kapitel. Schriftgrößenpfeile ändern auch gebrochene Größen tatsächlich im Editor; der Font-Dropdown-Pfeil öffnet die Auswahl. Ein Hover-Ereignis zeigt eine inzwischen geänderte Eintragsbeschreibung.

Die ursprünglichen Projekt-, Kalender-, Bild-, PDF-, Verknüpfungs- und Speicherabbruchprüfungen laufen weiterhin. Physischer Druck und ein manueller Test auf unterschiedlichen Endnutzer-Geräten sind damit nicht ersetzt.

---

# Prüfbericht · 21. Oktober 2026

## Version 0.2 – Schreibatelier und Windows-EXE

Sieben Integrationstests sind unter Linux und unter Windows Server 2025 (nativer Qt-Windows-Plattformtreiber) bestanden. Die gebaute einzelne `Storynator.exe` wurde auf Windows gestartet. Der EXE-Test lädt das eingebettete Beispiel, öffnet Editor und Timeline, speichert und liest eine Projektdatei und erzeugt ein PDF. Der erfolgreiche Workflow veröffentlicht die Datei automatisch als GitHub-Release.

Geprüfter Windows-Lauf: https://github.com/Burigames/storynator/actions/runs/39632103316

Die folgenden ursprünglichen Detailtests dokumentieren zusätzlich den Stand der ersten Version; deren Aussage „Windows-EXE nicht durchgeführt“ gilt für Version 0.1. Physischer Druck und ein ausführlicher manueller Windows-Test auf Endnutzer-Geräten stehen weiterhin aus.

## Ursprünglicher Prüfstand (Version 0.1)

Umgebung: Linux, Python 3.11, PySide6 6.12.0, Qt-Offscreen-Plattform.

Ergebnis: **7 automatisierte Tests unter Linux bestanden** (`python -m pytest -q`).

1. **Vollständiger Projekt-Roundtrip:** Kategorie „Charaktere“ mit Text-, Bild-, Dropdown- und Slider-Feld; Charakter und Land mit gegenseitiger Verknüpfung; formatiertes Kapitel mit Bild und Charakterlink; eigener Kalender; zwei überlappende Zeitalter und zwei gleichzeitige Ereignisse. ZIP-Datei speichern, aus Datei neu laden, Daten und Bildbytes vergleichen. Alle Objekte in echten Qt-Tabs öffnen; grafische Timeline aufbauen. Bildressource im exportierten Textdokument prüfen. Charakter umbenennen, Linknamen auflösen, PDF erzeugen, Text aus PDF auslesen und erneut speichern/öffnen.
2. **Kalenderarithmetik:** Negative Jahre, Übergang von Jahr −1 zu Jahr 1 ohne Jahr null, Ablehnung von Jahr null, ungültige Spanne, Schaltjahre vor und nach dem Ursprung, Kalender mit Jahr null und Kalender mit reinen Jahreszahlen.
3. **Speicherabbruch:** Den abschließenden Dateiaustausch gezielt mit einer Ausnahme scheitern lassen. Die bisherige Projektdatei bleibt bytegenau erhalten; temporäre Datei wird entfernt.
4. **@-Verknüpfung und Umbenennen über die Oberfläche:** Tastatureingabe im echten Qt-Editor, durchsuchbarer Picker, Übernahme des Ziels, Umbenennen über den Menü-Codepfad. Linktext und stabile Ziel-ID überprüfen; automatische Wiederherstellung schreiben und laden; über die App speichern und wieder öffnen.
5. **PDF mit mehreren Kapiteln:** Zwei ausgewählte Kapitel ergeben zwei PDF-Seiten mit dem richtigen Inhalt. PDF-Linktext hat im exportierten Dokument keine Anchor-Formatierung, keine Linkfarbe und keine Linkunterstreichung; Fettdruck bleibt bestehen.
6. **Vorlagen- und Kalenderdialoge:** Die vier erforderlichen Feldtypen im wirklichen Vorlagendialog anlegen und übernehmen; Kalender über seine Formularfelder verändern und übernehmen.

Zusätzlich: Python-Syntaxprüfung und Start-Smoke-Test, Öffnen aller Feldtypen, visuelle Kontrolle eines Qt-Fensterbilds. Das Beispielprojekt ist eine unabhängig gespeicherte `.storynator`-Datei.

**Nicht als durchgeführt zu verstehen:** interaktiver vollständiger Handtest auf Windows, tatsächliches Beenden und Neustarten eines Windows-Prozesses, Erzeugung einer Windows-EXE, physischer Druck, Hardware-Stromausfall oder Validierung auf fremden Druckern. „Wiederöffnen“ ist im Test ein neues Einlesen des Archivs bzw. der App-Öffnen-Codepfad. Die noch fehlenden Produktfunktionen stehen in README.md.

## Überarbeitung des Schreibateliers und Windows-Paketierung

Zusätzlich geprüft: Navigation zwischen Editor, Welt und Timeline, Erhalt der Schreibposition und Fokusmodus mit ausgeblendeten Seitenbereichen. Der neue gemeinsame Stil wurde anhand von Fensteraufnahmen von Editor, Startseite, Welt und Timeline kontrolliert.

Der Windows-Release-Workflow führt dieselben Tests unter Windows mit der nativen Qt-Windows-Plattform aus. Anschließend baut PyInstaller eine einzelne EXE und startet genau diese mit `--smoke-test`: eingebettetes Beispiel laden, Editor und Timeline anzeigen, Projekt speichern/wieder laden und PDF erzeugen. Nur bei Erfolg wird die EXE als GitHub-Release veröffentlicht. Der erste Lauf fand einen Windows-spezifischen Fehler beim Synchronisieren eines nur lesend geöffneten Dateihandles; die Synchronisierung verwendet nun einen schreibfähigen Handle.
