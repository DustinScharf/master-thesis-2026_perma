# Codierleitfaden und Annotationsprüfung der Qualitätsreferenz

Dieser Leitfaden dokumentiert die Bedeutung und Grenzen des vorhandenen Stands von `ground_truth.json`. Die Qualitätsannotation wurde von Dustin Scharf, dem Verfasser der Masterarbeit, erstellt. Der Leitfaden ist keine neue unabhängige Annotation und kein Nachweis, dass die Labels bereits durch einen zweiten Gutachter bestätigt wurden. Die Labels und Rohtexte wurden bei der Überarbeitung der Graphpipeline und der abschließenden Sensitivitätsanalyse nicht geändert.

## 1. Gegenstand und Einheiten

Die Qualitätsreferenz enthält die 58 Rohstories von G03 und 51 Rohstories von G04, insgesamt 109 datensatzspezifische IDs. Jede Story besitzt vier boolesche Defektlabels. Mehrere Labels dürfen für dieselbe Story zutreffen. `true` bezeichnet die zu prüfende Defekthypothese, `false` deren Verneinung in diesem Annotationsstand; es ist kein allgemeines Qualitätsurteil über die Story.

Diese Datei ist **nicht** die Komponentenreferenz aus der Vorarbeit. Die Dateien unter `vendor/user-story-extractor/pos_baseline/` annotieren extrahierte Personas, Actions, Entities und Benefits. Sie dienen Camargo da Silvas Extraktionsbewertung und können weder die Qualitätslabels noch eine paarweise Redundanzannotation ersetzen.

## 2. Dokumentierte Kategorien

| Label | Gemeinter Gegenstand | Abgrenzung und Prüfrisiko |
| --- | --- | --- |
| `missing_benefit` | Der Rohtext nennt keinen ausdrücklichen End-/Benefit-Teil. | Kein Urteil über tatsächlichen Geschäftswert. Der Check ist eine Ergänzung zu QUS; ein Benefit ist für QUS-Well-formedness nicht zwingend. |
| `non_atomic` | Der funktionale Anforderungsteil verbindet mehrere trennbare Funktionalitäten, insbesondere durch `and`, `or`, `and/or` oder `/`. | Eine Konjunktion allein genügt nicht; gleichrangige Objekte oder Erläuterungen müssen nicht mehrere Funktionen bedeuten. Eine zusätzliche Handlung im Benefit ist nicht automatisch eine weitere unabhängige Anforderung. Die konjunktionsnahe Operationalisierung kann AQUSA gegenüber Action-Count-Regeln begünstigen. |
| `incomplete_means` | Der funktionale Means-Teil wird im vorhandenen Stand als nicht hinreichend bestimmt bewertet. | Nicht mit QUS-Complete gleichzusetzen. Eine passive Form allein beweist keinen Defekt. Der einzige positive Fall G03_54 ist strittig; siehe Abschnitt 3. Die technische Dangling-Action-Regel prüft lediglich das Fehlen einer eigenen extrahierten Target-Beziehung. |
| `uniqueness` | Der vollständige Rohtext ist mit einer früheren Story desselben Backlogs identisch. | Nur die spätere Wiederholung erhält `true`, hier G03_46. Kein Label für teilweise funktionale Überlappung, Synonymie, Konflikte oder jedes redundante Storypaar. |

Aktueller Bestand positiver Labels: Missing Benefit 6, Non-Atomic 19, Incomplete Means 1, Uniqueness 1. Diese Anzahlen sind keine unabhängige Validierung der Kategorien oder Einzelfälle.

## 3. Strittiger Fall G03_54

**Prüfstatus:** fachlich strittig; keine Bestätigung durch den Betreuer dokumentiert. `incomplete_means=true` bleibt zur Reproduzierbarkeit des vorhandenen Annotationsstands unverändert. Das Beibehalten ist keine fachliche Bestätigung des Labels.

Rohtext:

