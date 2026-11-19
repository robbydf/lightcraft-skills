"""lightcraft-mcp: start / stop the LightCraft GUI + CLI MCP bridge and (dis)connect Claude Code.

Usage: python lightcraft-mcp.py start|stop [-Port 7980] [-Library DIR] [-Scope local|user]
                                [-TimeoutSec 60] [-Force] [-LightCraftDir DIR] [-TokenFile FILE]
(python3 on macOS / Linux). The install folder comes from -LightCraftDir, else find_lightcraft.py
(env LIGHTCRAFT_DIR, config.env, then the usual install places for this system). Standard library only.

Exit codes: 2 LightCraft runs without the control port, 3 the port never opened, 4 the CLI can't
drive the GUI, 5 the bridge handshake failed, 6 `claude mcp add` failed (or claude not found),
7 stop: the GUI is still open, 8 stop: the registration is still there, 9 LightCraft not found.
"""
import argparse
import csv
import io
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from find_lightcraft import CLI_NAME, find  # noqa: E402
from lcargs import fix_argv  # noqa: E402

WIN = os.name == "nt"
MAC = sys.platform == "darwin"
NAME = "lightcraft"
GUI_NAMES = ["lightcraft.exe"] if WIN else ["lightcraft", "LightCraft"]
if WIN:
    LOG_HINT = r"%APPDATA%\LightCraft\logs\lightcraft.log"
elif MAC:
    LOG_HINT = "~/Library/Application Support/LightCraft/logs/lightcraft.log"
else:
    LOG_HINT = "~/.local/share/LightCraft/logs/lightcraft.log"


def say(s):
    print(s, flush=True)


def run(args, timeout=60, **kw):
    """Run a command; never raise for a missing program or a timeout."""
    try:
        return subprocess.run(args, capture_output=True, timeout=timeout, **kw)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(args, -9, e.stdout or b"", e.stderr or b"")
    except OSError as e:
        return subprocess.CompletedProcess(args, -1, b"", str(e).encode())


def text(b):
    return (b or b"").decode("utf-8", "replace")


