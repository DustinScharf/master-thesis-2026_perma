# Evaluationsartefakte: Graphenbasierte Qualitätssicherung für User Story Backlogs

Dieses Verzeichnis enthält die vollständige, eigenständig ausführbare Evaluations- und Testumgebung zur Masterarbeit. Alle von den Skripten benötigten Eingabe- und Referenzdaten liegen innerhalb von `evaluation/`; es bestehen keine Dateipfad-Abhängigkeiten zum übrigen lokalen Arbeitsverzeichnis.

**Titel:** Graph-based design and implementation of quality assurance checks for user story backlogs  
**Autor:** Dustin Scharf (Matrikelnummer: 4001730)  
**Institution:** Brandenburgische Technische Universität Cottbus-Senftenberg (BTU)  
**Fakultät:** Fakultät 1 MINT – Mathematik, Informatik, Physik, Elektro- und Informationstechnik  
**Institut:** Institut für Informatik, Lehrstuhl Software-Systemtechnik (Prof. Dr. rer. nat. Leen Lambers)  
**Jahr:** 2026  

---

## 1. Verzeichnis- und Artefaktstruktur

```text
evaluation/
├── .gitignore                  Ausschluss lokaler Caches, Umgebungen und Zugangsdaten
├── CITATION.cff                Maschinenlesbare Zitationsangabe des Artefakts
├── MANIFEST.sha256             SHA-256-Prüfsummen aller ausgelieferten Artefaktdateien
├── README.md                   Dokumentation und Ausführungsanleitung
├── ground_truth.json           Theoriegeleitet annotierte Ground Truth (109 Stories)
├── evaluation_results.json     Strukturierter Export aller berechneten Evaluationsmetriken
├── import_to_neo4j.py          Nativer Python/Cypher ETL-Ingestionsprozess
├── quality_checks.cql          Sammlung formalisierter Cypher-Qualitätsregeln
├── run_full_evaluation.py      Automatisierter Evaluations- und Metrikabgleich (Cypher vs. AQUSA)
├── run_llm_comparison.py       Reproduzierbarer FF4-Abgleich der vier JSON-Extraktionen
├── llm_comparison_results.json Strukturierter Export des FF4-Abgleichs
├── run_performance_evaluation.py Reproduzierbarer Warm-Cache-Kleinbenchmark
├── performance_results.json    Strukturierter Export der Laufzeit- und DB-Hits-Messungen
├── requirements.txt            Fixierte Python-Abhängigkeit der Reproduktionsumgebung
├── tests/
│   └── test_suite.py           Automatisierte Testsuite (Unit-, Integrations- und Systemtests)
├── extracted_data/             Gespeicherte Extraktionsresultate für FF4 und ETL
│   ├── gpt-4-turbo/           G03 und G04
│   ├── gpt-4o-mini/           G03 und G04
│   ├── ollama3/               G03 und G04
│   └── chatgpt/               G03 und G04
├── aqusa_outputs/
│   ├── g03-aqusa.txt           Originale Analyseausgabe des NLP-Referenzwerkzeugs AQUSA für G03
│   └── g04-aqusa.txt           Originale Analyseausgabe des NLP-Referenzwerkzeugs AQUSA für G04
└── raw_datasets/
    ├── g03-loudoun.txt         Originales Benchmark-Korpus G03 (58 User Stories, Dalpiaz 2018)
    └── g04-recycling.txt       Originales Benchmark-Korpus G04 (51 User Stories, Dalpiaz 2018)
```

---

## 2. Systemvoraussetzungen und Installation

Die abschließende Reproduktionsprüfung wurde mit folgenden Softwarekomponenten durchgeführt:

- Python 3.13.2
- Neo4j Graph Database 2026.04.0 Enterprise
- Python-Treiber `neo4j` 6.2.0

Die verwendeten Abfragen benötigen keine Enterprise-spezifische Erweiterung. Andere Neo4j-Versionen können abweichende Query-Pläne und Laufzeiten erzeugen.

Zur Installation der Python-Abhängigkeiten führen Sie folgenden Befehl aus:

```bash
pip install -r requirements.txt
```

---

## 3. Datenbankkonfiguration

