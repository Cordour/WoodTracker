-- =========================
-- Données importées
-- =========================
local objectifs = WoodTracker_Objectifs
if not objectifs then return end

local dataDirty = false
local IsLoggedIn = false
local HideZero = true
local lastExportTime = time()
local ExportToSavedVariables
local WoodTracker_AH_StatusText = nil
local IsLoggingOut = false
local CachedTotals = {}







if not WoodTracker_AH or not WoodTracker_AH.prices then
  print("⚠ AH Bridge not ready")
end


WoodTrackerDB = WoodTrackerDB or {
    fadeOnFly = true,
    flyAlpha = 0.4,
}

-- =========================
-- Utils
-- =========================
-- TOTAL = inventaire + banque + banque de bataillon
local function GetTotalItemCount(itemID)
    return C_Item.GetItemCount(itemID, true, true, true, true) or 0
end
local function ComputeChecksum(tbl)
    local sum = 0
    for _, v in pairs(tbl) do
        sum = sum + (v or 0)
    end
    return sum
end

local FadeDriver = CreateFrame("Frame")
local ActiveFades = {}

local function Fade(frame, fromAlpha, toAlpha, duration)
    frame:SetAlpha(fromAlpha)
    ActiveFades[frame] = {
        from = fromAlpha,
        to = toAlpha,
        time = 0,
        duration = duration
    }

    FadeDriver:SetScript("OnUpdate", function(_, elapsed)
        for f, d in pairs(ActiveFades) do
            d.time = d.time + elapsed
            local t = math.min(d.time / d.duration, 1)
            local p = t * t * (3 - 2 * t) -- SmoothStep
            local a = d.from + (d.to - d.from) * p
            f:SetAlpha(a)

            if p >= 1 then
                f:SetAlpha(d.to)
                ActiveFades[f] = nil
            end
        end

        if not next(ActiveFades) then
            FadeDriver:SetScript("OnUpdate", nil)
        end
    end)
end


-- =========================
-- Watcher inventaire
-- =========================
local syncWatcher = CreateFrame("Frame")
syncWatcher:RegisterEvent("BAG_UPDATE_DELAYED")

local exportTimer

syncWatcher:SetScript("OnEvent", function()
    if IsLoggingOut then return end
    dataDirty = true
end)


-- =========================
-- Frame principale
-- =========================
local frame = CreateFrame("Frame", "WoodTrackerFrame", UIParent)
frame:SetSize(320, 200)
frame:SetPoint("CENTER")
frame:SetMovable(true)
frame:EnableMouse(true)
frame:RegisterForDrag("LeftButton")
frame:SetScript("OnDragStart", frame.StartMoving)
frame:SetScript("OnDragStop", frame.StopMovingOrSizing)
frame:Hide()

frame.bg = frame:CreateTexture(nil, "BACKGROUND")
frame.bg:SetAllPoints()
frame.bg:SetColorTexture(0, 0, 0, 0.7)


-- =========================
-- Opacité vol
-- =========================


local function IsActuallyFlying()
    return IsFlying()
end



local lastFlyingState

local function UpdateOpacity(force)
    if not frame or not frame:IsShown() then return end

    local flying = IsActuallyFlying()
    if not force and flying == lastFlyingState then return end
    lastFlyingState = flying

    local targetAlpha = 1
    if WoodTrackerDB.fadeOnFly and flying then
        targetAlpha = WoodTrackerDB.flyAlpha or 0.4
    end

    Fade(frame, frame:GetAlpha(), targetAlpha, 0.25)
end








-- =========================
-- Options
-- =========================

local settings = CreateFrame("Frame", "WoodTrackerSettings", UIParent, "BasicFrameTemplateWithInset")
settings:SetSize(260, 120)
settings:SetPoint("CENTER")
settings:SetMovable(true)
settings:EnableMouse(true)
settings:RegisterForDrag("LeftButton")
settings:SetScript("OnDragStart", settings.StartMoving)
settings:SetScript("OnDragStop", settings.StopMovingOrSizing)
settings:Hide()

settings.title = settings:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
settings.title:SetPoint("TOP", 0, -8)
settings.title:SetText("WoodTracker – Options")

local fadeCheck = CreateFrame("CheckButton", nil, settings, "UICheckButtonTemplate")
fadeCheck:SetPoint("TOPLEFT", 20, -40)
fadeCheck.text:SetText("Réduire l’opacité en vol")

