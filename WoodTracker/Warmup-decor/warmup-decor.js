#!/usr/bin/env node

/* ===========================
   CONFIG
=========================== */
import "dotenv/config";
import fs from "fs";

const CONCURRENCY_LIMIT = 2;
const OUTPUT_FILE = "decor.json";

const CLIENT_ID = process.env.BLIZZARD_CLIENT_ID;
const CLIENT_SECRET = process.env.BLIZZARD_CLIENT_SECRET;

if (!CLIENT_ID || !CLIENT_SECRET) {
  console.error("❌ Missing BLIZZARD_CLIENT_ID or BLIZZARD_CLIENT_SECRET");
  process.exit(1);
}


function normalize(str) {
  return str
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

/* ===========================
   METIER (FOURNI)
=========================== */

function getWoodCount(recipe, tierName) {
  if (!recipe || !tierName) return 0;

  const WOOD_BY_TIER = [
    { key: "classique", id: 245586 },
    { key: "outreterre", id: 242691 },
    { key: "norfendre", id: 251762 },
    { key: "cataclysm", id: 251764 },
    { key: "pandarie", id: 251763 },
    { key: "draenor", id: 251766 },
    { key: "legion", id: 251767 },
    { key: "kul tiras", id: 251768 },
    { key: "zandalar", id: 251768 },
    { key: "ombreterre", id: 251772 },
    { key: "iles aux dragons", id: 251773 },
    { key: "khaz algar", id: 248012 }
  ];

  const tierNorm = normalize(tierName);
  const woodId = WOOD_BY_TIER.find(w => tierNorm.includes(w.key))?.id;
  if (!woodId) return 0;

  let total = 0;

  if (Array.isArray(recipe.reagents)) {
    for (const r of recipe.reagents) {
      if (r.reagent?.id === woodId) {
        total += r.quantity || 0;
      }
    }
  }

  if (Array.isArray(recipe.reagent_slots)) {
    for (const slot of recipe.reagent_slots) {
      if (!Array.isArray(slot.reagents)) continue;

      const match = slot.reagents.find(r => r.reagent?.id === woodId);
      if (match) {
        return slot.quantity || 0;
      }
    }
  }

  return total;
}

/* ===========================
   FETCH BLIZZARD (FOURNI)
=========================== */

async function fetchBlizzard(path, token, retries = 3) {
  const res = await fetch(
    `https://eu.api.blizzard.com${path}?namespace=static-eu&locale=fr_FR`,
    {
      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  );

  if (!res.ok) {
    if (retries > 0) {
      // backoff progressif
      await new Promise(r => setTimeout(r, 400 * (4 - retries)));
      return fetchBlizzard(path, token, retries - 1);
    }
    throw new Error(`Blizzard API error ${res.status} on ${path}`);
  }

  return res.json();
}

/* ===========================
   AUTH
=========================== */

async function getAccessToken() {
  const res = await fetch("https://oauth.battle.net/token", {
    method: "POST",
    headers: {
      Authorization:
        "Basic " +
        Buffer.from(`${CLIENT_ID}:${CLIENT_SECRET}`).toString("base64"),
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body: "grant_type=client_credentials"
  });

  if (!res.ok) {
    throw new Error("OAuth token error");
  }

  const data = await res.json();
  return data.access_token;
}

/* ===========================
   CONCURRENCY POOL
=========================== */

async function runWithConcurrency(tasks, limit) {
  const results = [];
  let index = 0;

  async function worker() {
    while (index < tasks.length) {
      const current = index++;
      try {
        results[current] = await tasks[current]();
      } catch (e) {
        results[current] = null;
      }
    }
  }

  const workers = Array.from({ length: limit }, worker);
  await Promise.all(workers);
  return results;
}

/* ===========================
   EXTRACTION
=========================== */

async function fetchProfessions(token) {
  const data = await fetchBlizzard("/data/wow/profession/index", token);
  return data.professions || [];
}

async function fetchProfessionTiers(token, professionId) {
  const data = await fetchBlizzard(
    `/data/wow/profession/${professionId}`,
    token
  );
  return data.skill_tiers || [];
}

async function fetchTierRecipes(token, professionId, tierId) {
  const data = await fetchBlizzard(
    `/data/wow/profession/${professionId}/skill-tier/${tierId}`,
    token
  );
  return data.categories?.flatMap(c => c.recipes || []) || [];
}

async function fetchRecipe(token, recipeId) {
  return fetchBlizzard(`/data/wow/recipe/${recipeId}`, token);
}

/* ===========================
   MAIN
=========================== */

(async function main() {
  const start = Date.now();
  let errorCount = 0;
  let recipeCount = 0;

  console.log("▶ Auth Blizzard...");
  const token = await getAccessToken();

  console.log("▶ Fetch professions...");
  const professions = await fetchProfessions(token);

  const output = [];

  for (const prof of professions) {
    console.log(`\n🛠 ${prof.name}`);

    let tiers;
    try {
      tiers = await fetchProfessionTiers(token, prof.id);
    } catch (e) {
      console.warn(`  ⚠ tiers failed`);
      errorCount++;
      continue;
    }

    for (const tier of tiers) {
      console.log(`  ▸ ${tier.name}`);

      let recipes;
      try {
        recipes = await fetchTierRecipes(token, prof.id, tier.id);
      } catch (e) {
        console.warn(`    ⚠ recipes failed`);
        errorCount++;
        continue;
      }

      const tasks = recipes.map(r => async () => {
        try {
          const recipe = await fetchRecipe(token, r.id);
          recipeCount++;

          const wood = getWoodCount(recipe, tier.name);
          if (wood > 0) {
            return {
              name: recipe.name,
              wood
            };
          }
        } catch {
          errorCount++;
        }
        return null;
      });

      const results = await runWithConcurrency(
        tasks,
        CONCURRENCY_LIMIT
      );

      const items = results.filter(Boolean);
      if (items.length > 0) {
        output.push({
          professionId: prof.id,
          profession: prof.name,
          tierId: tier.id,
          tier: tier.name,
          items
        });
      }
    }
  }

  

    fs.writeFileSync(
    OUTPUT_FILE,
    JSON.stringify(output, null, 2),
    "utf8"
    );

  const duration = ((Date.now() - start) / 1000).toFixed(1);

  console.log("\n==============================");
  console.log("✅ TERMINÉ");
  console.log(`⏱ Durée       : ${duration}s`);
  console.log(`📦 Recettes   : ${recipeCount}`);
  console.log(`❌ Erreurs    : ${errorCount}`);
  console.log(`📄 Fichier    : ${OUTPUT_FILE}`);
  console.log("==============================");
})().catch(err => {
  console.error("💥 Fatal error", err);
  process.exit(1);
});
