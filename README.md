# lightcraft-skills

A Claude Code plugin for culling and editing photos in **LightCraft**, ArtCraft's non-destructive photo
library and raw developer. Claude drives the LightCraft GUI through its CLI and MCP bridge, measures the
renders, and asks you before anything that depends on your taste.

| Skill | What it does |
|---|---|
| `lightcraft-mcp` | `start`: launch LightCraft with its control port, check the CLI and MCP bridge, and register the `lightcraft` MCP server with Claude Code. `stop`: disconnect and close LightCraft gracefully. |
| `lightcraft-cull` | Cull a day or a whole library. The best frame of each burst and usable singles get picked, clear failures get the reject flag, and everything else stays unmarked. Big libraries run chunk by chunk in subagents, with an optional 3-reviewer panel for borderline frames. Every mark is logged and can be rolled back. |
| `lightcraft-edit` | Edit only the photos you name: approved looks per scene type, measured subject lifts with SAM 3 or Auto Mask, local masks (signs, food, details), opt-in bystander removal, AI Denoise, and straightening. The output is a review page plus phone-sized before/after images. |

## Install

```
/plugin install lightcraft --marketplace robbydf/lightcraft-skills
```

Or add the marketplace first, then install from it:

```
/plugin marketplace add robbydf/lightcraft-skills
/plugin install lightcraft@lightcraft-skills
```

Then, in Claude Code, run `/lightcraft:lightcraft-mcp start` (plugin skills are namespaced), or just
ask Claude to start LightCraft. Copy `preferences.example.md` to `~/.claude/lightcraft/preferences.md`
first, or let the skills do it on first use.

## Requirements

- **Windows only.** The scripts use Windows PowerShell 5.1 with System.Drawing, the registry and
  Windows process APIs. macOS and Linux are **not supported**.
- **LightCraft**, tested on **0.21.1**. The install folder is detected automatically (see Configuration).
- **Git Bash.** The skills run CLI commands from Bash, because PowerShell 5.1 strips the quotes
  inside JSON arguments.
- **Python 3**, standard library only (no numpy or PIL).
- **Optional:** LightCraft's SAM 3 segmentation model, for describe and click masks. The skills never
  download it, because it needs your licence acceptance. Install it from LightCraft yourself. Without
  it, the edit skill uses the Auto Mask brush.

## Configuration

Everything personal lives outside the plugin, in `~/.claude/lightcraft/` (or `$LIGHTCRAFT_HOME`):

| File | Purpose |
|---|---|
| `preferences.md` | Your cull rules, looks, mask values and straightening policy. Copy `preferences.example.md` there and edit it. The skills read it, ask you when a key is missing, and mark a look `approved: true` once you approve a sample. |
| `config.env` | Optional `KEY=value` lines: `LIGHTCRAFT_DIR` (the install folder, written automatically after the first detection) and `LIGHTCRAFT_RUNS` (where run state is kept; default `~/.claude/lightcraft/runs`). |
| `runs/<library>/` | Durable cull and edit state: `baseline.json`, `log.jsonl`, `edits.jsonl`. |

**Install folder detection,** in this order:
1. the `LIGHTCRAFT_DIR` environment variable;
2. `LIGHTCRAFT_DIR` in `config.env`;
3. the uninstall entries in the registry;
4. `Program Files\ArtCraft\LightCraft`, `Program Files\LightCraft` or `%LOCALAPPDATA%\Programs\…`.

`scripts/find-lightcraft.ps1` prints what it finds.

**Token:** LightCraft 0.21.1 has no auth on its control port (127.0.0.1 only), so no token is needed.
`-TokenFile` / `LIGHTCRAFT_TOKEN_FILE` only sets `LIGHTCRAFT_TOKEN` inside the start script, which is a
no-op on 0.21.1. It's kept for a future LightCraft that needs auth. Never commit a token.

## Layout

```
.claude-plugin/plugin.json        plugin manifest
.claude-plugin/marketplace.json   lets this repo be added as a marketplace
skills/lightcraft-mcp/SKILL.md
skills/lightcraft-cull/SKILL.md   plus panel-brief.md (the borderline panel's reviewer brief)
skills/lightcraft-edit/SKILL.md
scripts/
  lc-env.sh             sourced by every Bash call: sets CLI, LC_SCRIPTS, RUNS, PREFS, M, PSX
  find-lightcraft.ps1   install folder detection
  lightcraft-mcp.ps1    start / stop
  measure.ps1           sharp, tilt, mean, clip, crops, sheet (contact sheet), batch (many boxes), grid
  lfit.ps1 rgb.ps1 sbs.ps1   line fit, region colour, phone before|after images
  bursts.py runstate.py review.py   burst grouping, durable run state, review page
  editlog.py                        valid edits.jsonl lines (start, done, check --fix)
  people.py                         photo -> named people map from LightCraft face naming
  looks.py                          look presets vs preferences; end-of-chunk develop check
  denoise-wait.sh                   wait for the denoise queue, write a marker (device, time)
preferences.example.md
```

## Safety

- The cull marks only with explicit ids, never deletes, never touches photos you marked before the
  run, and logs every mark. `runstate.py rollback` prints the commands to undo them.
- The edit skill records each photo's history cursor before changing it, so it can restore it.
- Neither skill rates, flags or edits outside the photos it was given.

## Using LightCraft while a run is going

A cull or edit run drives the same LightCraft window you see. You can look at photos, but don't edit
or export, and keep to these rules so nothing lands on the wrong photo:

- **Safe:** scrolling the grid, looking at and zooming or panning the photo already on screen,
  resizing the window or moving it to another monitor.
- **Avoid while a worker is running:**
  - **Clicking or arrowing to other photos.** Mask, crop, geometry and history commands act on the
    active photo. The worker re-selects its photo before each command, but a click between that select
    and the command can put the step on the photo you clicked.
  - **Changing the source, filters or album.** Workers select photos by id; a filter that hides the
    photo can make the select fail. The cull also checks that the library view is unfiltered.
  - **Minimizing the window.** It stops drawing and every request fails ("the app drew no frame").
  - **Opening dialogs** (Settings, Export, Preferences). A modal dialog can block requests the same way.
  - **Rating, flagging or editing anything.** The check after each chunk compares the whole library with
    the run log, and any change shows as a mismatch.
- **Better:** look between chunks (ask Claude for a gap), or look at the review pages and exported
  renders, which don't touch LightCraft.
- If you clicked something by accident, tell Claude the time and the photo. It checks that photo's
  history after the chunk and undoes any step that landed on it.

## Known behaviour, LightCraft 0.21.1

- A **minimized** window stops drawing, and every request then fails with "the app drew no frame".
  Keep it visible. `lightcraft-mcp start` restores it.
- A backslash in a CLI `path=` value breaks `run`: use forward slashes.
- `geometry.upright mode=auto` is unreliable on busy scenes. `geometry.guides` switches the mode to
  guided.
- `lightcraft-cli mcp` without `--connect` starts a separate headless session, not the GUI.

## License

MIT. See [LICENSE](LICENSE).