local alphaSlider = CreateFrame("Slider", nil, settings, "OptionsSliderTemplate")
alphaSlider:SetPoint("TOP", settings, "TOP", 0, -95)
alphaSlider:SetMinMaxValues(0.2, 1)
alphaSlider:SetValueStep(0.05)
alphaSlider:SetValue(WoodTrackerDB.flyAlpha or 0.4)
alphaSlider.Text:SetText("Opacité en vol")
alphaSlider.Text:ClearAllPoints()
alphaSlider.Text:SetPoint("BOTTOM", alphaSlider, "TOP", 0, 4)
alphaSlider.Low:Hide()
alphaSlider.High:Hide()


alphaSlider:SetScript("OnValueChanged", function(self, value)
    WoodTrackerDB.flyAlpha = value
    UpdateOpacity(true)
end)
alphaSlider:SetMinMaxValues(0.2, 1)
settings:SetScript("OnShow", function()
    fadeCheck:SetChecked(WoodTrackerDB.fadeOnFly)
    alphaSlider:SetValue(WoodTrackerDB.flyAlpha or 0.4)
end)
fadeCheck:SetScript("OnClick", function(self)
    local enabled = self:GetChecked()
    WoodTrackerDB.fadeOnFly = enabled
    alphaSlider:SetEnabled(enabled)
    UpdateOpacity()
end)

settings:SetScript("OnShow", function()
    fadeCheck:SetChecked(WoodTrackerDB.fadeOnFly)
    alphaSlider:SetValue(WoodTrackerDB.flyAlpha or 0.4)
    alphaSlider:SetEnabled(WoodTrackerDB.fadeOnFly)
end)

-- =========================
-- Bouton fermer
-- =========================
local closeBtn = CreateFrame("Button", nil, frame, "UIPanelCloseButton")
closeBtn:SetPoint("TOPRIGHT", frame, "TOPRIGHT", -4, -4)
closeBtn:SetScript("OnClick", function()
    frame:Hide()
    ResetLines()
end)

-- =========================
-- Config visuelle
-- =========================
local lineHeight  = 22
local lineSpacing = 26
local barWidth    = 190
local iconSize    = 20

local nomsCourts = {
    Bois_TWW="TWW", Bois_DF="DF", Bois_SL="SL", Bois_BFA="BFA",
    Bois_LEGION="LEGION", Bois_WOD="WOD", Bois_MISTS="MISTS",
    Bois_CATA="CATA", Bois_WOTLK="WOTLK", Bois_BC="BC", Bois_CLASSIC="CLASSIC"
}

local ordre = {
    "Bois_TWW","Bois_DF","Bois_SL","Bois_BFA","Bois_LEGION","Bois_WOD",
    "Bois_MISTS","Bois_CATA","Bois_WOTLK","Bois_BC","Bois_CLASSIC"
}

local fallbackIcon = "Interface\\AddOns\\WoodTracker\\media\\icon"

-- =========================
-- Lignes
-- =========================
frame.lines = {}

for _, key in ipairs(ordre) do
    local line = {}

    line.icon = frame:CreateTexture(nil, "OVERLAY")
    line.icon:SetSize(iconSize, iconSize)

    line.bar = CreateFrame("StatusBar", nil, frame)
    line.bar:SetSize(barWidth, lineHeight)
    line.bar:SetStatusBarTexture("Interface\\TARGETINGFRAME\\UI-StatusBar")

    line.name = line.bar:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    line.name:SetPoint("LEFT", line.bar, "LEFT", 6, 0)
    line.name:SetText(nomsCourts[key])

    line.text = line.bar:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    line.text:SetPoint("RIGHT", line.bar, "RIGHT", -6, 0)

    line.rest = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    line.rest:SetJustifyH("LEFT")
    line.rest:SetTextColor(1, 0, 0)
    line.icon:SetAlpha(0)
    line.bar:SetAlpha(0)
    line.rest:SetAlpha(0)
    line.icon:Hide()
    line.bar:Hide()
    line.rest:Hide()
    line.visible = false
    frame.lines[key] = line
end

local function ResetLines()
    for _, line in pairs(frame.lines) do
        line.visible = false
        line.icon:SetAlpha(0)
        line.bar:SetAlpha(0)
        line.rest:SetAlpha(0)
        line.icon:Hide()
        line.bar:Hide()
        line.rest:Hide()
    end
end
-- =========================
-- Checkbox Hide 0
-- =========================
local hideCheckbox = CreateFrame("CheckButton", nil, frame, "UICheckButtonTemplate")
hideCheckbox:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", 12, 50)
hideCheckbox.text:SetText("Bois à recolter")
hideCheckbox:SetChecked(HideZero)
hideCheckbox:SetScript("OnClick", function(self)
    HideZero = self:GetChecked()
    UpdateDisplay()
end)

