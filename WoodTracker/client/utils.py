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
    log_cb("📥 Copie de l’addon WoodTracker…")

    # 1️⃣ Source addon (embarqué)
    source = resource_path("addon/WoodTracker")
    if not source.exists():
        raise RuntimeError(f"Addon source introuvable : {source}")

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

    target = addons_dir / "WoodTracker"

    # 3️⃣ Remplacement propre
    if target.exists():
        shutil.rmtree(target)

    shutil.copytree(source, target)

    # 4️⃣ Mise à jour config
    set_wow_addon_dir(str(target))

    log_cb("✔ Addon WoodTracker installé avec succès")
    return str(target)
