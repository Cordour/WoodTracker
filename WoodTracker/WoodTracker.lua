-- =========================
-- Données importées
-- =========================
local objectifs = WoodTracker_Objectifs
if not objectifs then return end

local dataDirty = false
local IsLoggedIn = false
local HideZero = false
local lastExportTime = 0
local ExportToSavedVariables

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
-- =========================
-- Watcher inventaire
-- =========================
local syncWatcher = CreateFrame("Frame")
syncWatcher:RegisterEvent("BAG_UPDATE_DELAYED")

syncWatcher:SetScript("OnEvent", function()
    dataDirty = true
    ExportToSavedVariables()
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
-- Bouton fermer
-- =========================
local closeBtn = CreateFrame("Button", nil, frame, "UIPanelCloseButton")
closeBtn:SetPoint("TOPRIGHT", frame, "TOPRIGHT", -4, -4)
closeBtn:SetScript("OnClick", function()
    frame:Hide()
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

    frame.lines[key] = line
end

-- =========================
-- Checkbox Hide 0
-- =========================
local hideCheckbox = CreateFrame("CheckButton", nil, frame, "UICheckButtonTemplate")
hideCheckbox:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", 12, 50)
hideCheckbox.text:SetText("Hide 0")
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

        if not data or (HideZero and data.objectif == 0) then
            line.icon:Hide()
            line.bar:Hide()
            line.rest:Hide()
        else
            visibleIndex = visibleIndex + 1
            local y = -10 - (visibleIndex - 1) * lineSpacing

            local totalWidth = iconSize + 6 + barWidth + 40
            local startX = (frame:GetWidth() - totalWidth) / 2

            line.icon:SetPoint("TOPLEFT", frame, "TOPLEFT", startX, y)
            line.bar:SetPoint("LEFT", line.icon, "RIGHT", 6, 0)
            line.rest:SetPoint("LEFT", line.bar, "RIGHT", 10, 0)

            line.icon:Show()
            line.bar:Show()
            line.rest:Show()

            local total = GetTotalItemCount(data.itemID)
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
        end
    end

    frame:SetHeight(math.max(visibleIndex * lineSpacing + 110, 160))
end

-- =========================
-- Export SavedVariables
-- =========================
ExportToSavedVariables = function()
    
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
        local data = objectifs[key]
        if data then
            WoodTracker_Sync.data[key] = GetTotalItemCount(data.itemID)
        end
    end

    WoodTracker_Sync.checksum = ComputeChecksum(WoodTracker_Sync.data)
end


-- =========================
-- OnUpdate
-- =========================

frame:SetScript("OnUpdate", function(self, elapsed)
    self.time = (self.time or 0) + elapsed
    if self.time > 1 and IsLoggedIn then
        UpdateDisplay()

        if time() - lastExportTime > 5 then
            ExportToSavedVariables()
            lastExportTime = time()
        end

        self.time = 0
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
    OnClick = function()
        frame:SetShown(not frame:IsShown())
    end,
    OnTooltipShow = function(tt)
        tt:AddLine("WoodTracker")
        tt:AddLine("Click to show/hide")
    end,
})

LibStub("LibDBIcon-1.0"):Register("WoodTracker", LDB, DB.minimapIcon)

-- =========================
-- Login / Logout
-- =========================
local f = CreateFrame("Frame")
f:RegisterEvent("PLAYER_LOGIN")
f:RegisterEvent("PLAYER_LOGOUT")

-- =========================
-- Login
-- =========================
local f = CreateFrame("Frame")
f:RegisterEvent("PLAYER_LOGIN")

f:SetScript("OnEvent", function(_, event)
    if event == "PLAYER_LOGIN" then
        IsLoggedIn = true
        for key, data in pairs(objectifs) do
            local icon = C_Item.GetItemIconByID(data.itemID)
            if icon and frame.lines[key] then
                frame.lines[key].icon:SetTexture(icon)
            end
        end
    end
end)
