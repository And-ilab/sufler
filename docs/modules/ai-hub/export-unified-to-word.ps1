# Export tz-unified-v1.4.md -> Word (.docx)
# Usage:
#   .\export-unified-to-word.ps1                    # customer version (default)
#   .\export-unified-to-word.ps1 -Internal          # full draft with all status values
#   .\export-unified-to-word.ps1 -OutputPath "D:\TZ-unified-v1.4.docx"
#   .\export-unified-to-word.ps1 -Version 1.3       # export older version

param(
    [switch]$Internal,
    [string]$OutputPath = "",
    [string]$Version = "1.4"
)

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$inputMd = Join-Path $here "tz-unified-v$Version.md"
$prepareScript = Join-Path $here "prepare_customer_export.py"

if (-not (Test-Path $inputMd)) {
    throw "Input file not found: $inputMd"
}

if (-not (Get-Command pandoc -ErrorAction SilentlyContinue)) {
    Write-Host "Pandoc not found. Install: winget install --id JohnMacFarlane.Pandoc -e" -ForegroundColor Red
    exit 1
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    if ($Internal) {
        $OutputPath = Join-Path $here "TZ-unified-v$Version-internal.docx"
    } else {
        $OutputPath = Join-Path $here "TZ-unified-v$Version.docx"
    }
}

$mdForPandoc = $inputMd
$tempMd = $null

if (-not (Test-Path $prepareScript)) {
    throw "Export prepare script not found: $prepareScript"
}

$tempMd = Join-Path $env:TEMP ("tz-unified-v$Version-export-{0}.md" -f [guid]::NewGuid().ToString("N"))
if ($Internal) {
    & py $prepareScript --internal $inputMd $tempMd
    Write-Host "Mode:   internal draft (anchors synced for Word links)"
} else {
    & py $prepareScript $inputMd $tempMd
    Write-Host "Mode:   customer (filtered + anchors synced for Word links)"
}
if ($LASTEXITCODE -ne 0) {
    throw "prepare_customer_export.py failed with exit code $LASTEXITCODE"
}
$mdForPandoc = $tempMd

Write-Host "Input:  $mdForPandoc"
Write-Host "Output: $OutputPath"

$exportDate = Get-Date -Format "yyyy-MM-dd"
$docTitle = "TZ AI Hub v$Version"

try {
    & pandoc $mdForPandoc `
        -o $OutputPath `
        --from markdown+gfm_auto_identifiers+header_attributes `
        --to docx `
        --standalone `
        --metadata "title=$docTitle" `
        --metadata "date=$exportDate"

    if ($LASTEXITCODE -ne 0) {
        throw "Pandoc failed with exit code $LASTEXITCODE"
    }

    Write-Host "Done: $OutputPath" -ForegroundColor Green
}
finally {
    if ($tempMd -and (Test-Path $tempMd)) {
        Remove-Item $tempMd -Force
    }
}
