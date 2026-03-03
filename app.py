"""
Military Aircraft Monitor – Flask Backend

Filter-Strategie (Priorität):
  1. CSV-Datenbank (aircraft.csv.gz) – flags & 1 = MILITARY  ← Hauptquelle
  2. ICAO-HEX-Bereichs-Fallback – greift wenn DB noch nicht geladen
  3. Squawk 7700 – Notfall, immer anzeigen

Die CSV wird beim Start geladen und alle DB_RELOAD_HOURS Stunden automatisch
neu heruntergeladen. Die Datei liegt unter DB_PATH (Standard: /app/aircraft.csv.gz).
"""

import gzip
import csv
import threading
import time
import logging
import os
from flask import Flask, jsonify, send_from_directory, request, Response
from functools import wraps
import requests as http_requests

log = logging.getLogger(__name__)
app = Flask(__name__, static_folder=".", static_url_path="")

# ── Config ────────────────────────────────────────────────────────────────────
USER             = os.environ.get("AUTH_USER", "admin")
PASSWORD         = os.environ.get("AUTH_PASS", "milcom2026")
PI_IP            = os.environ.get("PI_IP", "172.16.16.35")
DATA_URL         = f"http://{PI_IP}/airplanes/data/aircraft.json"
RECEIVER_URL     = f"http://{PI_IP}/airplanes/data/receiver.json"

# DB path: lives in the same directory as app.py (i.e. /app/ in Docker)
DB_PATH          = os.path.join(os.path.dirname(__file__), "aircraft.csv.gz")
DB_URL           = "https://raw.githubusercontent.com/wiedehopf/tar1090-db/csv/aircraft.csv.gz"
DB_RELOAD_HOURS  = 12   # auto-refresh interval


# ── Auth ──────────────────────────────────────────────────────────────────────
def require_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != USER or auth.password != PASSWORD:
            return Response(
                "⛔ Authentication required.",
                401,
                {"WWW-Authenticate": 'Basic realm="MILCOM Dashboard"'},
            )
        return f(*args, **kwargs)
    return decorated


# ── Aircraft DB (in-memory) ───────────────────────────────────────────────────
# MILITARY_HEXES: set of uppercase ICAO hex codes with military flag (bit 0)
# AC_TYPE_MAP:    dict hex → type code string  (e.g. "C17", "EUFI")
_db_lock        = threading.Lock()
MILITARY_HEXES  = set()    # uppercase, e.g. "3F6A05"
AC_TYPE_MAP     = {}       # uppercase hex → type string

DB_STATUS = {
    "loaded_at":  None,
    "count":      0,
    "error":      None,
}


def _download_db() -> bool:
    """Download aircraft.csv.gz from GitHub. Returns True on success."""
    try:
        log.info("Downloading aircraft.csv.gz …")
        r = http_requests.get(DB_URL, timeout=30, stream=True)
        r.raise_for_status()
        with open(DB_PATH, "wb") as fh:
            for chunk in r.iter_content(65536):
                fh.write(chunk)
        log.info("aircraft.csv.gz downloaded (%d bytes)", os.path.getsize(DB_PATH))
        return True
    except Exception as exc:
        log.error("DB download failed: %s", exc)
        return False


