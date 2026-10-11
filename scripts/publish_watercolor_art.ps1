<#
.SYNOPSIS
Publish 88 watercolor PNGs to PR #71 from the corrected v2 ZIP.
.EXAMPLE
.\scripts\publish_watercolor_art.ps1 -RepoPath C:\dev\drawTemp -BundlePath C:\Downloads\drawTemp_assets_Jeanne_88_sprites_v2.zip
.DESCRIPTION
Requires a clean git checkout with push permissions. Refuses a local branch
diverged from origin, stages only PNG sprites, does not merge the PR.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [Parameter(Mandatory = $true)][string]$BundlePath
)
$ErrorActionPreference = "Stop"
$branch = "art/jeanne-watercolor-sprite-import-20261011"
$repo = (Resolve-Path -LiteralPath $RepoPath).Path
$zip = (Resolve-Path -LiteralPath $BundlePath).Path
if (-not (Test-Path -LiteralPath (Join-Path $repo ".git"))) {
    throw "Not a Git checkout: $repo"
}
$dirty = @(git -C $repo status --porcelain)
if ($LASTEXITCODE -ne 0 -or $dirty.Count -gt 0) {
    throw "Refusing to run with uncommitted or untracked files."
}
git -C $repo fetch origin $branch
if ($LASTEXITCODE -ne 0) { throw "Could not fetch PR #71 branch." }
git -C $repo show-ref --verify --quiet "refs/heads/$branch"
$localExists = ($LASTEXITCODE -eq 0)
if ($localExists) {
    git -C $repo switch $branch
    if ($LASTEXITCODE -ne 0) { throw "Could not switch to PR branch." }
    git -C $repo merge --ff-only "origin/$branch"
    if ($LASTEXITCODE -ne 0) { throw "Local branch diverged; resolve manually." }
} else {
    git -C $repo switch --track -c $branch "origin/$branch"
    if ($LASTEXITCODE -ne 0) { throw "Could not track PR branch." }
}
$head = (git -C $repo rev-parse HEAD).Trim()
$remoteHead = (git -C $repo rev-parse "origin/$branch").Trim()
if ($head -ne $remoteHead) {
    throw "Local PR branch has extra commits; refusing to publish unrelated changes."
}
$temp = Join-Path ([IO.Path]::GetTempPath()) ("drawtemp-art-" + [Guid]::NewGuid().ToString("N"))
try {
    Expand-Archive -LiteralPath $zip -DestinationPath $temp
    $source = Join-Path $temp "assets/watercolor/sprites"
    $indexFile = Join-Path $temp "assets/watercolor/index.json"
    $manifest = Join-Path $temp "assets/watercolor/registry.json"
    if (-not (Test-Path -LiteralPath $source) -or
        -not (Test-Path -LiteralPath $indexFile) -or
        -not (Test-Path -LiteralPath $manifest)) {
        throw "The ZIP does not contain the expected watercolor layout."
    }
    $index = Get-Content -LiteralPath $indexFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $registry = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
    $pngs = @(Get-ChildItem -LiteralPath $source -Recurse -File -Filter "*.png")
    $indexed = @($index.sprites)
    $registered = @($registry.entries | Where-Object { $_.kind -eq "sprite" })
    if ($pngs.Count -ne 88 -or $indexed.Count -ne 88 -or $registered.Count -ne 88) {
        throw "Expected 88 PNGs and 88 matching manifest entries."
    }
    $target = Join-Path $repo "assets/watercolor/sprites"
    New-Item -Path $target -ItemType Directory -Force | Out-Null
    Get-ChildItem -LiteralPath $source -Directory | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse -Force
    }
    $copied = @(Get-ChildItem -LiteralPath $target -Recurse -File -Filter "*.png")
    if ($copied.Count -ne 88) { throw "Copy incomplete: $($copied.Count) PNGs" }
    # Validate actual PNG IHDR dimensions, manifest IDs and all animations
    # before staging or pushing. A partial/malformed pack must not enter PR #71.
    python (Join-Path $repo "scripts/verify_watercolor_release.py") --root (Join-Path $repo "assets/watercolor")
    if ($LASTEXITCODE -ne 0) {
        throw "Release preflight failed: PNGs do not match index.json/registry.json."
    }
    git -C $repo add -- assets/watercolor/sprites
    if ($LASTEXITCODE -ne 0) { throw "git add failed" }
    git -C $repo diff --cached --stat
    git -C $repo commit -m "art(jeanne): publish 88 watercolor PNG sprites"
    if ($LASTEXITCODE -ne 0) { throw "git commit failed" }
    git -C $repo push origin $branch
    if ($LASTEXITCODE -ne 0) { throw "git push failed" }
    Write-Host "88 PNGs pushed to PR #71. Review alpha edges and Player rendering before merge."
}
finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
