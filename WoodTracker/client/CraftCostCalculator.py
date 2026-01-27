import json
import os
import threading
import time
from pathlib import Path
import sys

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from utils import resource_path
from parse_savedvariables import load_ah_prices


# ============================================================
# BASE PATH (DEV / EXE)
# ============================================================

if hasattr(sys, "_MEIPASS"):
    BASE = resource_path("Warmup-decor")
else:
    BASE = Path(__file__).resolve().parent.parent / "Warmup-decor"


# ============================================================
# LOCKS
# ============================================================

_RUN_LOCK = threading.Lock()
_LAST_RUN_TS = 0


# ============================================================
# PATHS & CONFIG
# ============================================================

APPDATA = os.environ.get("APPDATA", "")
CONFIG_PATH = os.path.join(APPDATA, "WoodTracker", "config.json")
TOKEN_PATH = os.path.join(APPDATA, "WoodTracker", "token.json")


# ============================================================
# CONSTANTS
# ============================================================

WOOD_IDS = {
    "245586", "242691", "251762", "251764", "251763",
    "251766", "251767", "251768", "251772", "251773", "248012"
}

IGNORED_REAGENTS = {
    "204634", "166970", "120945", "124124",
    "200953", "136693", "54440"
}

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# ============================================================
# HELPERS
# ============================================================

def _log(msg, log_cb):
    if log_cb:
        log_cb(msg)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_best_price(item_id, ah_components, ah_server):
    item_id = int(item_id)

    prices = []

    if item_id in ah_components:
        prices.append(ah_components[item_id]["price"])

    if item_id in ah_server:
        prices.append(ah_server[item_id]["price"])

    return min(prices) if prices else 0


# ============================================================
# CRAFT COST CALCULATION
# ============================================================

def calc_craft_cost(recipe, ah_components, ah_server, wood_item_ids):
    total = 0
    ignored_ids = wood_item_ids | IGNORED_REAGENTS

    # 🔹 reagents directs
    for r in recipe.get("reagents", []):
        item_id = str(r["reagent"]["id"])
        if item_id in ignored_ids:
            continue

        qty = r.get("quantity", 0)
        price = get_best_price(item_id, ah_components, ah_server)

        if price == 0:
            continue  # composant absent HV → ignoré

        total += qty * price

    # 🔹 reagent slots (choix multiples)
    for slot in recipe.get("reagent_slots", []):
        qty = slot.get("quantity", 0)
        prices = []

        for r in slot.get("reagents", []):
            item_id = str(r["reagent"]["id"])
            if item_id in ignored_ids:
                continue

            p = get_best_price(item_id, ah_components, ah_server)
            if p > 0:
                prices.append(p)

        if not prices:
            continue  # slot entier ignoré

        total += qty * min(prices)

    return total


# ============================================================
# GOOGLE SHEETS
# ============================================================

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

    _log(f"📤 {result.get('updatedCells')} cellules mises à jour", log_cb)


# ============================================================
# ENTRY POINT
# ============================================================

def run(log_cb=None):
    global _LAST_RUN_TS

    def log(msg):
        _log(msg, log_cb)

    required_files = ["decor.json", "recipe_cache.json", "ah_cache.json"]
    for fname in required_files:
        if not os.path.exists(os.path.join(BASE, fname)):
            raise RuntimeError(f"Fichier manquant : {fname}")

    if not _RUN_LOCK.acquire(blocking=False):
        log("⏳ Calcul déjà en cours — ignoré")
        return

    try:
        config = load_json(CONFIG_PATH)
        sheet_id = config.get("sheet_id")
        if not sheet_id:
            raise RuntimeError("Sheet ID manquant dans config.json")

        decor_list = load_json(os.path.join(BASE, "decor.json"))
        recipes = load_json(os.path.join(BASE, "recipe_cache.json"))

        ah_components = load_ah_prices(log_cb)
        ah_server = {}

        log("🧮 Calcul des coûts de craft…")

        results = []

        for decor in decor_list:
            recipe = recipes.get(str(decor.get("recipeId")))
            if not recipe:
                continue

            crafted_id = decor.get("itemID")
            wood = decor.get("wood", 0)
            if not crafted_id or wood <= 0:
                continue

            prix_vente = get_best_price(crafted_id, ah_components, ah_server)
            cost = calc_craft_cost(
                recipe,
                ah_components,
                ah_server,
                WOOD_IDS
            )

            rent = (prix_vente - cost) / wood

            results.append([
                round(rent / 10000),
                int(crafted_id)
            ])

        write_to_sheets(sheet_id, results, log_cb)

        log(f"✔ Décors exploitables : {len(results)}")
        log("🧮 Calcul terminé")
        _LAST_RUN_TS = time.time()

    finally:
        _RUN_LOCK.release()
