#!/usr/bin/env node

import "dotenv/config";
import fs from "fs";

const CLIENT_ID = process.env.BLIZZARD_CLIENT_ID;
const CLIENT_SECRET = process.env.BLIZZARD_CLIENT_SECRET;

if (!CLIENT_ID || !CLIENT_SECRET) {
  console.error("❌ Missing BLIZZARD_CLIENT_ID or BLIZZARD_CLIENT_SECRET");
  process.exit(1);
}

const OUTPUT_FILE = "recipes.json";
const RECIPE_CACHE_FILE = "recipe_cache.json";
const CONCURRENCY_LIMIT = 16;

/* ===========================
   CACHE
=========================== */

let RECIPE_CACHE = {};
if (fs.existsSync(RECIPE_CACHE_FILE)) {
  try {
    RECIPE_CACHE = JSON.parse(fs.readFileSync(RECIPE_CACHE_FILE, "utf8"));
    console.log(`📦 Cache chargé (${Object.keys(RECIPE_CACHE).length}) recettes`);
  } catch {
    console.warn("⚠ Cache corrompu, ignoré");
    RECIPE_CACHE = {};
  }
}

/* ===========================
   BLIZZARD
=========================== */

async function fetchBlizzard(path, token, retries = 3) {
  const res = await fetch(
    `https://eu.api.blizzard.com${path}?namespace=static-eu&locale=fr_FR`,
    {
      headers: { Authorization: `Bearer ${token}` }
    }
  );

  if (!res.ok) {
    if (retries > 0) {
      await new Promise(r => setTimeout(r, 300 * (4 - retries)));
      return fetchBlizzard(path, token, retries - 1);
    }
    throw new Error(`Blizzard API error ${res.status}`);
  }

  return res.json();
}

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

  const data = await res.json();
  return data.access_token;
}

/* ===========================
   CONCURRENCY
=========================== */

async function runWithConcurrency(tasks, limit) {
  let index = 0;

  async function worker() {
    while (index < tasks.length) {
      const i = index++;
      await tasks[i]();
    }
  }

  await Promise.all(Array.from({ length: limit }, worker));
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
  const token = await getAccessToken();
  const professions = await fetchProfessions(token);

  const recipesOutput = {};
  let total = 0;

  for (const prof of professions) {
    console.log(`🛠 ${prof.name}`);

    const tiers = await fetchProfessionTiers(token, prof.id);

    for (const tier of tiers) {
      const recipes = await fetchTierRecipes(token, prof.id, tier.id);

      const tasks = recipes.map(r => async () => {
        let recipe;

        if (RECIPE_CACHE[r.id]) {
          recipe = RECIPE_CACHE[r.id];
        } else {
          recipe = await fetchRecipe(token, r.id);
          RECIPE_CACHE[r.id] = recipe;
        }

        total++;

        const reagents = [];

        // 🔹 reagents fixes
        if (Array.isArray(recipe.reagents)) {
          for (const r of recipe.reagents) {
            if (r.reagent?.id && r.quantity > 0) {
              reagents.push({
                itemID: r.reagent.id,
                qty: r.quantity,
                optional: false
              });
            }
          }
        }

        // 🔹 reagent slots (choix)
        if (Array.isArray(recipe.reagent_slots)) {
          for (const slot of recipe.reagent_slots) {
            if (!Array.isArray(slot.reagents)) continue;

            for (const r of slot.reagents) {
              if (r.reagent?.id) {
                reagents.push({
                  itemID: r.reagent.id,
                  qty: slot.quantity || 1,
                  optional: true
                });
              }
            }
          }
        }

        if (reagents.length === 0) return;

        recipesOutput[recipe.name] = {
          profession: prof.name,
          tier: tier.name,
          craftedItemID: recipe.crafted_item?.id ?? null,
          reagents
        };
      });

      await runWithConcurrency(tasks, CONCURRENCY_LIMIT);
    }
  }

  fs.writeFileSync(RECIPE_CACHE_FILE, JSON.stringify(RECIPE_CACHE), "utf8");
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(recipesOutput, null, 2), "utf8");

  console.log("\n==============================");
  console.log("✅ RECIPES OK");
  console.log(`📦 Total recettes traitées : ${total}`);
  console.log(`📄 Fichier : ${OUTPUT_FILE}`);
  console.log("==============================");
})().catch(err => {
  console.error("💥 Fatal error", err);
  process.exit(1);
});
