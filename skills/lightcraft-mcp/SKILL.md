---
name: lightcraft-mcp
description: Use when the user asks to start/launch or stop/shut down LightCraft (the ArtCraft photo editor GUI, not headless) together with the LightCraft CLI MCP bridge, to connect or disconnect Claude Code from the LightCraft MCP server, or runs /lightcraft-mcp start or /lightcraft-mcp stop. Also when lightcraft-cli --connect or mcp__lightcraft__* tools fail because nothing is listening on 127.0.0.1:7980.
---

# lightcraft-mcp

Two subcommands, both handled by the plugin's script. The argument after the skill name picks one
(`/lightcraft-mcp start`, `/lightcraft-mcp stop`). With no argument, ask which.

The script is in the plugin's `scripts` folder, two levels above this skill's base directory
(`<base>/../../scripts/lightcraft-mcp.ps1`). Use the real base directory you were given when this
skill loaded. From PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<base>\..\..\scripts\lightcraft-mcp.ps1" start
powershell -NoProfile -ExecutionPolicy Bypass -File "<base>\..\..\scripts\lightcraft-mcp.ps1" stop
```

- **Install folder:** found automatically by `find-lightcraft.ps1` in this order: `-LightCraftDir`,
  the `LIGHTCRAFT_DIR` environment variable, `LIGHTCRAFT_DIR=` in `~/.claude/lightcraft/config.env`,
  the registry, then `Program Files\ArtCraft\LightCraft`. That folder holds `lightcraft.exe` (the GUI)
  and `lightcraft-cli.exe` (the CLI and bridge).
- **Control address:** `127.0.0.1:7980`.
- **MCP server name in Claude Code:** `lightcraft`.

## start

1. Starts the GUI with `--control 7980`, or reuses an instance already serving the port.
2. Checks that the CLI can drive it (`lightcraft-cli run --connect … engine.commands`).
3. Checks that the bridge answers an MCP `initialize` (`lightcraft-cli mcp --connect 127.0.0.1:7980`).
4. Connects Claude Code if the server isn't registered yet:
   `claude mcp add -s local lightcraft -- "<cli>" mcp --connect 127.0.0.1:7980`. Claude Code spawns
   the bridge itself (stdio), so nothing is left running for it.

Options:
- `-Library "<folder>"`: only when it starts a new GUI; the default is the last library.
- `-Scope user`: register for every project instead of only the current folder.
- `-Port`, `-TimeoutSec`, `-LightCraftDir`, and `-TokenFile` (see Token).

Success ends with `READY`. The `mcp__lightcraft__*` tools appear after Claude Code (re)connects. If
they are missing in the current session, tell the user to start a new session.

## stop

1. Disconnects Claude Code: `claude mcp remove lightcraft` from every scope it is in.
2. Stops any running `lightcraft-cli … mcp` bridge processes.
3. Closes the GUI gracefully (a window close, so the library saves) and waits up to `-TimeoutSec`.

Success ends with `STOPPED`. `-Force` kills LightCraft if it won't close; use it only when the user
says so.

## Exit codes

| Exit | Meaning | What to do |
|------|---------|------------|
| 2 | start: LightCraft is running **without** `--control` | Tell the user, and offer `stop` then `start`. Never kill it unasked. |
| 3 | start: the control port never opened | Check `%APPDATA%\LightCraft\logs\lightcraft.log` (`control server failed to bind` means the port is busy). |
| 4 / 5 | start: the CLI or bridge handshake failed | Show the error line. |
| 6 | start: `claude mcp add` failed | Run it by hand to see the error. |
| 7 | stop: the GUI is still open (a dialog?) | Ask the user, and re-run `stop -Force` only on their yes. |
| 8 | stop: the registration is still present | Run `claude mcp list` and remove it by hand. |
| 9 | LightCraft not found | Ask for the install folder and save it as `LIGHTCRAFT_DIR=<folder>` in `~/.claude/lightcraft/config.env`. |

## Token

Tested on LightCraft 0.21.1, which has **no auth** on the control port (127.0.0.1 only), so no token
is needed.
- If you have a token file anyway, pass `-TokenFile <file>` or set `LIGHTCRAFT_TOKEN_FILE`. `start`
  then exports it as `LIGHTCRAFT_TOKEN` for any wrapper.
- Never print the token.
- If a newer LightCraft rejects connections for missing auth, look for a new token flag or
  environment variable in `lightcraft.exe --help` and in the `lightcraft-cli.exe` usage (run it with
  no arguments).

## Common mistakes

- `lightcraft-cli mcp` **without** `--connect` starts a separate headless session, not the GUI.
- `claude mcp get lightcraft` exiting 1 with `No MCP server named "lightcraft"` just means it isn't
  registered.
- Running `stop` closes the user's LightCraft window: only run it when they asked to stop.
- A **minimized** LightCraft draws no frames, so it ignores control requests ("the app drew no frame
  for 5 s") and window-close.
  - The script restores the window first.
  - If you call `lightcraft-cli` or `mcp__lightcraft__*` tools directly and see that error, restore
    the window, or re-run `start`.