Die Skripte greifen standardmäßig auf eine lokale Neo4j-Instanz unter `neo4j://127.0.0.1:7687` zu. Das Passwort wird bewusst nicht im Artefakt gespeichert und muss vor der Ausführung als Umgebungsvariable gesetzt werden. Unter PowerShell lautet die Konfiguration beispielsweise:

```powershell
$env:NEO4J_URI = "neo4j://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "<lokales Passwort>"
$env:NEO4J_DATABASE = "userstories"
```

Unter Bash lautet die entsprechende Konfiguration:

```bash
export NEO4J_URI="neo4j://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="<lokales Passwort>"
export NEO4J_DATABASE="userstories"
```

Zugangsdaten dürfen weder in die Skripte noch in eine versionierte Datei eingetragen werden. Eine lokale `.env`-Datei wird durch `.gitignore` ausgeschlossen, von den Skripten jedoch nicht automatisch eingelesen.

---

## 4. Replikations- und Ausführungsschritte

Alle folgenden Befehle werden aus dem Verzeichnis `evaluation/` ausgeführt. Die gespeicherten Extraktionsresultate der vier untersuchten Modellkonfigurationen befinden sich unter `extracted_data/`; der außerhalb dieses Verzeichnisses liegende historische Extraktionscode ist für die Replikation der berichteten Evaluation nicht erforderlich.

### Schritt 4.1: ETL-Ingestion in die Neo4j-Graphdatenbank
Der Import initialisiert die notwendigen Eindeutigkeits-Constraints und Performance-Indizes und überführt die extrahierten User Stories in das Labeled Property Graph Modell:

```bash
python import_to_neo4j.py
```

### Schritt 4.2: Ausführung der automatisierten Testsuite
Die Testsuite verifiziert die modulare Datenaufbereitung, die Datenbankpersistierung und vier Cypher-Testorakel anhand festgelegter Äquivalenzklassen und Kardinalitäten:

```bash
python tests/test_suite.py
```

### Schritt 4.3: Gesamtevaluation und Metrikberechnung
Der automatisierte Abgleich analysiert die Defekterkennung des entwickelten Cypher-Frameworks sowie des NLP-Referenzwerkzeugs AQUSA gegen die Ground Truth und exportiert die Ergebnisse nach `evaluation_results.json`:

```bash
python run_full_evaluation.py
```

### Schritt 4.4: Modellvergleich (FF4)
Der Modellvergleich arbeitet direkt auf den gespeicherten JSON-Extraktionsartefakten und benötigt keine laufende Neo4j-Instanz:

```bash
python run_llm_comparison.py
```

### Schritt 4.5: Explorative Ausführungsanalyse
Der Kleinbenchmark führt fünf zentrale Cypher-Regeln nach 25 Aufwärmdurchläufen jeweils 250-mal sequenziell aus, konsumiert die vollständige Ergebnismenge und speichert Median, 95. Perzentil sowie DB Hits in `performance_results.json`:

```bash
python run_performance_evaluation.py
```

Für Datenbankexperimente mit unterschiedlichen LLM-Modellen ist jeweils eine getrennte oder vorab geleerte Neo4j-Zieldatenbank zu verwenden, damit global harmonisierte Konzeptknoten und Beziehungen nicht zwischen Modellläufen vermischt werden.

### Schritt 4.6: Integritätsprüfung des Abgabeartefakts

Die Datei `MANIFEST.sha256` enthält die SHA-256-Prüfsummen aller ausgelieferten Dateien mit Ausnahme des Manifests selbst. Unter PowerShell können einzelne Werte mit `Get-FileHash -Algorithm SHA256 <Datei>` kontrolliert werden; unter Linux beziehungsweise Git Bash kann das gesamte Manifest aus dem Verzeichnis `evaluation/` mit `sha256sum --check MANIFEST.sha256` geprüft werden.

---

## 5. Quantitative Evaluationsergebnisse