> As a Staff member, I need to be notified when Geospatial attributes change, so that I can ensure that I am reviewing the permit/application to the most current data and appropriate standards.

Die bisherige Defektzuordnung knüpft an die passive Formulierung „need to be notified“ und einen als unvollständig angesehenen Benachrichtigungsprozess an. Es gibt jedoch eine plausible Gegeninterpretation: Rolle, gewünschte Benachrichtigung und auslösendes Ereignis (Änderung geospatialer Attribute) sind genannt. Eine User Story muss nicht zwingend den technisch ausführenden Akteur oder einen vollständigen Prozessablauf benennen. Passivität oder das Abweichen vom üblichen „I want to“-Muster beweisen daher nicht, dass der Means-Teil fehlt.

Die gespeicherte AQUSA-Ausgabe meldet für G03_54 `well_formed.no_means`. Ein Werkzeugalarm ist aber keine unabhängige Begründung dafür, denselben Text als Ground-Truth-Defekt zu annotieren. Die für die Graphregel angenommene Bedingung „Aktion ohne eigenes Target“ ist zudem nicht identisch mit jeder linguistischen Auslegung von Incomplete Means.

G03_54 fehlt bereits in den übernommenen Extraktionsrecords. Der Neo4j-Check kann diese nicht importierte Story deshalb nicht als Graphalarm ausgeben. Der in der Vollauswertung entstehende False Negative ist ein End-to-End-Auslassungsfall und kein isolierter Nachweis, dass die Cypher-Regel einen vorhandenen Zielgraphen falsch abfragt.

Da G03_54 das einzige positive Label dieser Kategorie ist, wird Incomplete Means **nicht als regulärer Klassifikationsvergleich** ausgewertet. Die Berichte kennzeichnen die Kategorie mit `metrics_applicable=false` und dokumentieren die Alarme für die qualitative Analyse. Ausschließlich zur Rückverfolgbarkeit bleibt unter `historical_annotation_comparison` der ursprüngliche Labelabgleich erhalten (AQUSA TP=1/FP=0/FN=0; Graph TP=0/FP=3/FN=1). Diese Zahlen sind keine belastbaren Leistungskennzahlen dieser Defektklasse.

Eine spätere Entscheidung sollte das zugrunde gelegte fachliche Kriterium, die Begründung und die unabhängige Prüfung dokumentieren. Erst danach wäre eine versionierte Labeländerung mit erneuter Berechnung sämtlicher betroffener Ergebnisse angebracht. Dieser Leitfaden nimmt eine solche Entscheidung nicht vorweg.

## 4. Zuordnung von Rohstories und Graphstories

Der Defektvergleich verwendet `(Backlog, normalisierter Text)` und erhält alle zugehörigen Rohstory-IDs. Nur hierfür werden optionale `#G03#`-/`#G04#`-Präfixe entfernt, die Texte kleingeschrieben, Satzzeichen entfernt und äußere Leerzeichen abgeschnitten. Konzeptnamen und die auf dem unveränderten Text beruhenden Graph-IDs werden dadurch nicht geändert.

Die identischen Rohstories G03_45/G03_46 werden beide auf denselben Turbo-Graphknoten `g03_933c6b73` abgebildet. Ein struktureller Alarm dieses Knotens wird auf beide Referenz-IDs projiziert. AQUSA-Alarme werden über die explizite Storynummer und einen geprüften Textabgleich zugeordnet; der Duplikatalarm bleibt daher G03_46 zugeordnet.

Der Turbo-Input enthält bereits nur 103 Records. Daraus entstehen 103 Storyknoten, die 104 Rohstory-IDs repräsentieren. Fünf Rohstories fehlen schon im Eingabebestand: G03_39, G03_54, G04_05, G04_15, G04_48. Die Ursache dieser Auslassungen lässt sich aus dem vorliegenden Subset allein nicht beweisen. Beim aktuellen Import werden null weitere identische Records zusammengeführt.

