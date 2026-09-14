# Evaluationsartefakt: Graphenbasierte Qualitätssicherung von User-Story-Backlogs

Dieses Verzeichnis enthält die Replikationsumgebung zur Masterarbeit von **Dustin Scharf**, BTU Cottbus-Senftenberg, Lehrstuhl Software-Systemtechnik. Alle benötigten Eingabe- und Referenzdateien sind enthalten; eine Neo4j-Installation ist für die Datenbankläufe zusätzlich erforderlich. Die PDF und die Typst-Quelldatei sind nicht Teil dieses Artefakts.

Die LLM-Extraktion und die gespeicherten Extraktionsresultate stammen aus der **Vorarbeit von Thayná Camargo da Silva**. Diese Arbeit ergänzt die formale Qualitätssicherung, den provenienzerhaltenden Import, Cypher-Prüfungen, Defektevaluation und Tests. Sie führt mit den hier dokumentierten Befehlen keine neue LLM-Extraktion durch.

Implementierungsstand: `story-provenance-v2`. Die eigene Defektannotation ist von der übernommenen Referenz für die Komponentenextraktion zu unterscheiden. Insbesondere ist die Annotation **G03_54 fachlich strittig und nicht durch den Betreuer bestätigt**; siehe [Codierleitfaden](GROUND_TRUTH_CODEBOOK.md).

## 1. Bestand und Herkunft

| Datei/Verzeichnis | Zweck und Herkunft |
| --- | --- |
| `raw_datasets/` | Unveränderte Teilkorpora G03 und G04 von Dalpiaz (2018), insgesamt 109 Stories |
| `extracted_data/` | Übernommene gespeicherte Extraktionen der Konfigurationen `gpt-4-turbo`, `gpt-4o-mini`, `ollama3` und `chatgpt`; keine in diesem Replikationslauf neu erzeugten LLM-Ausgaben |
| `ground_truth.json` | Von Dustin Scharf erstellte Qualitätsannotation für alle 109 Rohstories; ursprüngliche Labels unverändert |
| `GROUND_TRUTH_CODEBOOK.md` | Bedeutung der Defektlabels, Abbildungsregeln und dokumentierte Annotationsunsicherheit |
| `aqusa_outputs/` | Archivierte Analyseausgaben und Herkunftshinweis; kein neuer AQUSA-Lauf und kein vollständiger Nachweis der ursprünglichen Laufumgebung |
| `vendor/user-story-extractor/` | Unveränderte Auswahl aus Camargo da Silvas Forschungsartefakt: Evaluator, zwei Komponentenreferenzen, drei historische CSV-Dateien und vier Pickle-Dateien für den Repräsentationsvergleich |
| `graph_model.py` | Gemeinsamer Parser, Story-IDs, Referenzzuordnung, Metriken und mengenbasierte Referenzauswertung |
| `graph_queries.py` | Gemeinsame Import- und Prüfqueries |
| `graph_database.py` | Schema-/Partitionsprüfung, exakter Abgleich von Knoten, Beziehungen und Texten |
| `evaluation_report.py` | AQUSA-Abgleich, Projektion auf Rohstory-IDs und Ergebnisberichte |
| `import_to_neo4j.py` | Kommandozeileneinstieg für den sicheren Import |
| `quality_checks.cql` | Lesende Cypher-Prüfungen; ihre Übereinstimmung mit `graph_queries.py` wird getestet |
| `run_full_evaluation.py` | Defektevaluation der Neo4j-Ausgaben gegenüber der eigenen Defektannotation |
| `run_llm_comparison.py` | Nachgelagerte QA-Regeln auf den vier gespeicherten JSON-Konfigurationen |
| `run_extraction_validation.py` | Eigener Adapter zur Reproduktion ausgewählter Originalfunktionen von Camargo da Silvas Komponenten-Evaluator |
| `run_performance_evaluation.py` | Laufzeitmessung der gemeinsamen Cypher-Regeln, getrennt nach Backlog |
| `run_annotation_sensitivity.py`, `annotation_review.json` | Nachträgliche Prüfung der 19 positiven Atomaritätslabels und Sensitivitätsrechnung zu sieben mehrdeutigen Fällen; keine neue Ground Truth |
| `run_representation_audit.py` | Hashgesicherter Pickle-/JSON-Abgleich und datenbankfreie Repräsentationsvarianten |
| `tests/` | 55 Tests: 45 ohne Datenbank, 10 mit explizit gewählter Testdatenbank |
| `evaluation_results.json` | Tatsächlich erzeugter Neo4j-Defektbericht; Konfiguration und Quellenprüfsummen unter `protocol` |
| `llm_comparison_results.json` | Abgeleitete JSON-Referenzauswertung, ausdrücklich kein neuer LLM- oder Neo4j-Lauf |
| `extraction_validation_results.json` | Abgeleitete Reproduktion der Komponentenbewertung und ihrer Referenzabdeckung |
| `performance_results.json` | Tatsächlich gemessene Laufzeiten und DB Hits einschließlich Umgebung und Protokoll |
| `annotation_sensitivity_results.json` | Symmetrischer Ausschluss der sieben Grenzfälle und alle 128 binären Labelvarianten bei festen Vorhersagen |
| `representation_audit_results.json` | 206 geprüfte Dokumentprojektionen, Relationsherkunft und abweichende Endpunkttypen |
| `verification_results.json` | Abschließender Teststand mit explizit erfolgreichen/übersprungenen Tests und Quelltexthashes |
| `requirements.txt` | Python-Abhängigkeit |
| `CITATION.cff` | Zitationsangabe für dieses Artefakt |
| `.gitignore`, `.gitattributes` | Ausschluss lokaler Arbeitsdateien und Erhaltung der ausgelieferten Dateibytes |
| `MANIFEST.sha256` | Prüfsummen sämtlicher ausgelieferter Dateien außer dem Manifest selbst |

