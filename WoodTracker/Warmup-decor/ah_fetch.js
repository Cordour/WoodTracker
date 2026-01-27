#!/usr/bin/env node

import fs from "fs";
import { getAccessToken } from "./blizzard_auth.js";

/* ===========================
   AH BLIZZARD
=========================== */

async function fetchAuctionHouse(token) {
  const res = await fetch(
    "https://eu.api.blizzard.com/data/wow/connected-realm/1080/auctions?namespace=dynamic-eu&locale=fr_FR",
    {
      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  );

  if (!res.ok) {
    throw new Error(`AH équipements fetch failed (${res.status})`);
  }

  return res.json();
}

async function fetchCommodityAH(token) {
  const res = await fetch(
    "https://eu.api.blizzard.com/data/wow/auctions/commodities?namespace=dynamic-eu&locale=fr_FR",
    {
      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  );

  if (!res.ok) {
    throw new Error(`AH commodities fetch failed (${res.status})`);
  }

  return res.json();
}

function extractMinPrices(ahData) {
  const prices = {};

  for (const auction of ahData.auctions) {
    const itemId = auction.item?.id;
    if (!itemId) continue;

    // 🔒 IGNORER tout ce qui n'a pas de buyout
    if (!auction.buyout || auction.buyout <= 0) continue;

    // 💰 buyout est TOUJOURS en copper
    const priceGold = Math.floor(auction.buyout / 10000);

    if (!prices[itemId] || priceGold < prices[itemId]) {
      prices[itemId] = priceGold;
    }
  }

  return prices;
}


function extractCommodityPrices(data) {
  const prices = {};

  for (const entry of data.auctions) {
    const itemId = entry.item?.id;
    const unitPrice = entry.unit_price;

    if (!itemId || !unitPrice) continue;

    if (!prices[itemId] || unitPrice < prices[itemId]) {
      prices[itemId] = unitPrice;
    }
  }

  return prices;
}

function writeAhCache(pricesCommo, pricesServer) {
  const output = {
    components: {},
    server: {}
  };

  for (const [itemId, price] of Object.entries(pricesCommo)) {
    output.components[itemId] = { price };
  }

  for (const [itemId, price] of Object.entries(pricesServer)) {
    output.server[itemId] = { price };
  }

  fs.writeFileSync(
    "ah_cache.json",
    JSON.stringify(output, null, 2),
    "utf8"
  );

  console.log(
    `💾 ah_cache.json généré (${Object.keys(output.components).length} commodities, ${Object.keys(output.server).length} server items)`
  );
}



/* ===========================
   MAIN
=========================== */

async function main() {
  console.log("▶ Auth Blizzard...");
  const token = await getAccessToken();

  console.log("▶ Fetch AH équipements (connected realm)...");
  const ahEquip = await fetchAuctionHouse(token);

  console.log("▶ Fetch AH commodities (régional)...");
  const ahCommo = await fetchCommodityAH(token);

  console.log("▶ Extraction des prix...");
  const pricesEquip = extractMinPrices(ahEquip);
  const pricesCommo = extractCommodityPrices(ahCommo);

  writeAhCache(pricesCommo, pricesEquip);
}


main().catch(err => {
  console.error("💥 AH fetch error:", err);
  process.exit(1);
});