def listening(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def gui_pids():
    if WIN:
        r = run(["tasklist", "/FI", "IMAGENAME eq lightcraft.exe", "/FO", "CSV", "/NH"])
        return [int(row[1]) for row in csv.reader(io.StringIO(text(r.stdout)))
                if len(row) > 1 and row[0].lower() == "lightcraft.exe" and row[1].isdigit()]
    r = run(["ps", "-axo", "pid=,comm="])
    out = []
    for line in text(r.stdout).splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit() and os.path.basename(parts[1]) in GUI_NAMES:
            out.append(int(parts[0]))
    return out


def bridge_pids():
    """lightcraft-cli processes running `mcp` (Claude Code may still hold one after removal)."""
    rows = []
    if WIN:
        ps = ("Get-CimInstance Win32_Process -Filter \"Name='lightcraft-cli.exe'\" | "
              "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }")
        r = run(["powershell", "-NoProfile", "-Command", ps])
        for line in text(r.stdout).splitlines():
            pid, _, cmd = line.partition("\t")
            rows.append((pid.strip(), cmd))
    else:
        r = run(["ps", "-axo", "pid=,args="])
        for line in text(r.stdout).splitlines():
            pid, _, cmd = line.strip().partition(" ")
            if "lightcraft-cli" in cmd:
                rows.append((pid, cmd))
    return [int(p) for p, c in rows if p.isdigit() and re.search(r"\bmcp\b", c)]


def kill(pid, force=True):
    if WIN:
        run(["taskkill", "/F", "/PID", str(pid)] if force else ["taskkill", "/PID", str(pid)])
    else:
        try:
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        except OSError:
            pass


def _main_windows(pids):
    """Windows: top-level, visible, unowned windows of these processes."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    u.GetWindow.restype = wintypes.HWND
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _l):
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in pids and u.IsWindowVisible(h) and not u.GetWindow(h, 4):  # 4 = GW_OWNER
            found.append(h)
        return True

    u.EnumWindows(cb, 0)
    return u, found


def restore_gui():
    """LightCraft draws no frames while minimized, so it ignores control requests and window close."""
    pids = set(gui_pids())
    if not pids:
        return
    if WIN:
        u, wins = _main_windows(pids)
        for h in wins:
            if u.IsIconic(h):
                u.ShowWindow(h, 9)  # SW_RESTORE
                say("gui: window was minimized; restored it")
                time.sleep(0.5)
    elif MAC:
        run(["osascript", "-e", 'tell application "System Events" to set visible of '
             '(every process whose unix id is ' + str(min(pids)) + ') to true'], timeout=10)
    elif shutil.which("wmctrl"):
        run(["wmctrl", "-x", "-R", "lightcraft"], timeout=10)


def close_gui(pids):
    """Ask the GUI to close like a window close, so it saves the library."""
    if WIN:
        import ctypes
        u, wins = _main_windows(set(pids))
        # Like .NET CloseMainWindow: only the first top-level window (LightCraft can have a second one).
        for h in wins[:1]:
            ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE
    elif MAC:
        r = run(["osascript", "-e", 'tell application "System Events" to set n to name of '
                 '(first process whose unix id is ' + str(min(pids)) + ')', "-e", "tell application n to quit"],
                timeout=15)
        if r.returncode != 0:
            for p in pids:
                kill(p, force=False)
    else:
        if shutil.which("wmctrl") and run(["wmctrl", "-x", "-c", "lightcraft"], timeout=10).returncode == 0:
            return
        for p in pids:
            kill(p, force=False)


def claude_cmd():
    return shutil.which("claude")


def registered(claude):
    return bool(claude) and run([claude, "mcp", "get", NAME]).returncode == 0


def start(a, lcdir, cli, addr):
    if a.TokenFile and os.path.isfile(a.TokenFile):
        with open(a.TokenFile, encoding="utf-8-sig") as fh:
            os.environ["LIGHTCRAFT_TOKEN"] = fh.read().strip()
        say("token: loaded into LIGHTCRAFT_TOKEN (not required by LightCraft itself)")

    # 1. GUI with control channel
    if listening(a.Port):
        say(f"gui: control port {addr} already listening; reusing the running app")
    else:
        running = gui_pids()
        if running:
            say(f"ERROR: LightCraft is running (pid {','.join(map(str, running))}) but NOT serving control port "
                f"{a.Port}. Ask the user to close it, or run 'stop', then 'start' again.")
            return 2
        gui = next((os.path.join(lcdir, g) for g in GUI_NAMES if os.path.isfile(os.path.join(lcdir, g))), "")
        if not gui:
            say(f"ERROR: no LightCraft app ({' or '.join(GUI_NAMES)}) next to {cli}. Pass -LightCraftDir.")
            return 9
        args = [gui, "--control", str(a.Port)] + (["--library", a.Library] if a.Library else [])
        kw = {"cwd": lcdir, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if WIN:
            kw["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kw["start_new_session"] = True
        subprocess.Popen(args, **kw)
        deadline = time.time() + a.TimeoutSec
        while not listening(a.Port):
            if time.time() > deadline:
                say(f"ERROR: GUI did not open {addr} within {a.TimeoutSec} s (see {LOG_HINT})")
                return 3
            time.sleep(0.5)
        say(f"gui: started, control channel listening on {addr}")

    # 2. CLI can drive the GUI
    restore_gui()
    r = run([cli, "run", "--connect", addr, "engine.commands"], timeout=60)
    first = (text(r.stdout).splitlines() or [""])[0]
    if '"ok":true' not in first:
        say(f"ERROR: CLI could not drive the GUI: {first[:300] or text(r.stderr)[:300]}")
        return 4
    say(f"cli: run --connect {addr} OK")

    # 3. Bridge handshake: one initialize request on stdin, then EOF.
    init = ('{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18",'
            '"capabilities":{},"clientInfo":{"name":"lightcraft-mcp","version":"1"}}}\n')
    r = run([cli, "mcp", "--connect", addr], timeout=30, input=init.encode())
    reply = next((ln for ln in text(r.stdout).splitlines() if '"id":1' in ln), "")
    if '"result"' not in reply:
        say(f"ERROR: bridge handshake failed: {reply[:300] or text(r.stderr)[:300]}")
        return 5
    say(f"bridge: lightcraft-cli mcp --connect {addr} answered initialize OK")

    # 4. Connect Claude Code (a stdio MCP server; Claude Code spawns the bridge itself)
    claude = claude_cmd()
    if not claude:
        say("ERROR: the claude command is not on PATH, so the MCP server can't be registered")
        return 6
    if registered(claude):
        say(f"claude: MCP server '{NAME}' already registered")
    else:
        run([claude, "mcp", "add", "-s", a.Scope, NAME, "--", cli, "mcp", "--connect", addr])
        if not registered(claude):
            say("ERROR: 'claude mcp add' failed")
            return 6
        say(f"claude: registered MCP server '{NAME}' ({a.Scope} scope) -> {cli} mcp --connect {addr}")
    say(f"READY gui={addr} mcp={NAME}")
    return 0


def stop(a):
    problems = 0
    # 1. Disconnect Claude Code from the local and user scopes (never a project's .mcp.json)
    claude = claude_cmd()
    removed = []
    if claude:
        for s in ("local", "user"):
            if run([claude, "mcp", "remove", NAME, "-s", s]).returncode == 0:
                removed.append(s)
    if removed:
        say(f"claude: removed MCP server '{NAME}' from scope(s): {', '.join(removed)}")
    elif claude:
        say(f"claude: MCP server '{NAME}' was not registered")
    else:
        say("claude: the claude command is not on PATH; registration not checked")
    if registered(claude):
        say(f"WARN: '{NAME}' still registered (claude mcp get {NAME})")
        problems += 1

    # 2. Stop bridge processes
    bridges = bridge_pids()
    for b in bridges:
        kill(b)
    say(f"bridge: stopped {len(bridges)} lightcraft-cli mcp process(es)" if bridges
        else "bridge: no lightcraft-cli mcp process running")

    # 3. Close the GUI gracefully (lets it save the library); kill only with -Force
    pids = gui_pids()
    if not pids:
        say("gui: LightCraft not running")
    else:
        restore_gui()
        close_gui(pids)
        deadline = time.time() + a.TimeoutSec
        while gui_pids() and time.time() < deadline:
            time.sleep(0.5)
        left = gui_pids()
        if not left:
            say("gui: LightCraft closed")
        elif a.Force:
            for p in left:
                kill(p)
            say(f"gui: LightCraft did not close in {a.TimeoutSec} s; killed (-Force)")
        else:
            say(f"ERROR: LightCraft still running after {a.TimeoutSec} s (a dialog may be open). "
                "Ask the user, or re-run 'stop -Force'.")
            return 7
    if problems:
        return 8
    say("STOPPED")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="lightcraft-mcp.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["start", "stop"], type=str.lower)
    ap.add_argument("-Port", type=int, default=7980)
    ap.add_argument("-Library", default="")
    ap.add_argument("-Scope", choices=["local", "user"], default="local", type=str.lower)
    ap.add_argument("-TimeoutSec", type=int, default=60)
    ap.add_argument("-Force", action="store_true")
    ap.add_argument("-LightCraftDir", default="")
    ap.add_argument("-TokenFile", default=os.environ.get("LIGHTCRAFT_TOKEN_FILE", ""))
    a = ap.parse_args(fix_argv(argv, ["-Port", "-Library", "-Scope", "-TimeoutSec", "-LightCraftDir", "-TokenFile"],
                               ["-Force"]))
    lcdir = a.LightCraftDir or find()
    cli = os.path.join(lcdir, CLI_NAME) if lcdir else ""
    if not cli or not os.path.isfile(cli):
        say("ERROR: LightCraft not found. Pass -LightCraftDir or set LIGHTCRAFT_DIR (env or "
            "~/.claude/lightcraft/config.env).")
        return 9
    if a.action == "start":
        return start(a, lcdir, cli, f"127.0.0.1:{a.Port}")
    return stop(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
