param([Parameter(Position=0)][string]$Target,[string]$Profile,[switch]$Uninstall,[switch]$User,[switch]$DefaultRule,[switch]$Register,[switch]$Status,[string]$MarketplaceDir,[string]$Claude)
$ErrorActionPreference = 'Stop'
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { [Console]::Error.WriteLine('python not found on PATH; install Python 3.11+ and rerun'); exit 1 }
$ArgsList=@()
if ($Target) { $ArgsList += $Target }
if ($Profile) { $ArgsList += @('--profile',$Profile) }
if ($Uninstall) { $ArgsList += '--uninstall' }
if ($User) { $ArgsList += '--user' }
if ($DefaultRule) { $ArgsList += '--default-rule' }
if ($Register) { $ArgsList += '--register' }
if ($Status) { $ArgsList += '--status' }
if ($MarketplaceDir) { $ArgsList += @('--marketplace-dir',$MarketplaceDir) }
if ($Claude) { $ArgsList += @('--claude',$Claude) }
python (Join-Path $PSScriptRoot 'scripts/install.py') @ArgsList
exit $LASTEXITCODE
