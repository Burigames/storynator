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


## Version 0.4

23 automatisierte Tests unter Linux mit echtem Qt (offscreen) bestanden. Zusätzlich Starttest der Anwendung mit Beispielprojekt, Speichern/Wiederöffnen und PDF. Kalender-Inversrechnung deckt negative Daten, verschiedene Epochen, Kalender mit/ohne Jahr null, ungleiche Monate und Schaltregeln ab. Timeline prüft verkleinerten Wertebereich, horizontales Verschieben, Cluster und echte Datumswerte. Preset-Tests prüfen strikte Ablehnung von Eintragsdaten auf allen Ebenen, Aktivierung ohne Einträge, ID-Erhalt beim Reaktivieren, Vorlagenexport und Datenerhalt beim Löschen. Welt-Leseansicht und kategoriebasierte Dropdown-IDs sind geprüft. Ein tatsächlich gerendertes PDF bleibt auf der ersten Seite weiß, auch mit dunklem Theme und altem blauem Absatzhintergrund.

Die Windows-Pipeline führt dieselben Qt-Tests aus, startet die gebaute Anwendung, installiert den Installer still, prüft Startmenü-Ziel und beide Dateizuordnungen und startet anschließend die installierte Anwendung im Projektspeicher/PDF-Test. Veröffentlichung erfolgt erst nach erfolgreichen Schritten. Keine Aussage über ausbleibende Antivirus- oder SmartScreen-Warnungen: Der Build ist ohne vertrauenswürdiges Herausgeberzertifikat unsigniert.

## Version 0.5 – M12/M13 und Cover

**45 automatisierte Tests unter Linux bestanden**; zusätzlich 2 Layout-/Kontrasttests bei `QT_SCALE_FACTOR=1.5` und der erweiterte Starttest mit geöffneter PDF-Vorschau. Die Windows-Pipeline führt die vollständige Suite, die Skalierungsprüfung sowie die Tests der gebauten und installierten Anwendung aus.

Neu geprüft:

- Mehrere historische Projektstände, Begrenzung der Aufbewahrung, Vermeidung identischer Folgestände und Prüfsummenprüfung beim Wiederherstellen.
- Migration fester v1-/v2-Dateien, Erhalt unbekannter Metadaten und bytegenaue Originalkopie vor Schreiben einer migrierten Datei.
- Ablehnung beschädigter Archive, veränderter Ressourcen/Projektbeschreibungen, doppelter IDs und unbekannter künftiger Versionen.
- Projektsperre zwischen zwei Fenstern und erneutes Öffnen nach Freigabe; Übernahme einer Sperre nach tatsächlichem Prozessende ohne reguläre Freigabe.
- Fehlgeschlagene Sicherung vor Migration erhält das aktuell geöffnete Projekt; abgebrochenes Speichern erhält Originaldatei und ungespeicherte Änderungen.
- Hintergrundsicherung enthält einen stabilen Schnappschuss, während GUI-Ereignisse weiter verarbeitet werden.
- Wiederherstellung öffnet eine Kopie mit neuer Projektkennung und überschreibt keine Quelldatei.
- Ressourcenerkennung schützt Cover, archivierte Werte und unbekannte Feldinhalte; fehlende Verweise und Ressourcen werden erkannt.
- Tatsächlich erzeugte PDF-Dateien: zwei Cover plus Manuskript ergeben drei Seiten; das Druckdokument enthält eine Seite ohne Cover. Auswahl nur eines Covers ergibt zwei Seiten. Bild- und Textinhalt werden ausgelesen.
- Abbrechen des Coverdialogs verwirft neue, unbenutzte Bilder. Großer Bildimport begrenzt Auflösung und vermeidet identische Duplikate.
- Große Textänderungen werden vor Speichern und Tab-Schließen vollständig übernommen.
- Welt-Leseansichten werden aktualisiert, die Schreibposition des Manuskripts bleibt erhalten.
- Tastatursteuerung, 1000×700-Fenster, scrollbar angeordnete Formatleiste und Textkontraste in allen Themes/Akzenten.
- Lasttest mit 5.000 Welt-Einträgen und 5.000 Timeline-Ereignissen: Suchindex, Navigation, Speichern, Wiederöffnen, Timeline und Spurzuordnung. In dieser Linux-Umgebung rund 0,4 Sekunden für den gemessenen Testabschnitt; kein allgemeines Leistungsversprechen.

