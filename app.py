"""Streamlit-Oberfläche des GPX-Trackers.

Start über main.py oder direkt: streamlit run app.py
"""

import html as html_text
import io
import xml.etree.ElementTree as ET
from pathlib import Path

import folium
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import gpx

ORDNER = Path(__file__).resolve().parent
BEISPIELE = ORDNER / "data" / "aktivitaeten"
AUSGABE = ORDNER / "ausgabe"
WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

st.set_page_config(page_title="GPX-Tracker", page_icon="🏃", layout="wide")


@st.cache_data
def lade_beispiele():
    return [gpx.lies(d, d.name) for d in sorted(BEISPIELE.glob("*.gpx"))]


@st.cache_data
def lade_upload(name, inhalt):
    return gpx.lies(io.BytesIO(inhalt), name)


# --- Aktivitäten sammeln ------------------------------------------------------------
with st.sidebar:
    st.header("🏃 Aktivitäten")
    hochgeladen = st.file_uploader("Eigene GPX-Dateien", type="gpx", accept_multiple_files=True)
    mit_beispielen = st.toggle("Synthetische Beispiele anzeigen", value=True)

aktivitaeten, fehler = [], []
if mit_beispielen:
    aktivitaeten += lade_beispiele()
for datei in hochgeladen or []:
    try:
        aktivitaeten.append(lade_upload(datei.name, datei.getvalue()))
    except (ValueError, ET.ParseError) as f:
        fehler.append(f"{datei.name}: {f}")
for f in fehler:
    st.sidebar.error(f)
if not aktivitaeten:
    st.title("🏃 GPX-Tracker")
    st.info("GPX-Dateien hochladen oder die Beispiele einschalten.")
    st.stop()

uebersicht = pd.DataFrame([gpx.kennzahlen(m, p) for m, p in aktivitaeten])
uebersicht = uebersicht.sort_values("start", ascending=False).reset_index(drop=True)

with st.sidebar:
    namen = list(uebersicht["datei"])
    gewaehlt = st.selectbox("Aktivität", namen, format_func=lambda d: uebersicht.set_index("datei").loc[d, "name"])
meta, punkte = next((m, p) for m, p in aktivitaeten if m["datei"] == gewaehlt)
k = uebersicht.set_index("datei").loc[gewaehlt]

st.title(f"🏃 {meta['name']}")
if pd.notna(k["start"]):
    start = k["start"].tz_convert("Europe/Berlin")
    st.caption(f"{meta['typ']} · {WOCHENTAGE[start.weekday()]}, {start:%d.%m.%Y, %H:%M} Uhr · {meta['datei']}")
else:
    st.caption(f"{meta['typ']} · ohne Zeitangaben")
if k["zeitanteil"] == 0:
    st.info("Diese Datei enthält keine Zeitangaben (z. B. eine geplante Route). Strecke, Höhe und Karte "
            "werden angezeigt, Dauer und Tempo nicht.")
elif k["zeitanteil"] < 0.95:
    st.caption(f"Hinweis: Nur {k['zeitanteil']:.0%} der Punkte haben eine Zeitangabe; Dauer und Tempo beruhen auf diesen.")
spalten = st.columns(6)
spalten[0].metric("Strecke", f"{k['strecke_km']:.2f} km")
spalten[1].metric("Dauer", gpx.formatiere_dauer(k.get("dauer_s")))
spalten[2].metric("In Bewegung", gpx.formatiere_dauer(k.get("bewegung_s")),
                  f"−{gpx.formatiere_dauer(k['pause_s'])} Pause" if k.get("pause_s", 0) > 60 else None, delta_color="off")
spalten[3].metric("Tempo", f"{k['tempo_kmh']:.1f} km/h" if pd.notna(k.get("tempo_kmh")) else "–")
spalten[4].metric("Pace", f"{gpx.formatiere_dauer(k['pace_s_km'])} /km" if pd.notna(k["pace_s_km"]) else "–")
spalten[5].metric("Aufstieg", f"{k['aufstieg_m']:.0f} m")