Herkunft, Lizenz und Prüfwerte der unverändert übernommenen Fremddateien stehen im [Drittmaterialnachweis](vendor/user-story-extractor/THIRD_PARTY_NOTICE.md). Es bestehen keine Pfadabhängigkeiten zum übrigen Arbeitsverzeichnis des Autors.

## 2. Datenumfang und Graphmodell

G03 und G04 sind unabhängige Backlogs. Im neuen Modell wird jedes Konzept ausschließlich innerhalb einer Kombination aus **`model` und `pid`** zusammengeführt:

- `Backlog`: Schlüssel `(model, pid)`; über `HAS_STORY` mit seinen Stories verbunden.
- `UserStory`: Schlüssel `(model, pid, id)`.
- `Persona`, `Action`, `Entity`, `Benefit`: Schlüssel `(model, pid, name)`.
- Jede `TRIGGERS`- und `TARGETS`-Beziehung besitzt zusätzlich die `story_id` ihrer Ursprungsstory.

Der dokumentierte Hauptlauf speichert G03 und G04 zusätzlich in zwei physischen Neo4j-Datenbanken namens `g03` und `g04`. Jeder Backlog besitzt damit einen eigenen Graphspeicher und Transaktionsraum. Die zusammengesetzten Schlüssel und Partitionsprüfungen bleiben als zusätzliche Integritätssicherung erhalten: Identische Namen in G03/G04 erzeugen schon wegen der Datenbankgrenze keine gemeinsamen Knoten. Überlappungsabfragen vergleichen nur Stories innerhalb der jeweils geöffneten Datenbank und verlangen die passenden eigenen Beziehungsbelege beider Stories.

Der Parser vereinigt primäre und sekundäre Actions/Entities sowie die Endpunkte der expliziten Beziehungen. Er verändert keine Konzeptnamen, Groß-/Kleinschreibung oder Bedeutungen. Die vorhandenen Turbo-Story-IDs bleiben erhalten: Sie verwenden das bisherige MD5-Präfix des unveränderten Quelltexts. `#G03#`-/`#G04#`-Präfixe werden nur für den Textabgleich mit der Defektannotation entfernt, nicht vor der ID-Bildung.

