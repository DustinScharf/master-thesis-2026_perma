# Evaluationsartefakte: Graphenbasierte Qualitätssicherung für User Story Backlogs

Dieses Verzeichnis enthält die experimentelle Evaluations- und Testumgebung zur Masterarbeit:

**Titel:** Graph-based design and implementation of quality assurance checks for user story backlogs  
**Autor:** Scharf  
**Institution:** Brandenburgische Technische Universität Cottbus-Senftenberg (BTU)  
**Fakultät:** Fakultät für Mathematik, Informatik, Physik, Elektrotechnik und Informationstechnik  
**Institut:** Institut für Informatik, Lehrstuhl Software-Systemtechnik (Prof. Dr. rer. nat. Leen Lambers)  
**Jahr:** 2026  

---

## 1. Verzeichnis- und Artefaktstruktur

```text
evaluation/
├── README.md                   Dokumentation und Ausführungsanleitung
├── ground_truth.json           Theoriegeleitet annotierte Ground Truth (109 Stories)
├── evaluation_results.json     Strukturierter Export aller berechneten Evaluationsmetriken
├── import_to_neo4j.py          Nativer Python/Cypher ETL-Ingestionsprozess
├── quality_checks.cql          Sammlung formalisierter Cypher-Qualitätsregeln
├── run_full_evaluation.py      Automatisierter Evaluations- und Metrikabgleich (Cypher vs. AQUSA)
├── tests/
│   └── test_suite.py           Automatisierte Testsuite (Unit-, Integrations- und Systemtests)
├── aqusa_outputs/
│   ├── g03-aqusa.txt           Originale Analyseausgabe des NLP-Referenzwerkzeugs AQUSA für G03
│   └── g04-aqusa.txt           Originale Analyseausgabe des NLP-Referenzwerkzeugs AQUSA für G04
└── raw_datasets/
    ├── g03-loudoun.txt         Originales Benchmark-Korpus G03 (58 User Stories, Dalpiaz 2018)
    └── g04-recycling.txt       Originales Benchmark-Korpus G04 (51 User Stories, Dalpiaz 2018)
```

---

## 2. Systemvoraussetzungen und Installation

Die Ausführung der Evaluationsskripte und der automatisierten Testsuite setzt folgende Softwarekomponenten voraus:

- Python (Version >= 3.10)
- Neo4j Graph Database (Version >= 5.x)
- Python-Treiber `neo4j`

Zur Installation der Python-Abhängigkeiten führen Sie folgenden Befehl aus:

```bash
pip install neo4j
```

---

## 3. Datenbankkonfiguration

Die Skripte greifen standardmäßig auf eine lokale Neo4j-Instanz unter `neo4j://127.0.0.1:7687` zu. Eine individuelle Konfiguration kann über standardisierte Umgebungsvariablen vorgenommen werden:

```bash
export NEO4J_URI="neo4j://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="master2026"
export NEO4J_DATABASE="userstories"
```

---

## 4. Replikations- und Ausführungsschritte

### Schritt 4.1: ETL-Ingestion in die Neo4j-Graphdatenbank
Der Import initialisiert die notwendigen Eindeutigkeits-Constraints und Performance-Indizes und überführt die extrahierten User Stories in das Labeled Property Graph Modell:

```bash
python import_to_neo4j.py
```

### Schritt 4.2: Ausführung der automatisierten Testsuite
Die Testsuite verifiziert die Funktionsfähigkeit der modularen Datenaufbereitung, der Datenbankpersistierung und der formulierten Cypher-Testorakel gemäß dem RIPR-Fehlermodell und der Äquivalenzklassenmethode:

```bash
python tests/test_suite.py
```

### Schritt 4.3: Gesamtevaluation und Metrikberechnung
Der automatisierte Abgleich analysiert die Defekterkennung des entwickelten Cypher-Frameworks sowie des NLP-Referenzwerkzeugs AQUSA gegen die Ground Truth und exportiert die Ergebnisse nach `evaluation_results.json`:

```bash
python run_full_evaluation.py
```

---

## 5. Quantitative Evaluationsergebnisse

| Qualitätsmetrik | Baseline (AQUSA) | Graphen-Ansatz (Cypher) | Bemerkung |
| :--- | :---: | :---: | :--- |
| **Missing Benefit** | F1: 0,0 % (TP=0, FP=0, FN=6) | **F1: 100,0 % (TP=6, FP=0, FN=0)** | Deterministische Erkennung fehlender Nutzenknoten |
| **Atomizität (Fat Story)** | **F1: 81,2 % (TP=13, FP=0, FN=6)** | F1: 37,0 % (TP=10, FP=25, FN=9) | AQUSA präzise bei Konjunktionen; Graph sensitiv bei $k > 2$ |
| **Incomplete Means** | **F1: 100,0 % (TP=1, FP=0, FN=0)** | F1: 0,0 % (TP=0, FP=2, FN=1) | LLM kaschiert fehlende Zielobjekte im Fließtext |
| **Redundanz / Duplikate** | Reaktiv (Erkennung als Textdefekt) | **Präventiv (Hash-Deduplizierung)** | Zusammenführung redundanter Anforderungen beim Import ($100\,\%$) |

---

## 6. Referenzen und Zitation

- **Dalpiaz, F. (2018):** Requirements data sets (user stories) (Version 2) [Datensatz]. Mendeley Data. https://doi.org/10.17632/7zbk8zsd8y.2
- **Lucassen, G., Dalpiaz, F., van der Werf, J. M. E. M., & Brinkkemper, S. (2016):** Improving agile requirements: the Quality User Story framework and tool. *Requirements Engineering*, 21(3), 383–403. https://doi.org/10.1007/s00766-016-0250-x
- **da Silva, T. C., Lambers, L., Mosser, S., & Revoredo, K. (2025):** Provider-agnostic knowledge graph extraction from user stories using large language models. *CEUR Workshop Proceedings*, 4122, Paper 18.
