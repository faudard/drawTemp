<#
R23.E read-only Authenticode verification. No signing keys or certificates.
Require a previously pinned publisher certificate thumbprint, not subject text.
#>
param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$ExpectedThumbprint
)
$ErrorActionPreference = 'Stop'
if ($ExpectedThumbprint -notmatch '^[0-9a-fA-F]{40}$') {
    throw 'Independent SHA-1 certificate thumbprint is mandatory'
}
if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
    throw 'Installer is absent'
}
$sig = Get-AuthenticodeSignature -LiteralPath $Installer
if ($null -eq $sig -or $sig.Status -ne 'Valid' -or $null -eq $sig.SignerCertificate) {
    throw 'Authenticode chain/policy verification failed'
}
$actual = $sig.SignerCertificate.Thumbprint.Replace(' ', '').ToLowerInvariant()
if ($actual -ne $ExpectedThumbprint.ToLowerInvariant()) {
    throw 'Signing certificate thumbprint does not match independent trust anchor'
}
# No certificate or private key material is emitted to logs.
Write-Output 'R23.E Authenticode OS trust and pinned certificate: verified'
