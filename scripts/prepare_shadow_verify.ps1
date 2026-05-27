param(
    [Parameter(Mandatory = $true)]
    [string]$SourcePath,

    [Parameter(Mandatory = $true)]
    [string]$SampleName,

    [string]$ShadowRoot = (Join-Path $PSScriptRoot "..\shadow-verify")
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host "[shadow-verify] $msg"
}

if (-not (Test-Path -LiteralPath $SourcePath)) {
    throw "SourcePath not found: $SourcePath"
}

$sampleRoot = Join-Path $ShadowRoot ("samples\" + $SampleName)
$targetRoot = Join-Path $sampleRoot "source"

Write-Step "source = $SourcePath"
Write-Step "target = $targetRoot"

New-Item -ItemType Directory -Force -Path $targetRoot | Out-Null

$excludeDirs = @("/XD", ".recycle", "@eaDir", "#recycle", '$RECYCLE.BIN', "System Volume Information")
$robocopyArgs = @(
    $SourcePath,
    $targetRoot,
    "/E",
    "/R:1",
    "/W:1",
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS",
    "/NP"
) + $excludeDirs

Write-Step "copying sample tree"
& robocopy @robocopyArgs | Out-Null
$rc = $LASTEXITCODE
if ($rc -ge 8) {
    throw "robocopy failed with exit code $rc"
}

$beforeTree = Join-Path $sampleRoot "before-tree.txt"
Write-Step "writing before-tree snapshot"
tree /F $targetRoot | Out-File -FilePath $beforeTree -Encoding utf8

Write-Step "done"
Write-Step "before snapshot = $beforeTree"
