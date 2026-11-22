# lightcraft-skills

A Claude Code plugin for culling and editing photos in **LightCraft**, ArtCraft's non-destructive photo
library and raw developer. Claude drives the LightCraft GUI through its CLI and MCP bridge, measures the
renders, and asks you before anything that depends on your taste.

| Skill | What it does |
|---|---|
| `lightcraft-mcp` | `start`: launch LightCraft with its control port, check the CLI and MCP bridge, and register the `lightcraft` MCP server with Claude Code. `stop`: disconnect and close LightCraft gracefully. |
| `lightcraft-cull` | Cull a day or a whole library. The best frame of each burst and usable singles get picked, clear failures get the reject flag, and everything else stays unmarked. Big libraries run chunk by chunk in subagents, with an optional 3-reviewer panel for borderline frames. Every mark is logged and can be rolled back. |
| `lightcraft-edit` | Edit only the photos you name: approved looks per scene type, measured subject lifts (through `lightcraft-face-lift`), local masks (signs, food, details), opt-in bystander removal, AI Denoise, straightening, and a hand-off to PhotoCraft (a rendered PSD copy) for pixel edits. The output is a review page plus phone-sized before/after images. |
| `lightcraft-face-lift` | Lift the faces of your own people and pets with a SAM 3 or Auto Mask mask, measured against the background, and lessen a shadow across a face. `lightcraft-edit` calls it for its subject-lift step; you can also use it on its own ("brighten his face"). |
| `lightcraft-export` | `/lightcraft-export [target] [trip]` (default target `google-photos`): export a trip's picks that show your own people (from LightCraft's face naming) at the target's settings into a folder the platform picks up. For Google Photos this is 16 MP sRGB JPEG with the date and GPS kept, into a folder Google Drive for desktop backs up. It is read-only on the catalog, never overwrites, and a manifest makes reruns skip what was already exported. |

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

- **Windows, macOS or Linux.** The helpers are Python and bash. Tested on Windows 11; on macOS and
  Linux the install-folder detection and the GUI start/stop use best-guess paths (see Configuration),
  so set `LIGHTCRAFT_DIR` if LightCraft isn't found.
- **LightCraft**, tested on **0.21.1**. The install folder is detected automatically (see Configuration).
- **Bash:** Git Bash on Windows (the skills run CLI commands from Bash, because PowerShell 5.1 strips
  the quotes inside JSON arguments); the system bash on macOS and Linux.
- **Python 3.8+** (`python`, or `python3` where there is no `python`), with **Pillow and numpy** for the
  image helpers: `python -m pip install --user pillow numpy`. The other scripts use the standard
  library only.
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

**Install folder detection,** in this order (the same as `scripts/find_lightcraft.py`):
1. the folder given on the command line (`--dir` to `find_lightcraft.py`, `-LightCraftDir` to
   `lightcraft-mcp.py`);
2. the `LIGHTCRAFT_DIR` environment variable;
3. `LIGHTCRAFT_DIR` in `config.env`;
4. then per system:
   - **Windows:** the uninstall entries in the registry, then `ArtCraft\LightCraft` or `LightCraft`
     in `Program Files`, `Program Files (x86)` and `%LOCALAPPDATA%\Programs`;
   - **macOS:** `LightCraft.app`, `ArtCraft/LightCraft.app`, `ArtCraft LightCraft.app` or any
     `*LightCraft*.app` in `/Applications` or `~/Applications` (the CLI in `Contents/MacOS`);
   - **Linux:** `/opt/lightcraft`, `/opt/LightCraft`, `/opt/ArtCraft/LightCraft`, `/usr/lib/lightcraft`,
     `~/.local/share/lightcraft`, `~/.local/opt/lightcraft`;
5. last, on every system, the folder of `lightcraft-cli` on `PATH`.

`python scripts/find_lightcraft.py` prints what it finds (`--help` for the options).

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
skills/lightcraft-face-lift/SKILL.md (the subject lift, called by lightcraft-edit)
skills/lightcraft-export/SKILL.md plus targets/<target>.md (one per platform: google-photos.md)
scripts/
  lc-env.sh             sourced by every Bash call: sets CLI, LC_SCRIPTS, LC_PY, RUNS, PREFS, M, LCX
  find_lightcraft.py    install folder detection (Windows, macOS, Linux)
  lightcraft-mcp.py     start / stop
  measure.py            sharp, tilt, mean, clip, crops, sheet (contact sheet), batch (many boxes), grid, corners
  lfit.py rgb.py sbs.py   line fit, region colour, phone before|after images
  lcimg.py lcargs.py    shared image code (Pillow + numpy) and PowerShell-style options
  bursts.py runstate.py review.py   burst grouping, durable run state, review page
  editlog.py                        valid edits.jsonl lines (start, done, done-ids, check --fix)
  lcjson.py                         read CLI output: history cursor, crop % per edge, masks, SAM parts
  people.py                         photo -> named people map from LightCraft face naming
  looks.py                          look presets vs preferences; end-of-chunk develop check
  denoise-wait.sh                   wait for the denoise queue and the listed photos (--ids), write a marker
  seg-wait.sh                       prepare SAM 3 for a photo and wait until it is ready
  seg-chain.sh                      one SAM 3 prompt mask over several people, waiting for each part
  export-ids.sh                     export photos as ID-SUFFIX.jpg (no id token in export names)
  tiltprev.py                       tilt preview sheet (-6..+6 deg) for the user to pick an angle
  export_picks.py                   export selection: picks with your own people, review list, manifest skip
  export_stage.py export-stage.sh   batched export into a watched folder: same-drive staging, no overwrite,
                                    manifest with crash recovery, edit-history signatures
preferences.example.md
```

Tests (no LightCraft needed; the image tests skip without Pillow and numpy):
`python -E -m unittest discover -s tests -v` from the repo root (`python3` on macOS and Linux).
GitHub Actions runs them on Windows, macOS and Linux (`.github/workflows/tests.yml`).

## Safety

- The cull marks only with explicit ids, never deletes, never touches photos you marked before the
  run, and logs every mark. `runstate.py rollback` prints the commands to undo them.
- The edit skill records each photo's history cursor before changing it, so it can restore it.
- Neither skill rates, flags or edits outside the photos it was given.
- The export skill never marks or edits anything: it checks afterwards that no rating or flag changed.
  It never overwrites or deletes in the export folder, and it never uploads or signs in anywhere.

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
