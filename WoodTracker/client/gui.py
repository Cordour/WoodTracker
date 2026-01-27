import tkinter as tk
import threading
import os
import sys
import time
from pathlib import Path
from PIL import Image, ImageTk
from tkinter import ttk
from woodtracker_sync import run_sync, EXTENSION_ORDER
from config import get_sheet_id, set_sheet_id
from google_oauth import has_google_account
import webbrowser
from tkinter import filedialog, messagebox
from config import set_wow_addon_dir
from config import get_wow_addon_dir
from woodtracker_sync import sync_bdd_blizzard
from utils import resource_path
import requests
import subprocess
from wow_status import is_wow_alive_via_heartbeat
from config import get_appdata_dir
from CraftCostCalculator import run as run_craft_cost


GITHUB_VERSION_URL = "https://raw.githubusercontent.com/Cordour/WoodTracker/main/version.json"


APP_VERSION = "1.2.0"

def check_update():
    r = requests.get(GITHUB_VERSION_URL, timeout=5)
    r.raise_for_status()
    return r.json()

def launch_patcher(download_url):
    app_dir = Path(sys.executable).parent
    exe_name = Path(sys.executable).name

    patcher = app_dir / "woodtracker_updater.bat"

    patcher.write_text(f"""@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "APPDIR={app_dir}"
set "EXE={exe_name}"
set "TEMPDIR=%TEMP%\\WoodTrackerUpdate"
set "ZIP=update.zip"

echo === WoodTracker Safe Updater ===

mkdir "%TEMPDIR%" >nul 2>&1
cd /d "%TEMPDIR%"

timeout /t 2 >nul

echo Downloading...
powershell -Command ^
"Invoke-WebRequest '{download_url}' -OutFile '%ZIP%'"

if not exist "%ZIP%" (
    echo ERROR: download failed
    pause
    exit /b
)

echo Extracting...
powershell -Command ^
"Expand-Archive '%ZIP%' 'new' -Force"

if not exist "new\\WoodTracker\\WoodTracker.exe" (
    echo ERROR: invalid ZIP structure
    pause
    exit /b
)

echo Updating files...
xcopy "new\\WoodTracker\\*" "%APPDIR%\\" /E /I /Y >nul

echo Restarting...
start "" "%APPDIR%\\%EXE%"

echo Cleanup...
rmdir /s /q "%TEMPDIR%"
del "%~f0"
""", encoding="utf-8")

    subprocess.Popen(
        ["cmd", "/c", str(patcher)],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    sys.exit(0)








def is_newer(remote, local):
    return tuple(map(int, remote.split("."))) > tuple(map(int, local.split(".")))

SHEET_TEMPLATE_URL = (
    "https://docs.google.com/spreadsheets/d/1r-ViDripw6nRBD0mRsqdhebW3E5UXer6DXU6ekCASuw/copy"
)




BG_MAIN = "#1e2126"
BG_PANEL = "#2b2e33"
FG_TEXT = "#e6e6e6"
ACCENT = "#3fa9f5"
HONEY = "#f4b400"      # miel doré (Google-like)
HONEY_DARK = "#d89b00" # hover / actif





def normalize_sheet_id(value: str) -> str:
    value = value.strip()
    if "/d/" in value:
        try:
            return value.split("/d/")[1].split("/")[0]
        except IndexError:
            return ""
    return value

def find_wow_addon_dir():
    candidates = [
        Path(os.environ.get("PROGRAMFILES", "")) / "World of Warcraft",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "World of Warcraft",
        Path.home() / "Games" / "World of Warcraft",
    ]

    for base in candidates:
        addon = (
            base
            / "_retail_"
            / "Interface"
            / "AddOns"
            / "WoodTracker"
        )
        if (addon / "WoodTracker.toc").exists():
            return str(addon)

    return None


class WoodTrackerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.after(10 * 60 * 1000, self._auto_craft_timer)
        self._craft_cooldown_sec = 120  # 2 minutes
        self._craft_running = False
        self.update_available = False
        self.status_var = tk.StringVar(value="")
        try:
            self.iconbitmap(resource_path("assets/woodtracker.ico"))
        except Exception as e:
            print("Icône non chargée:", e)


        self.recap_labels = {}
        self.main = tk.Frame(self, bg=BG_MAIN)
        self.main.pack(fill="both", expand=True)
        self.title("WoodTracker Client")
        self.geometry("720x420")
        self.resizable(False, False)
        self.configure(bg=BG_MAIN)
        self._wow_opened_at = None
        self.sync_running = False
        self.last_craft_ts = None
        self.last_craft_var = tk.StringVar(value="")
        self.after(1000, self._update_last_craft_label)
        self.had_warning = False
        self.after(500, self._maybe_update_addon)
        self._update_button_shown = False

        self._build_header()
        self._build_content()
        self._build_footer()


        # 🔍 Auto-détection WoW si non configuré
        if not get_wow_addon_dir():
            detected = find_wow_addon_dir()
            if detected:
                set_wow_addon_dir(detected)
                self.log_cb("✔ Dossier WoW détecté automatiquement")
        self.refresh_sync_button()
        if self.is_ready_for_sync():
            self.stop_config_blink()

        if not has_google_account() or not get_sheet_id():
            self.log_cb("ℹ Veuillez configurer votre WoodTracker")
            self.start_config_blink()
        # Auto-sync au démarrage
        self.after(100, self._check_updates_startup)

        # Auto-sync au démarrage (décidé APRÈS le check update)
        def _maybe_autosync():
            if self.is_ready_for_sync() and not self.update_available:
                self.start_sync()

        self.after(1200, _maybe_autosync)
        
        self._wow_was_running = is_wow_alive_via_heartbeat()
        self.after(3000, self._watch_wow_process)

    def _auto_craft_timer(self):
        if self.is_ready_for_sync():
            self.log_cb("⏲️ Recalcul automatique des crafts")
            self.run_craft_cost_calculator()

        # 🔁 relance du timer
        self.after(10 * 60 * 1000, self._auto_craft_timer)


    def open_patchnotes_window(self, data):
        win = tk.Toplevel(self)
        try:
            win.iconbitmap(resource_path("assets/woodtracker.ico"))
        except Exception:
            pass
        win.title(f"Mise à jour v{data['version']}")
        win.resizable(False, False)
        win.configure(bg=BG_MAIN)
        win.transient(self)
        win.grab_set()

        def on_close():
            self.update_button.config(state="normal")
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

        # Titre
        tk.Label(
            win,
            text=f"Patch notes – v{data['version']}",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=16, pady=(16, 8))

        # ⚠ Avertissement addon
        if data.get("addon_updated"):
            tk.Label(
                win,
                text="⚠ Cette mise à jour inclut aussi une mise à jour de l’addon World of Warcraft. \nVous conservez toutefois vos réglages.",
                bg=BG_MAIN,
                fg="#ffb300",
                font=("Segoe UI", 9, "bold"),
                wraplength=500,
                justify="left",
            ).pack(anchor="w", padx=16, pady=(0, 8))

        # Zone texte scrollable
        frame = tk.Frame(win, bg=BG_PANEL)
        frame.pack(fill="both", expand=True, padx=16)

        text = tk.Text(
            frame,
            bg=BG_MAIN,
            fg=FG_TEXT,
            relief="flat",
            font=("Consolas", 9),
            wrap="word",
            height=12,
        )
        text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(frame, command=text.yview)
        scrollbar.pack(side="right", fill="y")
        text.config(yscrollcommand=scrollbar.set)

        text.insert("1.0", data.get("changelog", ""))
        text.configure(state="disabled")

        # Boutons
        btn_frame = tk.Frame(win, bg=BG_MAIN)
        btn_frame.pack(fill="x", padx=16, pady=16)

        tk.Button(
            btn_frame,
            text="❌ Plus tard",
            bg=BG_PANEL,
            fg=FG_TEXT,
            relief="flat",
            command=on_close,
        ).pack(side="right", padx=(8, 0))

        tk.Button(
            btn_frame,
            text="✅ Mettre à jour",
            bg=HONEY,
            fg="#1e2126",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            command=lambda: self._confirm_update(data, win),
        ).pack(side="right")

        win.update_idletasks()
        win.minsize(win.winfo_width(), win.winfo_height())
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        win_w = win.winfo_width()
        win_h = win.winfo_height()

        x = (screen_w // 2) - (win_w // 2)
        y = (screen_h // 2) - (win_h // 2)

        win.geometry(f"+{x}+{y}")


    def _confirm_update(self, data, win):
        win.destroy()

        if data.get("addon_updated"):
            flag = get_appdata_dir() / "update_addon.flag"
            flag.write_text("1")

        launch_patcher(data["zip_url"])



    def _maybe_update_addon(self):
        flag = get_appdata_dir() / "update_addon.flag"
        if not flag.exists():
            return

        try:
            from utils import install_addon
            self.log_cb("📦 Mise à jour de l’addon WoodTracker…")
            install_addon(self.log_cb)
            self.log_cb("✔ Addon mis à jour avec succès")
        except Exception as e:
            self.log_cb(f"❌ Mise à jour addon échouée : {e}")
        finally:
            flag.unlink(missing_ok=True)

    def _watch_wow_process(self):
        wow_running = (
            is_wow_alive_via_heartbeat()
            or is_wow_alive_via_heartbeat()  # fallback sécurité
        )

        # 🎮 WoW vient de s’ouvrir
        if wow_running and not self._wow_was_running:
            self._wow_opened_at = time.time()
            self.log_cb("🎮 World of Warcraft lancé")

        # 🟥 WoW vient de se fermer
        if self._wow_was_running and not wow_running:
            duration = 0
            if self._wow_opened_at:
                duration = time.time() - self._wow_opened_at

            self.log_cb("🎮 World of Warcraft fermé")

            # ⏱️ Évite les faux positifs (crash, refresh rapide, etc.)
            if duration > 10:
                if self.update_available:
                    self.log_cb("🔄 Mise à jour disponible — synchronisation automatique suspendue")
                elif self.is_ready_for_sync():
                    self.log_cb("🔄 Synchronisation automatique après fermeture du jeu")
                    self.start_sync()

            self._wow_opened_at = None

        self._wow_was_running = wow_running
        self.after(3000, self._watch_wow_process)

    
    def _check_updates_startup(self):
        try:
            data = check_update()

            version = data.get("version")
            if not version:
                self.log_cb("❌ version.json invalide")
                return

            self.log_cb(
                f"🧪 Version locale: {APP_VERSION} | distante: {version}"
            )

            if is_newer(version, APP_VERSION):
                self.update_available = True
                self._show_update_button()
                self.log_cb(f"🔄 Mise à jour disponible : v{version}")
                self.log_cb(
                    "ℹ Une mise à jour est disponible — la synchronisation automatique est en pause"
                )
            else:
                self.log_cb("✅ WoodTracker est à jour")

        except Exception as e:
            self.log_cb(f"❌ Update check error: {e}")




    def _show_update_button(self):
        if self._update_button_shown:
            return

        self._update_button_shown = True
        self.update_button.pack(side="right", padx=16)
        self._update_blink_on = False
        self._update_blink_active = True
        self._blink_update_button()



    def _blink_update_button(self):
        if not getattr(self, "_update_blink_active", False):
            return

        self._update_blink_on = not self._update_blink_on
        self.update_button.config(
            bg=HONEY if self._update_blink_on else BG_PANEL
        )

        self.after(500, self._blink_update_button)

        
    def _on_update_click(self):
        self.update_button.config(state="disabled")
        self._update_blink_active = False
        self.update_button.config(bg=BG_PANEL)

        def worker():
            try:
                data = check_update()
                self.after(0, lambda: self.open_patchnotes_window(data))
            except Exception as e:
                self.after(0, lambda: (
                    self.log_cb(f"❌ Update check error: {e}"),
                    self.update_button.config(state="normal")
                ))

        threading.Thread(target=worker, daemon=True).start()




    def install_addon_ui(self):
        self.log_cb("📥 Installation de l’addon WoodTracker…")
        try:
            from utils import install_addon
            path = install_addon(self.log_cb)
            #("✔ Addon installé")
            self.log_cb(f"📂 Addon installé dans : {path}")
            self.refresh_sync_button()
            self.stop_config_blink()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            self.log_cb(f"❌ {e}")
    
    def is_ready_for_sync(self):
        return (
            has_google_account()
            and get_sheet_id()
            and get_wow_addon_dir()
        )


    def choose_wow_addon_dir(self):
        folder = filedialog.askdirectory(
            title="Sélectionnez le dossier WoodTracker (AddOn WoW)"
        )

        if not folder:
            return

        folder = Path(folder)

        # Vérification minimale
        toc = folder / "WoodTracker.toc"
        if not toc.exists():
            messagebox.showerror(
                "Dossier invalide",
                "Ce dossier ne contient pas WoodTracker.toc"
            )
            return

        set_wow_addon_dir(str(folder))
        self.log_cb("✔ Dossier WoW configuré")
        #("✔ Dossier WoW configuré")
        self.refresh_sync_button()
        if self.is_ready_for_sync():
            self.stop_config_blink()

        
    def open_sheet_template(self):
        webbrowser.open(SHEET_TEMPLATE_URL)
    # ======================
    # CONFIG
    # ======================
    def save_config_and_close(self, win):
        raw = self.sheet_var.get()
        sheet_id = normalize_sheet_id(raw)

        if not sheet_id:
            self.config_error_var.set(
                "Veuillez entrer un ID ou une URL valide."
            )
            return

        set_sheet_id(sheet_id)
        self.config_error_var.set("")
        #("✔ Google Sheet configuré")
        self.log_cb("✔ Google Sheet configuré")
        self.refresh_sync_button()
        if has_google_account() and get_sheet_id():
            self.stop_config_blink()
        win.destroy()
        # 🔄 Lancer une synchro automatiquement si tout est prêt
        if self.is_ready_for_sync():
            self.after(200, self.start_sync)

    def open_config_window(self):
        if hasattr(self, "config_window") and self.config_window.winfo_exists():
            self.config_window.focus()
            return

        win = tk.Toplevel(self)
        self.config_window = win

        win.title("Configuration WoodTracker")
        win.resizable(False, False)
        win.configure(bg=BG_MAIN)
        win.transient(self)
        win.grab_set()

        google_header = tk.Frame(win, bg=BG_MAIN)
        google_header.pack(fill="x", padx=16, pady=(16, 8))
        linked = has_google_account()
        tk.Label(
            google_header,
            text="Google",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left")


        btn_google = tk.Button(
            google_header,
            text="🔐 Compte Google lié" if linked else "🔐 Lier mon compte Google",
            bg=HONEY_DARK if linked else HONEY,
            fg=FG_TEXT if linked else "#1e2126",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            state="disabled" if linked else "normal",
            command=self.link_google_account,
        )
        btn_google.pack(side="right")

        self.apply_hover(btn_google, HONEY, HONEY_DARK)

        sheet_header = tk.Frame(win, bg=BG_MAIN)
        sheet_header.pack(fill="x", padx=16, pady=(12, 6))
        tk.Label(
            sheet_header,
            text="Google Sheet",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left")

        generate=tk.Button(
            sheet_header,
            text="🍯 Générer mon Google Sheet",
            bg=HONEY,
            fg="#1e2126",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            command=self.open_sheet_template,
        )
        generate.pack(side="right")

        self.apply_hover(generate, HONEY, HONEY_DARK)

        tk.Label(
            win,
            text="Entrez le lien de votre Google Sheet ou son ID",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=16)

        # Exemple (avec seulement SHEET_ID mis en évidence)
        example_frame = tk.Frame(win, bg=BG_MAIN)
        example_frame.pack(anchor="w", padx=16, pady=(2, 6))

        tk.Label(
            example_frame,
            text="https://docs.google.com/spreadsheets/d/",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Segoe UI", 8),
        ).pack(side="left")

        tk.Label(
            example_frame,
            text="SHEET_ID",
            bg=BG_MAIN,
            fg="#ff5c5c",
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left")

        tk.Label(
            example_frame,
            text="/copy",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Segoe UI", 8),
        ).pack(side="left")

        self.sheet_var = tk.StringVar(value=get_sheet_id() or "")
        self.config_error_var = tk.StringVar(value="")
        entry = tk.Entry(
            win,
            textvariable=self.sheet_var,
            bg=BG_PANEL,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        )
        entry.pack(fill="x", padx=16, pady=(6, 2))


        tk.Label(
            win,
            text="Il vous faut absolument partager votre sheets:\n En haut à droite Partager > Accès général > Limité => Tout les utilisateurs qui ont le lien > Lecteur => éditeur.",
            bg=BG_MAIN,
            fg="#ff5c5c",
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=16)


        wow_header = tk.Frame(win, bg=BG_MAIN)
        wow_header.pack(fill="x", padx=16, pady=(22, 6))

        tk.Label(
            wow_header,
            text="World of Warcraft",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        btn_wow = tk.Button(
            wow_header,
            text="📂 Choisir le dossier WoodTracker",
            bg=HONEY,
            fg="#1e2126",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            command=self.choose_wow_addon_dir,
        )
        btn_wow.pack(side="right")

        self.apply_hover(btn_wow, HONEY, HONEY_DARK)

        tk.Label(
            win,
            text="Choisissez le chemin de votre répertoire wow puis /_retail_/Interface/AddOns/Woodtracker",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=16)


        path = get_wow_addon_dir()
        if path:
            tk.Label(
                win,
                text=f"Dossier actuel : {path}",
                bg=BG_MAIN,
                fg="#9ccc65",
                font=("Segoe UI", 8),
                wraplength=360,
                justify="left",
            ).pack(anchor="w", padx=16, pady=(0, 8))





        tk.Label(
            win,
            textvariable=self.config_error_var,
            bg=BG_MAIN,
            fg="#ff5c5c",
            font=("Segoe UI", 9),
        ).pack(fill="x", padx=16, pady=(0, 10))

        entry.focus_set()
        entry.bind("<Return>", lambda e: self.save_config_and_close(win))
        entry.bind("<Key>", lambda e: self.config_error_var.set(""))


        btn_install = tk.Button(
            wow_header,
            text="📥 Installer l'addon automatiquement",
            bg=HONEY,
            fg="#1e2126",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            command=self.install_addon_ui,
        )
        btn_install.pack(side="right", padx=(0, 8))

        self.apply_hover(btn_install, HONEY, HONEY_DARK)


        btn_frame = tk.Frame(win, bg=BG_MAIN)
        btn_frame.pack(fill="x", padx=16, pady=12)

        register=tk.Button(
            btn_frame,
            text="💾 Enregistrer",
            bg=HONEY,
            fg="#1e2126",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            command=lambda: self.save_config_and_close(win),
        )
        register.pack(side="right")

        self.apply_hover(register, HONEY, HONEY_DARK)

        tk.Button(
            btn_frame,
            text="Fermer",
            bg=BG_PANEL,
            fg=FG_TEXT,
            relief="flat",
            command=win.destroy,
        ).pack(side="right", padx=(0, 8))

        win.update_idletasks()
        win.minsize(win.winfo_width(), win.winfo_height())

    # ======================
    # HEADER
    # ======================
    def _build_header(self):
        
        header = tk.Frame(self.main, bg=BG_PANEL, height=60)
        header.pack(fill="x")

        
        tk.Label(
            header,
            text="WoodTracker",
            bg=BG_PANEL,
            fg=FG_TEXT,
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left", padx=16)

        """self.status_var = tk.StringVar(value="Prêt")

        tk.Label(
            header,
            textvariable=self.status_var,
            bg=BG_PANEL,
            fg=FG_TEXT,
            font=("Segoe UI", 10),
        ).pack(side="right", padx=16)"""

        self.update_button = tk.Button(
            header,
            text="🔄 Mise à jour dispo",
            bg=BG_PANEL,
            fg=FG_TEXT,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            command=self._on_update_click,
        )
        self.update_button.pack(side="right", padx=16)
        self.update_button.pack_forget()  # caché par défaut

        tk.Label(
            header,
            text=f"v{APP_VERSION}",
            bg=BG_PANEL,
            fg="#9e9e9e",
            font=("Segoe UI", 9),
        ).pack(side="right", padx=(0, 12))


        self.config_button = tk.Button(
            header,
            text="⚙ Configuration",
            bg=BG_PANEL,
            fg=FG_TEXT,
            relief="flat",
            font=("Segoe UI", 9),
            command=self.open_config_window,
        )
        self.config_button.place(relx=0.5, rely=0.5, anchor="center")


    # ======================
    # CONTENT
    # ======================
    def _build_content(self):
        content = tk.Frame(self.main, bg=BG_MAIN)
        content.pack(fill="both", expand=True)
        content.pack_propagate(False)


        left_container = tk.Frame(content, bg=BG_PANEL)
        left_container.pack(side="left", fill="y", padx=(0, 10))

        canvas = tk.Canvas(
            left_container,
            bg=BG_PANEL,
            highlightthickness=0,
            width=260,
        )
        canvas.pack(side="left", fill="y")







        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            

        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")

        left_container.bind("<Enter>", _bind_mousewheel)
        left_container.bind("<Leave>", _unbind_mousewheel)

        self.left_panel = tk.Frame(canvas, bg=BG_PANEL)
        canvas.create_window((0, 0), window=self.left_panel, anchor="nw")

        tk.Label(
            self.left_panel,
            text="Récap bois",
            bg=BG_PANEL,
            fg=FG_TEXT,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 6))

        # En-tête colonnes
        header_row = tk.Frame(self.left_panel, bg=BG_PANEL)
        header_row.pack(fill="x", padx=12, pady=(0, 6))

        tk.Label(header_row, bg=BG_PANEL, width=2).pack(side="left")
        tk.Label(header_row, bg=BG_PANEL, width=6).pack(side="left")

        tk.Label(
            header_row,
            text="Total",
            bg=BG_PANEL,
            fg=FG_TEXT,
            width=6,
            anchor="e",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(6, 8))

        tk.Label(
            header_row,
            text="Objectif",
            bg=BG_PANEL,
            fg=FG_TEXT,
            width=10,
            anchor="e",   # 👈 alignement à droite
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right")  # 👈 IMPORTANT


        for ext in EXTENSION_ORDER:
            self._add_placeholder_recap(ext)

        self.left_panel.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        # Logs
        self.right_panel = tk.Frame(content, bg=BG_PANEL)
        self.right_panel.pack(side="right", fill="both", expand=True)

        tk.Label(
            self.right_panel,
            text="Logs",
            bg=BG_PANEL,
            fg=FG_TEXT,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 6))

        self.log_text = tk.Text(
            self.right_panel,
            bg=BG_MAIN,
            fg=FG_TEXT,
            relief="flat",
            font=("Consolas", 9),
            wrap="word",
        )
        self.log_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.log_text.configure(state="disabled")


    def _add_placeholder_recap(self, key):
        row = tk.Frame(self.left_panel, bg=BG_PANEL)
        row.pack(fill="x", padx=12, pady=4)

        # --- Icône ---
        icon_label = tk.Label(row, bg=BG_PANEL)
        icon_label.pack(side="left", padx=(0, 6))

        icon_image = None
        icon_path = resource_path(f"icons/{key}.png")

        if os.path.exists(icon_path):
            try:
                pil_img = Image.open(icon_path)
                pil_img = pil_img.resize((18, 18), Image.LANCZOS)
                icon_image = ImageTk.PhotoImage(pil_img)
                icon_label.config(image=icon_image)
            except Exception as e:
                if "403" in str(e):
                    self.log_cb(
                        "❌ Accès refusé au Google Sheet.\n"
                        "Vérifiez :\n"
                        "• que vous avez les droits d’édition\n"
                        "• que la feuille n’est pas protégée\n"
                        "• que le Google Sheet est bien le vôtre"
                    )
                else:
                    self.log_cb(f"❌ {e}")

        # --- Nom ---
        tk.Label(
            row,
            text=key,
            bg=BG_PANEL,
            fg=FG_TEXT,
            width=6,
            anchor="w",
        ).pack(side="left")

        # --- Total ---
        total_label = tk.Label(
            row,
            text="0",
            bg=BG_PANEL,
            fg=FG_TEXT,
            width=6,
            anchor="e",
        )
        total_label.pack(side="left", padx=(6, 8))

        # --- Objectif ---
        objectif_label = tk.Label(
            row,
            text="0 / 0",
            bg=BG_PANEL,
            fg=FG_TEXT,
            width=10,
            anchor="e",
        )
        objectif_label.pack(side="right")

        # ✅ Création UNIQUE de la structure
        self.recap_labels[key] = {
            "total": total_label,
            "objectif": objectif_label,
            "icon": icon_label,
            "icon_image": icon_image,  # 🔒 référence conservée
        }


    # ======================
    # FOOTER
    # ======================
    def _build_footer(self):
        footer = tk.Frame(self.main, bg=BG_MAIN)
        footer.pack(fill="x", padx=12, pady=(6, 10))

        # Barre de progression
        self.progress = ttk.Progressbar(
            footer,
            mode="indeterminate",
            length=400
        )
        self.progress.pack(fill="x", pady=(0, 8))

        # Conteneur libre
        bottom = tk.Frame(footer, bg=BG_MAIN, height=60)
        bottom.pack(fill="x")
        bottom.pack_propagate(False)

        # =========================
        # HV à gauche
        # =========================
        left = tk.Frame(bottom, bg=BG_MAIN, width=220, height=50)
        left.place(x=50, y=18)
        left.pack_propagate(False)

        tk.Button(
            left,
            text="🐻 Mise à jour HV",
            bg=BG_PANEL,
            fg=FG_TEXT,
            relief="flat",
            font=("Segoe UI", 9),
            command=self.run_craft_cost_calculator,
        ).pack(anchor="w")

        label = tk.Label(
            left,
            textvariable=self.last_craft_var,
            bg=BG_MAIN,
            fg="#9e9e9e",
            font=("Segoe UI", 8, "italic"),
            anchor="w",
        )

        label.place(x=8, y=26)



        # =========================
        # SYNCHRO CENTRÉ (FORCÉ)
        # =========================
        self.sync_button = tk.Button(
            bottom,
            text="Synchroniser",
            bg=HONEY,
            fg="#1e2126",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            state="normal" if self.is_ready_for_sync() else "disabled",
            command=self.start_sync,
        )
        self.apply_hover(self.sync_button, HONEY, HONEY_DARK)

        # 💥 CENTRAGE ABSOLU
        self.sync_button.place(relx=0.5, y=10, anchor="n")

        # =========================
        # BDD Blizzard
        # =========================
        self.bdd_button = tk.Button(
            footer,
            text="🔄 Actualiser la BDD Blizzard",
            bg=BG_PANEL,
            fg=FG_TEXT,
            relief="flat",
            font=("Segoe UI", 9),
            state="normal" if self.is_ready_for_sync() else "disabled",
            command=self.start_bdd_blizzard,
        )
        self.bdd_button.pack(pady=(6, 0))




       
    # ======================
    # LOGIC
    # ======================
    def run_craft_cost_calculator(self, force=False):
        """
        Lance CraftCostCalculator avec cooldown intelligent
        """

        now = time.time()

        # ⛔ déjà en cours
        if self._craft_running:
            self.log_cb("⏳ Calcul déjà en cours")
            return

        self._craft_running = True
        self.log_cb("🧮 Calcul des coûts de craft…")

        def worker():
            try:
                run_craft_cost(self.log_cb)
            finally:
                self.after(0, self._on_craft_cost_done)

        threading.Thread(target=worker, daemon=True).start()


    def _on_craft_cost_done(self):
        self.last_craft_ts = time.time()
        self._craft_running = False
        self.log_cb("✔ Calcul des crafts terminé")


    def _update_last_craft_label(self):
        if not self.last_craft_ts:
            self.last_craft_var.set("")
        else:
            delta = int(time.time() - self.last_craft_ts)

            if delta < 60:
                txt = f"Dernière MAJ {delta} s"
            elif delta < 3600:
                txt = f"Dernière MAJ  {delta // 60} min"
            else:
                txt = f"Dernière MAJ  {delta // 3600} h"

            self.last_craft_var.set(txt)

        self.after(1000, self._update_last_craft_label)


    def apply_hover(self, widget, normal, hover):
        widget.bind("<Enter>", lambda e: widget.config(bg=hover))
        widget.bind("<Leave>", lambda e: widget.config(bg=normal))
    def log_cb(self, msg: str):
        def _append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

            # status text (si le label existe)
            if hasattr(self, "status_var"):
                self.status_var.set(msg)

        # Toujours repasser par le thread UI
        self.after(0, _append)
        

    def start_config_blink(self):
        if getattr(self, "_blink_active", False):
            return
        self._blink_on = False
        self._blink_active = True
        self._blink_config()

    def stop_config_blink(self):
        self._blink_active = False
        self.config_button.config(bg=BG_PANEL)

    def _blink_config(self):
        if not self._blink_active:
            return

        self._blink_on = not self._blink_on
        self.config_button.config(
            bg=HONEY if self._blink_on else BG_PANEL
        )

        self.after(500, self._blink_config)

    def progress_cb(self, value):
        pass

    def link_google_account(self):
        self.log_cb("Connexion au compte Google requise…")
        try:
            # Déclenche OAuth volontairement
            from google_oauth import get_gspread_client
            get_gspread_client()
            self.log_cb("✔ Compte Google lié avec succès")
            #("✔ Compte Google lié")
        except Exception as e:
            msg = str(e)

            if "invalid_grant" in msg or "expired" in msg:
                self.log_cb(
                    "❌ Connexion Google expirée\n"
                    "👉 Allez dans Configuration > Lier le compte Google"
                )

            elif "403" in msg:
                self.log_cb(
                    "❌ Accès refusé au Google Sheet.\n"
                    "Vérifiez :\n"
                    "• que vous avez les droits d’édition\n"
                    "• que la feuille n’est pas protégée\n"
                    "• que le Google Sheet est bien le vôtre"
                )

            else:
                self.log_cb(f"❌ {e}")
        if has_google_account() and get_sheet_id():
            self.stop_config_blink()
            self.refresh_sync_button()

    def refresh_sync_button(self):
        state = "normal" if self.is_ready_for_sync() else "disabled"
        self.sync_button.config(state=state)
        if hasattr(self, "bdd_button"):
            self.bdd_button.config(state=state)
    def start_bdd_blizzard(self):
        if self.sync_running:
            return

        if not has_google_account():
            self.log_cb("🔐 Liez d’abord votre compte Google")
            return

        if not get_sheet_id():
            self.log_cb("⚙ Configurez d’abord votre Google Sheet")
            return

        self.sync_running = True
        self.sync_button.config(state="disabled")
        self.progress["value"] = 0
        self.log_cb("— Mise à jour de la BDD Blizzard —")
        self.bdd_button.config(text="⏳ Mise à jour en cours…", state="disabled")
        self.progress.config(mode="indeterminate")
        self.progress.start(10)

        threading.Thread(
            target=self._run_bdd_blizzard_thread,
            daemon=True,
        ).start()

    def _run_bdd_blizzard_thread(self):
        try:
            sync_bdd_blizzard(self.log_cb)
            #("✔ BDD Blizzard mise à jour")
        except Exception as e:
            if "403" in str(e):
                self.log_cb(
                    "❌ Accès refusé au Google Sheet.\n"
                    "Vérifiez vos droits d’édition."
                )
            else:
                self.log_cb(f"❌ {e}")
        finally:
            self.progress.stop()
            self.progress.config(mode="determinate")
            self.progress["value"] = 0

            self.sync_running = False
            self.bdd_button.config(
                text="🔄 Actualiser la BDD Blizzard",
                state="normal"
            )
            self.refresh_sync_button()

            self.log_cb("🧮 Recalcul des crafts après MAJ BDD")
            self.run_craft_cost_calculator(force=True)


    def start_sync(self):
        if not get_wow_addon_dir():
            #("📂 Configurez le dossier World of Warcraft")
            self.log_cb("📂 Dossier WoW non configuré")
            return

        if not has_google_account():
            #("🔐 Liez d’abord votre compte Google")
            self.log_cb("🔐 Compte Google non lié")
            return
        self.log_cb("— Nouvelle synchronisation —")
        if not get_sheet_id():
            #("⚙ Configurez d’abord votre Google Sheet")
            self.log_cb("\nImportant :\nMerci de vérifier que ce Google Sheet est bien accessible\ndepuis votre compte Google (droits d’édition)\n En haut à droite Partager > Accès général > Limité -> Tout les utilisateurs qui ont le lien > Lecteur -> éditeur.")
            return
        if self.sync_running:
            return


        self.sync_running = True

        # 🔒 Désactiver les boutons
        self.sync_button.config(text="⏳ Synchronisation…", state="disabled")
        self.bdd_button.config(state="disabled")

        # 🔄 Progress indéterminée
        self.progress.config(mode="indeterminate")
        self.progress.start(10)
        self.progress["value"] = 0
        self.log_text.configure(state="normal")
        self.log_text.configure(state="disabled")

        threading.Thread(
            target=self._run_sync_thread,
            daemon=True,
        ).start()

    def _run_sync_thread(self):
        try:
            totals = run_sync(self.log_cb, self.progress_cb)
            if totals:
                self.update_recap(totals)
                # Résumé des valeurs non nulles
                self.log_cb("📊 Récapitulatif (valeurs non nulles) :")

                for key, data in totals.items():
                    total = data.get("total", 0)
                    objectif = data.get("objectif", 0)

                    if objectif > 0:
                        self.log_cb(f"• {key} : {total} / {objectif}")
            #("✔ Synchronisation terminée")
        except Exception as e:
            if "403" in str(e):
                self.log_cb(
                    "❌ Accès refusé au Google Sheet.\n"
                    "Vérifiez :\n"
                    "• que vous avez les droits d’édition\n"
                    "• que la feuille n’est pas protégée\n"
                    "• que le Google Sheet est bien le vôtre"
                )
            else:
                self.log_cb(f"❌ {e}")
        finally:
            self.progress.stop()
            self.progress.config(mode="determinate")
            self.progress["value"] = 0

            self.sync_running = False

            # 🔓 Réactiver les boutons
            self.sync_button.config(text="Synchroniser")
            self.refresh_sync_button()

    def update_recap(self, totals):
        for key, data in totals.items():
            if key not in self.recap_labels:
                continue

            total = data["total"]
            objectif = data["objectif"]

            labels = self.recap_labels[key]
            labels["total"].config(text=str(total))
            labels["objectif"].config(text=f"{total} / {objectif}")

            if total >= objectif and objectif > 0:
                labels["objectif"].config(fg="#4caf50")
            else:
                labels["objectif"].config(fg=FG_TEXT)


if __name__ == "__main__":
    app = WoodTrackerGUI()
    app.mainloop()
