# Storynator 0.5 – M12, M13 und Cover

## M12 – Stabile Alltagsversion

### 12.1 Fehler und Bedienung
- [x] Tastaturzugriff auf Bereiche, Suche, Tabs, Welt-Bearbeitung und Timeline.
- [x] Sichtbare Fokusmarkierungen und zugängliche Bezeichnungen wichtiger Bedienelemente.
- [x] Welt-Leseansichten, Verknüpfungsnamen, Auswahlbeschriftungen und geöffnete Timeline aktualisieren sich nach Änderungen.
- [x] Verknüpfungsnamen im Editor aktualisieren, ohne den vollständigen Editor neu zu laden.
- [x] Lokale rotierende Fehlerprotokolle und Sicherungsversuch bei unerwarteten UI-Fehlern.
- [x] Fehler beim Öffnen/Speichern behalten das bisherige Projekt und die letzte gültige Datei.

### 12.2 Leistung
- [x] Suchindex mit verzögerter Abfrage und begrenzter Ergebnisdarstellung.
- [x] Navigation gruppiert Einträge in einem Durchlauf; Symbole werden zwischengespeichert.
- [x] Timeline mit sortierten Ereignissen, Bereichssuche, Cluster-Cache und effizienter Spurzuordnung.
- [x] Automatische Sicherungen im Hintergrund mit unveränderlichem Schnappschuss.
- [x] Große Texte verzögern die HTML-Serialisierung; Speichern und Tab-Schließen übernehmen ausstehende Änderungen.
- [x] Bildimport begrenzt die längste Kante auf 4096 Pixel und erkennt identische importierte Bilder.
- [x] Editor lädt nur verwendete Bilder, Galerien und Cover verwenden verkleinerte Vorschauen.
- [x] Automatisierter Lasttest mit 5.000 Welt-Einträgen und 5.000 Ereignissen, plus großem Manuskript und großem Bildimport.

### 12.3 Darstellung
- [x] Horizontal scrollbar angeordnete Formatleiste in schmalen Fenstern.
- [x] Schreibhilfe unter 1150 logischen Pixeln automatisch ausgeblendet; breite Fenster zeigen sie wieder.
- [x] Lange Inhalte in scrollbaren Ansichten und verkleinerbare Such-/Kopfbereiche.
- [x] Automatisierte Kontrastprüfung für Textrollen in allen fünf Akzenten und beiden Themes.
- [x] Automatisierte Tastatur- und Layoutprüfung bei 150 % Windows-Skalierung im Release-Workflow.
- [ ] Vollständiger manueller Screenreader-Test.
- [ ] Mehrmonitor-/DPI-Wechsel und lange Schreibsitzungen auf unterschiedlichen realen Windows-Geräten.

Die offenen Punkte betreffen die manuelle Abnahme. Die automatisierten Tests ersetzen diese nicht. Keine Zusage, dass jedes beliebig große Projekt innerhalb derselben Zeiten lädt.

## M13 – Datensicherheit und Projektpflege

### 13.1 Sicherungen
- [x] Mehrere datierte vollständige Projektstände, lokal je Projektkennung gespeichert.
- [x] Intervall 15–3600 Sekunden; Aufbewahrung 3–200 Stände, standardmäßig 60 Sekunden und 20 Stände.
- [x] Sicherung vor Überschreiben und nach erfolgreichem Speichern; identische aufeinanderfolgende Stände werden nicht dupliziert.
- [x] Manuelle Sicherung, Vorschau mit Kapiteltexten/Cover, Export und Wiederherstellung.
- [x] Wiederherstellung öffnet eine ungespeicherte Kopie mit neuer Projektkennung; Original bleibt erhalten.
- [x] Getrennte Wiederherstellungsdateien pro laufender Instanz; aktive andere Sitzungen werden nicht übernommen.