-- =========================
-- Slider Scale
-- =========================
local scaleSlider = CreateFrame("Slider", nil, frame, "OptionsSliderTemplate")
scaleSlider:SetPoint("BOTTOM", frame, "BOTTOM", 0, 20)
scaleSlider:SetMinMaxValues(0.6, 1.6)
scaleSlider:SetValue(1)
scaleSlider:SetValueStep(0.05)
scaleSlider:SetObeyStepOnDrag(true)
scaleSlider.Text:SetText("Scale")
scaleSlider.Low:Hide()
scaleSlider.High:Hide()

scaleSlider:SetScript("OnMouseUp", function(self)
    frame:SetScale(self:GetValue())
end)

-- =========================
-- Update affichage
-- =========================
function UpdateDisplay()
    local visibleIndex = 0

    for _, key in ipairs(ordre) do
        local data = objectifs[key]
        local line = frame.lines[key]

        local shouldShow = data and not (HideZero and data.objectif == 0)

        if shouldShow then
            visibleIndex = visibleIndex + 1
            local y = -10 - (visibleIndex - 1) * lineSpacing
            local totalWidth = iconSize + 6 + barWidth + 40
            local startX = (frame:GetWidth() - totalWidth) / 2

            line.icon:SetPoint("TOPLEFT", frame, "TOPLEFT", startX, y)
            line.bar:SetPoint("LEFT", line.icon, "RIGHT", 6, 0)
            line.rest:SetPoint("LEFT", line.bar, "RIGHT", 10, 0)

            if not line.visible then
                line.visible = true

                line.icon:Show()
                line.bar:Show()
                line.rest:Show()

                Fade(line.icon, line.icon:GetAlpha(), 1, 0.25)
                Fade(line.bar,  line.bar:GetAlpha(),  1, 0.25)
                Fade(line.rest, line.rest:GetAlpha(), 1, 0.25)
            end


            -- mise à jour valeurs
            local total = GetTotalItemCount(data.itemID)
            CachedTotals[key] = total
            local objectif = data.objectif
            local reste = math.max(objectif - total, 0)

            line.bar:SetMinMaxValues(0, objectif)
            line.bar:SetValue(total)

            if reste == 0 then
                line.bar:SetStatusBarColor(0, 1, 0)
                line.rest:SetText("")
            else
                line.bar:SetStatusBarColor(1, 1, 0)
                line.rest:SetText(reste)
            end

            line.text:SetText(total .. " / " .. objectif)

        else
            if line.visible then
                line.visible = false

                Fade(line.icon, line.icon:GetAlpha(), 0, 0.2)
                Fade(line.bar, line.bar:GetAlpha(), 0, 0.2)
                Fade(line.rest, line.rest:GetAlpha(), 0, 0.2)

                C_Timer.After(0.2, function()
                    line.icon:Hide()
                    line.bar:Hide()
                    line.rest:Hide()
                end)
            end
        end

    end

    frame:SetHeight(math.max(visibleIndex * lineSpacing + 110, 160))
end

-- =========================
-- Export SavedVariables
-- =========================
ExportToSavedVariables = function()

    -- 🔒 Sécurité : ne jamais écraser avec du vide
    if not next(CachedTotals) then return end

    WoodTracker_Sync = WoodTracker_Sync or {}

    WoodTracker_Sync.meta = {
        version   = "1.0",
        schema    = 1,
        character = UnitName("player"),
        realm     = GetNormalizedRealmName(),
    }

    WoodTracker_Sync.timestamp = time()
    WoodTracker_Sync.timestamp_iso = date("%Y-%m-%d %H:%M:%S")
    WoodTracker_Sync.heartbeat = time()
    WoodTracker_Sync.data = {}

    for _, key in ipairs(ordre) do
        local cached = CachedTotals[key]
        if cached ~= nil then
            WoodTracker_Sync.data[key] = cached
        end
    end

    WoodTracker_Sync.checksum = ComputeChecksum(WoodTracker_Sync.data)
end



-- =========================
-- OnUpdate
-- =========================

frame.elapsed = 0
frame.opacityTimer = 0

frame:SetScript("OnUpdate", function(self, elapsed)
    self.elapsed = self.elapsed + elapsed
    self.opacityTimer = self.opacityTimer + elapsed

    -- UI refresh
    if self.elapsed > 0.3 and IsLoggedIn then
        UpdateDisplay()

        if time() - lastExportTime > 5 then
            ExportToSavedVariables()
            lastExportTime = time()
        end

        self.elapsed = 0
    end

    -- Opacity polling (clé du fix)
    if self.opacityTimer > 0.2 then
        UpdateOpacity()
        self.opacityTimer = 0
    end
end)



