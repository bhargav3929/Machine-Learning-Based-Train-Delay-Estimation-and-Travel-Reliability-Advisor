"""Bundled railway priors: stations, trains, seasonal fog / monsoon vulnerability.

These are hand-curated planning priors (approximate coordinates, distances and
timetable times), not a live feed from Indian Railways.
"""

# code: (name, lat, lon, region, junction congestion 0-1, aliases)
STATIONS = {
    "HWH": ("Howrah Jn", 22.5832, 88.3426, "east", 0.85, ["howrah", "kolkata howrah", "hwh"]),
    "ASN": ("Asansol Jn", 23.6850, 86.9750, "east", 0.55, ["asansol"]),
    "DHN": ("Dhanbad Jn", 23.7957, 86.4304, "east", 0.60, ["dhanbad"]),
    "GAYA": ("Gaya Jn", 24.7955, 85.0002, "gangetic", 0.55, ["gaya"]),
    "DDU": ("Pt Deen Dayal Upadhyaya Jn (Mughalsarai)", 25.2820, 83.1190, "gangetic", 0.90,
            ["mughalsarai", "mughal sarai", "ddu", "deen dayal upadhyaya", "dd upadhyaya"]),
    "PRYJ": ("Prayagraj Jn", 25.4440, 81.8330, "gangetic", 0.80, ["prayagraj", "allahabad"]),
    "CNB": ("Kanpur Central", 26.4530, 80.3510, "gangetic", 0.88, ["kanpur", "kanpur central"]),
    "TDL": ("Tundla Jn", 27.2150, 78.2370, "gangetic", 0.80, ["tundla"]),
    "AGC": ("Agra Cantt", 27.1580, 77.9900, "gangetic", 0.72, ["agra", "agra cantt"]),
    "NDLS": ("New Delhi", 28.6428, 77.2197, "northwest", 0.95, ["new delhi", "delhi", "ndls", "nizamuddin"]),
    "HYB": ("Hyderabad Deccan", 17.3930, 78.4680, "deccan", 0.60, ["hyderabad", "hyderabad deccan", "nampally", "hyb"]),
    "SC": ("Secunderabad Jn", 17.4340, 78.5010, "deccan", 0.65, ["secunderabad", "sc"]),
    "KZJ": ("Kazipet Jn", 17.9780, 79.5120, "deccan", 0.40, ["kazipet", "warangal"]),
    "BPQ": ("Balharshah Jn", 19.8450, 79.3520, "deccan", 0.45, ["balharshah", "ballarshah"]),
    "NGP": ("Nagpur Jn", 21.1520, 79.0880, "central", 0.75, ["nagpur"]),
    "BPL": ("Bhopal Jn", 23.2680, 77.4130, "central", 0.70, ["bhopal"]),
    "JHS": ("Jhansi Jn", 25.4440, 78.5800, "central", 0.75, ["jhansi"]),
    "MMCT": ("Mumbai Central", 18.9690, 72.8190, "west", 0.85, ["mumbai", "mumbai central", "bombay central", "mmct"]),
    "BVI": ("Borivali", 19.2290, 72.8570, "west", 0.80, ["borivali"]),
    "ST": ("Surat", 21.2050, 72.8410, "west", 0.75, ["surat"]),
    "BRC": ("Vadodara Jn", 22.3100, 73.1810, "west", 0.70, ["vadodara", "baroda"]),
    "ADI": ("Ahmedabad Jn", 23.0250, 72.6010, "west", 0.65, ["ahmedabad"]),
    "RTM": ("Ratlam Jn", 23.3340, 75.0400, "west", 0.50, ["ratlam"]),
    "KOTA": ("Kota Jn", 25.1800, 75.8640, "northwest", 0.55, ["kota"]),
    "SBC": ("KSR Bengaluru", 12.9780, 77.5690, "south", 0.75, ["bengaluru", "bangalore", "ksr bengaluru", "sbc", "bangalore city"]),
    "GTL": ("Guntakal Jn", 15.1670, 77.3700, "south", 0.50, ["guntakal"]),
    "GHY": ("Guwahati", 26.1815, 91.7458, "northeast", 0.70, ["guwahati", "ghy", "gauhati"]),
    "CPK": ("Chaparmukh Jn", 26.1167, 92.5833, "northeast", 0.55, ["chaparmukh"]),
    "LMG": ("Lumding Jn", 25.7485, 93.1707, "northeast", 0.70, ["lumding"]),
    "FKG": ("Furkating Jn", 26.4833, 93.8667, "northeast", 0.55, ["furkating"]),
    "DBRG": ("Dibrugarh", 27.4728, 94.9120, "northeast", 0.50, ["dibrugarh", "dbrg"]),
    "PNBE": ("Patna Jn", 25.6020, 85.1380, "gangetic", 0.80, ["patna"]),
    "LKO": ("Lucknow Charbagh", 26.8320, 80.9230, "gangetic", 0.80, ["lucknow"]),
    "JP": ("Jaipur Jn", 26.9190, 75.7880, "northwest", 0.60, ["jaipur"]),
    "PUNE": ("Pune Jn", 18.5290, 73.8740, "west", 0.70, ["pune"]),
    "NZB": ("Nizamabad Jn", 18.6725, 78.0941, "deccan", 0.40, ["nizamabad"]),
    "KRNT": ("Kurnool City", 15.8281, 78.0373, "south", 0.45, ["kurnool", "kurnool city"]),
    "RU": ("Renigunta Jn", 13.6337, 79.5110, "south", 0.55, ["renigunta"]),
    "TPTY": ("Tirupati", 13.6288, 79.4192, "south", 0.60, ["tirupati", "tirupathi"]),
    "MAS": ("Chennai Central", 13.0825, 80.2750, "south", 0.75, ["chennai", "chennai central", "madras"]),
}

