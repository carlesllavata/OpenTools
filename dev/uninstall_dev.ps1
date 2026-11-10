<#
.SYNOPSIS
    Removes the OpenTools-dev bundle installed by dev\install_dev.ps1.
#>
param(
    [string]$PluginsDir = (Join-Path $env:APPDATA "Autodesk\ApplicationPlugins")
)

$target = Join-Path $PluginsDir "OpenTools-dev.bundle"
if (Test-Path (Join-Path $target "Contents\scripts\opentools_dev_startup.ms")) {
    Remove-Item -Recurse -Force -Path $target
    Write-Host "Removed $target. Restart 3ds Max."
} else {
    Write-Host "Nothing to remove at $target"
}
