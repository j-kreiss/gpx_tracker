"""GPX-Dateien lesen und auswerten (ohne Oberfläche).

Strecke mit der Haversine-Formel, Höhenmeter mit Glättung, Pausen werden
an langsamen Abschnitten erkannt und aus der Bewegungszeit herausgerechnet.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

ERDRADIUS_M = 6_371_000
PAUSE_TEMPO_MS = 0.5        # langsamer als 1,8 km/h gilt als Pause
HOEHEN_SCHWELLE_M = 3       # kleinere Schwankungen zählen nicht als Höhenmeter (GPS-Rauschen)


def haversine(lat1, lon1, lat2, lon2):
    """Abstand in Metern; funktioniert auch mit numpy-Arrays."""
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((phi2 - phi1) / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * ERDRADIUS_M * np.arcsin(np.sqrt(a))


def lies(quelle, dateiname=None):
    """Liest eine GPX-Datei (Pfad oder Datei-Objekt).

    Gibt (Metadaten, DataFrame) zurück. Der DataFrame hat die Spalten
    lat, lon, ele, zeit, abstand_m (zum Vorgänger), strecke_m (kumuliert).
    """
    wurzel = ET.parse(quelle).getroot()
    # {*} passt auf jeden Namensraum: GPX 1.1, GPX 1.0 und Dateien ohne Namensraum.
    # Geplante Routen enthalten oft Routenpunkte (rtept) statt Trackpunkten (trkpt).
    knoten = list(wurzel.iterfind(".//{*}trkpt")) or list(wurzel.iterfind(".//{*}rtept"))
    zeilen = []
    for p in knoten:
        zeit = p.findtext("{*}time")
        ele = p.findtext("{*}ele")
        try:
            hoehe = float(ele) if ele else np.nan
        except ValueError:
            hoehe = np.nan
        zeilen.append((float(p.get("lat")), float(p.get("lon")), hoehe, zeit))
    if len(zeilen) < 2:
        raise ValueError("Die Datei enthält zu wenige Track- oder Routenpunkte.")
    punkte = pd.DataFrame(zeilen, columns=["lat", "lon", "ele", "zeit"])
    # format="ISO8601" liest jede ISO-Schreibweise einzeln (mit/ohne Millisekunden, Z oder +02:00);
    # ohne diese Angabe leitet pandas das Format aus dem ersten Wert ab und verwirft abweichende Werte
    punkte["zeit"] = pd.to_datetime(punkte["zeit"], utc=True, errors="coerce", format="ISO8601")
    abstand = haversine(punkte["lat"].shift(), punkte["lon"].shift(), punkte["lat"], punkte["lon"])
    punkte["abstand_m"] = abstand.fillna(0)
    punkte["strecke_m"] = punkte["abstand_m"].cumsum()
    name = (wurzel.findtext(".//{*}trk/{*}name") or wurzel.findtext(".//{*}rte/{*}name")
            or Path(dateiname or str(quelle)).stem)
    typ = wurzel.findtext(".//{*}trk/{*}type") or "Aktivität"
    return {"name": name, "typ": typ, "datei": Path(dateiname or str(quelle)).name}, punkte


def hoehenmeter(ele):
    """Auf- und Abstieg; nur Änderungen über der Schwelle zählen (Hysterese gegen Rauschen)."""
    werte = ele.dropna().to_numpy()
    if len(werte) == 0:
        return 0.0, 0.0
    auf = ab = 0.0
    bezug = werte[0]
    for wert in werte[1:]:
        if wert - bezug >= HOEHEN_SCHWELLE_M:
            auf += wert - bezug
            bezug = wert
        elif bezug - wert >= HOEHEN_SCHWELLE_M:
            ab += bezug - wert
            bezug = wert
    return auf, ab


def mit_zeit(punkte):
    """Nur die Punkte mit gültiger Zeit, zeitlich sortiert; leer, wenn es weniger als zwei sind.

    Manche Dateien haben gar keine Zeiten (geplante Routen), manche nur an einzelnen Punkten.
    Strecke und Höhe werden aus allen Punkten berechnet, Dauer und Tempo aus diesen.
    """
    zeitpunkte = punkte.dropna(subset=["zeit"])
    zeitpunkte = zeitpunkte[zeitpunkte["zeit"].diff().dt.total_seconds().fillna(0) >= 0]  # Rücksprünge verwerfen
    return zeitpunkte if len(zeitpunkte) >= 2 else zeitpunkte.iloc[0:0]


def kennzahlen(meta, punkte):
    """Kennzahlen einer Aktivität. Ohne Zeitangaben sind Dauer, Tempo und Pace NaN."""
    strecke = punkte["strecke_m"].iloc[-1]
    auf, ab = hoehenmeter(punkte["ele"])
    ergebnis = {**meta, "strecke_km": strecke / 1000, "aufstieg_m": auf, "abstieg_m": ab,
                "hoechster_m": punkte["ele"].max(), "tiefster_m": punkte["ele"].min(),
                "start": pd.NaT, "dauer_s": np.nan, "bewegung_s": np.nan, "pause_s": np.nan,
                "tempo_kmh": np.nan, "pace_s_km": np.nan, "zeitanteil": 0.0}
    zeitpunkte = mit_zeit(punkte)
    if zeitpunkte.empty:
        return ergebnis
    sekunden = zeitpunkte["zeit"].diff().dt.total_seconds().fillna(0)
    meter = zeitpunkte["strecke_m"].diff().fillna(0)
    tempo = meter / sekunden.replace(0, np.nan)
    pause = (tempo < PAUSE_TEMPO_MS) & (sekunden > 0)
    gesamt_s = sekunden.sum()
    bewegung_s = sekunden[~pause].sum()
    ergebnis.update(start=zeitpunkte["zeit"].iloc[0], dauer_s=gesamt_s, bewegung_s=bewegung_s,
                    pause_s=gesamt_s - bewegung_s,
                    tempo_kmh=strecke / bewegung_s * 3.6 if bewegung_s else np.nan,
                    pace_s_km=bewegung_s / (strecke / 1000) if bewegung_s and strecke else np.nan,
                    zeitanteil=len(zeitpunkte) / len(punkte))
    return ergebnis


def kilometerzeiten(punkte):
    """Zeit je voller Kilometer (Sekunden) als Liste – Pausen sind enthalten."""
    zeitpunkte = mit_zeit(punkte)
    if zeitpunkte.empty:
        return []
    zeiten = []
    for km in range(1, int(zeitpunkte["strecke_m"].iloc[-1] // 1000) + 1):
        ende = zeitpunkte["zeit"][zeitpunkte["strecke_m"] >= km * 1000].iloc[0]
        start = zeitpunkte["zeit"][zeitpunkte["strecke_m"] >= (km - 1) * 1000].iloc[0]
        zeiten.append((ende - start).total_seconds())
    return zeiten


def beste_zeit(punkte, distanz_m):
    """Schnellste Zeit (s) für ein beliebiges Teilstück der Länge distanz_m, sonst None."""
    zeitpunkte = mit_zeit(punkte)
    if zeitpunkte.empty or zeitpunkte["strecke_m"].iloc[-1] - zeitpunkte["strecke_m"].iloc[0] < distanz_m:
        return None
    strecke = zeitpunkte["strecke_m"].to_numpy()
    sekunden = (zeitpunkte["zeit"] - zeitpunkte["zeit"].iloc[0]).dt.total_seconds().to_numpy()
    ende = np.searchsorted(strecke, strecke + distanz_m)  # erster Punkt nach distanz_m ab jedem Startpunkt
    gueltig = ende < len(strecke)
    if not gueltig.any():
        return None
    return float(np.min(sekunden[ende[gueltig]] - sekunden[gueltig]))


def formatiere_dauer(sekunden):
    if sekunden is None or pd.isna(sekunden):
        return "–"
    s = int(round(sekunden))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"
