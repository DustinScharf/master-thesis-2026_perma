# Herkunft und Reproduzierbarkeitsgrenze der AQUSA-Ausgaben

Die beiden Textdateien in diesem Verzeichnis sind archivierte AQUSA-Analyseausgaben
zu G03 und G04. Sie werden für den Vergleich unverändert eingelesen. Der aktuelle
Replikationsablauf führt AQUSA selbst nicht erneut aus.

Ein exakter Software-Commit, die vollständige ursprüngliche Laufumgebung und der
damalige Aufruf sind nicht dokumentiert. Die Bezeichnung AQUSA v1 in der Arbeit
ist daher kein vollständiger Versionsnachweis für eine erneut installierbare
Baseline. Aus den gespeicherten Alarmen allein lässt sich dieser Nachweis nicht
rekonstruieren.

`evaluation_report.py` prüft die expliziten Story-Nummern gegen die Referenztexte
und berechnet die Kennzahlen aus den archivierten Alarmen. Das Manifest sichert
die ausgelieferten Ausgabebytes. Diese Prüfungen machen den Ergebnisabgleich
reproduzierbar, nicht die ursprüngliche Erzeugung der AQUSA-Ausgaben.
