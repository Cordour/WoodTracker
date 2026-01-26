import { google } from "googleapis";
import fs from "fs";

// ⚠️ réutilise EXACTEMENT les mêmes credentials OAuth que ton app Python
// ex: token.json généré lors du login Google
const auth = new google.auth.OAuth2(
  "815900454490-iqujei71et09r9dvl8tqvfbv6giojicv.apps.googleusercontent.com",
  "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",
  "http://localhost"
);

// Charge le token existant
auth.setCredentials(
  JSON.parse(fs.readFileSync("google-token.json", "utf8"))
);

const sheets = google.sheets({ version: "v4", auth });

const SHEET_ID = "TON_SHEET_ID";

async function test() {
  const rows = [
    [
      null,
      null,
      "TEST",
      "Node.js",
      "Objet de test",
      42,
      '=HYPERLINK("https://www.wowhead.com/fr","Wowhead 🔍")'
    ]
  ];

  await sheets.spreadsheets.values.update({
    spreadsheetId: SHEET_ID,
    range: "BDD!A7:G7",
    valueInputOption: "USER_ENTERED",
    requestBody: { values: rows }
  });

  console.log("✅ Écriture Sheets OK");
}

test().catch(console.error);
