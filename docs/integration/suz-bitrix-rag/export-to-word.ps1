# Export tz-bitrix-rag-sufler.md -> Word (.docx) with Mermaid diagrams as PNG.
# Usage: .\export-to-word.ps1
#        .\export-to-word.ps1 -OutputPath "D:\TZ-Bitrix-RAG.docx"
#
# Requires: Pandoc, Python (py -3), Node.js (npx) for @mermaid-js/mermaid-cli

param(
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$builder = Join-Path $here "_build_docx_mermaid.py"
$inputMd = Join-Path $here "tz-bitrix-rag-sufler.md"
$defaultOut = Join-Path $here "TZ-Bitrix-RAG.docx"

if (-not (Test-Path $inputMd)) {
    throw "Input file not found: $inputMd"
}
if (-not (Test-Path $builder)) {
    throw "Builder not found: $builder"
}
if (-not (Get-Command pandoc -ErrorAction SilentlyContinue)) {
    Write-Host "Pandoc not found. Install: winget install --id JohnMacFarlane.Pandoc -e" -ForegroundColor Red
    exit 1
}
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "Python launcher (py) not found." -ForegroundColor Red
    exit 1
}

Write-Host "Building DOCX with Mermaid diagrams via $builder"
& py -3 $builder
if ($LASTEXITCODE -ne 0) {
    throw "Builder failed with exit code $LASTEXITCODE - see _pipeline_status.txt"
}

if (-not [string]::IsNullOrWhiteSpace($OutputPath) -and (Resolve-Path $defaultOut).Path -ne (Resolve-Path $OutputPath -ErrorAction SilentlyContinue)) {
    Copy-Item -Force $defaultOut $OutputPath
    Write-Host "Copied to: $OutputPath" -ForegroundColor Green
}

Write-Host "Done: $defaultOut" -ForegroundColor Green
if (Test-Path (Join-Path $here "_pipeline_status.txt")) {
    Get-Content (Join-Path $here "_pipeline_status.txt") -Tail 5
}