def load_military_db(download_if_missing: bool = True) -> int:
    """
    Parse aircraft.csv.gz and rebuild MILITARY_HEXES + AC_TYPE_MAP.

    tar1090-db CSV format (semicolon-separated, no header):
      col 0: icao hex  (lowercase, 6 chars)
      col 1: registration  (e.g. "31+03")
      col 2: type code     (generic type code, e.g. "C17")
      col 3: icao type code(specific model, e.g. "C17")
      col 4: flags         (int; bit 0=military, bit 1=interesting, bit 3=LADD)

    We use col 4 for flags as per current tar1090-db format.
    """
    global MILITARY_HEXES, AC_TYPE_MAP

    if not os.path.exists(DB_PATH):
        if download_if_missing:
            if not _download_db():
                DB_STATUS["error"] = "DB not found and download failed"
                return 0
        else:
            DB_STATUS["error"] = "DB file not found"
            return 0

    new_military = set()
    new_types    = {}
    count        = 0

    try:
        with gzip.open(DB_PATH, "rt", encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(fh, delimiter=";")
            for row in reader:
                if len(row) < 4:
                    continue
                hex_upper = row[0].strip().upper()
                if not hex_upper:
                    continue

                # Type code (col 2)
                t = row[2].strip()
                if t:
                    new_types[hex_upper] = t

                # Flags stehen in tar1090-db/csv immer in Spalte 4 (row[4])
                try:
                    flags = int(row[4]) if len(row) > 4 else 0
                except (ValueError, IndexError):
                    continue

                if flags & 1:          # bit 0 = military
                    new_military.add(hex_upper)
                    count += 1

        with _db_lock:
            MILITARY_HEXES = new_military
            AC_TYPE_MAP    = new_types

        DB_STATUS["loaded_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        DB_STATUS["count"]     = count
        DB_STATUS["error"]     = None
        log.info("DB loaded: %d military ICAOs, %d type entries", count, len(new_types))
        return count

    except Exception as exc:
        DB_STATUS["error"] = str(exc)
        log.error("DB parse error: %s", exc)
        return 0


def _db_refresh_loop():
    """Background thread: reload DB every DB_RELOAD_HOURS hours."""
    while True:
        time.sleep(DB_RELOAD_HOURS * 3600)
        log.info("Auto-refreshing aircraft DB …")
        _download_db()
        load_military_db(download_if_missing=False)


# ── ICAO HEX range fallback (used when DB hasn't loaded yet) ─────────────────
MILITARY_HEX_RANGES = [
    (0xAE0000, 0xAFFFFF), (0x43C000, 0x43CFFF),
    (0x3E8000, 0x3E8FFF), (0x3FC800, 0x3FCFFF),
    (0x3A0000, 0x3A0FFF), (0x33FF00, 0x33FFFF),
    (0x478100, 0x4781FF), (0x480C00, 0x480CFF),
    (0x448000, 0x448FFF), (0x340000, 0x340FFF),
    (0x4B8000, 0x4BFFFF), (0x4A0000, 0x4AFFFF),
    (0x7CF800, 0x7CFFFF), (0xC0CDF9, 0xC0FFFF),
    (0x840000, 0x87FFFF), (0x710000, 0x71FFFF),
    (0x150000, 0x15FFFF),
]


def _hex_in_range(hex_code: str) -> bool:
    try:
        v = int(hex_code, 16)
    except ValueError:
        return False
    return any(lo <= v <= hi for lo, hi in MILITARY_HEX_RANGES)


# ── Filter + Type logic ───────────────────────────────────────────────────────
def _is_military(ac: dict) -> bool:
    """
    Three-tier filter (OR logic – all checks run, any match wins):
      1. Squawk 7700    → emergency, always show
      2. CSV DB lookup  → precise match from tar1090-db (bit 0 = military)
      3. ICAO HEX range → reliable broad catch, always active as safety net
    """
    squawk    = str(ac.get("squawk") or "").strip()
    hex_upper = (ac.get("hex") or "").strip().upper()

    # 1) Emergency
    if squawk == "7700":
        return True

    # 2) CSV DB lookup (when populated)
    with _db_lock:
        if hex_upper in MILITARY_HEXES:
            return True

    # 3) HEX range – always runs as safety net, regardless of CSV state
    return _hex_in_range(hex_upper.lower())


def _identify_type(ac: dict) -> str:
    """
    Type string priority:
      1. CSV DB type code  (most accurate, e.g. "C17", "EUFI", "A400")
      2. 't' field from live JSON  (readsb enrichment when available)
      3. Generic 'MILITARY'
    """
    hex_upper = (ac.get("hex") or "").strip().upper()
    t_live    = (ac.get("t")   or "").strip()

    with _db_lock:
        db_type = AC_TYPE_MAP.get(hex_upper, "")

    return db_type or t_live or "MILITARY"


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
@require_auth
def index():
    return send_from_directory(".", "index.html")


@app.route("/fetch")
@require_auth
def fetch_data():
    try:
        resp = http_requests.get(DATA_URL, timeout=4)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return jsonify({"error": str(exc), "aircraft": [], "now": 0}), 502

    receiver = {}
    try:
        r = http_requests.get(RECEIVER_URL, timeout=2)
        r.raise_for_status()
        rdata = r.json()
        receiver = {"lat": rdata.get("lat"), "lon": rdata.get("lon")}
    except Exception:
        pass

    all_aircraft = data.get("aircraft", [])
    military = []
    for ac in all_aircraft:
        if _is_military(ac):
            ac["_type"] = _identify_type(ac)
            ac["_mil"]  = True
            military.append(ac)

    return jsonify({
        "now":            data.get("now", 0),
        "total":          len(all_aircraft),
        "military_count": len(military),
        "aircraft":       military,
        "receiver":       receiver,
        "db_status":      DB_STATUS,
    })


@app.route("/db-debug")
@require_auth
def db_debug():
    """Return first 10 raw CSV rows so we can verify the column format."""
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "DB file not found"}), 404
    rows = []
    try:
        with gzip.open(DB_PATH, "rt", encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(fh, delimiter=";")
            for i, row in enumerate(reader):
                if i >= 10:
                    break
                rows.append(row)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"sample_rows": rows, "col_explanation": "0=icao, 1=reg, 2=type, 3=icao_type, 4=flags"})


@app.route("/db-status")
@require_auth
def db_status():
    """Quick endpoint to check DB load status."""
    with _db_lock:
        mil_count = len(MILITARY_HEXES)
    return jsonify({**DB_STATUS, "military_hexes_loaded": mil_count})


@app.route("/db-reload", methods=["POST"])
@require_auth
def db_reload():
    """Manual DB reload trigger (POST /db-reload)."""
    threading.Thread(target=lambda: (
        _download_db(), load_military_db(download_if_missing=False)
    ), daemon=True).start()
    return jsonify({"status": "reload started"})


# ── Startup ───────────────────────────────────────────────────────────────────
def _startup():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    log.info("Loading aircraft DB at startup …")
    # Load in background so Flask starts instantly
    t = threading.Thread(target=load_military_db, kwargs={"download_if_missing": True},
                         daemon=True)
    t.start()

    # Start auto-refresh loop
    threading.Thread(target=_db_refresh_loop, daemon=True).start()


_startup()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
