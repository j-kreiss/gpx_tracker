# 14. GPX-Tracker

Wertet Läufe und Wanderungen aus GPX-Dateien im Browser aus: Kennzahlen, interaktive Karte, Höhenprofil, Kilometerzeiten und Statistik über alle Aktivitäten.

**Oberfläche:** Streamlit (Browser)

## Funktionen der Ausgangsversion

- GPX-Dateien lesen (auch hochladen), Strecke mit der Haversine-Formel, Dauer, Bewegungszeit ohne Pausen, Tempo und Pace
- Höhenprofil als Diagramm, Auf- und Abstieg mit Rauschfilter
- Strecke auf einer interaktiven folium-Karte, als HTML speicherbar
- Mehrere Aktivitäten: Wochen- und Monatsstatistik, persönliche Bestleistungen (schnellste 1/5/10 km, längste Strecke, meiste Höhenmeter)

## Installation und Start

Voraussetzung: Python 3.12 (vorgegeben in `.python-version`). Pakete: streamlit, pandas, matplotlib, folium, numpy.

```bash
python -m venv .venv
# virtuelle Umgebung aktivieren (Befehl je nach Betriebssystem)
pip install -r requirements.txt
python main.py
```

Aus dem Hauptordner des Repositorys: `python start_14_gpx_tracker.py` – die Oberfläche öffnet sich im Browser, beenden mit Strg+C im Terminal.

## Bedienung

1. Eigene GPX-Dateien hochladen oder die zwölf synthetischen Beispiele nutzen; Aktivität in der Seitenleiste wählen.
2. Reiter „Karte“: Start, Ziel und Kilometermarken; „Karte im Ordner ausgabe/ speichern“.
3. Reiter „Statistik“: Übersicht, Summen je Woche oder Monat, Bestleistungen.

## Projektstruktur

```
main.py                                   startet Streamlit
app.py                                    Streamlit-Oberfläche
gpx.py                                    GPX lesen, Haversine, Höhenmeter, Pausen, Bestzeiten (ohne Oberfläche)
erzeuge_testdaten.py                      erzeugt die synthetischen Aktivitäten
data/aktivitaeten/                        zwölf synthetische GPX-Dateien
requirements.txt                          Abhängigkeiten
```

## Datenquellen und Lizenzen

| Quelle | Wofür | Lizenz oder Nutzungsbedingungen |
| --- | --- | --- |
| data/aktivitaeten/*.gpx | Läufe und Wanderungen | synthetisch, keine echten Spuren |
| OpenStreetMap über folium | Kartenkacheln | © OpenStreetMap-Mitwirkende, ODbL |

## Bekannte Einschränkungen

- Pausen (langsamer als 1,8 km/h) werden aus der Bewegungszeit herausgerechnet; die Kilometerzeiten enthalten sie.
- Die Karte braucht Internet (Leaflet und Kartenkacheln).
- Gelesen werden GPX 1.0 und 1.1, Track- und Routenpunkte. Dateien ohne Zeitangaben (geplante Routen) zeigen Strecke, Höhe und Karte, aber keine Dauer; fehlen Zeiten nur an einzelnen Punkten, beruhen Dauer und Tempo auf den übrigen.
