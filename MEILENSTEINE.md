# Storynator 0.7 – M12 bis M18 und Cover

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
- [x] Versioniertes Dateiformat mit Projektkennung, Cover-Zuordnung und Integritätsmanifest; aktuell v3.
- [x] Migration von v1/v2 im Speicher, ohne die Quelldatei beim Laden zu überschreiben.
- [x] Vor Übernahme/Speichern einer alten Datei bytegenaue Originalkopie neben der Datei: `.before-v3-<Prüfsumme>.bak`.
- [x] Unbekannte JSON-Metadaten bleiben erhalten; zukünftige unbekannte Formatversionen werden abgewiesen.
- [x] Feste v1-/v2-/v3-Testdateien und Roundtrip-/Abbruch-/Beschädigungstests.

Ältere Storynator-Versionen können Format v3 nicht öffnen. Die Originalkopie bleibt mit der alten Version lesbar und ist über „Projekt öffnen“ auch als `.bak` auswählbar. Sicherungen sind lokal, nicht Teil der portablen Hauptdatei; sie können einzeln exportiert werden.

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

## M14 – Schreiben und Manuskriptorganisation (Version 0.6)

### 14.1 Struktur
- [x] Teile, Kapitel und Szenen mit dauerhaft gespeicherter Elternzuordnung.
- [x] Drag-and-drop in der Manuskriptnavigation und im Dialog „Struktur & Status“.
- [x] Umbenennen und Status Entwurf / Überarbeitung / Fertig, im Editor direkt wählbar.
- [x] Zyklische Strukturen und Unterdokumente von Szenen verhindern.
- [x] Beim Löschen einer übergeordneten Einheit bleiben ihre Unterdokumente erhalten.
- [x] Hierarchische Druckauswahl mit gemeinsam schaltbaren Teilbäumen; Überschrift/Kapiteltext und einzelne Szenen getrennt wählbar.
- [x] Druck/PDF folgen der Struktur; Teile und Kapitel beginnen auf neuen Seiten, Szenen laufen weiter.

### 14.2 Schreibwerkzeuge
- [x] Suchen und Ersetzen im aktuellen Dokument oder gesamten Manuskript.
- [x] Vorschau der Treffer, Groß-/Kleinschreibung und ganze Wörter.
- [x] Ersetzen bewahrt Richtextformatierung und eingebettete Bildverweise. Verknüpfte Namen bleiben ihren Zielobjekten zugeordnet und werden übersprungen.
- [x] Wortzahlen je Dokument und Projekt, Projekt- und Tagesziele.
- [x] Optionale lokale Schreibsitzungen mit Netto-Wortzuwachs und geschätzter aktiver Zeit.
- [x] Offline-Rechtschreibprüfung Deutsch/Englisch mit mitgelieferten Hunspell-Wörterbüchern.
- [x] Korrektur eines Wortes an seinen nicht verknüpften Vorkommen; eigenes, entfernbares Projektwörterbuch.

Die Rechtschreibprüfung wird bewusst über „Kapitel prüfen“ gestartet. Sie ist keine Grammatikprüfung und kann gültige Eigennamen/Fachbegriffe melden. Die aktive Zeit wird aus Textänderungen geschätzt; lange Pausen werden nicht vollständig gezählt. Tagesfortschritt summiert positive Nettozuwächse der Sitzungen, kein exakter Anschlagszähler.

### 14.3 Überarbeitung
- [x] Kommentare an Textauswahl oder Schreibposition und Randnotizen in der Schreibhilfe.
- [x] Bearbeiten, als erledigt/offen markieren, anspringen und löschen.
- [x] Lesezeichen mit Namen und Textposition.
- [x] Textstellen folgen Änderungen; entfernte Passagen bleiben als abgelöste Kommentare erkennbar.
- [x] Benannte Kapitelstände mit Vorschau, Wiederherstellung und bestätigtem Löschen.
- [x] Vor Massenersetzung, Rechtschreibkorrektur und Wiederherstellung automatisch den aktuellen Kapitelstand sichern.
- [x] Kommentare, Formatierung, Bildverweise und Status werden mit Kapitelständen gespeichert. Bildressourcen historischer Stände bleiben vor Bereinigung geschützt.

Kommentare und Lesezeichen sind Bearbeitungsmetadaten und erscheinen nicht im Manuskript-PDF oder Druck. Die Schreibhilfe ist bei kleinen Fenstern/Fokusmodus ausgeblendet; der Dialog bleibt über „Manuskript“ erreichbar.

## M15 – Weltwissen und Beziehungen (Version 0.6)