# number: dict(name, tier, tier_label, bias, turnaround, single_line, dep, run_min, route [(code, km)], keys)
TRAINS = {
    "12301": dict(name="Howrah Rajdhani Express", tier=1, bias=1.25, turnaround=0.40, single_line=0.0, dep="16:55", run_min=1020,
                  route=[("HWH", 0), ("ASN", 210), ("DHN", 260), ("GAYA", 458), ("DDU", 650), ("PRYJ", 792), ("CNB", 985), ("TDL", 1240), ("NDLS", 1447)],
                  keys=["howrah rajdhani", "howrah new delhi rajdhani", "hwh rajdhani"]),
    "12723": dict(name="Telangana Express", tier=2, bias=1.05, turnaround=0.45, single_line=0.0, dep="06:25", run_min=1405,
                  route=[("HYB", 0), ("SC", 8), ("KZJ", 135), ("BPQ", 325), ("NGP", 580), ("BPL", 940), ("JHS", 1230), ("AGC", 1480), ("NDLS", 1677)],
                  keys=["telangana"]),
    "12627": dict(name="Karnataka Express", tier=2, bias=1.05, turnaround=0.50, single_line=0.0, dep="19:20", run_min=2020,
                  route=[("SBC", 0), ("GTL", 395), ("SC", 710), ("KZJ", 845), ("BPQ", 1035), ("NGP", 1290), ("BPL", 1670), ("JHS", 1960), ("AGC", 2190), ("NDLS", 2360)],
                  keys=["karnataka express", "karnataka sf"]),
    "12009": dict(name="Mumbai Central - Ahmedabad Shatabdi Express", tier=1, bias=0.70, turnaround=0.20, single_line=0.0, dep="06:25", run_min=390,
                  route=[("MMCT", 0), ("BVI", 30), ("ST", 263), ("BRC", 393), ("ADI", 491)],
                  keys=["ahmedabad shatabdi", "mumbai ahmedabad shatabdi", "mumbai central ahmedabad"]),
    "15909": dict(name="Guwahati - Dibrugarh Corridor Express", tier=3, bias=1.15, turnaround=0.50, single_line=0.50, dep="22:15", run_min=600,
                  route=[("GHY", 0), ("CPK", 125), ("LMG", 215), ("FKG", 405), ("DBRG", 485)],
                  keys=["guwahati dibrugarh", "dibrugarh corridor"]),
    "12794": dict(name="Rayalaseema Express", tier=3, bias=1.00, turnaround=0.45, single_line=0.10, dep=None, run_min=None,
                  route=[("NZB", 0), ("SC", 175), ("KRNT", 390), ("GTL", 510), ("RU", 815), ("TPTY", 825)],
                  keys=["rayalaseema"]),
    "12951": dict(name="Mumbai Rajdhani Express", tier=1, bias=1.00, turnaround=0.35, single_line=0.0, dep="16:55", run_min=925,
                  route=[("MMCT", 0), ("BRC", 392), ("RTM", 676), ("KOTA", 915), ("NDLS", 1384)],
                  keys=["mumbai rajdhani"]),
    "12002": dict(name="Bhopal Shatabdi Express", tier=1, bias=0.80, turnaround=0.25, single_line=0.0, dep="06:00", run_min=515,
                  route=[("NDLS", 0), ("AGC", 195), ("JHS", 465), ("BPL", 705)],
                  keys=["bhopal shatabdi"]),
}