Für `gpt-4-turbo` gilt:

| Ebene | G03 | G04 | Gesamt |
| --- | ---: | ---: | ---: |
| Rohstories / Defektreferenz | 58 | 51 | 109 |
| Bereitgestellte Extraktionsrecords | 55 | 48 | 103 |
| Persistierte UserStory-Knoten | 55 | 48 | 103 |
| Persistierte Knoten insgesamt | 391 | 304 | 695 |
| Persistierte Beziehungen insgesamt | 847 | 660 | 1.507 |
| Zugeordnete Rohstory-IDs | 56 | 48 | 104 |
| Bereits in den Eingabeextraktionen fehlende Rohstories | 2 | 3 | 5 |

G03_45 und G03_46 haben denselben Text. Ein Graphknoten wird für den Defektvergleich daher auf **beide** Rohstory-IDs zurückgeführt. G03_39, G03_54, G04_05, G04_15 und G04_48 fehlen bereits in den übernommenen Extraktionsdateien. Aus ihrem Fehlen allein lässt sich dessen Ursache nicht bestimmen.

Die bereitgestellten 103 Records enthalten selbst keine weiteren identischen Records: **Dieser Import führt im aktuellen Input null neue Dubletten zusammen.** Die technische Fähigkeit zur identischen ID-Bildung wird separat getestet; dafür wird kein Graph-Duplikat-F1 ausgewiesen. Die Evaluation berücksichtigt alle 109 Rohstories, weist die 104 abgedeckten IDs separat aus und behandelt fehlende Extraktionen nicht als erfolgreich geprüfte Stories.

## 3. Voraussetzungen und Verbindung

Die dokumentierte Datenbankreproduktion verwendet Python 3.13.2, den Treiber `neo4j==6.2.0` und **Neo4j Enterprise 2026.04.0**. Die Enterprise-Edition ist für zwei gleichzeitig verwaltete physische Datenbanken erforderlich. Die Serverinstallation selbst gehört nicht zu diesem Ordner. Der Import erstellt oder startet keine Neo4j-Instanz.

Alle nachfolgenden Befehle werden im Ordner `evaluation/` ausgeführt:

```bash
python -m pip install -r requirements.txt
```

Für die exakte Reproduktion sind zwei **eigene, leere Zieldatenbanken** mit den Namen `g03` und `g04` vorzubereiten. Verwaltungsbefehle werden in Neo4j Browser gegen `system` ausgeführt:

```cypher
:use system
SHOW DATABASES;
CREATE DATABASE g03 WAIT;
CREATE DATABASE g04 WAIT;
```

Vor dem Erstellen muss `SHOW DATABASES` bestätigen, dass beide Namen noch frei sind. `OR REPLACE` darf nicht verwendet werden. Der Import leert oder migriert keine vorhandene Datenbank. Insbesondere bleibt die historische Datenbank `userstories` geschützt; auch `system` ist als Importziel gesperrt.

PowerShell:

```powershell
$env:NEO4J_URI = "bolt://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = [System.Net.NetworkCredential]::new("", (Read-Host "Neo4j-Passwort" -AsSecureString)).Password
```

Bash:

```bash
export NEO4J_URI="bolt://127.0.0.1:7687"
export NEO4J_USER="neo4j"
read -r -s -p "Neo4j-Passwort: " NEO4J_PASSWORD
export NEO4J_PASSWORD
```

Die URI ist an die eigene Instanz anzupassen. Passwörter werden nicht in Dateien oder Kommandozeilenargumenten gespeichert. Eine lokale `.env` wird ignoriert, von den Skripten aber nicht automatisch geladen. `--separate-databases` ordnet G03 der Datenbank `g03` und G04 der Datenbank `g04` zu. Für gezielte Einzelprüfungen kann stattdessen weiterhin `--database` zusammen mit genau einem `--backlog` verwendet werden; `NEO4J_DATABASE` wird nicht ausgewertet.

## 4. Replikation

