import json
import os
from collections import Counter
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import threading
import time
import subprocess
from pathlib import Path
from utils import resource_path
import sys

if hasattr(sys, "_MEIPASS"):
    # EXE PyInstaller
    BASE = resource_path("Warmup-decor")
else:
    # DEV : client/ → remonter au dossier WoodTracker/
    BASE = Path(__file__).resolve().parent.parent / "Warmup-decor"




def run_node_script(script_name: str, log_cb):
    """
    Lance un script Node.js de Warmup-decor
    Compatible DEV + EXE PyInstaller
    """
    node_exe = resource_path("node/node.exe")

    # 🔁 DEV vs EXE
    if hasattr(sys, "_MEIPASS"):
        # EXE PyInstaller
        base = Path(sys._MEIPASS)
    else:
        # DEV : on remonte depuis client/
        base = Path(__file__).resolve().parent.parent

    script_path = base / "Warmup-decor" / script_name

    if not node_exe.exists():
        raise RuntimeError(f"node.exe introuvable : {node_exe}")

    if not script_path.exists():
        raise RuntimeError(f"Script Node introuvable : {script_path}")

    log_cb(f"▶ Lancement Node : {script_name}")

    process = subprocess.Popen(
        [str(node_exe), str(script_path)],
        cwd=script_path.parent,   # 🔥 CRITIQUE
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    for line in process.stdout:
        log_cb(line.rstrip())

    process.wait()

    if process.returncode != 0:
        raise RuntimeError(f"Erreur Node sur {script_name}")

    

_RUN_LOCK = threading.Lock()
_LAST_RUN_TS = 0
COOLDOWN_SECONDS = 120 
# ======================
# PATHS & CONFIG
# ======================

APPDATA = os.environ.get("APPDATA", "")
CONFIG_PATH = os.path.join(APPDATA, "WoodTracker", "config.json")
TOKEN_PATH = os.path.join(APPDATA, "WoodTracker", "token.json")



# ======================
# CONSTANTS
# ======================

WOOD_IDS = {
    "245586",  # classique
    "242691",  # outreterre
    "251762",  # norfendre
    "251764",  # cataclysm
    "251763",  # pandarie
    "251766",  # draenor
    "251767",  # legion
    "251768",  # kul tiras / zandalar
    "251772",  # ombreterre
    "251773",  # îles aux dragons
    "248012",  # khaz algar
}

IGNORED_REAGENTS = {
    "204634",
    "166970",
    "120945",
    "124124",
    "200953",
    "136693",
    "54440",
}

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ======================
# HELPERS
# ======================

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_best_price(item_id, ah_components, ah_server):
    prices = []

    if item_id in ah_components:
        prices.append(ah_components[item_id]["price"])

    if item_id in ah_server:
        prices.append(ah_server[item_id]["price"])

    return min(prices) if prices else None


def calc_craft_cost(recipe, ah_components, ah_server, wood_item_ids):
    total = 0
    missing = []
    ignored_ids = wood_item_ids | IGNORED_REAGENTS

    for r in recipe.get("reagents", []):
        item_id = str(r["reagent"]["id"])
        if item_id in ignored_ids:
            continue

        qty = r.get("quantity", 0)
        price = get_best_price(item_id, ah_components, ah_server)

        if price is None:
            missing.append(f"reagent:{item_id}")
            continue

        total += qty * price

    for slot in recipe.get("reagent_slots", []):
        qty = slot.get("quantity", 0)
        best_price = None

        for r in slot.get("reagents", []):
            item_id = str(r["reagent"]["id"])
            if item_id in ignored_ids:
                continue

            p = get_best_price(item_id, ah_components, ah_server)
            if p is not None and (best_price is None or p < best_price):
                best_price = p

        if best_price is None:
            missing.append("slot:no_price")
            continue

        total += qty * best_price

    return total, missing


def calc_rentabilite(decor, recipe, ah_components, ah_server, prix_vente):
    wood = decor.get("wood", 0)
    if wood <= 0:
        return None

    cost, missing = calc_craft_cost(
        recipe,
        ah_components,
        ah_server,
        WOOD_IDS
    )

    if missing:
        return None

    return (prix_vente - cost) / wood


# ======================
# GOOGLE SHEETS
# ======================

def write_to_sheets(sheet_id, values, log_cb=None):
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    service = build("sheets", "v4", credentials=creds)

    body = {"values": values}

    result = service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="BDD!K7:L",
        valueInputOption="RAW",
        body=body
    ).execute()

    if log_cb:
        log_cb(f"📤 {result.get('updatedCells')} cellules mises à jour")


