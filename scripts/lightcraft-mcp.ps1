# lightcraft-mcp: start / stop the LightCraft GUI + CLI MCP bridge and (dis)connect Claude Code.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File lightcraft-mcp.ps1 start|stop [-Port 7980] [-Library DIR] [-Scope local|user] [-TimeoutSec 60] [-Force] [-LightCraftDir DIR] [-TokenFile FILE]
# The install folder comes from -LightCraftDir, else find-lightcraft.ps1 (env LIGHTCRAFT_DIR, config.env, registry, Program Files).
param(
    [Parameter(Mandatory = $true, Position = 0)][ValidateSet("start", "stop")][string]$Action,
    [int]$Port = 7980,
    [string]$Library = "",
    [ValidateSet("local", "user")][string]$Scope = "local",
    [int]$TimeoutSec = 60,
    [switch]$Force,  # stop: kill LightCraft if it does not close gracefully
    [string]$LightCraftDir = "",
    [string]$TokenFile = $env:LIGHTCRAFT_TOKEN_FILE   # optional; LightCraft 0.21.1 ignores tokens
)
# "Continue": lightcraft-cli and claude write status to stderr, which PS 5.1 turns into terminating errors under "Stop".
$ErrorActionPreference = "Continue"
$dir = $LightCraftDir
if (-not $dir) { $dir = & (Join-Path $PSScriptRoot "find-lightcraft.ps1") }
if (-not $dir -or -not (Test-Path (Join-Path $dir "lightcraft-cli.exe"))) {
    Write-Output "ERROR: LightCraft not found. Pass -LightCraftDir or set LIGHTCRAFT_DIR (env or ~/.claude/lightcraft/config.env)."
    exit 9
}
$gui = Join-Path $dir "lightcraft.exe"
$cli = Join-Path $dir "lightcraft-cli.exe"
$addr = "127.0.0.1:$Port"
$name = "lightcraft"

function Test-Listening { [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) }
function Test-Registered { cmd /c "claude mcp get $name >nul 2>nul"; return ($LASTEXITCODE -eq 0) }
# LightCraft draws no frames while minimized, so it ignores control requests and WM_CLOSE. Restore it first.
Add-Type -Namespace LcMcp -Name Win -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
"@
function Restore-Gui {
    foreach ($p in @(Get-Process lightcraft -ErrorAction SilentlyContinue)) {
        $h = $p.MainWindowHandle
        if ($h -ne [IntPtr]::Zero -and [LcMcp.Win]::IsIconic($h)) {
            [LcMcp.Win]::ShowWindow($h, 9) | Out-Null   # SW_RESTORE
            Write-Output "gui: window was minimized; restored it"
            Start-Sleep -Milliseconds 500
        }
    }
}
function Get-Bridges {
    Get-CimInstance Win32_Process -Filter "Name='lightcraft-cli.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match '\bmcp\b' }
}