### 4.1 Import und vollständige Tests

```bash
python -B import_to_neo4j.py --separate-databases --model gpt-4-turbo --backlog g03 g04
```

Vor dem Import werden alle ausgewählten Eingabedateien validiert. Der Import erzeugt zusammengesetzte Eindeutigkeitsconstraints und prüft anschließend die vollständigen Knoten-/Beziehungsmengen sowie die Storytexte. Ein erneuter Import unveränderter, vollständig passender Daten ist zulässig. Geänderte Quellen, ein altes Schema, fehlende Beziehungen oder fremde Graphdaten werden abgelehnt; dafür ist eine neue Zieldatenbank zu verwenden.

Weitere Modellkonfigurationen können mit demselben Befehl und anderem `--model` importiert werden. Sie bleiben innerhalb der jeweiligen Backlogdatenbank durch ihre Modellschlüssel getrennt. `--backlog g03` oder `--backlog g04` wählt einen einzelnen Backlog.

Die vollständige Testsuite benötigt zusätzlich eine ausdrücklich ausgewählte Testdatenbank. PowerShell:

```powershell
$env:NEO4J_TEST_DATABASE_G03 = "g03"
$env:NEO4J_TEST_DATABASE_G04 = "g04"
$env:NEO4J_TEST_MODEL = "gpt-4-turbo"
python -B -m unittest discover -s tests -v
```

Bash:

```bash
export NEO4J_TEST_DATABASE_G03="g03"
export NEO4J_TEST_DATABASE_G04="g04"
export NEO4J_TEST_MODEL="gpt-4-turbo"
python -B -m unittest discover -s tests -v
```

Von den 55 Tests laufen 45 ohne Datenbank; 10 prüfen die echte Persistierung und Cypher-Abfragen. Die synthetischen Datenbankfälle werden ausschließlich in anschließend zurückgerollten Transaktionen angelegt. Die ursprünglichen Extraktionspartitionen werden dabei nicht geändert. Die Tests umfassen unter anderem vertauschte Action-Entity-Paare, fehlende eigene Targets/Triggers, Backlog-/Modellisolation, Idempotenz, vollständige Importtreue sowie die ergänzenden Repräsentations- und Annotationsprüfungen.

Ohne gesetzte Testdatenbank/Zugangsdaten werden die zehn Datenbanktests ausdrücklich **übersprungen**. Das ist kein vollständiger Datenbank-Testlauf.

Der ausgelieferte Prüfbericht dokumentiert **55 erfolgreiche Tests, keine Fehler und keine übersprungenen Tests**, einschließlich der zehn Live-Datenbanktests. Die beiden Datenbanken `g03` und `g04` besitzen unterschiedliche Datenbankidentitäten; der vollständige Graphbestand und alle Qualitätsausgaben wurden erneut mit der JSON-Referenzberechnung abgeglichen. Inhaltsprüfsummen vor und nach den Tests bestätigen, dass die beiden Evaluationsgraphen und die ursprüngliche Datenbank `userstories` unverändert geblieben sind. `verification_results.json` hält die geprüften Identitäten, Kardinalitäten, Inhaltsprüfsummen und Quelltexthashes fest.

`evaluation_results.json` enthält den erneut bestätigten Neo4j-Abgleich mit aktuellem Ausführungszeitpunkt. Die gesonderte Kennzeichnung des historischen Incomplete-Means-Labelabgleichs bleibt unter `protocol.report_revision` nachvollziehbar. Die Laufzeitwerte in `performance_results.json` behalten dagegen den Zeitpunkt ihrer ursprünglichen Messung; der abschließende Funktionstest ersetzt keinen Laufzeitbenchmark.

### 4.2 Defektevaluation in Neo4j

```bash
python -B run_full_evaluation.py --separate-databases --model gpt-4-turbo
```

Der Lauf öffnet für jeden Backlog ausschließlich dessen eigene Datenbank und überprüft vor der Auswertung die vollständige Übereinstimmung mit der jeweiligen Eingabe. `evaluation_results.json` enthält Gesamtwerte, `per_backlog`, die separat ausgewiesene `coverage` und explorative Muster unter `exploratory.per_backlog`.