reiter = st.tabs(["🗺️ Karte", "⛰️ Höhenprofil", "⏱️ Kilometerzeiten", "📊 Statistik"])

# --- Karte ---------------------------------------------------------------------------
with reiter[0]:
    koordinaten = punkte[["lat", "lon"]].to_numpy().tolist()
    karte = folium.Map(tiles="OpenStreetMap")
    folium.PolyLine(koordinaten, color="#d6336c", weight=4, opacity=0.85, tooltip=html_text.escape(meta["name"])).add_to(karte)
    folium.Marker(koordinaten[0], tooltip="Start", icon=folium.Icon(color="green", icon="play")).add_to(karte)
    folium.Marker(koordinaten[-1], tooltip="Ziel", icon=folium.Icon(color="red", icon="flag")).add_to(karte)
    for km in range(1, int(k["strecke_km"]) + 1):  # Kilometermarken
        zeile = punkte[punkte["strecke_m"] >= km * 1000].iloc[0]
        folium.CircleMarker((zeile["lat"], zeile["lon"]), radius=9, color="#333", fill=True, fill_color="white",
                            fill_opacity=0.9, tooltip=f"km {km}").add_to(karte)
    karte.fit_bounds([punkte[["lat", "lon"]].min().tolist(), punkte[["lat", "lon"]].max().tolist()])
    html = karte.get_root().render()
    if hasattr(st, "iframe"):  # ab Streamlit 1.5x; ältere Versionen nutzen components.html
        st.iframe(html, height=520)
    else:
        components.html(html, height=520)
    links, rechts = st.columns([1, 3])
    links.download_button("Karte als HTML herunterladen", html.encode("utf-8"),
                          f"{Path(meta['datei']).stem}_karte.html", "text/html")
    if rechts.button("Karte im Ordner ausgabe/ speichern"):
        AUSGABE.mkdir(exist_ok=True)
        ziel = AUSGABE / f"{Path(meta['datei']).stem}_karte.html"
        karte.save(str(ziel))
        rechts.success(f"Gespeichert: {ziel}")
    st.caption("Kartendaten © OpenStreetMap-Mitwirkende")

# --- Höhenprofil ------------------------------------------------------------------------
with reiter[1]:
    if punkte["ele"].isna().all():
        st.info("Die Datei enthält keine Höhenangaben.")
    else:
        fig, ax = plt.subplots(figsize=(12, 4))
        km = punkte["strecke_m"] / 1000
        ax.fill_between(km, punkte["ele"], punkte["ele"].min() - 10, color="#8fbc8f", alpha=0.5)
        ax.plot(km, punkte["ele"], color="#2e7d32")
        ax.set_xlabel("Strecke in km")
        ax.set_ylabel("Höhe in m")
        ax.set_xlim(0, km.iloc[-1])
        ax.grid(alpha=0.3)
        fig.tight_layout()
        st.pyplot(fig)
        s = st.columns(4)
        s[0].metric("Aufstieg", f"{k['aufstieg_m']:.0f} m")
        s[1].metric("Abstieg", f"{k['abstieg_m']:.0f} m")
        s[2].metric("Höchster Punkt", f"{k['hoechster_m']:.0f} m")
        s[3].metric("Tiefster Punkt", f"{k['tiefster_m']:.0f} m")
        st.caption(f"Höhenänderungen unter {gpx.HOEHEN_SCHWELLE_M} m werden als GPS-Rauschen ignoriert.")

