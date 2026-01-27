-- =========================================================
-- WoodTracker_AHBridge.lua
-- =========================================================

WoodTracker_AH_DB = WoodTracker_AH_DB or {}

WoodTracker_AH_State = WoodTracker_AH_State or {
  scanning = false,
  total = 0,
  current = 0,
}

local ADDON_NAME = "WoodTracker_AHBridge"
local SCAN_DELAY = 0.05 -- 50 ms entre items

local queue = {}
local index = 1

-- =========================================================
-- Utils : merge + dedupe
-- =========================================================

local function BuildScanQueue()
  local seen = {}
  local result = {}

  local function add(tbl)
    if type(tbl) ~= "table" then return end
    for _, id in ipairs(tbl) do
      if type(id) == "number" and not seen[id] then
        seen[id] = true
        table.insert(result, id)
      end
    end
  end

  add(WoodTracker_DecorItemIDs)
  add(WoodTracker_ComponentItemIDs)

  return result
end

-- =========================================================
-- Scan AH (PUBLIC)
-- =========================================================

function WoodTracker_StartAHScan()
  -- sécurité anti double scan
  if WoodTracker_AH_State.scanning then
    print("⚠ Scan AH déjà en cours")
    return
  end

  if not Auctionator or not Auctionator.API or not Auctionator.API.v1 then
    print(" Auctionator API introuvable")
    return
  end

  if type(WoodTracker_DecorItemIDs) ~= "table" then
    print(" WoodTracker_DecorItemIDs introuvable")
    return
  end

  queue = BuildScanQueue()
  index = 1

  WoodTracker_AH_State.scanning = true
  WoodTracker_AH_State.total = #queue
  WoodTracker_AH_State.current = 0

  print(" WoodTracker : scan AH de", #queue, "items")

  C_Timer.NewTicker(SCAN_DELAY, function(ticker)
    local itemID = queue[index]
    if not itemID then
      ticker:Cancel()
      WoodTracker_AH_State.scanning = false
      print(" Scan AH terminé")
      return
    end

    local price = Auctionator.API.v1.GetAuctionPriceByItemID(
      ADDON_NAME,
      itemID
    )

    WoodTracker_AH_DB[itemID] = {
      price = (type(price) == "number" and price > 0) and price or 0,
      timestamp = time(),
    }

    WoodTracker_AH_State.current = index
    index = index + 1
  end)
end