Eine datenbankfreie Referenzberechnung ist getrennt möglich:

```bash
python -B run_full_evaluation.py --source-json-only
```

Sie schreibt `evaluation_source_results.json` und kennzeichnet `protocol.execution` als `json_reference`. Das ist weder ein Neo4j-Ausführungsnachweis noch eine unabhängige Prüfung der LLM-Extraktion.

### 4.3 Nachgelagerte QA im Modellvergleich

```bash
python -B run_llm_comparison.py
```

Dieser datenbankfreie Lauf wendet dieselbe Quelleninterpretation und dieselben mengenbasierten QA-Bedingungen auf alle vier gespeicherten Modellkonfigurationen an. Das Ergebnis steht unter `llm_comparison_results.json → models`. Es misst Defektalarme auf den gespeicherten Extraktionen, **nicht** die Güte der Komponentenextraktion. Graphkardinalitäten werden pro Backlog als aus den Quellen abgeleitete Werte berichtet. Eine Modellwahl erfolgt nicht automatisch anhand dieser Testergebnisse; `chatgpt` ist zunächst eine übernommene Konfigurationsbezeichnung.

### 4.4 Komponentenbewertung aus der Vorarbeit

```bash
python -B run_extraction_validation.py
```

Der Adapter verwendet die per Prüfsumme abgesicherten Originalfunktionen von Camargo da Silvas Evaluator und die mitgelieferten Komponentenreferenzen. Der unveränderte Fremdcode wird nicht als eigenes Verfahren ausgegeben. Ausgeführt wird standardmäßig der ursprüngliche strikte Vergleich; schwere Bibliotheksimporte, das ursprüngliche Hauptprogramm und BERTScore werden nicht ausgeführt.

Die gespeicherte Reproduktion bestätigt sechs historische CSV-Zeilen beziehungsweise 72 P/R/F1-Werte für `gpt-4-turbo`, `gpt-4o-mini` und `ollama3`. Für `chatgpt` liegen keine entsprechenden Vergleichszeilen vor; dessen Werte werden neu aus den gespeicherten Eingaben berechnet. Die ursprüngliche Methode bewertet nur zugeordnete Referenzstories: 55/55 für G03 und 48/48 für G04, bei `ollama3` G04 nur 47/48. Fehlende Referenzvorkommen werden gesondert dokumentiert.

Der Bericht verwendet Verhältniswerte von 0 bis 1; die Defektberichte verwenden Prozentwerte von 0 bis 100. Komponentenbewertung, Neo4j-Importtreue und Defektklassifikation sind drei verschiedene Prüfungen. Dieser Komponenten-Evaluator bewertet keine semantischen Beziehungen und keine paarweise Story-Redundanz.

### 4.5 Laufzeitmessung

```bash
python -B run_performance_evaluation.py --separate-databases --model gpt-4-turbo
```

Jede der fünf Regeln wird für **jeden Backlog getrennt** nach 25 Aufwärmläufen 250-mal ausgeführt. `performance_results.json → measurements_per_backlog` enthält Ergebniszeilen, DB Hits, Median, 95. Perzentil, Minimum und Maximum. Gemessen wird die clientseitige Laufzeit einschließlich Treiberkommunikation. Die gespeicherten Werte stammen aus einer tatsächlichen lokalen Messung, sind aber keine Skalierbarkeitsaussage. Sie sind wegen des geänderten Modells nicht mit früheren globalen Graphmessungen gleichzusetzen.

Alle Berichtsskripte akzeptieren `--output`. Ohne diese Option ersetzen sie beim erneuten Ausführen ihre jeweilige Ergebnisdatei. Für einen Vergleich mit den ausgelieferten Berichten sollten neue Läufe einen anderen Ausgabepfad verwenden; die ausgelieferten Prüfsummen gelten nur für den unveränderten Lieferstand.

