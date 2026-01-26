import re
from pathlib import Path
from config import get_wow_addon_dir

TABLE_NAME = "WoodTracker_Sync"


def find_savedvariables_file() -> Path:
    addon_dir = Path(get_wow_addon_dir()).resolve()

    # Remonte jusqu'à _retail_
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
            "Lancez WoW au moins une fois avec l’addon activé, puis fermez le jeu."
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

    checksum_match = re.search(r'\["checksum"\]\s*=\s*(\d+)', lua_block)
    ts_iso_match = re.search(r'\["timestamp_iso"\]\s*=\s*"([^"]+)"', lua_block)

    checksum = int(checksum_match.group(1))
    timestamp_iso = ts_iso_match.group(1)
    heartbeat_match = re.search(r'\["heartbeat"\]\s*=\s*(\d+)', lua_block)
    heartbeat = int(heartbeat_match.group(1)) if heartbeat_match else None

    # 🔐 Validation checksum
    if sum(data.values()) != checksum:
        raise ValueError("Checksum invalide")

    return {
        "data": data,
        "meta": meta,
        "checksum": checksum,
        "timestamp_iso": timestamp_iso,
        "heartbeat": heartbeat,
    }
if __name__ == "__main__":
    sync = load_sync_data()
    print("✔ Sync chargée")
    print("Compte détecté :", sync["meta"].get("account"))
    print("Perso :", sync["meta"].get("character"))
    print("Royaume :", sync["meta"].get("realm"))
    print("Timestamp :", sync["timestamp_iso"])
    print("Données :", sync["data"])
