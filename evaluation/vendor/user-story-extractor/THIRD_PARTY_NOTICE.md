# Übernommene Bestandteile des User Story Extractor

Autorin: **Thayná Camargo da Silva** (2024).

Titel: *Extracting Knowledge Graphs from User Stories using LangChain*, Version 1.

Quelle: [versioniertes Forschungsartefakt auf Zenodo](https://doi.org/10.5281/zenodo.14254059).
Der übergeordnete [Konzept-DOI](https://doi.org/10.5281/zenodo.14254058) bezeichnet die Versionsfamilie.
Das [Originalarchiv](https://zenodo.org/api/records/14254059/files/user-story-extractor.zip/content)
hat die MD5-Prüfsumme `a845c52916202a3e992089cf0fd410dc`.

Die [Metadaten dieser Archivversion](https://zenodo.org/api/records/14254059) weisen
**Creative Commons Attribution 4.0 International (CC BY 4.0)** aus:
[Lizenzbedingungen](https://creativecommons.org/licenses/by/4.0/).
Die zehn nachfolgend aufgeführten Dateien wurden unverändert übernommen; ihre
Bytes wurden mit dem versionierten Originalarchiv verglichen. Vorhandene Hinweise
und Kommentare in den Dateien bleiben erhalten. Die Übernahme bedeutet keine
Unterstützung oder Prüfung dieser Masterarbeit durch die Autorin.

| Übernommene Datei | SHA-256 |
| --- | --- |
| `evaluation.py` | `0473e807fdc7941735ae9b36143edd7eee5cc165dbe2271621edb15e8ad2cd8a` |
| `pos_baseline/g03_baseline_intersecting_pos.json` | `3756e788d7bdd57d3581e993540601ce52ee479eaa63d700c12cd81957f6ce5c` |
| `pos_baseline/g04_baseline_intersecting_pos.json` | `7e18460eed22db841b499ef510b988d6598d730bd8e9ae86eb98cba46e4ccfac` |
| `evaluation/gpt-4-turbo/strict_dataset_results.csv` | `b17c3ce60269806b9f1659d69b5e4b4be0ac8755463b7f6383770730be2d8350` |
| `evaluation/gpt-4o-mini/strict_dataset_results.csv` | `d16244a031df97978bea1b46785c932f3b17814e5baefc0cc9bff3c4a39433e3` |
| `evaluation/ollama3/strict_dataset_results.csv` | `b05a4c57b77d31c946a35c732b02cbf2e8f3b5daf64012eb25e43587f451ca76` |
| `pickle/gpt-4-turbo/g03.pickle` | `229a38999820d13d6977874941dc39b8ddaeeb9827d1b60a64e16a253b39a189` |
| `pickle/gpt-4-turbo/g04.pickle` | `21d281f879268778a1e5a4c0f161d57a074bc1637c563ead525617b7a2bfbab1` |
| `pickle/gpt-4o-mini/g03.pickle` | `57f59e5d38055b02e970f15b29d7539d28aa5a5396d9ef334a5227fd661132bb` |
| `pickle/gpt-4o-mini/g04.pickle` | `cfeceee8640bf710fabe3e5cb7d9d2784028c357f34781783dea482addeeaffb` |

Die drei vollständigen CSV-Dateien enthalten jeweils Ergebnisse mehrerer Backlogs.
Der eigene Adapter nutzt daraus ausschließlich die sechs Zeilen zu G03 und G04.
Die vier Pickle-Dateien dienen ausschließlich dem nachträglichen Vergleich mit
den entsprechenden JSON-Projektionen; die produktiven Graphimporte bleiben
JSON-basiert. Nicht benötigte Teile des Originalarchivs, insbesondere die
LLM-Extraktionssoftware, sind nicht Bestandteil dieser Kopie.

## Herkunft der Referenzannotationen und Storytexte

Die Referenzannotationen gehen auf Sathurshan Arulmohan, Sébastien Mosser und
Marie-Jean Meurs (2023), *ace-design/qualified-user-stories: Version 1.0*, zurück:
[Datensatz](https://doi.org/10.5281/zenodo.8136975).
Die [LICENSE-Datei der Originalversion](https://github.com/ace-design/qualified-user-stories/blob/v1.0/LICENSE)
enthält **CC0 1.0 Universal**:
[Bedingungen](https://creativecommons.org/publicdomain/zero/1.0/).
Die hier übernommenen `pos_baseline`-Dateien stammen in ihrer konkreten,
gefilterten und um POS-Angaben ergänzten Form aus dem oben genannten
CC-BY-4.0-Artefakt von da Silva; es werden keine weiteren Dateien aus dem
separaten Repository `nlp-stories` übernommen.

Die ursprünglichen Storytexte stammen von Fabiano Dalpiaz (2018),
*Requirements data sets (user stories)*, Version 1:
[Originaldatensatz](https://doi.org/10.17632/7zbk8zsd8y.1),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Die Referenzdateien bilden eine bearbeitete Teilmenge dieses Ausgangsmaterials.

## Abgrenzung des eigenen Adapters

`../../run_extraction_validation.py` ist eine Ergänzung dieser Masterarbeit und
nicht Bestandteil von da Silvas Originalsoftware. Sie lädt ausschließlich
explizit ausgewählte, per Quelltext-Prüfsumme abgesicherte Funktionen aus der
unveränderten `evaluation.py`. Sie führt weder deren Hauptprogramm noch die
schweren Bibliotheksimporte oder die BERTScore-Routinen aus. UTF-8-Dateilesen,
zeilenweiser Eins-zu-eins-Abgleich mit offengelegter Abdeckung, Ergebnisexport und
Prüfung gegen die historischen CSV-Werte sind im Adapter dokumentiert.

Die Reproduktion misst die Übereinstimmung extrahierter Textbestandteile mit der
Referenz. Sie prüft weder Neo4j-Importtreue noch Qualitätsmängel oder Redundanz von
User Stories. Die Referenzannotationen und die eigene Qualitäts-Ground-Truth sind
unterschiedliche Datenbestände mit unterschiedlichen Zwecken.

`../../run_representation_audit.py` ist ebenfalls eine eigene Ergänzung. Es prüft
vor dem Dekodieren die oben dokumentierten SHA-256-Werte und ersetzt ausschließlich
die vier erwarteten LangChain-Klassen durch inerte Datenobjekte. Fremde Klassen
und veränderte Pickle-Dateien werden abgewiesen. Das Programm führt weder einen
LLM-Lauf noch den ursprünglichen LangChain-Neo4j-Import aus. Es vergleicht die
gespeicherten Inhalte und berechnet ausdrücklich bezeichnete Varianten des
festgelegten Zielschemas. Unbekannte Pickle-Dateien dürfen nicht ungeprüft mit
einem allgemeinen `pickle.load` geladen werden.