-- =========================
-- Minimap (LDB)
-- =========================
local DB = { minimapIcon = { hide = false } }

local LDB = LibStub("LibDataBroker-1.1"):NewDataObject("WoodTracker", {
    type = "data source",
    text = "WoodTracker",
    icon = fallbackIcon,
    OnClick = function(_, button)
        if button == "RightButton" then
            SlashCmdList["WOODTRACKER"]()
        else
            if frame:IsShown() then
                frame:Hide()
                ResetLines()
            else
                ResetLines()          -- 🔑 LIGNE MANQUANTE
                frame:Show()
                UpdateOpacity(true)
                UpdateDisplay()
            end
        end
    end,
})

LibStub("LibDBIcon-1.0"):Register("WoodTracker", LDB, DB.minimapIcon)

-- =========================
-- Login / Logout
-- =========================
local f = CreateFrame("Frame")
f:RegisterEvent("PLAYER_LOGIN")
f:RegisterEvent("PLAYER_LOGOUT")

f:SetScript("OnEvent", function(_, event)
    if event == "PLAYER_LOGIN" then
        UpdateOpacity()
        IsLoggedIn = true

        for key, data in pairs(objectifs) do
            local icon = C_Item.GetItemIconByID(data.itemID)
            if icon and frame.lines[key] then
                frame.lines[key].icon:SetTexture(icon)
            end 
        end
        C_Timer.After(0.1, UpdateDisplay)
    elseif event == "PLAYER_LOGOUT" then
        IsLoggingOut = true
        ExportToSavedVariables()
    end
end)



local opacityWatcher = CreateFrame("Frame")
opacityWatcher:RegisterEvent("PLAYER_STARTED_MOVING")
opacityWatcher:RegisterEvent("PLAYER_STOPPED_MOVING")
opacityWatcher:RegisterEvent("PLAYER_MOUNT_DISPLAY_CHANGED")
opacityWatcher:RegisterEvent("ZONE_CHANGED_NEW_AREA")
opacityWatcher:RegisterEvent("PLAYER_ENTERING_WORLD")

opacityWatcher:SetScript("OnEvent", function()
    UpdateOpacity(true)
end)


-- =========================
-- Commandes
-- =========================
SLASH_WOODTRACKER1 = "/wt"
SLASH_WOODTRACKER2 = "/woodtracker"

SlashCmdList["WOODTRACKER"] = function()
    if settings:IsShown() then
        settings:Hide()
    else
        settings:Show()
    end

    UpdateOpacity()
end



-- =========================
-- AUCTION HOUSE BUTTON (BOTTOM – UNIVERSAL)
-- =========================

local AHButtonCreated = false
local AHWatcher = CreateFrame("Frame")
AHWatcher:RegisterEvent("AUCTION_HOUSE_SHOW")

AHWatcher:SetScript("OnEvent", function()
    if AHButtonCreated then return end
    if not AuctionHouseFrame then return end

    AHButtonCreated = true

    local btn = CreateFrame("Button", nil, AuctionHouseFrame, "UIPanelButtonTemplate")
    btn:SetSize(200, 22)
    btn:SetText("WoodTracker – Scanner l’HV")

    -- ✅ POSITION EXACTE (BAS, SAFE, TOUJOURS VISIBLE)
    btn:SetPoint("BOTTOM", AuctionHouseFrame, "BOTTOM", 0, 6)
    btn:SetFrameStrata("HIGH")
    btn:SetFrameLevel(200)

    WoodTracker_AH_StatusText = btn:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    WoodTracker_AH_StatusText:SetPoint("BOTTOM", btn, "TOP", 0, 4)
    WoodTracker_AH_StatusText:SetText("")


    btn:SetScript("OnClick", function()
    if not WoodTracker_StartAHScan then
        WoodTracker_AH_StatusText:SetText("❌ AH Bridge non chargé")
        return
    end

    if WoodTracker_AH_State and WoodTracker_AH_State.scanning then
        return -- empêche double scan
    end

    WoodTracker_AH_StatusText:SetText("0 %")
    WoodTracker_StartAHScan()
    end)
end)

-- =========================
-- AH Scan Progress (%)
-- =========================

local AHProgressUpdater = CreateFrame("Frame")
AHProgressUpdater:SetScript("OnUpdate", function()
  if not WoodTracker_AH_StatusText then return end
  if not WoodTracker_AH_State then return end
  if not WoodTracker_AH_State.scanning then return end

  local total = WoodTracker_AH_State.total or 0
  local current = WoodTracker_AH_State.current or 0

  if total > 0 then
    local pct = math.floor((current / total) * 100)
    WoodTracker_AH_StatusText:SetText(pct .. " %")
  end
end)

