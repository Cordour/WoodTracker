import re
from pathlib import Path

from config import get_wow_addon_dir
from paths import get_wow_savedvariables_dir


TABLE_NAME = "WoodTracker_Sync"


# ============================================================
# UTIL
# ============================================================

def _log(msg, log_cb):
    if log_cb:
        log_cb(msg)


# ============================================================
# SYNC DATA (WoodTracker.lua)
# ============================================================

def find_savedvariables_file() -> Path:
    addon_dir = Path(get_wow_addon_dir()).resolve()

    retail_dir = addon_dir
    while retail_dir.name.lower() != "_retail_":
        if retail_dir.parent == retail_dir:
            raise FileNotFoundError("_retail_ introuvable depuis le dossier addon")
        retail_dir = retail_dir.parent

    accounts_dir = retail_dir / "WTF" / "Account"
    if not accounts_dir.exists():
        raise FileNotFoundError(f"Dossier introuvable : {accounts_dir}")

    candidates = []
    for account in accounts_dir.iterdir():
        sv = account / "SavedVariables" / "WoodTracker.lua"
        if sv.exists():
            candidates.append(sv)

    if not candidates:
        raise FileNotFoundError(
            "WoodTracker.lua introuvable.\n"
            "Lance WoW au moins une fois avec l’addon activé, puis ferme le jeu."
        )

    return max(candidates, key=lambda p: p.stat().st_mtime)


def extract_table(text: str, table_name: str) -> str:
    m = re.search(rf"{table_name}\s*=\s*\{{", text)
    if not m:
        raise ValueError(f"Table {table_name} introuvable")

    start = m.end() - 1
    depth = 0

    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    raise ValueError("Table Lua mal formée")


def parse_simple_table(block: str) -> dict:
    result = {}

    for key, value in re.findall(r'\["([^"]+)"\]\s*=\s*([^,\n]+)', block):
        value = value.strip()

        if value.startswith('"') and value.endswith('"'):
            result[key] = value[1:-1]
        else:
            try:
                result[key] = int(value)
            except ValueError:
                pass

    return result


def load_sync_data():
    sv_file = find_savedvariables_file()
    text = sv_file.read_text(encoding="utf-8")

    lua_block = extract_table(text, TABLE_NAME)

    data_block = re.search(r'\["data"\]\s*=\s*\{(.*?)\}', lua_block, re.S)
    meta_block = re.search(r'\["meta"\]\s*=\s*\{(.*?)\}', lua_block, re.S)

    if not data_block or not meta_block:
        raise ValueError("Bloc data ou meta manquant")

    data = parse_simple_table(data_block.group(1))
    meta = parse_simple_table(meta_block.group(1))

    checksum = int(re.search(r'\["checksum"\]\s*=\s*(\d+)', lua_block).group(1))
    timestamp_iso = re.search(r'\["timestamp_iso"\]\s*=\s*"([^"]+)"', lua_block).group(1)
    heartbeat_match = re.search(r'\["heartbeat"\]\s*=\s*(\d+)', lua_block)
    heartbeat = int(heartbeat_match.group(1)) if heartbeat_match else None

    if sum(data.values()) != checksum:
        raise ValueError("Checksum invalide")

    return {
        "data": data,
        "meta": meta,
        "checksum": checksum,
        "timestamp_iso": timestamp_iso,
        "heartbeat": heartbeat,
    }


# ============================================================
# AH PRICES (WoodTracker_AHBridge.lua)
# ============================================================

def load_ah_prices(log_cb=None):
    base = get_wow_savedvariables_dir()

    candidates = []
    for account_dir in base.iterdir():
        sv = account_dir / "SavedVariables" / "WoodTracker_AHBridge.lua"
        if sv.exists():
            candidates.append(sv)

    if not candidates:
        raise RuntimeError(
            "SavedVariables WoodTracker_AHBridge introuvable.\n"
            "👉 Ouvre l’HV en jeu puis ferme WoW."
        )

    path = max(candidates, key=lambda p: p.stat().st_mtime)
    _log(f"[AH] Fichier utilisé : {path}", log_cb)

    text = path.read_text(encoding="utf-8")

    if "WoodTracker_AH_DB" not in text:
        raise RuntimeError("Table WoodTracker_AH_DB introuvable")

    table_block = extract_table(text, "WoodTracker_AH_DB")

    prices = {}

    pattern = re.compile(
        r"\[(\d+)\]\s*=\s*\{\s*"
        r'\["price"\]\s*=\s*(\d+),\s*'
        r'\["timestamp"\]\s*=\s*(\d+),?\s*'
        r"\},?",
        re.S,
    )

    for item_id, price, ts in pattern.findall(table_block):
        prices[int(item_id)] = {
            "price": int(price),
            "timestamp": int(ts),
        }

    _log(f"[AH] Items AH chargés : {len(prices)}", log_cb)
    return prices


# ============================================================
# MAIN (debug standalone)
# ============================================================

if __name__ == "__main__":
    sync = load_sync_data()
    print("✔ Sync chargée")
    print("Compte :", sync["meta"].get("account"))
    print("Perso :", sync["meta"].get("character"))
    print("Royaume :", sync["meta"].get("realm"))
    print("Timestamp :", sync["timestamp_iso"])
