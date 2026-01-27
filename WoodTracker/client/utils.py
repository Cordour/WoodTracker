# utils.py
import sys
import os
import shutil
from pathlib import Path
from config import set_wow_addon_dir


def resource_path(relative_path: str) -> Path:
    # MODE EXE (PyInstaller)
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path

    # MODE SCRIPT
    base = Path(__file__).resolve().parent

    # utils.py est dans client/
    return base / relative_path



def install_addon(log_cb):
    log_cb("📥 Installation des addons WoodTracker…")

    # 1️⃣ Source addons (embarqués dans l'exe)
    base_source = resource_path("addon")

    addons_to_install = [
        "WoodTracker",
        "WoodTracker_AHBridge",
    ]

    for addon_name in addons_to_install:
        src = base_source / addon_name
        if not src.exists():
            raise RuntimeError(f"Addon source introuvable : {src}")

    # 2️⃣ Localisation WoW
    candidates = [
        Path(p) / "World of Warcraft"
        for p in (
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            Path.home() / "Games",
        )
        if p
    ]

    wow_root = None
    for base in candidates:
        if (base / "_retail_").exists():
            wow_root = base
            break

    if not wow_root:
        raise RuntimeError("World of Warcraft introuvable")

    addons_dir = wow_root / "_retail_" / "Interface" / "AddOns"
    addons_dir.mkdir(parents=True, exist_ok=True)

    # 3️⃣ Copie des addons
    for addon_name in addons_to_install:
        src = base_source / addon_name
        dst = addons_dir / addon_name

        if dst.exists():
            shutil.rmtree(dst)

        shutil.copytree(src, dst)
        log_cb(f"✔ Addon installé : {addon_name}")

    # 4️⃣ Mise à jour config (addon principal)
    set_wow_addon_dir(str(addons_dir / "WoodTracker"))

    log_cb("✅ Tous les addons WoodTracker sont installés")
    return str(addons_dir)
