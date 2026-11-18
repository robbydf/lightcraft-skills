# find-lightcraft.ps1: print the folder that holds lightcraft.exe and lightcraft-cli.exe.
# Order: -Dir argument, $env:LIGHTCRAFT_DIR, LIGHTCRAFT_DIR in <LIGHTCRAFT_HOME>\config.env,
# the uninstall entries in the registry, then the usual install folders.
# Exit 1 (and print nothing) if no folder with lightcraft-cli.exe is found.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File find-lightcraft.ps1 [-Dir <folder>]
param([string]$Dir = "")
$ErrorActionPreference = "SilentlyContinue"

function Test-Dir([string]$d) { $d -and (Test-Path -LiteralPath (Join-Path $d "lightcraft-cli.exe")) }

$home2 = if ($env:LIGHTCRAFT_HOME) { $env:LIGHTCRAFT_HOME } else { Join-Path $env:USERPROFILE ".claude\lightcraft" }
$fromConfig = ""
$cfg = Join-Path $home2 "config.env"
if (Test-Path $cfg) {
    foreach ($line in Get-Content $cfg) {
        if ($line -match '^\s*LIGHTCRAFT_DIR\s*=\s*"?([^"]+?)"?\s*$') { $fromConfig = $Matches[1] }
    }
}

$candidates = @($Dir, $env:LIGHTCRAFT_DIR, $fromConfig)

foreach ($root in @("HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")) {
    Get-ChildItem $root | ForEach-Object {
        $p = Get-ItemProperty -LiteralPath $_.PSPath
        if ($p.DisplayName -match 'LightCraft|ArtCraft') {
            $candidates += $p.InstallLocation
            if ($p.DisplayIcon) { $candidates += (Split-Path ($p.DisplayIcon -replace '"|,\d+$', '')) }
        }
    }
}

foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, (Join-Path $env:LOCALAPPDATA "Programs"))) {
    if ($base) {
        $candidates += (Join-Path $base "ArtCraft\LightCraft")
        $candidates += (Join-Path $base "LightCraft")
    }
}

foreach ($c in $candidates) {
    if (Test-Dir $c) { (Resolve-Path -LiteralPath $c).Path; exit 0 }
    # Search one level deeper only inside a LightCraft/ArtCraft folder, never a drive root or Program Files itself.
    if ($c -and (Test-Path -LiteralPath $c) -and ((Split-Path -Leaf $c) -match 'LightCraft|ArtCraft')) {
        $hit = Get-ChildItem -LiteralPath $c -Recurse -Depth 2 -Filter lightcraft-cli.exe | Select-Object -First 1
        if ($hit) { $hit.DirectoryName; exit 0 }
    }
}
exit 1
