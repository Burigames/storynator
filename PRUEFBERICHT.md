# Prüfbericht · 21. Oktober 2026

Umgebung: Linux, Python 3.11, PySide6 6.12.0, Qt-Offscreen-Plattform.

Ergebnis: **6 automatisierte Tests bestanden** (`python -m pytest -q`).

1. **Vollständiger Projekt-Roundtrip:** Kategorie „Charaktere“ mit Text-, Bild-, Dropdown- und Slider-Feld; Charakter und Land mit gegenseitiger Verknüpfung; formatiertes Kapitel mit Bild und Charakterlink; eigener Kalender; zwei überlappende Zeitalter und zwei gleichzeitige Ereignisse. ZIP-Datei speichern, aus Datei neu laden, Daten und Bildbytes vergleichen. Alle Objekte in echten Qt-Tabs öffnen; grafische Timeline aufbauen. Bildressource im exportierten Textdokument prüfen. Charakter umbenennen, Linknamen auflösen, PDF erzeugen, Text aus PDF auslesen und erneut speichern/öffnen.
2. **Kalenderarithmetik:** Negative Jahre, Übergang von Jahr −1 zu Jahr 1 ohne Jahr null, Ablehnung von Jahr null, ungültige Spanne, Schaltjahre vor und nach dem Ursprung, Kalender mit Jahr null und Kalender mit reinen Jahreszahlen.
3. **Speicherabbruch:** Den abschließenden Dateiaustausch gezielt mit einer Ausnahme scheitern lassen. Die bisherige Projektdatei bleibt bytegenau erhalten; temporäre Datei wird entfernt.
4. **@-Verknüpfung und Umbenennen über die Oberfläche:** Tastatureingabe im echten Qt-Editor, durchsuchbarer Picker, Übernahme des Ziels, Umbenennen über den Menü-Codepfad. Linktext und stabile Ziel-ID überprüfen; automatische Wiederherstellung schreiben und laden; über die App speichern und wieder öffnen.
5. **PDF mit mehreren Kapiteln:** Zwei ausgewählte Kapitel ergeben zwei PDF-Seiten mit dem richtigen Inhalt. PDF-Linktext hat im exportierten Dokument keine Anchor-Formatierung, keine Linkfarbe und keine Linkunterstreichung; Fettdruck bleibt bestehen.
6. **Vorlagen- und Kalenderdialoge:** Die vier erforderlichen Feldtypen im wirklichen Vorlagendialog anlegen und übernehmen; Kalender über seine Formularfelder verändern und übernehmen.

Zusätzlich: Python-Syntaxprüfung und Start-Smoke-Test, Öffnen aller Feldtypen, visuelle Kontrolle eines Qt-Fensterbilds. Das Beispielprojekt ist eine unabhängig gespeicherte `.storynator`-Datei.

**Nicht als durchgeführt zu verstehen:** interaktiver vollständiger Handtest auf Windows, tatsächliches Beenden und Neustarten eines Windows-Prozesses, Erzeugung einer Windows-EXE, physischer Druck, Hardware-Stromausfall oder Validierung auf fremden Druckern. „Wiederöffnen“ ist im Test ein neues Einlesen des Archivs bzw. der App-Öffnen-Codepfad. Die noch fehlenden Produktfunktionen stehen in README.md.
