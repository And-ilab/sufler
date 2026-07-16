# Export tz-ai-hub-contour.md -> Word (.docx)
# Usage: .\export-to-word.ps1
#        .\export-to-word.ps1 -OutputPath "D:\TZ-AI-Hub.docx"

param(
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$inputMd = Join-Path $here "tz-ai-hub-contour.md"

if (-not (Test-Path $inputMd)) {
    throw "Input file not found: $inputMd"
}

if (-not (Get-Command pandoc -ErrorAction SilentlyContinue)) {
    Write-Host "Pandoc not found. Install: winget install --id JohnMacFarlane.Pandoc -e" -ForegroundColor Red
    exit 1
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $here "TZ-AI-Hub.docx"
}

Write-Host "Input:  $inputMd"
Write-Host "Output: $OutputPath"

& pandoc $inputMd `
    -o $OutputPath `
    --from markdown `
    --to docx `
    --standalone `
    --toc `
    --toc-depth=3 `
    --metadata title="TZ AI Hub contour" `
    --metadata date="$(Get-Date -Format 'yyyy-MM-dd')"

if ($LASTEXITCODE -ne 0) {
    throw "Pandoc failed with exit code $LASTEXITCODE"
}

Write-Host "Done: $OutputPath" -ForegroundColor Green