### 15.1 Vorlagen
- [x] Feldgruppen und zwei gleich breite Spalten im Lese- und Bearbeitungsmodus.
- [x] Pflichtfelder und Hilfetexte pro Feld.
- [x] Fehlende Pflichtwerte beim Fertigstellen melden; unvollständige Entwürfe bleiben speicherbar.
- [x] Auswahlquelle nach Kategorie und einem zusätzlichen Feldvergleich filtern (gleich / enthält).
- [x] Bestehende Werte außerhalb des aktuellen Filters sichtbar erhalten.
- [x] Layout, Pflichtfelder, Hilfetexte und Auswahlfilter beim Preset-Export erhalten und interne Quellfeld-IDs beim Import neu zuordnen.

### 15.2 Beziehungen
- [x] Eigene Beziehungstypen mit Bezeichnung, optionaler Rückbezeichnung und gerichtet/ungerichtet.
- [x] Beziehungen erstellen, bearbeiten und löschen; verwendete Typen nicht unbemerkt entfernen.
- [x] Beschreibung sowie optionaler Anfang/Ende im Projektkalender. Ein Anfang ohne Ende bedeutet „ab diesem Datum“.
- [x] Automatische Rückverweise aus Text, festen Verknüpfungen und verknüpften Feldern.
- [x] Beziehungen und Rückverweise auf der Welt-Leseseite anzeigen.
- [x] Gültigkeit nach Datum im Beziehungsdialog filtern.
- [x] Löschwarnungen berücksichtigen Beziehungen; gelöschte Ziele bleiben als fehlend erkennbar und werden beim Bearbeiten nicht automatisch neu zugeordnet.
- [x] Zoom- und verschiebbarer Graph mit Richtungen, getrennten parallelen Verbindungen und anklickbaren Objektnamen.

Der Graph zeigt bis zu 200 Objekte pro Ansicht. Ein Fokusobjekt grenzt auf seine direkten Nachbarn ein; die vollständige Beziehungsliste bleibt unabhängig davon verfügbar. Er ist eine Übersicht, kein automatischer genealogischer oder kartografischer Layout-Editor.

### 15.3 Navigation
- [x] Favoriten, zuletzt geöffnete Einträge und alphabetische Sortierung.
- [x] Suchtext, Kategorie, Favoriten und Feldinhalt kombinieren.
- [x] Benannte Suchansichten speichern, laden und löschen.
- [x] Einträge mit neuer ID duplizieren; Feldwerte, Bilder und bisherige Verknüpfungsziele behalten. Typisierte Beziehungen werden standardmäßig nicht dupliziert.
- [x] Kategorieübertragung mit expliziter, typgleicher Feldzuordnung.
- [x] Vollständige bisherige Feldwerte mit Vorlageninformation im Eintrag archivieren; vor Übertragung zusätzlich eine Projektsicherung erstellen.

Favoriten und Suchansichten gehören zum Projekt. Die Liste zuletzt geöffneter Objekte liegt lokal je Projekt in den Einstellungen. Beziehungen bleiben beim Kategorieübertrag durch die unveränderte Objekt-ID gültig.

## Format und Veröffentlichung ab 0.6

Neue Projekte verwenden Format v3. Dateien v1/v2 werden unter Erhalt von Originalkopien übernommen. Ältere Programmversionen sollen neue Manuskriptstrukturen nicht verändern und können v3 deshalb nicht öffnen. Feste Testdateien aller drei Formate sichern die Rückwärtskompatibilität ab.

Die vorher genannten offenen manuellen Screenreader-/Mehrmonitor-/Langzeittests und die fehlende vertrauenswürdige Codesignatur bleiben offen. M14/M15 ergänzen keine Cloud-Pflicht und keine Laufzeit-Downloads.

# M16–M18 – Community-Austausch (Version 0.7)

## M16 – Inhalte als Pakete teilen
- [x] Versioniertes, rein deklaratives `.storynator-pack`-Format, atomarer Export, Größenlimit und Validierung.
- [x] Kategorievorlagen, Kalender, leere Projekt-Starter und Challenges, Weltpakete, Lesefassungen und Welt-Schaufenster.
- [x] Titel, Autor, Beschreibung, Version, Sprache, Tags und Lizenz.
- [x] Auswahl einzelner Inhalte; private Weltfelder gezielt ausschließen, Abhängigkeiten optional aufnehmen.
- [x] Freigabevorschau mit vollständigem Textinhalt und Ressourcenliste statt Bild-Binärdaten.
- [x] Keine Kapitelstände, Kommentare, Feldarchive oder Sitzungsdaten im öffentlichen Paket.
- [x] Auswahl vor Import, neue Objekt-/Feld-/Ressourcen-IDs und interne Neuzuordnung.
- [x] Namenskonflikte sichtbar kennzeichnen; Sicherung vor tatsächlicher Übernahme.
- [x] Externe Bildquellen, aktive HTML-Inhalte und unbekannte Paketformate abweisen.
- [x] Bisherige Addons bleiben ausschließlich Kategorievorlagen und erzeugen weiterhin keine Einträge.