Der Starttest der veröffentlichten EXE lädt das alte eingebettete Beispiel in Format v2, speichert es erneut, prüft die Sicherungshistorie, exportiert beide Cover in ein PDF, liest dessen Seitenzahl mit QtPdf und öffnet/schließt die echte QtPdfWidgets-Vorschau. Die Installer-Prüfung kontrolliert weiterhin Startmenü-Eintrag, Projekt-/Preset-Dateizuordnungen und Start der installierten Anwendung.

Offene manuelle Abnahmen: Screenreader mit realen Hilfsmitteln, Mehrmonitor-/DPI-Wechsel, längere Schreibsitzungen auf verschiedener Windows-Hardware sowie physischer Druck. Die genaue Untergliederung und priorisierte Abnahmeliste stehen in `MEILENSTEINE.md`.

## Version 0.6 – M14 und M15

Testumfang: **72 automatisierte Tests**. Ergänzt wurden echte Qt-Dialog-, Dokument-, Archiv- und PDF-Prüfungen für:

- Teile/Kapitel/Szenen, Reihenfolge, Elternzuordnung, Status und Abweisung zyklischer Strukturen. Reparenting im Strukturdialog erhält die Bedienelemente und Metadaten.
- Suchen/Ersetzen mit Format-, Bild- und Kommentarerhalt, übersprungenen Verweisnamen und unmittelbar benachbarten Treffern.
- Kommentare, Randnotizen und Lesezeichen; Textpositionen nach Einfügen, Ersetzen, Entfernen und Umbenennen referenzierter Objekte in geschlossenen Kapiteln.
- Benannte Kapitelstände mit Wiederherstellung und Schutz historischer Bildressourcen vor Bereinigung.
- Tatsächliches PDF einer Kapitel-/Szenenstruktur in korrekter Reihenfolge und ohne unnötigen Szenen-Seitenumbruch.
- Hierarchische Druckauswahl, Teilbaum-Schaltung und gespeicherte Einzelauswahl. Ausstehende Änderungen großer Dokumente werden vor dem Export übernommen.
- Deutsche und englische Offline-Wörterbücher, Projektwörter und asynchrone Prüfung.
- Schreibziele, Netto-Wortzuwachs und portable Sitzungsdaten.
- Pflichtfelder, Gruppen/Spalten/Hilfetexte, gefilterte Auswahlfelder und Preset-Export mit neu zugeordneten Quellfeld-IDs. Unvollständige Entwürfe bleiben speicherbar.
- Typisierte Beziehungen mit Rückbezeichnung, Richtung und Kalender-Gültigkeit; Rückverweise, Löschwarnungen und sichere Anzeige fehlender Ziele beim Bearbeiten.
- Duplikate und Kategorieübertragung mit Feldzuordnung, Archiv, unverändertem Objekt-Identifier und Bild-/Verknüpfungserhalt.
- Favoriten, zuletzt geöffnete Objekte, gespeicherte Ansichten und Öffnen eines Objekts über dessen Namen im Beziehungsgraphen.
- Geöffnete Welt-Leseseiten aktualisieren neue Beziehungen und Rückverweise.
- Feste Formatdateien v1/v2/v3 mit Roundtrip und Erhalt unbekannter Metadaten.

Zusätzlich werden die Layout-/Kontrasttests bei 150 % Skalierung ausgeführt. Der Starttest lädt beide Wörterbücher aus den mitgelieferten ZIP-Dateien, erstellt Kapitelstand und Szene, speichert eine typisierte Beziehung, öffnet/schließt den Graphen, prüft Archiv/Sicherungshistorie und exportiert/zeigt das PDF mit beiden Covern. Drei vollständige lokale Starts und Beendigungen wurden nach Korrektur der Qt-Aufräumreihenfolge erfolgreich geprüft.

Die Windows-Pipeline führt die vollständige Suite und Skalierungsprüfung aus und testet anschließend die gebaute EXE sowie den Installer samt Dateizuordnungen. Die Veröffentlichung erfolgt erst nach erfolgreichen Schritten. Screenreader-, Mehrmonitor- und längere manuelle Alltagstests bleiben wie bisher gesonderte offene Abnahmen.