### 4.6 Ergänzende Repräsentations- und Annotationsprüfungen

```bash
python -B run_representation_audit.py
python -B run_annotation_sensitivity.py
```

Beide Programme laufen ohne Datenbank, LLM-Aufruf oder Änderung der Eingabedaten.
Der Repräsentationsvergleich akzeptiert ausschließlich die vier Original-Pickle-Dateien
mit den dokumentierten SHA-256-Werten und führt deren ursprüngliche Klassen nicht aus.
Er prüft 206 Dokumentprojektionen und simuliert Herkunftsverlust sowie die strikte
Übernahme der ursprünglichen Endpunkttypen. Das ist kein erneuter LangChain-Import.

Die Annotationsprüfung verwendet die in `annotation_review.json` begründeten
mehrdeutigen Fälle. Sie vergleicht sowohl deren symmetrischen Ausschluss als auch
alle 128 binären Zuordnungen. Die ursprüngliche Qualitätsannotation bleibt
unverändert. Diese nachträgliche KI-unterstützte Analyse ersetzt keine unabhängige
Zweitannotation und liefert keine statistischen Konfidenzintervalle.

## 5. Einordnung der gespeicherten Defektergebnisse

Für die Turbo-Konfiguration und die unveränderten Labels in `ground_truth.json` ergeben sich:

| Prüfung | AQUSA | Graphregel |
| --- | --- | --- |
| Missing Benefit | Nicht implementiert; kein Leistungsvergleich | TP=6, FP=0, FN=0; F1=100,0 % |
| Atomarität, Actions >1 | TP=13, FP=0, FN=6; F1=81,2 % | TP=18, FP=79, FN=1; F1=31,0 % |
| Atomarität, Actions >2 | Dieselbe AQUSA-Ausgabe | TP=10, FP=26, FN=9; F1=36,4 % |
| Atomarität, Actions >4 | Dieselbe AQUSA-Ausgabe | TP=2, FP=0, FN=17; F1=19,0 % |
| Incomplete Means / Dangling Action | Qualitative Analyse; keine bestätigte positive Referenz | Qualitative Analyse von vier Aktionen in drei Stories; keine regulären P/R/F1-Werte |
| Exaktes Textduplikat | G03_46 als gespeicherter AQUSA-Alarm | Technische Importinvariante, **kein Graph-Duplikat-F1** |

Die Rückprojektion des kanonischen Duplikattexts auf beide Rohstory-IDs erklärt die zusätzlichen False Positives gegenüber älteren Auswertungen bei Actions >1 und >2. Die Herkunftsbindung erkennt nun zusätzlich die Dangling Action `fix` in G04_51. Diese Anpassungen verändern nicht die Ground-Truth-Labels.

Bei Precision oder Recall mit Nenner null steht im JSON `null` statt eines fingierten Prozentwerts. F1 wird direkt als `2*TP/(2*TP+FP+FN)` berechnet; auch hier ist ein Nenner von null als nicht definiert gekennzeichnet.

Missing Benefit prüft einen ausdrücklich genannten Nutzen, nicht den tatsächlichen Wert der Funktion. Ein Benefit ist bei QUS-Well-formedness optional. Die konjunktionsnahe Atomaritätsannotation kann AQUSA gegenüber einer Action-Count-Heuristik begünstigen. Der historische Incomplete-Means-Labelabgleich ist ausschließlich zur Rückverfolgbarkeit unter `historical_annotation_comparison` gespeichert; `metrics_applicable=false` schließt ihn vom regulären Leistungsbericht aus.

Bei Ausschluss der sieben mehrdeutigen Atomaritätsfälle ergeben sich F1=90,9 % für AQUSA und 21,6 %, 31,1 % beziehungsweise 0,0 % für die drei Turbo-Schwellen. AQUSAs F1 liegt in allen 128 untersuchten Labelkombinationen über den sechs geprüften Graphkonfigurationen. Die absoluten Werte hängen somit von den Labels ab; die Rangfolge ist gegenüber diesen sieben Entscheidungen stabil. Weitere Annotationsunsicherheiten sind damit nicht ausgeschlossen.