# --- Kilometerzeiten ----------------------------------------------------------------------
with reiter[2]:
    zeiten = gpx.kilometerzeiten(punkte)
    if not zeiten:
        st.info("Keine Zeitangaben oder kürzer als ein Kilometer.")
    else:
        fig, ax = plt.subplots(figsize=(12, 3.8))
        mittel = sum(zeiten) / len(zeiten)
        farben = ["#2e7d32" if z <= mittel else "#c62828" for z in zeiten]
        ax.bar(range(1, len(zeiten) + 1), [z / 60 for z in zeiten], color=farben)
        ax.axhline(mittel / 60, color="gray", linestyle="--", label=f"Mittel {gpx.formatiere_dauer(mittel)} min/km")
        ax.set_xlabel("Kilometer")
        ax.set_ylabel("Minuten")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        st.pyplot(fig)
        st.caption("Grün: schneller als der Durchschnitt, rot: langsamer. Pausen sind in den Kilometerzeiten enthalten.")

# --- Statistik über alle Aktivitäten -------------------------------------------------------
with reiter[3]:
    tabelle = uebersicht.assign(
        Datum=uebersicht["start"].dt.strftime("%d.%m.%Y"),
        Dauer=uebersicht["dauer_s"].map(gpx.formatiere_dauer),
        Pace=uebersicht["pace_s_km"].map(gpx.formatiere_dauer))
    st.dataframe(tabelle[["Datum", "name", "typ", "strecke_km", "Dauer", "tempo_kmh", "Pace", "aufstieg_m"]],
                 hide_index=True, width="stretch",
                 column_config={"name": "Aktivität", "typ": "Typ",
                                "strecke_km": st.column_config.NumberColumn("Strecke (km)", format="%.2f"),
                                "tempo_kmh": st.column_config.NumberColumn("Tempo (km/h)", format="%.1f"),
                                "aufstieg_m": st.column_config.NumberColumn("Aufstieg (m)", format="%.0f")})

    zeitraum = st.radio("Zusammenfassen nach", ["Woche", "Monat"], horizontal=True)
    mit_zeit = uebersicht.dropna(subset=["start"]).set_index("start")
    if mit_zeit.empty:
        st.info("Keine Aktivität mit Zeitangaben – Wochen- und Monatsstatistik nicht möglich.")
    else:
        regel = "W-MON" if zeitraum == "Woche" else "MS"
        summen = mit_zeit.groupby("typ").resample(regel)[["strecke_km", "aufstieg_m"]].sum().reset_index()
        pivot = summen.pivot_table(index="start", columns="typ", values="strecke_km", fill_value=0)
        fig, ax = plt.subplots(figsize=(12, 3.8))
        beschriftung = [f"KW {d.isocalendar().week}" if zeitraum == "Woche" else f"{d:%m/%Y}" for d in pivot.index]
        unten = None
        for typ in pivot.columns:
            ax.bar(beschriftung, pivot[typ], bottom=unten, label=typ)
            unten = pivot[typ] if unten is None else unten + pivot[typ]
        ax.set_ylabel("Strecke in km")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        st.pyplot(fig)

    st.subheader("🏆 Persönliche Bestleistungen")
    beste = []
    for distanz, titel in ((1000, "1 km"), (5000, "5 km"), (10000, "10 km")):
        kandidaten = [(gpx.beste_zeit(p, distanz), m["name"]) for m, p in aktivitaeten]
        kandidaten = [c for c in kandidaten if c[0] is not None]
        if kandidaten:
            zeit, name = min(kandidaten)
            beste.append((f"Schnellste {titel}", gpx.formatiere_dauer(zeit), name))
    laengste = uebersicht.loc[uebersicht["strecke_km"].idxmax()]
    beste.append(("Längste Strecke", f"{laengste['strecke_km']:.2f} km", laengste["name"]))
    hoechste = uebersicht.loc[uebersicht["aufstieg_m"].idxmax()]
    beste.append(("Meiste Höhenmeter", f"{hoechste['aufstieg_m']:.0f} m", hoechste["name"]))
    spalten = st.columns(len(beste))
    for spalte, (titel, wert, name) in zip(spalten, beste):
        spalte.metric(titel, wert)
        spalte.caption(name)
