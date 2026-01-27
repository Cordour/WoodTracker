import json
import os
from collections import Counter
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build



CONFIG_PATH = os.path.join(
    os.environ["APPDATA"],
    "WoodTracker",
    "config.json"
)

TOKEN_PATH = os.path.join(
    os.environ["APPDATA"],
    "WoodTracker",
    "token.json"
)

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
    
config = load_json(CONFIG_PATH)
SHEET_ID = config["sheet_id"]
print("📄 Config utilisé :", CONFIG_PATH)
print("📊 Sheet ID :", SHEET_ID)
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


def get_best_price(item_id, ah_components, ah_server):
    prices = []

    if item_id in ah_components:
        prices.append(ah_components[item_id]["price"])

    if item_id in ah_server:
        prices.append(ah_server[item_id]["price"])

    if not prices:
        return None

    return min(prices)


def calc_craft_cost(recipe, ah_components, ah_server, wood_item_ids):
    total = 0
    missing = []
    IGNORED_IDS = wood_item_ids | IGNORED_REAGENTS

    for r in recipe.get("reagents", []):
        item_id = str(r["reagent"]["id"])
        if item_id in IGNORED_IDS:
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
            if item_id in IGNORED_IDS:
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



# ========= MAIN =========

BASE = "../Warmup-decor/"

decor_list = load_json(BASE + "decor.json")
recipes = load_json(BASE + "recipe_cache.json")
ah_data = load_json(BASE + "ah_cache.json")
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
        no_price_items.append({
            "name": decor["name"],
            "itemID": crafted_id,
            "recipeId": decor["recipeId"]
        })
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
            "itemID": decor["itemID"],
            "recipeId": decor["recipeId"],
            "missing": missing
        })
        continue

    results.append({
        "name": decor["name"],
        "itemID": crafted_id,
        "po_par_bois": round(rent / 10000)
    })


values_ok = [
    [r["po_par_bois"], int(r["itemID"])]
    for r in results
]
values_no_price = [
    ["", int(r["itemID"])]
    for r in no_price_items
]
values = values_ok + values_no_price


def write_to_sheets(sheet_id, values):
    creds = Credentials.from_authorized_user_file(
        TOKEN_PATH,
        ["https://www.googleapis.com/auth/spreadsheets"]
    )

    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    body = {
        "values": values
    }

    result = sheet.values().update(
        spreadsheetId=sheet_id,
        range="BDD!K7:L",
        valueInputOption="RAW",
        body=body
    ).execute()

    print(f"📤 {result.get('updatedCells')} cellules mises à jour")

    
write_to_sheets(SHEET_ID, values)

print(f"Décors exploitables : {len(results)}")
print(f"Décors sans prix    : {len(no_price_items)}")
print(f"Décors rejetés      : {len(rejected)}")
print(f"Total décor bois    : {len(decor_list)}")


print("\n--- LISTE COMPLÈTE DES REJETS ---")

if not rejected:
    print("Aucun rejet 🎉")
else:
    for r in rejected:
        print(f"- {r['name']} (itemID={r['itemID']}, recipeId={r['recipeId']})")
        for m in r["missing"]:
            print("   ❌", m)
counter = Counter()

for r in rejected:
    for m in r["missing"]:
        counter[m] += 1
print("\n--- LISTE DES DÉCORS SANS PRIX AH ---")

for d in no_price_items:
    print(f"- {d['name']} (itemID={d['itemID']}, recipeId={d['recipeId']})")
print("\n--- STATS DES REJETS ---")
for reason, count in counter.most_common():
    print(f"{reason} : {count}")
with open("rejected_decors.json", "w", encoding="utf-8") as f:
    json.dump(rejected, f, indent=2, ensure_ascii=False)