# ======================
# ENTRY POINT (IMPORTANT)
# ======================

def run(log_cb=None):
    def log(msg):
        if log_cb:
            log_cb(msg)

    global _LAST_RUN_TS

    # 🔍 Vérification fichiers nécessaires
    required_files = [
        "decor.json",
        "recipe_cache.json",
        "ah_cache.json",
    ]

    for fname in required_files:
        path = os.path.join(BASE, fname)
        if not os.path.exists(path):
            raise RuntimeError(
                f"Fichier manquant : {fname}\n"
                f"👉 Lance d'abord l'actualisation BDD Blizzard"
            )

    # 🔒 Anti double-run
    if not _RUN_LOCK.acquire(blocking=False):
        log("⏳ Calcul déjà en cours — ignoré")
        return

    now = time.time()
    elapsed = now - _LAST_RUN_TS

    if elapsed < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - elapsed)
        log(f"⏱️ Cooldown actif — encore {remaining}s")
        _RUN_LOCK.release()
        return


    try:

        config = load_json(CONFIG_PATH)
        sheet_id = config.get("sheet_id")

        if not sheet_id:
            raise RuntimeError("Sheet ID manquant dans config.json")

        decor_list = load_json(os.path.join(BASE, "decor.json"))
        recipes = load_json(os.path.join(BASE, "recipe_cache.json"))
        ah_data = load_json(os.path.join(BASE, "ah_cache.json"))

        ah_components = ah_data["components"]
        ah_server = ah_data.get("server", {})

        results = []
        rejected = []
        no_price_items = []

        for decor in decor_list:
            recipe = recipes.get(str(decor["recipeId"]))
            if not recipe:
                continue

            crafted_id = str(decor.get("itemID"))
            if not crafted_id:
                continue

            prix_vente = get_best_price(crafted_id, ah_components, ah_server)
            if prix_vente is None:
                no_price_items.append(crafted_id)
                continue

            rent = calc_rentabilite(
                decor,
                recipe,
                ah_components,
                ah_server,
                prix_vente
            )

            if rent is None:
                cost, missing = calc_craft_cost(
                    recipe,
                    ah_components,
                    ah_server,
                    WOOD_IDS
                )

                rejected.append({
                    "name": decor["name"],
                    "itemID": crafted_id,
                    "recipeId": decor["recipeId"],
                    "missing": missing
                })
                continue

            results.append([
                round(rent / 10000),
                int(crafted_id)
            ])
        log("▶ Lancement récupération AH Blizzard")
        run_node_script("ah_fetch.js", log)
        log("✔ AH Blizzard terminé")
        values = results + [["", int(i)] for i in no_price_items]

        write_to_sheets(sheet_id, values, log)

        with open(
            os.path.join(os.path.dirname(__file__), "rejected_decors.json"),
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(rejected, f, indent=2, ensure_ascii=False)

        log(f"✔ Décors exploitables : {len(results)}")
        log(f"⚠ Décors sans prix    : {len(no_price_items)}")
        log(f"❌ Décors rejetés      : {len(rejected)}")
        log("🧮 Calcul terminé")
        _LAST_RUN_TS = time.time()

    finally:
        # 🔓 Toujours libérer le lock
        _RUN_LOCK.release()
