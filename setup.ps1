param([Parameter(Position=0)][string]$Target,[string]$Profile,[switch]$Uninstall,[switch]$User,[switch]$DefaultRule,[string]$MarketplaceDir)
$ArgsList=@()
if ($Target) { $ArgsList += $Target }
if ($Profile) { $ArgsList += @('--profile',$Profile) }
if ($Uninstall) { $ArgsList += '--uninstall' }
if ($User) { $ArgsList += '--user' }
if ($DefaultRule) { $ArgsList += '--default-rule' }
if ($MarketplaceDir) { $ArgsList += @('--marketplace-dir',$MarketplaceDir) }
python (Join-Path $PSScriptRoot 'scripts/install.py') @ArgsList
exit $LASTEXITCODE