Grenzen: Vorlagen enthalten weiterhin ihre sichtbaren Felddefinitionen, Auswahloptionen und Hilfetexte. Diese müssen in der Vorschau ebenfalls geprüft werden. Verknüpfte, nicht freigegebene Ziele werden aus Weltpaketen entfernt beziehungsweise als „Nicht freigegeben“ ersetzt. Ein Kalenderimport wird bei bereits vorhandenen datierten Inhalten abgewiesen, um keine Daten umzudeuten. Ein Starter übernimmt seinen Kalender nur in ein Projekt ohne Welt-/Timeline-/Beziehungsinhalte.

## M17 – Bibliothek und Paketverwaltung
- [x] „Addon → Community · Bibliothek & Austausch“ mit lokaler Paketbibliothek.
- [x] Suche sowie Filter nach Pakettyp, Sprache und Lizenz; Genres über Tags suchbar.
- [x] Paketdetails, Entfernung nur aus der Bibliothek und dauerhafte Offline-Nutzung.
- [x] Optionaler GitHub-Katalog, ausschließlich auf ausdrückliche Anforderung geladen.
- [x] Asynchrone begrenzte Downloads mit Timeout, HTTPS-Quellprüfung und SHA-256-Prüfung.
- [x] Vier initiale geprüfte Katalogpakete, darunter zwei eingebaute Offline-Challenges.
- [x] Unterschiedliche Paketversionen nebeneinander, Versionshinweise und Inhaltsvergleich beim Download.
- [x] Weltpaket-/Starter-/Challenge-Updates mit Vergleich gegen den ursprünglichen Import und Konfliktentscheidung pro Objekt.
- [x] Standard bei Konflikten: lokale Fassung behalten. Entfernte Paketobjekte werden nie automatisch gelöscht.
- [x] Einreichungsordner mit Paket, Metadaten und Anleitung; GitHub-Issues für Einreichungen und Fehlermeldungen.
- [x] Windows-Dateizuordnung für `.storynator-pack`.

Grenzen: Kalender und reine Kategorievorlagen werden über den geprüften Import übernommen; ein automatischer Vorlagenabgleich mit Feldmigration ist nicht enthalten. Bei Weltpaket-Updates wird je ganzem Objekt entschieden, nicht je Textabsatz/Feld. Eine ausgewählte Paketfassung ersetzt dieses Objekt einschließlich seiner Felder; zuvor wird gesichert. Es gibt keine Konten, öffentliche Kommentare/Bewertungen oder automatische Veröffentlichung. Katalogänderungen müssen durch den Repository-Betreiber geprüft und aufgenommen werden. Die Einreichungsfunktion verschickt selbst keine Nachricht.

## M18 – Präsentation und Feedback
- [x] Kapitelbasierte Lesefassung ohne interne Bearbeitungsmetadaten und ohne Welt-Datenbank.
- [x] Optionales Buchcover, Beschreibung und Autorenangabe.
- [x] PDF-Leseprobe über denselben formaterhaltenden Export wie das Manuskript; Verknüpfungsmarkierungen neutralisieren.
- [x] Lesefassung separat öffnen, Textstellen kommentieren, Kommentare entfernen und Feedback-Datei speichern.
- [x] Rückimport mit Projekt-/Kapitelzuordnung, ursprünglicher Textstelle und Duplikaterkennung.
- [x] Geänderte Kapitel: Kommentar sichtbar abgelöst statt falscher exakter Zuordnung.
- [x] Kommentare anschließend im bestehenden Kommentar-/Überarbeitungsdialog bearbeiten und erledigen.
- [x] Eigenständige statische HTML-Weltenenzyklopädie mit eingebetteten Bildern, Suche, Kategoriefilter und internen Links.
- [x] HTML-Lesefassung und Welt-Schaufenster mit Cover und Beschreibung; keine Installation für Leser erforderlich.
- [x] Challenges als leere Starter; Antworten über Lesefassung oder Welt-Schaufenster teilbar.

Grenzen: HTML wird lokal exportiert; Hosting und die Aufnahme in ein öffentliches Schaufenster erfolgen durch den Benutzer beziehungsweise manuell im Katalog. Kein eigener Community-Server, keine Echtzeit-Zusammenarbeit, kein Chat. HTML bewahrt übliche Textformatierung, ist aber kein seitengetreuer Word-Export. Feedback ist eine gesonderte Datei, keine gemeinsame Live-Bearbeitung.

## Prüfung 0.7
Neue Integrationstests decken Paketrundlauf, Ausschlüsse, Abhängigkeiten, ID-Neuzuordnung, selektiven Import, Kalendergrenzen, reale PDF-Erzeugung, Feedback-Zuordnung, Bibliotheksversionen, Katalogquellen/Prüfsummen, Update-Konflikte, tatsächliche Projektübernahme mit Sicherung und deutsch/englische Dialoglayouts ab. Der Windows-Workflow prüft zusätzlich den Start der Community- und Leseroberfläche in der gebauten EXE.
