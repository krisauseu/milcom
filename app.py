"""
Military Aircraft Monitor – Flask Backend
Fetches ADS-B data from a local SkyAware receiver and filters for military traffic.
Provides aircraft type identification via HEX codes and callsign patterns.
"""

from flask import Flask, jsonify, send_from_directory, request, Response
from functools import wraps
import requests, os

app = Flask(__name__, static_folder=".", static_url_path="")

# ── Basic Auth credentials (override via env vars) ──────────────────────────
USER     = os.environ.get("AUTH_USER", "admin")
PASSWORD = os.environ.get("AUTH_PASS", "milcom2026")


def require_auth(f):
    """Decorator that enforces HTTP Basic Auth on a route."""
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

# ── Data source (override PI_IP via env var) ─────────────────────────────────
PI_IP        = os.environ.get("PI_IP", "172.16.16.35")
DATA_URL     = f"http://{PI_IP}/skyaware/data/aircraft.json"
RECEIVER_URL = f"http://{PI_IP}/skyaware/data/receiver.json"

# ── Stricter Military Filter (Callsign Prefixes) ─────────────────────────────
# Updated list based on user request for "pure MilCom display"
CALLSIGN_ROLES = {
    # US Air Force / Navy / NATO
    "RCH":   "USAF Reach",
    "C5":    "USAF C-5",
    "C17":   "USAF C-17",
    "C130":  "USAF C-130",
    "CNV":   "US Navy",
    "NATO":  "NATO AWACS",
    "MAGIC": "AWACS",
    
    # German Air Force / Navy
    "GAF":   "German AF",
    "GNY":   "German Navy",
    
    # UK RAF
    "RRR":   "RAF (Ascot)",
    "ASCOT": "RAF (Ascot)",
    
    # Other NATO Partners
    "BAF":   "Belgian AF",
    "NAF":   "Netherlands AF",
    "IAM":   "Italian AF",
    "AME":   "French AF",
    "FAF":   "French AF",
    "HUAF":  "Hungarian AF",
    "CZE":   "Czech AF",
    "POL":   "Polish AF",
    "HAF":   "Hellenic AF",
    
    # Tankers
    "LAGR":  "Tanker",
    "NCHO":  "Tanker",
    "QID":   "Tanker",
    "GOLD":  "Tanker",
    "TEX":   "Tanker",
    "TARTN": "Tanker",
    
    # Special Ops / ISR
    "DUKE":  "Special Ops",
    "VADER": "Special Ops",
    "JAKE":  "ISR",
    "FORTE": "ISR / RQ-4",
}

MILITARY_CALLSIGN_PREFIXES = tuple(CALLSIGN_ROLES.keys())

