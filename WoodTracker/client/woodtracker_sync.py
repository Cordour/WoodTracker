import sys
import json
import subprocess
from pathlib import Path
from urllib.parse import quote

from utils import resource_path
from google_oauth import get_gspread_client
from parse_savedvariables import load_sync_data
from paths import is_wow_running
from config import get_sheet_id, get_wow_addon_dir
import gspread

EXTENSION_ORDER = [
    "TWW",
    "DF",
    "SL",
    "BFA",
    "LEGION",
    "WOD",
    "MISTS",
    "CATA",
    "WOTLK",
    "BC",
    "CLASSIC",
]

def read_totals_from_sheet(sheet):
    headers = sheet.row_values(HEADER_ROW)
    values = sheet.row_values(TOTALS_ROW)

    totals = {}

    for col, name in enumerate(headers):
        if name in EXTENSIONS:
            val = int(values[col]) if values[col] else 0
            totals[name] = val

    return totals

def default_log(msg):
    print(msg)

def default_progress(value):
    pass

VERBOSE = False
def log(msg):
    if VERBOSE:
        print(msg)

def run_sync(log_cb=default_log, progress_cb=default_progress):
    sheet_id = get_sheet_id()
    if not sheet_id:
        raise RuntimeError("Aucun Google Sheet configuré")

    # 1️⃣ Connexion Google
    log_cb("Connexion à Google Sheets")
    progress_cb(10)
    sheet = get_sheet(sheet_id, SHEET_NAME)

    # 2️⃣ WoW → Google Sheets (SI WoW FERMÉ)
    if is_wow_running():
        log_cb(
            "⚠ WoW est ouvert : "
            "les données en jeu ne peuvent pas être envoyées."
        )
    else:
        log_cb("Lecture des SavedVariables WoW")
        progress_cb(30)
        sync = load_sync_data()

        log_cb("Synchronisation WoW → Google Sheets")
        progress_cb(50)
        push_totals_to_sheet(
            sheet,
            sync["data"],
            log_cb,
            dry_run=False
        )

    # 3️⃣ Lecture des objectifs depuis Google Sheets
    log_cb("Lecture des objectifs depuis Google Sheets")
    progress_cb(70)
    objectifs = read_objectifs(sheet)

    # 4️⃣ Écriture objectifs.lua
    log_cb("Génération de objectifs.lua")
    progress_cb(85)
    write_objectifs_lua(objectifs)

    # 5️⃣ Lecture finale (source de vérité UI)
    totals = read_totals_from_sheet(sheet)

    result = {}
    for key in EXTENSION_ORDER:
        result[key] = {
            "total": totals.get(key, 0),
            "objectif": objectifs.get(key, 0),
            "itemID": EXTENSIONS[key]["itemID"],
        }

    log_cb("✔ Synchronisation terminée")
    progress_cb(100)
    return result

    
    



# =========================
# CONFIGURATION
# =========================





def get_output_file():
    wow_dir = get_wow_addon_dir()
    if not wow_dir:
        raise RuntimeError("Dossier WoW non configuré")

    generated = Path(wow_dir) / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    return generated / "objectifs.lua"


SHEET_NAME = "Tableau"


HEADER_ROW = 4
TOTALS_ROW = 5
OBJECTIFS_ROW = 6


# Source de vérité unique
EXTENSIONS = {
    "TWW":     {"itemID": 248012},
    "DF":      {"itemID": 251773},
    "SL":      {"itemID": 251772},
    "BFA":     {"itemID": 251768},
    "LEGION":  {"itemID": 251767},
    "WOD":     {"itemID": 251766},
    "MISTS":   {"itemID": 251763},
    "CATA":    {"itemID": 251764},
    "WOTLK":   {"itemID": 251762},
    "BC":      {"itemID": 242691},
    "CLASSIC": {"itemID": 245586},
}

# =========================
# GOOGLE SHEETS AUTH
# =========================
def get_sheet(sheet_id, sheet_name):
    client = get_gspread_client()
    return client.open_by_key(sheet_id).worksheet(sheet_name)


# =========================
# READ OBJECTIFS FROM SHEET
# =========================
def read_objectifs(sheet):
    headers = sheet.row_values(HEADER_ROW)
    values = sheet.row_values(OBJECTIFS_ROW)

    objectifs = {}

    for col, name in enumerate(headers):
        if name in EXTENSIONS:
            val = int(values[col]) if values[col] else 0
            objectifs[name] = val

    return objectifs

# =========================
# WRITE objectifs.lua
# =========================
def write_objectifs_lua(objectifs):
    output_file = get_output_file()
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("WoodTracker_Objectifs = {\n")
        for name in EXTENSION_ORDER:
            val = objectifs.get(name, 0)
            itemID = EXTENSIONS[name]["itemID"]
            f.write(
                f"    Bois_{name} = {{objectif = {val}, itemID = {itemID}}},\n"
            )
        f.write("}\n")








def push_totals_to_sheet(sheet, totals, log_cb, dry_run=False):
    headers = sheet.row_values(HEADER_ROW)

    for col_idx, header in enumerate(headers, start=1):
        key = f"Bois_{header}"
        if key not in totals:
            continue

        new_value = totals[key]
        cell = sheet.cell(TOTALS_ROW, col_idx)
        old_value = int(cell.value) if cell.value else 0

        if old_value != new_value:
            log_cb(f"→ {header}: {old_value} → {new_value}")
            if not dry_run:
                sheet.update_cell(TOTALS_ROW, col_idx, new_value)












def find_node_script():
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        # On part du fichier courant
        base = Path(__file__).resolve().parent

        # Si Warmup-decor n’est pas ici, on remonte d’un niveau
        if not (base / "Warmup-decor").exists():
            base = base.parent

    candidate = base / "Warmup-decor" / "warmup-decor.js"
    return candidate if candidate.exists() else None














def sync_bdd_blizzard(log_cb=default_log):
    log_cb("🌍 Mise à jour de la BDD Blizzard…")

    # 1️⃣ Trouver le script Node
    node_script = find_node_script()
    if not node_script:
        raise RuntimeError("Script Blizzard introuvable")

    log_cb(f"✔ Script Blizzard trouvé : {node_script}")

    # 2️⃣ Lancer Node
    node_exe = resource_path("node/node.exe")
    log_cb(f"Node utilisé : {node_exe}")
    log_cb(f"Script Node : {node_script}")
    process = subprocess.Popen(
        [str(node_exe), str(node_script)],
        cwd=node_script.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        bufsize=1,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    for line in process.stdout:
        log_cb(line.rstrip())

    process.wait()

    if process.returncode != 0:
        raise RuntimeError("Erreur pendant l’exécution du script Blizzard")


    # 3️⃣ Charger le JSON
    json_path = node_script.parent / "decor.json"
    if not json_path.exists():
        raise RuntimeError("decor.json non généré")

    data = json.loads(json_path.read_text(encoding="utf-8"))

    # 4️⃣ Construire les lignes Google Sheets
    rows = []
    for block in data:
        for item in block["items"]:
            rows.append([
                None,
                None,
                block["profession"],
                block["tier"],
                item["name"],
                item["wood"],
                "https://www.wowhead.com/fr/search?q=" + quote(item["name"])
            ])
            

    # 5️⃣ Écriture Sheets
    client = get_gspread_client()
    sheet = client.open_by_key(get_sheet_id()).worksheet("BDD")

    sheet.update(
        "A7:G",
        rows,
        value_input_option="USER_ENTERED"
    )

    log_cb(f"✅ BDD Blizzard mise à jour ({len(rows)} lignes)")





    