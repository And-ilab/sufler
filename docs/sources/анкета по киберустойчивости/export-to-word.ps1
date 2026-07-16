# Export all IB markdown documents -> Word (.docx)
# Usage: .\export-to-word.ps1
#        .\export-to-word.ps1 -OutputDir ".\outgoing\docx"

param(
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot

if (-not (Get-Command pandoc -ErrorAction SilentlyContinue)) {
    Write-Host "Pandoc not found. Install: winget install --id JohnMacFarlane.Pandoc -e" -ForegroundColor Red
    exit 1
}

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $here "outgoing\docx"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $OutputDir "documents") | Out-Null

$exportDate = Get-Date -Format "yyyy-MM-dd"

# Root-level docs
$rootDocs = @(
    "plan-dorabotok.md"
)

# documents/*.md
$docDir = Join-Path $here "documents"
$docFiles = @()
if (Test-Path $docDir) {
    $docFiles = Get-ChildItem -Path $docDir -Filter "*.md" | Sort-Object Name
}

# outgoing/*.md (markdown only, not docx output dir)
$outDir = Join-Path $here "outgoing"
$outFiles = @()
if (Test-Path $outDir) {
    $outFiles = Get-ChildItem -Path $outDir -Filter "*.md" | Sort-Object Name
}

function Export-MdToDocx {
    param(
        [string]$InputPath,
        [string]$OutputPath,
        [string]$Title
    )
    Write-Host "  $($InputPath) -> $OutputPath"
    & pandoc $InputPath `
        -o $OutputPath `
        --from markdown `
        --to docx `
        --standalone `
        --metadata "title=$Title" `
        --metadata "date=$exportDate"
    if ($LASTEXITCODE -ne 0) {
        throw "Pandoc failed for $InputPath (exit $LASTEXITCODE)"
    }
}

Write-Host "Export to: $OutputDir"
Write-Host ""

foreach ($name in $rootDocs) {
    $input = Join-Path $here $name
    if (-not (Test-Path $input)) { continue }
    $base = [System.IO.Path]::GetFileNameWithoutExtension($name)
    $output = Join-Path $OutputDir "$base.docx"
    Export-MdToDocx -InputPath $input -OutputPath $output -Title $base
}

foreach ($f in $docFiles) {
    $output = Join-Path $OutputDir "documents\$($f.BaseName).docx"
    Export-MdToDocx -InputPath $f.FullName -OutputPath $output -Title $f.BaseName
}

foreach ($f in $outFiles) {
    $output = Join-Path $OutputDir "$($f.BaseName).docx"
    Export-MdToDocx -InputPath $f.FullName -OutputPath $output -Title $f.BaseName
}

$count = (Get-ChildItem -Path $OutputDir -Recurse -Filter "*.docx").Count
Write-Host ""
Write-Host "Done: $count docx files in $OutputDir" -ForegroundColor Green