# ── Known HEX → specific airframe mapping ──────────────────────────────────
# Direct ICAO hex codes for known military airframes
HEX_AIRCRAFT_DB = {
    # US (AE____) – common C-17s, C-5s, KC-135s
    "ae0243": "C-17 Globemaster III",
    "ae059d": "C-17 Globemaster III",
    "ae01c6": "C-17 Globemaster III",
    "ae044c": "C-5M Super Galaxy",
    "ae0415": "C-5M Super Galaxy",
    "ae5a4a": "KC-135 Stratotanker",
    "ae5a4b": "KC-135 Stratotanker",
    "ae5a4c": "KC-135 Stratotanker",
    "ae68a4": "KC-46A Pegasus",
    "ae68a5": "KC-46A Pegasus",
    "ae1493": "KC-10 Extender",
    "ae222a": "RC-135W Rivet Joint",
    "ae222b": "RC-135V Rivet Joint",
    "ae222c": "RC-135U Combat Sent",
    "ae2c2a": "E-6B Mercury",
    "adf7c7": "RQ-4B Global Hawk",
    "adf7c8": "RQ-4B Global Hawk",
    "ae0168": "C-130J Hercules",
    "ae0169": "C-130J Hercules",
    "ae4843": "P-8A Poseidon",
    "ae6850": "E-8C JSTARS",
    # German AF (3E8___, 3F____)
    "3e8171": "A400M Atlas (GAF)",
    "3e8172": "A400M Atlas (GAF)",
    "3e8173": "A400M Atlas (GAF)",
    "3e8174": "A400M Atlas (GAF)",
    "3e8175": "A400M Atlas (GAF)",
    "3e8176": "A400M Atlas (GAF)",
    "3fc820": "A400M Atlas (GAF)",
    "3fc825": "A400M Atlas (GAF)",
    "3fc82a": "A400M Atlas (GAF)",
    "3fc82e": "Eurofighter (GAF)",
    "3fc82f": "Eurofighter (GAF)",
    "3fc830": "Eurofighter (GAF)",
    "3e2334": "CH-53G (GAF)",
    "3e2335": "CH-53G (GAF)",
    "3eab00": "A321 (GAF VIP)",
    "3eab01": "A340 (GAF VIP)",
    # UK RAF (43C___)
    "43c2c1": "E-3D Sentry (AWACS)",
    "43c2c2": "E-3D Sentry (AWACS)",
    "43c6ce": "RC-135W Airseeker",
    "43c6cf": "Shadow R1",
    "43c6d0": "Sentinel R1",
    "43c0c0": "A400M Atlas (RAF)",
    "43c0c1": "A400M Atlas (RAF)",
    "43c0c2": "C-17 Globemaster (RAF)",
    "43c0c3": "C-17 Globemaster (RAF)",
    "43c6da": "Voyager KC3 (RAF)",
    "43c6db": "Voyager KC2 (RAF)",
    # NATO
    "478101": "E-3A AWACS (NATO)",
    "478102": "E-3A AWACS (NATO)",
    "478103": "E-3A AWACS (NATO)",
    "478104": "E-3A AWACS (NATO)",
    "478107": "E-3A AWACS (NATO)",
    "470000": "NATO unclassified",
    # French AF
    "3a09b1": "A330 MRTT Phénix",
    "3a09b2": "A330 MRTT Phénix",
    "3a0800": "A400M Atlas (FAF)",
    "3a0801": "A400M Atlas (FAF)",
    "3a0802": "C-130J Hercules (FAF)",
    # Italian AF
    "33ff01": "KC-767A (IAM)",
    "33ff02": "KC-767A (IAM)",
    "33ff10": "C-130J Hercules (IAM)",
    # Belgian AF
    "448501": "A400M Atlas (BAF)",
    "448502": "A400M Atlas (BAF)",
    # Spanish AF
    "340201": "A400M Atlas (SAF)",
    "340202": "A400M Atlas (SAF)",
}

# ── HEX prefix → type guessing (broader ranges) ────────────────────────────
HEX_PREFIX_TYPES = [
    ("3e8",  "A400M (GAF)"),
    ("3fc8", "Bundeswehr"),
    ("3fc9", "Bundeswehr"),
    ("3e23", "Helikopter (GAF)"),
    ("43c2", "AWACS/ISR (RAF)"),
    ("43c0", "Transport (RAF)"),
    ("43c6", "Tanker/ISR (RAF)"),
    ("4781", "E-3A AWACS (NATO)"),
    ("ae",   "USAF"),
    ("af",   "USAF"),
    ("adf",  "USAF UAV"),
    ("3a0",  "French AF"),
    ("33ff", "Italian AF"),
    ("4485", "Belgian AF"),
    ("3402", "Spanish AF"),
]

