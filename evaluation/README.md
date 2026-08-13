# Evaluationsartefakte: Graphenbasierte Qualitätssicherung für User Story Backlogs

Dieses Verzeichnis enthält die experimentelle Evaluations- und Testumgebung zur Masterarbeit:

**Titel:** Graph-based design and implementation of quality assurance checks for user story backlogs  
**Autor:** Daniel Scharf (Matrikelnummer: 4001730)  
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