Für die Defektevaluation bleiben alle 109 Referenzstories im Auswertungsraum. Unrepräsentierte Stories erhalten keinen Alarm; positive Referenzlabels solcher Stories zählen dadurch als False Negatives. Die Abdeckung wird zusätzlich unter `coverage` berichtet und darf nicht mit fehlerfreier Prüfung verwechselt werden.

## 5. Metriken und Aussagegrenzen

- Precision = `TP / (TP + FP)` und Recall = `TP / (TP + FN)`; bei Nenner null ist der Wert nicht definiert und im JSON `null`.
- F1 = `2*TP / (2*TP + FP + FN)`; ebenfalls `null`, wenn der Nenner null ist.
- Der Missing-Benefit-Check ist in AQUSA v1 nicht implementiert und erhält daher keine regulären Vergleichsmetriken.
- Incomplete Means wird wegen der nicht bestätigten positiven Referenz qualitativ behandelt; der historische Labelabgleich ist kein regulärer P/R/F1-Vergleich.
- Die Importinvariante zur Behandlung identischer Texte ist keine eigenständige Duplikatklassifikation. Ein Graph-Duplikat-F1 wird nicht berechnet.
- Overlap- und Cross-Persona-Ergebnisse sind source-story-gebundene Review-Muster. Für sie liegt hier keine paarweise Ground Truth vor; Klassifikationsmetriken wären deshalb unbegründet.
- Schwellenwerte `Actions >1`, `>2` und `>4` werden auf demselben Sample gegenübergestellt und sind keine extern validierten optimalen Parameter.

Die Originaltexte stammen aus [Dalpiaz (2018)](https://doi.org/10.17632/7zbk8zsd8y.1); die QUS-Begriffe beziehen sich auf [Lucassen et al. (2016)](https://doi.org/10.1007/s00766-016-0250-x). Die Verwendung dieser Quellen macht die arbeitsbezogenen Defektlabels nicht zu Labels der jeweiligen Originalautorinnen und -autoren.

## 6. Nachträgliche Sensitivitätsanalyse zur Atomarität

`annotation_review.json` dokumentiert eine KI-unterstützte Plausibilitätsprüfung aller 19 ursprünglich positiven Atomaritätslabels. Sie erfolgte nach Kenntnis der Werkzeugergebnisse. Sie ist weder unabhängig noch verblindet und bewertet nicht sämtliche ursprünglich negativen Labels neu. Maßgeblich war die Frage, ob der Anforderungsteil mehrere trennbare Funktionen oder lediglich koordinierte Objekte beziehungsweise Aspekte einer Funktion benennt.

Unter dieser Abgrenzung sind G03_55, G04_17, G04_19, G04_35, G04_46, G04_49 und G04_50 mehrdeutig. Die Datei hält auch die Gründe für die zwölf beibehaltenen Interpretationen fest. Das Beibehalten einer Interpretation ist keine unabhängige Bestätigung ihrer Richtigkeit.

`run_annotation_sensitivity.py` prüft bei unveränderten Vorhersagen:

1. Den symmetrischen Ausschluss aller sieben Fälle aus Referenz und Alarmmengen jedes Verfahrens: 102 Rohstories mit zwölf positiven Labels.
2. Alle 128 binären Zuordnungen der sieben Labels auf dem vollständigen Sample. Alle übrigen Labels bleiben fest.

Die F1-Minima und -Maxima in `annotation_sensitivity_results.json` sind Szenariogrenzen, keine Konfidenzintervalle. In allen untersuchten Varianten bleibt AQUSAs F1 über den geprüften Action-Count-Konfigurationen. Dies begrenzt die Empfindlichkeit der beobachteten Rangfolge gegenüber diesen sieben Entscheidungen, behebt aber weder den Baseline-Bias noch mögliche andere Annotationsfehler. Die Originaldatei `ground_truth.json` wird vom Programm nicht verändert.
