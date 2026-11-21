"""GPX-Tracker mit Höhenprofil, Karte und Statistik über mehrere Aktivitäten (Streamlit-Oberfläche).

Start: python main.py
Startet die Streamlit-Oberfläche (app.py) und öffnet sie im Browser.
Beenden mit Strg+C im Terminal.
"""

import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

APP = Path(__file__).resolve().parent / "app.py"
PORT = 8514


def main():
    adresse = f"http://localhost:{PORT}"
    print(f"Oberfläche: {adresse}  (Beenden mit Strg+C)")
    # headless=true verhindert die E-Mail-Abfrage beim ersten Start; den Browser öffnen wir selbst
    threading.Timer(2.5, webbrowser.open, args=[adresse]).start()
    befehl = [sys.executable, "-m", "streamlit", "run", str(APP),
              "--server.headless", "true", "--server.port", str(PORT), "--server.address", "localhost",
              "--browser.gatherUsageStats", "false"]
    try:
        sys.exit(subprocess.call(befehl, cwd=APP.parent))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
