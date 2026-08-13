# Evaluation Artefakt-Repository: Graphenbasierte Qualitätssicherung für User Stories

Dieses Verzeichnis enthält die vollständige, reproduzierbare Evaluations- und Testumgebung zur Masterarbeit:
> **„Graph-based design and implementation of quality assurance checks for user story backlogs“** (BTU Cottbus-Senftenberg, 2026).

---

## 📁 Verzeichnis- und Artefaktstruktur

```text
evaluation/
├── aqusa_outputs/              # Original-Ausgaben des NLP-Referenztools AQUSA
│   ├── g03-aqusa.txt           # AQUSA Analyse für Backlog G03
│   └── g04-aqusa.txt           # AQUSA Analyse für Backlog G04
├── raw_datasets/               # Originale Benchmark-Korpora (Dalpiaz, 2018)
│   ├── g03-loudoun.txt         # 58 User Stories (Immobilienverwaltung Loudoun)
│   └── g04-recycling.txt       # 51 User Stories (Kommunale Services & Recycling)
├── tests/                      # Automatisierte Testsuite (Softwaretechnik-Standards)
│   └── test_suite.py           # 10 Unit-, Integrations- & System-Orakeltests
├── ground_truth.json           # Theoriegeleitetes Golden Sample (109 User Stories)
├── evaluation_results.json     # Exportierte Klassifikationsmetriken (TP, FP, FN, F1)
├── import_to_neo4j.py          # Nativer Python/Cypher ETL-Ingestionsprozess
├── quality_checks.cql          # Standalone Cypher-Regeln (Interaktiv & Browser)
└── run_full_evaluation.py      # Vollautomatisierter Evaluations- und Metrikabgleich
```

---

## 🚀 Schnellstart & Reproduktion

### 1. Voraussetzungen
* Python 3.10+
* Neo4j Database (lokal oder Docker, ab Version 5.x)
* Python-Treiber:
```bash
pip install neo4j
```

### 2. Datenbankkonfiguration (Optional via Umgebungsvariablen)
Standardmäßig verbindet sich die Pipeline mit `neo4j://127.0.0.1:7687` (User: `neo4j`, Password: `master2026`, Database: `userstories`).
Alternativ können Umgebungsvariablen gesetzt werden:
```bash
export NEO4J_URI="neo4j://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your_password"
export NEO4J_DATABASE="userstories"
```

### 3. Schritt-für-Schritt-Ausführung

#### A. Graphendatenbank initialisieren & Datensätze importieren
```bash
python evaluation/import_to_neo4j.py
```
*Initialisiert Schema-Indizes und Constraints und importiert die 103 User Stories der Benchmark-Backlogs G03 und G04.*

#### B. Automatisierte Testsuite ausführen
```bash
python evaluation/tests/test_suite.py
```
*Führt alle 10 Unit-, Integrations- und RIPR-Orakeltests aus.*

#### C. Gesamtevaluation und Metrikberechnung starten
```bash
python evaluation/run_full_evaluation.py
```
*Gleicht die Cypher-Ergebnisse und die AQUSA-Baseline gegen die 109 Stories der Ground Truth ab und aktualisiert `evaluation_results.json`.*

---

## 📊 Zusammenfassung der Hauptergebnisse

| Qualitätsmetrik | Baseline (AQUSA) | Graphen-Ansatz (Cypher) | Wissenschaftliche Erkenntnis |
| :--- | :---: | :---: | :--- |
| **Missing Benefit** | $F_1 = 0,0\,\%$ | $\mathbf{F_1 = 100,0\,\%}$ | Graph erkennt das Fehlen von Nutzen-Knoten deterministisch. |
| **Atomizität (Fat Story)** | $\mathbf{F_1 = 81,2\,\%}$ | $F_1 = 37,0\,\%$ | AQUSA ist präzise bei Konjunktionen; Graph überfächert bei LLM-Aktionen. |
| **Incomplete Means** | $\mathbf{F_1 = 100,0\,\%}$ | $F_1 = 0,0\,\%$ | LLM-Verbindungen kaschieren fehlende Zielobjekte im Fließtext. |
| **Redundanz / Duplikate** | Reaktiv (Meldet Textdopplung) | **Präventiv (Hash-Merge)** | Graph verhindert Duplikate direkt auf Datenbankebene ($100\,\%$). |

---

## 📜 Lizenz & Zitation
* **Ground Truth & Benchmark Datasets:** Dalpiaz, F. (2018). *Requirements data sets (user stories)*, Mendeley Data, https://doi.org/10.17632/7zbk8zsd8y.2.
* **Code:** MIT License.
