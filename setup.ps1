param([Parameter(Position=0,Mandatory=$true)][string]$Target,[string]$Profile,[switch]$Uninstall)
$ArgsList=@($Target)
if ($Profile) { $ArgsList += @('--profile',$Profile) }
if ($Uninstall) { $ArgsList += '--uninstall' }
python (Join-Path $PSScriptRoot 'scripts/install.py') @ArgsList
exit $LASTEXITCODE
