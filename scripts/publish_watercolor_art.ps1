<#
.SYNOPSIS
Publish all 88 audited v3 watercolor PNG files to the visual-fidelity PR.
.EXAMPLE
.\scripts\publish_watercolor_art.ps1 -RepoPath C:\dev\drawTemp -BundlePath C:\Downloads\drawTemp_assets_Jeanne_88_sprites_v3.zip
.DESCRIPTION
Requires a clean Git checkout and push permission. The Python publisher checks
the original ZIP SHA-256, all 88 image hashes, dimensions, CRCs and manifests
before staging any files. No automatic merge or force push is performed.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [Parameter(Mandatory = $true)][string]$BundlePath,
    [string]$Branch = "feat/visual-fidelity-art-gates-20261013"
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path -LiteralPath $RepoPath).Path
$zip = (Resolve-Path -LiteralPath $BundlePath).Path
if (-not (Test-Path -LiteralPath (Join-Path $repo ".git"))) {
    throw "Not a Git checkout: $repo"
}
$dirty = @(git -C $repo status --porcelain)
if ($LASTEXITCODE -ne 0 -or $dirty.Count -gt 0) {
    throw "Refusing to run with uncommitted or untracked files."
}
git -C $repo fetch origin $Branch
if ($LASTEXITCODE -ne 0) { throw "Could not fetch PR branch $Branch." }
git -C $repo show-ref --verify --quiet "refs/heads/$Branch"
$localExists = ($LASTEXITCODE -eq 0)
if ($localExists) {
    git -C $repo switch $Branch
    if ($LASTEXITCODE -ne 0) { throw "Could not switch to PR branch." }
    git -C $repo merge --ff-only "origin/$Branch"
    if ($LASTEXITCODE -ne 0) { throw "Local branch diverged; resolve manually." }
} else {
    git -C $repo switch --track -c $Branch "origin/$Branch"
    if ($LASTEXITCODE -ne 0) { throw "Could not track PR branch." }
}
$head = (git -C $repo rev-parse HEAD).Trim()
$remoteHead = (git -C $repo rev-parse "origin/$Branch").Trim()
if ($head -ne $remoteHead) {
    throw "Local PR branch has extra commits; refusing to push unrelated changes."
}

$root = Join-Path $repo "assets/watercolor"
python (Join-Path $repo "scripts/publish_watercolor_pack.py") --bundle $zip --root $root
if ($LASTEXITCODE -ne 0) {
    throw "Watercolor v3 validation or publication failed. No commit was created."
}
python (Join-Path $repo "scripts/verify_watercolor_release.py") --root $root
if ($LASTEXITCODE -ne 0) { throw "Strict 88-file PNG/release gate failed." }

git -C $repo add -- assets/watercolor/sprites
if ($LASTEXITCODE -ne 0) { throw "git add failed" }
git -C $repo diff --cached --stat
git -C $repo diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "Identical 88-PNG set is already committed. No push needed."
    exit 0
}
git -C $repo commit -m "art(jeanne): publish 88 approved watercolor v3 PNGs"
if ($LASTEXITCODE -ne 0) { throw "git commit failed" }
git -C $repo push origin $Branch
if ($LASTEXITCODE -ne 0) { throw "git push failed" }
Write-Host "88 audited watercolor PNGs pushed to $Branch. Visual art review is still required."
