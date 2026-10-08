# Link .cursor/skills/{name} -> skills/{name} for Cursor auto-discovery (Windows junctions).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$srcRoot = Join-Path $root "skills"
$dstRoot = Join-Path $root ".cursor\skills"
New-Item -ItemType Directory -Force -Path $dstRoot | Out-Null
$names = @(
    "drama-intake",
    "drama-series-develop",
    "0xsline-short-drama",
    "drama-series-h3-r2v-prompts"
)
foreach ($n in $names) {
    $src = Join-Path $srcRoot $n
    $dst = Join-Path $dstRoot $n
    if (-not (Test-Path -LiteralPath $src)) {
        Write-Warning "missing $src"
        continue
    }
    if (Test-Path -LiteralPath $dst) {
        cmd /c "rmdir `"$dst`""
    }
    cmd /c "mklink /J `"$dst`" `"$src`""
}
Write-Host "Cursor skill links ready under .cursor/skills/"
