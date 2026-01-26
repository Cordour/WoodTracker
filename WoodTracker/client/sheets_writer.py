from typing import Dict, Optional
from google_oauth import get_gspread_client
import unicodedata


def normalize(text: str) -> str:
    return (
        unicodedata.normalize("NFKC", text)
        .strip()
        .casefold()
    )


class RentabiliteSheetWriter:
    def __init__(
        self,
        spreadsheet_id: str,
        worksheet_name: str = "Rentabilité",
    ):
        client = get_gspread_client()
        self.spreadsheet = client.open_by_key(spreadsheet_id)
        self.sheet = self.spreadsheet.worksheet(worksheet_name)
        self.worksheet_name = worksheet_name

    def write_po_per_wood(
        self,
        values_by_name: Dict[str, Optional[int]],
    ):
        normalized_values = {
            normalize(k): v for k, v in values_by_name.items()
        }

        names = self.sheet.col_values(4)  # colonne D

        print(f"🔎 {len(names)-1} lignes analysées")

        updated = 0

        for row_idx, raw_name in enumerate(names, start=1):
            if row_idx == 1 or not raw_name:
                continue

            key = normalize(raw_name)
            if key not in normalized_values:
                continue

            value = normalized_values[key]
            print(f"✅ Match décor '{raw_name}' → {value}")

            cell_value = "" if value is None else int(value)

            # ✅ ÉCRITURE CORRECTE
            self.sheet.update_acell(
                f"F{row_idx}",
                cell_value,
            )

            updated += 1

        if updated == 0:
            print("⚠️ Aucun décor matché — rien à écrire")
        else:
            print(f"✅ {updated} cellule(s) mise(s) à jour")