TIER_LABELS = {1: "Tier 1 - Premium (Rajdhani / Shatabdi)", 2: "Tier 2 - Superfast / Express", 3: "Tier 3 - Mail / Express", 4: "Tier 4 - Ordinary"}
TIER_MULT = {1: 0.60, 2: 0.80, 3: 1.00, 4: 1.35}

# Seasonal prior by region, index 0 = January ... 11 = December (0 = none, 1 = severe).
FOG_PRIOR = {
    "gangetic": [.85, .60, .20, .05, 0, 0, 0, 0, .05, .20, .50, .85],
    "northwest": [.80, .55, .15, 0, 0, 0, 0, 0, 0, .15, .45, .80],
    "east": [.45, .30, .10, 0, 0, 0, 0, 0, 0, .05, .20, .40],
    "central": [.35, .20, .05, 0, 0, 0, 0, 0, 0, .05, .15, .35],
    "west": [.10, .05, 0, 0, 0, 0, 0, 0, 0, 0, .05, .10],
    "deccan": [.15, .10, 0, 0, 0, 0, 0, 0, 0, 0, .05, .12],
    "south": [.05, .03, 0, 0, 0, 0, 0, 0, 0, 0, 0, .04],
    "northeast": [.40, .30, .10, .05, 0, 0, 0, 0, 0, .10, .25, .40],
}
RAIN_PRIOR = {
    "gangetic": [.05, .05, .03, .03, .08, .35, .70, .75, .55, .15, .03, .03],
    "northwest": [.05, .05, .04, .03, .04, .15, .50, .55, .30, .05, .02, .04],
    "east": [.05, .08, .10, .15, .25, .55, .75, .80, .70, .35, .10, .03],
    "central": [.03, .03, .03, .03, .05, .45, .80, .80, .60, .15, .05, .03],
    "west": [.02, .02, .02, .02, .05, .70, .95, .90, .60, .15, .04, .02],
    "deccan": [.02, .03, .04, .08, .15, .40, .55, .55, .55, .35, .12, .04],
    "south": [.05, .04, .06, .15, .25, .40, .45, .40, .40, .50, .50, .25],
    "northeast": [.05, .10, .20, .40, .60, .85, .95, .95, .85, .40, .10, .05],
}
FOG_SENS = {"gangetic": 1.0, "northwest": 1.0, "east": 0.8, "central": 0.7, "west": 0.5, "deccan": 0.5, "south": 0.4, "northeast": 0.8}
RAIN_SENS = {"gangetic": 0.8, "northwest": 0.7, "east": 0.9, "central": 0.8, "west": 0.9, "deccan": 0.7, "south": 0.8, "northeast": 1.1}

CONNECTION_TYPES = {
    # label: (minimum minutes needed after arrival, target confidence for the safe buffer)
    "Connecting Flight at Destination": (75, 0.95),
    "Connecting Long-Distance Train": (30, 0.90),
    "Important Exam / Interview / Event": (45, 0.95),
    "Standard Point-to-Point Travel": (0, 0.80),
}


def region_for(lat, lon):
    """Coarse railway-zone guess for stations that are not in the bundled table."""
    if lon >= 90:
        return "northeast"
    if lat >= 28.8 and lon < 79.5:
        return "northwest"
    if lat >= 25.5 and lon < 77:
        return "northwest"
    if lat >= 24 and 80 <= lon <= 87:
        return "gangetic"
    if lat >= 21.5 and lon >= 86.5:
        return "east"
    if lon < 74.5 and lat < 24.5:
        return "west"
    if lat < 14:
        return "south"
    if lat < 20 and lon >= 76:
        return "deccan"
    return "central"
