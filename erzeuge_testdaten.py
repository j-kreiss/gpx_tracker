"""Erzeugt synthetische GPX-Dateien (data/aktivitaeten/*.gpx).

Zwölf erfundene Läufe und Wanderungen über acht Wochen auf verschiedenen
Rundkursen, mit Höhenprofil, leichtem GPS-Rauschen und einer Pause bei
den Wanderungen. Keine echten GPS-Spuren, kein echter Wohnort.
"""

import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ORDNER = Path(__file__).resolve().parent / "data" / "aktivitaeten"

# Name, Mittelpunkt, Halbachsen (m), Höhe (Basis, Amplitude), Typ
STRECKEN = [
    ("Seerunde", (51.3760, 7.4950), (1200, 700), (180, 25), "Lauf"),
    ("Waldschleife", (51.3420, 7.5300), (1800, 1100), (260, 60), "Lauf"),
    ("Kammweg", (51.3050, 7.6100), (3500, 2200), (380, 140), "Wanderung"),
]


def gpx_punkte(mitte, achsen, hoehe, start, tempo_ms, takt_s, pause_bei=None, pause_s=0):
    umfang = math.pi * (3 * sum(achsen) - math.sqrt((3 * achsen[0] + achsen[1]) * (achsen[0] + 3 * achsen[1])))
    anzahl = int(umfang / (tempo_ms * takt_s))
    m_lat = 111_320
    m_lon = 111_320 * math.cos(math.radians(mitte[0]))
    zeit = start
    punkte = []
    for i in range(anzahl + 1):
        w = 2 * math.pi * i / anzahl
        ost = achsen[0] * math.cos(w) + random.gauss(0, 2.5)
        nord = achsen[1] * math.sin(w) + random.gauss(0, 2.5)
        ele = hoehe[0] + hoehe[1] * (math.sin(w * 2) + 0.4 * math.sin(w * 5)) / 1.4 + random.gauss(0, 0.6)
        punkte.append((mitte[0] + nord / m_lat, mitte[1] + ost / m_lon, ele, zeit))
        # bergauf langsamer, bergab schneller
        steigung = math.cos(w * 2) * 2 + math.cos(w * 5)
        zeit += timedelta(seconds=takt_s * (1 + 0.08 * steigung) * random.uniform(0.95, 1.05))
        if pause_bei and i == int(anzahl * pause_bei):
            zeit += timedelta(seconds=pause_s)
    return punkte


def schreibe(datei, name, typ, punkte):
    zeilen = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<gpx version="1.1" creator="PKI-Testdaten" xmlns="http://www.topografix.com/GPX/1/1">',
              f"  <trk><name>{name}</name><type>{typ}</type><trkseg>"]
    for lat, lon, ele, zeit in punkte:
        zeilen.append(f'    <trkpt lat="{lat:.6f}" lon="{lon:.6f}"><ele>{ele:.1f}</ele>'
                      f'<time>{zeit:%Y-%m-%dT%H:%M:%SZ}</time></trkpt>')
    zeilen += ["  </trkseg></trk>", "</gpx>", ""]
    datei.write_text("\n".join(zeilen), encoding="utf-8")


def main():
    random.seed(7)
    ORDNER.mkdir(parents=True, exist_ok=True)
    for alt in ORDNER.glob("*.gpx"):
        alt.unlink()
    beginn = datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc)
    for nr in range(12):
        tag = beginn + timedelta(days=nr * 4 + random.randint(0, 2), hours=random.randint(0, 9))
        if nr % 4 == 3:
            name, mitte, achsen, hoehe, typ = STRECKEN[2]
            punkte = gpx_punkte(mitte, achsen, hoehe, tag, random.uniform(1.25, 1.45), 10, pause_bei=0.5, pause_s=1200)
        else:
            name, mitte, achsen, hoehe, typ = STRECKEN[nr % 2]
            # mit der Zeit etwas schneller: Trainingseffekt
            punkte = gpx_punkte(mitte, achsen, hoehe, tag, 2.6 + nr * 0.04 + random.uniform(-0.1, 0.1), 5)
        datei = ORDNER / f"{tag:%Y-%m-%d}_{name.lower()}.gpx"
        schreibe(datei, f"{name} {tag:%d.%m.}", typ, punkte)
        print(f"geschrieben: {datei.name}")


if __name__ == "__main__":
    main()