| Qualitätsmetrik | Baseline (AQUSA) | Graphen-Ansatz / ETL | Bemerkung |
| :--- | :---: | :---: | :--- |
| **Missing Benefit** | Nicht implementiert; Metriken nicht anwendbar | **F1: 100,0 % (TP=6, FP=0, FN=0)** | AQUSA v1 besitzt hierfür keine eigenständige Regel |
| **Atomarität (Fat Story)** | **F1: 81,2 % (TP=13, FP=0, FN=6)** | F1: 37,0 % (TP=10, FP=25, FN=9) | AQUSA präzise bei Konjunktionen; Graphschwelle `Actions > 2` |
| **Incomplete Means** | **F1: 100,0 % (TP=1, FP=0, FN=0)** | F1: 0,0 % (TP=0, FP=2, FN=1) | LLM kaschiert fehlende Zielobjekte im Fließtext |
| **Redundanz / Duplikate** | F1: 100,0 % (TP=1, FP=0, FN=0) | ETL-Invariante: eine exakte Dublette zusammengeführt | Keine eigenständige Klassifikationsausgabe der ETL; Metriken nicht anwendbar |

Die Atomaritätscodierung der Ground Truth knüpft an koordinierende Konjunktionen an und liegt damit näher an AQUSAs Detektionslogik als an der graphbasierten Action-Count-Heuristik. Dieser Unterschied kann den direkten Vergleich zugunsten der Baseline beeinflussen.

Im lokalen Warm-Cache-Kleinbenchmark lagen die Medianlaufzeiten der fünf untersuchten Regeln zwischen 2,156 und 5,075 ms. Diese Werte gelten nur für den Evaluationsgraphen mit 103 `UserStory`-Knoten und sind keine Skalierbarkeitsaussage.

---

## 6. GitHub- und USB-Abgabe

Das Verzeichnis `evaluation/` bildet die unveränderte Abgabeeinheit. Für den Online-Spiegel wird der komplette Ordner in das Wurzelverzeichnis des Repositorys hochgeladen, sodass der Pfad `master-thesis-2026_perma/evaluation/README.md` entsteht. Es dürfen insbesondere `extracted_data/`, `raw_datasets/`, `aqusa_outputs/`, `tests/`, die Ergebnis-JSON-Dateien, `.gitignore`, `CITATION.cff` und `MANIFEST.sha256` nicht ausgelassen werden.

Für den USB-Datenträger wird derselbe Ordner unverändert kopiert. Die finale Masterarbeits-PDF liegt daneben und nicht innerhalb des Artefaktordners:

```text
USB-Datenträger/
├── output.pdf
└── evaluation/
    └── ... vollständiger Artefaktbestand ...
```

Nicht Bestandteil des Uploads sind lokale Neo4j-Datenbankdateien, Zugangsdaten, Python-Caches, virtuelle Umgebungen, die Typst-Quelldatei und sonstige Arbeitsdateien außerhalb von `evaluation/`.

---

## 7. Referenzen und Zitation

- **Dalpiaz, F. (2018):** Requirements data sets (user stories) (Version 1) [Datensatz]. Mendeley Data. https://doi.org/10.17632/7zbk8zsd8y.1
- **Lucassen, G., Dalpiaz, F., van der Werf, J. M. E. M., & Brinkkemper, S. (2016):** Improving agile requirements: the Quality User Story framework and tool. *Requirements Engineering*, 21(3), 383–403. https://doi.org/10.1007/s00766-016-0250-x
- **da Silva, T. C., Lambers, L., Mosser, S., & Revoredo, K. (2025):** Provider-agnostic knowledge graph extraction from user stories using large language models. *CEUR Workshop Proceedings*, 4122, Paper 18.

### Drittmaterial und Lizenz

Die in `raw_datasets/` enthaltenen Teilkorpora G03 und G04 stammen aus dem Datensatz von Dalpiaz (2018) und stehen unter der Lizenz [Creative Commons Namensnennung 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/). Gegenüber dem veröffentlichten Gesamtdatensatz ist der hier bereitgestellte Umfang auf G03 und G04 beschränkt. Annotationen, extrahierte Graphstrukturen und Evaluationsergebnisse in den übrigen Dateien wurden im Rahmen dieser Arbeit daraus abgeleitet. Die oben angegebene Quellen- und Lizenzangabe gilt ebenfalls für dort wiedergegebene User-Story-Texte.