### 13.2 Projektintegrität
- [x] Fehlende Verweise, Kategorien, Quellkategorien und Bilder sowie nicht lesbare Bilder auflisten.
- [x] CRC-/SHA-256-Prüfung beim Lesen neuer Archive; beschädigte und strukturell ungültige Archive abweisen.
- [x] Projektsperre mit Prozessprüfung gegen gleichzeitige Bearbeitung desselben Dateipfads; verwaiste Sperren übernimmt Qt nach Prozessende.
- [x] Unbenutzte Ressourcen mit Vorschaubildern zur Auswahl anzeigen.
- [x] Bereinigung nur nach Auswahl/Bestätigung und erfolgreicher Sicherung.
- [x] Cover, archivierte Feldwerte und unbekannte Feldinhalte vor versehentlicher Ressourcenbereinigung schützen.

Sperren gelten für denselben Dateipfad, nicht für separat kopierte Dateien auf anderen Geräten. Sie sind keine verteilte Zusammenarbeit und keine Garantie auf jedem Netzwerkdateisystem. Fehlende Verweise werden nicht automatisch auf andere Objekte umgebogen.

### 13.3 Formatentwicklung
- [x] Dateiformat v2 mit Projektkennung, Cover-Zuordnung und Integritätsmanifest.
- [x] Migration von v1 im Speicher, ohne die Quelldatei beim Laden zu überschreiben.
- [x] Vor Übernahme/Speichern einer alten Datei bytegenaue Originalkopie neben der Datei: `.before-v2-<Prüfsumme>.bak`.
- [x] Unbekannte JSON-Metadaten bleiben erhalten; zukünftige unbekannte Formatversionen werden abgewiesen.
- [x] Feste v1-/v2-Testdateien und Roundtrip-/Abbruch-/Beschädigungstests.

Ältere Storynator-Versionen können Format v2 nicht öffnen. Die Originalkopie bleibt mit der alten Version lesbar und ist über „Projekt öffnen“ auch als `.bak` auswählbar. Sicherungen sind lokal, nicht Teil der portablen Hauptdatei; sie können einzeln exportiert werden.

## Zusatz: Projekt- und Buchcover
- [x] Zwei getrennte eingebettete Cover in „Projekt → Projekt & Buchcover“.
- [x] Projektcover als kleine Vorschau in der Projektnavigation.
- [x] Beide Cover separat im PDF-Dialog aktivierbar; Reihenfolge Projektcover, Buchcover, Manuskript.
- [x] Seitenformat berücksichtigen und Seitenverhältnis bewahren.
- [x] Eigene PDF-Vorschau ohne Druckaktion.
- [x] Druckvorschau und physischer Druck schließen Cover aus.
- [x] Echte PDF-Tests prüfen Seitenanzahl, Bilder und Manuskriptinhalt.

## Priorisierte Fehler- und Abnahmeliste

| Priorität | Fall | Stand / Nachweis |
|---|---|---|
| P0 | Abbruch beim Speichern überschreibt gültigen Stand | Behoben/abgesichert; Fehler vor Dateiaustausch simuliert |
| P0 | Zwei Instanzen überschreiben dieselbe Datei | Durch Projektsperre verhindert; Freigabe nach Schließen geprüft |
| P0 | Wiederherstellen überschreibt ursprüngliches Projekt | Verhindert; Wiederherstellung erfolgt als Kopie |
| P1 | Alte Formatdateien ohne Originalkopie überschrieben | Migrationskopie vor Schreiben; Bytegleichheit geprüft |
| P1 | Verzögerte große Textänderungen beim Speichern/Tab-Schließen verloren | Explizites Übernehmen ausstehender Änderungen; Regressionstest |
| P1 | Veraltete geöffnete Ansichten nach Änderungen | Automatische Aktualisierung und Cursor-Erhalt getestet |
| P1 | PDF-Cover erscheinen beim Drucken | Getrennte Dokumenterzeugung; echte PDF-/Druckdokumenttests |
| P2 | Manuelle Screenreader-/Mehrmonitor-Abnahme | Offen; automatisierte Zugänglichkeitsbezeichnungen und Skalierung vorhanden |
| P2 | Langzeittest auf verschiedener realer Windows-Hardware | Offen |

Unabhängig von M12/M13 bleibt die vertrauenswürdige Codesignatur offen. Eine Signatur oder Freiheit von SmartScreen-/Antivirus-Warnungen wird nicht behauptet.
