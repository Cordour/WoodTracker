# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

block_cipher = None

datas = []
binaries = []
hiddenimports = []

# ======================================================
# Collect complet des librairies tierces utilisées
# ======================================================
for pkg in [
    "requests",
    "certifi",
    "charset_normalizer",
    "psutil",
    "PIL",
    "setuptools",
    "gspread",
    "google.auth",
    "google_auth_oauthlib",
]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# ======================================================
# Données applicatives (fichiers NON Python)
# ======================================================
datas += [
    ("client/assets", "assets"),
    ("client/icons", "icons"),
    ("client/addon", "addon"),
    ("client/node", "node"),
    ("Warmup-decor", "Warmup-decor"),
    ("client/client_oauth.json", "."),
]

# ======================================================
# Modules internes (fichiers .py dans client/)
# ======================================================
hiddenimports += [
    "utils",               # client/utils.py
    "woodtracker_sync",    # client/woodtracker_sync.py
]

# ======================================================
# Analyse
# ======================================================
a = Analysis(
    ["client/main.py"],
    pathex=["client"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["venv"],   # IMPORTANT : exclut le venv
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

# ======================================================
# EXE
# ======================================================
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WoodTracker",
    debug=False,
    strip=False,
    upx=False,          # IMPORTANT (antivirus + stabilité)
    console=False,
    icon="client/assets/woodtracker.ico",
)

# ======================================================
# COLLECT (onedir)
# ======================================================
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="WoodTracker",
)