if ($Action -eq "start") {
    # Token: LightCraft 0.21.1 has no auth on the control port; export it for any wrapper that wants it.
    if ($TokenFile -and (Test-Path $TokenFile)) {
        $env:LIGHTCRAFT_TOKEN = (Get-Content $TokenFile -Raw).Trim()
        Write-Output "token: loaded into LIGHTCRAFT_TOKEN (not required by LightCraft itself)"
    }

    # 1. GUI with control channel
    if (Test-Listening) {
        Write-Output "gui: control port $addr already listening; reusing the running app"
    } else {
        $running = Get-Process lightcraft -ErrorAction SilentlyContinue
        if ($running) {
            Write-Output "ERROR: lightcraft.exe is running (pid $($running.Id -join ',')) but NOT serving control port $Port. Ask the user to close it, or run 'stop', then 'start' again."
            exit 2
        }
        $guiArgs = @("--control", "$Port")
        if ($Library) { $guiArgs += @("--library", "`"$Library`"") }
        Start-Process -FilePath $gui -ArgumentList $guiArgs -WorkingDirectory $dir | Out-Null
        $deadline = (Get-Date).AddSeconds($TimeoutSec)
        while (-not (Test-Listening)) {
            if ((Get-Date) -gt $deadline) { Write-Output "ERROR: GUI did not open $addr within $TimeoutSec s (see %APPDATA%\LightCraft\logs\lightcraft.log)"; exit 3 }
            Start-Sleep -Milliseconds 500
        }
        Write-Output "gui: started, control channel listening on $addr"
    }

    # 2. CLI can drive the GUI
    Restore-Gui
    $ping = & $cli run --connect $addr engine.commands 2>$null | Select-Object -First 1
    if ($ping -notmatch '"ok":true') { Write-Output "ERROR: CLI could not drive the GUI: $ping"; exit 4 }
    Write-Output "cli: run --connect $addr OK"

    # 3. Bridge handshake. Feed stdin from a BOM-less file via cmd; PowerShell 5.1 pipes corrupt it.
    $init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"lightcraft-mcp","version":"1"}}}'
    $req = Join-Path $env:TEMP "lightcraft-mcp-init.jsonl"
    [System.IO.File]::WriteAllText($req, $init + "`n", (New-Object System.Text.UTF8Encoding $false))
    $reply = cmd /c "`"$cli`" mcp --connect $addr < `"$req`" 2>nul" | Where-Object { $_ -match '"id":1' } | Select-Object -First 1
    Remove-Item $req -ErrorAction SilentlyContinue
    if ($reply -notmatch '"result"') { Write-Output "ERROR: bridge handshake failed: $reply"; exit 5 }
    Write-Output "bridge: lightcraft-cli mcp --connect $addr answered initialize OK"

    # 4. Connect Claude Code (register the stdio MCP server; Claude Code spawns the bridge itself)
    if (Test-Registered) {
        Write-Output "claude: MCP server '$name' already registered"
    } else {
        cmd /c "claude mcp add -s $Scope $name -- `"$cli`" mcp --connect $addr 2>&1" | Out-Null
        if (-not (Test-Registered)) { Write-Output "ERROR: 'claude mcp add' failed"; exit 6 }
        Write-Output "claude: registered MCP server '$name' ($Scope scope) -> $cli mcp --connect $addr"
    }
    Write-Output "READY gui=$addr mcp=$name"
    exit 0
}

# ---- stop ----
$problems = 0

# 1. Disconnect Claude Code: remove the registration from the local and user scopes (never a project's .mcp.json)
$removed = @()
foreach ($s in @("local", "user")) {
    cmd /c "claude mcp remove $name -s $s >nul 2>nul"
    if ($LASTEXITCODE -eq 0) { $removed += $s }
}
if ($removed) { Write-Output "claude: removed MCP server '$name' from scope(s): $($removed -join ', ')" }
else { Write-Output "claude: MCP server '$name' was not registered" }
if (Test-Registered) { Write-Output "WARN: '$name' still registered (claude mcp get $name)"; $problems++ }

# 2. Stop bridge processes (Claude Code may still hold a running bridge process after the config is removed)
$bridges = @(Get-Bridges)
foreach ($b in $bridges) { Stop-Process -Id $b.ProcessId -Force -ErrorAction SilentlyContinue }
if ($bridges.Count) { Write-Output "bridge: stopped $($bridges.Count) lightcraft-cli mcp process(es)" }
else { Write-Output "bridge: no lightcraft-cli mcp process running" }

# 3. Close the GUI gracefully (lets it save the library); kill only with -Force
$procs = @(Get-Process lightcraft -ErrorAction SilentlyContinue)
if (-not $procs.Count) {
    Write-Output "gui: LightCraft not running"
} else {
    Restore-Gui
    foreach ($p in $procs) { $p.CloseMainWindow() | Out-Null }
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Process lightcraft -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
    $left = @(Get-Process lightcraft -ErrorAction SilentlyContinue)
    if (-not $left.Count) {
        Write-Output "gui: LightCraft closed"
    } elseif ($Force) {
        $left | Stop-Process -Force
        Write-Output "gui: LightCraft did not close in $TimeoutSec s; killed (-Force)"
    } else {
        Write-Output "ERROR: LightCraft still running after $TimeoutSec s (a dialog may be open). Ask the user, or re-run 'stop -Force'."
        exit 7
    }
}
if ($problems) { exit 8 }
Write-Output "STOPPED"
exit 0
