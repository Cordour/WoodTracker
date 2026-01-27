from pathlib import Path
import os
import psutil


def find_wow_root():
    candidates = [
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "World of Warcraft",
        Path(os.environ.get("PROGRAMFILES", "")) / "World of Warcraft",
    ]

    for base in candidates:
        if (base / "_retail_").exists():
            return base / "_retail_"

    raise FileNotFoundError("World of Warcraft (_retail_) introuvable")


def find_savedvariables_file():
    retail = find_wow_root()
    account_dir = retail / "WTF" / "Account"

    if not account_dir.exists():
        raise FileNotFoundError("Dossier WTF/Account introuvable")

    patterns = [
        "*/SavedVariables/WoodTracker.lua",
        "*/SavedVariables/WoodTracker_Sync.lua",
    ]

    matches = []
    for pattern in patterns:
        matches.extend(account_dir.glob(pattern))

    if not matches:
        raise FileNotFoundError(
            "Aucun fichier SavedVariables WoodTracker trouvé"
        )

    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0]


def find_objectifs_lua():
    retail = find_wow_root()
    return (
        retail
        / "Interface"
        / "AddOns"
        / "WoodTracker"
        / "objectifs.lua"
    )


def is_wow_running():
    for p in psutil.process_iter(["name"]):
        name = p.info.get("name")
        if name and name.lower() == "wow.exe":
            return True
    return False


def get_wow_savedvariables_dir():
    retail = find_wow_root()
    return retail / "WTF" / "Account"
