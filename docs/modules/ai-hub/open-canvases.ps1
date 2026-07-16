# Sync canvas mockups from repo to Cursor managed folder.
# Run: .\open-canvases.ps1
#      .\open-canvases.ps1 -Mockup panel
#      .\open-canvases.ps1 -List

param(
    [ValidateSet("panel", "settings", "assistant", "chat", "sufer", "launcher", "internal", "ocr", "all")]
    [string]$Mockup = "all",
    [switch]$List,
    [switch]$NoExplorer
)

$ErrorActionPreference = "Stop"

$repoCanvasDir = Join-Path $PSScriptRoot "..\..\..\canvases"
if (-not (Test-Path $repoCanvasDir)) {
    throw "Repo canvases folder not found: $repoCanvasDir"
}
$repoCanvasDir = (Resolve-Path $repoCanvasDir).Path

$cursorCanvasDir = Join-Path $env:USERPROFILE ".cursor\projects\c-sufler\canvases"

$mockups = [ordered]@{
    panel      = "ai-hub-panel-mockup.canvas.tsx"
    settings   = "ai-hub-settings-mockup.canvas.tsx"
    assistant  = "ai-assistant-ui-mockup.canvas.tsx"
    chat       = "online-chat-mockups.canvas.tsx"
    sufer      = "sufer-phone-mockup.canvas.tsx"
    launcher   = "tray-launcher-mockup.canvas.tsx"
    internal   = "internal-user-kc-mockup.canvas.tsx"
    ocr        = "ocr-documents-mockup.canvas.tsx"
}

if ($List) {
    Write-Host "Available mockups:" -ForegroundColor Cyan
    foreach ($entry in $mockups.GetEnumerator()) {
        Write-Host ("  {0,-10} -> {1}" -f $entry.Key, $entry.Value)
    }
    exit 0
}

if (-not (Test-Path $cursorCanvasDir)) {
    New-Item -ItemType Directory -Path $cursorCanvasDir -Force | Out-Null
}

$selected = if ($Mockup -eq "all") {
    $mockups.Values
} else {
    @($mockups[$Mockup])
}

Write-Host ""
Write-Host "=== Canvas sync ===" -ForegroundColor Cyan
Write-Host "From: $repoCanvasDir"
Write-Host "To:   $cursorCanvasDir"
Write-Host ""

$copied = 0
foreach ($name in $selected) {
    $source = Join-Path $repoCanvasDir $name
    if (-not (Test-Path $source)) {
        Write-Host "SKIP  $name (missing in repo)" -ForegroundColor Yellow
        continue
    }

    Copy-Item -Path $source -Destination (Join-Path $cursorCanvasDir $name) -Force
    Write-Host "OK    $name" -ForegroundColor Green
    $copied++

    $dataName = $name -replace '\.canvas\.tsx$', '.canvas.data.json'
    $dataSource = Join-Path $repoCanvasDir $dataName
    if (Test-Path $dataSource) {
        Copy-Item -Path $dataSource -Destination (Join-Path $cursorCanvasDir $dataName) -Force
        Write-Host "OK    $dataName" -ForegroundColor DarkGreen
    }
}

if ($copied -eq 0) {
    throw "Nothing copied. Check mockup name: -Mockup panel|settings|assistant|chat|sufer|internal|ocr|all"
}

Write-Host ""
Write-Host "=== How to open visual mockup (not code) ===" -ForegroundColor Yellow
Write-Host "1. Close tabs opened from C:\sufler\canvases\ (they show source code)."
Write-Host "2. In Agent chat ask, for example:"
Write-Host "   Open canvas ai-hub-panel-mockup"
Write-Host "3. Click the canvas link in the agent reply."
Write-Host "4. Canvas opens in the preview panel beside chat."
Write-Host ""
Write-Host "Managed canvas path (for preview):"
Write-Host $cursorCanvasDir
Write-Host ""

if (-not $NoExplorer) {
    explorer $cursorCanvasDir
}

Write-Host "Done. Synced $copied mockup(s)." -ForegroundColor Green
Write-Host ""