Die provenienzgebundenen Abfragen liefern vier Overlap-Gruppen in G03 und fünf in G04 sowie zwei Cross-Persona-Muster in G04. Diese Ergebnisse sind Review-Hinweise; ohne paarweise Redundanzreferenz werden dafür keine Precision-, Recall- oder F1-Werte behauptet.

## 6. Integrität und Weitergabe

Die Prüfsummen beziehen sich auf alle Dateien des ausgelieferten Ordners mit Ausnahme von `MANIFEST.sha256` selbst. Unter Linux/Git Bash:

```bash
sha256sum --check MANIFEST.sha256
```

Unter PowerShell kann eine einzelne Datei beispielsweise so geprüft werden:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath "ground_truth.json"
```

Die `.gitattributes` deaktiviert die automatische Zeilenendenumwandlung für das Artefakt, damit Git die ausgelieferten Bytes und Originalprüfsummen erhält. Jede inhaltliche Änderung oder neue Berichtserzeugung erfordert eine erneute Manifestbildung.

Für GitHub und USB gelten dieselben Inhalte dieses Ordners; die Abschlussarbeits-PDF liegt separat. Lokale Datenbankdateien, Passwörter, Logs, Python-Caches und virtuelle Umgebungen gehören nicht zum Artefakt.

## 7. Quellen und Rechte

- Camargo da Silva, T. (2024). *Extracting knowledge graphs from user stories using LangChain* (Version 1) [Software]. Zenodo. [https://doi.org/10.5281/zenodo.14254059](https://doi.org/10.5281/zenodo.14254059)
- Camargo da Silva, T. (2025). *Extracting knowledge graphs from user stories using LangChain* [Masterarbeit, Brandenburgische Technische Universität Cottbus-Senftenberg]. BTUOpen. [https://doi.org/10.26127/BTUOpen-7038](https://doi.org/10.26127/BTUOpen-7038)
- Arulmohan, S., Mosser, S., & Meurs, M.-J. (2023). *ace-design/qualified-user-stories: Version 1.0* (v1.0) [Datensatz]. Zenodo. [https://doi.org/10.5281/zenodo.8136975](https://doi.org/10.5281/zenodo.8136975)
- Dalpiaz, F. (2018). *Requirements data sets (user stories)* (Version 1) [Datensatz]. Mendeley Data. [https://doi.org/10.17632/7zbk8zsd8y.1](https://doi.org/10.17632/7zbk8zsd8y.1)
- Lucassen, G., Dalpiaz, F., van der Werf, J. M. E. M., & Brinkkemper, S. (2016). Improving agile requirements: The Quality User Story framework and tool. *Requirements Engineering, 21*(3), 383–403. [https://doi.org/10.1007/s00766-016-0250-x](https://doi.org/10.1007/s00766-016-0250-x)

Die ursprünglichen Storytexte von Dalpiaz stehen unter [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), auch soweit sie in Extraktionen, Referenzen und Ergebnissen wiedergegeben werden. Hier wird nur die Teilmenge G03/G04 weitergegeben. Die übernommenen Extraktionen und Fremddateien sind dem versionierten CC-BY-4.0-Forschungsartefakt von Camargo da Silva zugeordnet; sie werden nicht Dustin Scharf als Urheber zugeschrieben. Die Komponentenreferenzen gehen auf Arulmohan et al. zurück und liegen hier in der von Camargo da Silva bearbeiteten Form vor.

Die genauen Herkunfts- und Lizenzangaben der Fremdanteile bleiben im [Drittmaterialnachweis](vendor/user-story-extractor/THIRD_PARTY_NOTICE.md) erhalten. Diese Hinweise lizenzieren nicht pauschal den eigenen Quellcode neu. Eigene Ergänzungen sind die oben benannten QA-/Import-/Reportmodule, Tests, Defektannotation, Dokumentation und der Adapter; die Komponentenextraktion selbst gehört zur Vorarbeit.