# ── Military ICAO hex ranges ───────────────────────────────────────────────
MILITARY_HEX_RANGES = [
    # US DoD
    (0xAE0000, 0xAFFFFF),
    # UK MoD
    (0x43C000, 0x43CFFF),
    # Germany (Specific Military Blocks)
    (0x3E8000, 0x3E8FFF),
    (0x3FC800, 0x3FCFFF),
    # France
    (0x3A0000, 0x3A0FFF),
    # Italy (Specific Mil)
    (0x33FF00, 0x33FFFF),
    # NATO (AWACS mostly)
    (0x478100, 0x4781FF),
    # Australia
    (0x7CF800, 0x7CFFFF),
    # Canada
    (0xC0CDF9, 0xC0FFFF),
    # Netherlands (Specific Mil)
    (0x480C00, 0x480CFF),
    # Belgium
    (0x448000, 0x448FFF),
    # Spain
    (0x340000, 0x340FFF),
    # Turkey
    (0x4B8000, 0x4BFFFF),
    # Japan
    (0x840000, 0x87FFFF),
    # South Korea
    (0x710000, 0x71FFFF),
    # Israel
    (0x738000, 0x73FFFF),
    # India
    (0x800000, 0x83FFFF),
    # China
    (0x780000, 0x7BFFFF),
    # Russia
    (0x150000, 0x15FFFF),
    # Brazil
    (0xE40000, 0xE4FFFF),
    # Sweden
    (0x4A0000, 0x4AFFFF),
    # Poland (Specific Mil)
    (0x484000, 0x4840FF),
    # UAE
    (0x896000, 0x896FFF),
    # Egypt
    (0x090000, 0x09FFFF),
    # Pakistan
    (0xA00000, 0xA0FFFF),
]


def _is_military_hex(hex_code: str) -> bool:
    """Check whether an ICAO hex address falls inside a known military block."""
    if not hex_code:
        return False
    try:
        value = int(hex_code, 16)
    except ValueError:
        return False
    for (lo, hi) in MILITARY_HEX_RANGES:
        if lo <= value <= hi:
            return True
    return False


def _identify_type(ac: dict) -> str:
    """Return the best-guess aircraft type string."""
    hex_code = (ac.get("hex") or "").strip().lower()
    flight = (ac.get("flight") or "").strip().upper()

    # 1) Exact HEX match
    if hex_code in HEX_AIRCRAFT_DB:
        return HEX_AIRCRAFT_DB[hex_code]

    # 2) HEX prefix match
    for prefix, label in HEX_PREFIX_TYPES:
        if hex_code.startswith(prefix):
            return label

    # 3) Callsign prefix → role
    for prefix, role in CALLSIGN_ROLES.items():
        if flight.startswith(prefix):
            return role

    return ""


def _is_military(ac: dict) -> bool:
    """
    Return True if the aircraft matches specific military criteria:
    - Callsign prefix from STRICT_MILITARY_PREFIXES
    - HEX code within a known military block
    - Emergency Squawk (7500, 7600, 7700) - NEVER exclude
    """
    flight = (ac.get("flight") or "").strip().upper()
    hex_code = (ac.get("hex") or "").strip().lower()
    squawk = str(ac.get("squawk") or "").strip()

    # 1) Emergency Exception (ALWAYS show)
    if squawk in ("7500", "7600", "7700"):
        return True

    # 2) Strict Callsign Prefix Filter
    for prefix in MILITARY_CALLSIGN_PREFIXES:
        if flight.startswith(prefix):
            return True

    # 3) Military HEX Range Filter
    if _is_military_hex(hex_code):
        return True

    return False


# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
@require_auth
def index():
    return send_from_directory(".", "index.html")


@app.route("/fetch")
@require_auth
def fetch_data():
    try:
        resp = requests.get(DATA_URL, timeout=4)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return jsonify({"error": str(exc), "aircraft": [], "now": 0}), 502

    # Fetch receiver position
    receiver = {}
    try:
        r = requests.get(RECEIVER_URL, timeout=2)
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
            military.append(ac)

    return jsonify({
        "now": data.get("now", 0),
        "total": len(all_aircraft),
        "military_count": len(military),
        "aircraft": military,
        "receiver": receiver,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
