---
name: edit
description: Use when the user asks to edit, develop, retouch or adjust photos in LightCraft (ArtCraft), e.g. "edit the picks from June 14", "brighten the person on the left", "the subject is too dark", "fix the exposure", "straighten this building", "denoise this", or "apply my night look".
---

# lightcraft:edit

Edit only the photos the user names, or a scene type they approved for a batch. Picks come from a
`lightcraft:cull` run, or from ids the user gives. Never rate, flag or reject here: that belongs to
`lightcraft:cull`.

## Setup

- LightCraft must be running with the bridge: use the `lightcraft:mcp` skill (`start`). Keep the window
  un-minimized, or requests fail with "the app drew no frame".
- **"lost the LightCraft app … control channel closed before a complete reply line"** twice in a row
  (a minute apart) means LightCraft has died, not that it is busy: in testing, a GPU driver reset
  stopped its window while an error box kept the process alive. Workers stop and report it. The
  orchestrator tells the user and restarts it only on their yes (`lightcraft:mcp` `stop -Force`, then
  `start`); edits made before the crash were kept. Then re-read each open photo with `develop.get`.
- Run CLI commands **from Bash**: Windows PowerShell 5.1 strips the `"` inside JSON arguments.
  Variables don't persist between calls, so start every Bash call with:
  ```bash
  source "<base>/../../scripts/lc-env.sh"   # <base> = this skill's base directory, written with forward slashes (C:/Users/...); sets CLI, LC_SCRIPTS, LC_PY, RUNS, PREFS, M, LCX, PSX
  RUN="$RUNS/<library name>"   # the cull run's folder; ask the user if unsure
  SP="<session scratchpad>/edit"; mkdir -p "$SP"
  ```
  Repeat all three lines in **every** Bash call, `RUN` and `SP` included: a new call starts with
  them unset. `editlog.py` refuses to run without a valid `RUN`; in testing, an unset `RUN` once
  wrote the edit log into the current folder. A library with no cull run has no run folder yet:
  create it once with `python -I "$LC_SCRIPTS/editlog.py" "$RUN" init` before the first `start`.
  If `lc-env.sh` can't find LightCraft, ask the user for the install folder and write
  `LIGHTCRAFT_DIR=<folder>` to `~/.claude/lightcraft/config.env`.
  - Use forward slashes in `path=`.
  - **Paths in Python:** `$RUN`, `$SP`, `$CLI` and `$LC_SCRIPTS` may be msys paths (`/c/Users/...`).
    Bash converts them only when they are passed as **arguments** to a program, so pass them that way
    (`python -I script.py "$RUN"`). Never write them inside Python code (a heredoc or `python -c`):
    there use a Windows-style path (`cygpath -m "$RUN"` gives `C:/Users/...`). Never call `$CLI` from
    a Python subprocess; run CLI commands from Bash. In testing, a worker hit both.
  - **Two kinds of scripts:** the standard-library ones (`editlog.py`, `runstate.py`, `looks.py`,
    `people.py`, `review.py`, `bursts.py`, `lcjson.py`) run as `python -I "$LC_SCRIPTS/<name>.py"`. The image
    helpers (`measure.py`, `lfit.py`, `rgb.py`, `sbs.py`, `tiltprev.py`) run **only** through `M` and
    `LCX`, which use `"$LC_PY" -E`: `-I` hides Pillow and numpy installed with `pip --user`, and the
    helper then reports them missing.
  - **Quote `"$CLI"` everywhere**, including inside loops and background jobs: its path has spaces,
    and an unquoted `$CLI` in a background loop died without a word in testing.
  - **Deleting files:** write `rm -f "${SP:?}"/name`, never a bare `"$SP"/*` (the safety check blocks
    it), and never inside a background `bash -c`.
  - **Files written from Python on Windows** get CR line endings: open them with `newline='\n'`, or
    strip with `tr -d '\r'`, before another script reads them line by line.
  - `M` modes:
    - `mean`: brightness 0–255.
    - `clip`: % blown (any channel at 255) and % crushed (all channels at 0).
    - `tilt`.
    - `crops`: at most 4 files.
    - `sheet`: a contact sheet of up to 12 whole frames, `-Cols` across (default 3), each labelled
      with its file name. 9 per sheet reads well: classify 25 frames in 3 Reads, e.g.
      `f=("$SP"/before1k/*.jpg); M sheet "${f[@]:0:9}" -Out "$SP/sheet1.png"` (an array keeps
      paths with spaces whole).
    - `batch`: one list file, one measurement per line: `<image>|x0,x1,y0,y1[|label]` (relative
      images are read from the list's folder; `/c/...` paths are converted on Windows). Prints mean, blown and crushed for every line in a
      single Python start. Use it for before/after numbers on a whole chunk: about 100 separate
      `M` calls were the slowest part of a chunk in testing.
    - `grid`.
    - `corners`: lens corner darkening, for the vignette rule (see Daylight adjustments). Give it
      every unedited render of one venue and lens (3 or more) and read the `MEDIAN` line it adds:
      single frames are swayed by the scene (sky, a dark doorway).
  - `-Region x0,x1,y0,y1` takes fractions of the frame, and `-Out` must end in `.png`. `M mean`
    always needs `-Region` (use `0,1,0,1` for the whole frame).
- **GPU rendering (once per run, before the first denoise; the orchestrator, never a worker).** Run
  `"$CLI" run --connect app.gpu wait=false`.
  - `enabled: true`: nothing to do.
  - `enabled: false` with `reason` "disabled by the GPU rendering preference": the GPU is off by the
    user's setting. **Ask the user** whether you (or a worker) may turn it on for this run, and say why:
    AI Denoise on the CPU took about 70 s per frame in testing, and on an entry-level GPU (MX130) about
    20 s. Also say the risk: on that MX130, GPU rendering plus a 6000 px export of a denoised photo
    hit the Windows GPU watchdog (a driver reset), and LightCraft died mid-run. It's their setting,
    so never turn it on without a yes.
  - **While GPU rendering is on, export at most `longEdge=4000`** on an entry-level GPU (2–4 GB, such
    as the MX130). The 100 % checks below then use 4000 px renders; say so in the report.
  - Any other reason (no adapter, a driver error): don't ask; denoise runs on the CPU. Say so once.
  - On a yes: `"$CLI" run --connect app.gpu enabled=true wait=true`. It must return
    `available: true` with an `adapter`; if not, set it back with `app.gpu enabled=false`, tell the
    user the `reason`, and go on with the CPU. `denoise.status` shows `device: {kind: "pending"}`
    until the next denoise job, then `kind: "gpu"`; check it on the first job and report the device.
  - Workers never change `app.gpu` or `denoise.settings`; put that in the brief.
- **Preferences:** read `$PREFS` (`~/.claude/lightcraft/preferences.md`) before the first edit.
  - If it doesn't exist, copy `preferences.example.md` from the plugin root there, and tell the user
    that every look and value is still unapproved.
  - If a key this skill needs is missing, ask the user and offer to add the answer.
  - Names in `backticks` such as `look.night` or `lift.mask_limit` are those keys.
- Helpers in `$LC_SCRIPTS`, run with `LCX <script> <args>`. Give the script name only
  (`LCX sbs.py …`): `LCX` adds the folder. They need Pillow and numpy (`"$LC_PY" -m pip install --user
  pillow numpy`); a missing package is reported by name. The old name `PSX x.ps1` still works.
  - `lfit.py <file> x0 y0 x1 y1`: line fit on one long edge (a pole, a roofline), returns its angle in
    degrees. More reliable than `M tilt`, which responds only 20–60 % to a real rotation on busy scenes.
  - `rgb.py <file> x0,x1,y0,y1`: mean R/G/B of a region, for colour checks (signs, food, skin).
  - `sbs.py -Before <f> -After <f> -Region x0,x1,y0,y1 -Out <f.jpg>`: a labelled BEFORE | AFTER
    side-by-side for viewing on a phone, at most 1600 px wide.
- **Reading CLI output:** pipe one call into `lcjson.py` instead of parsing JSON by hand (the CLI
  output starts with a blank line, or one line per command, which broke a worker's `json.load`):
  ```bash
  "$CLI" run --connect history.list id=ID | python -I "$LC_SCRIPTS/lcjson.py" cursor   # 12, or null
  "$CLI" run --connect develop.get id=ID  | python -I "$LC_SCRIPTS/lcjson.py" crop     # angle, crop % per edge
  "$CLI" run --connect develop.get id=ID  | python -I "$LC_SCRIPTS/lcjson.py" masks    # mask count
  "$CLI" run --connect develop.get id=ID  | python -I "$LC_SCRIPTS/lcjson.py" seg NAME # mask id, parts, parts with seg data
  python -I "$LC_SCRIPTS/editlog.py" "$RUN" done-ids <round> --ids 501,502           # done: … / todo: …
  ```
- **Id lists** (`--ids` of `runstate.py`, `denoise-wait.sh`, `editlog.py done-ids`): `501,502,503`,
  `501 502 503` and ranges `501-505` all work; a bad id or a reversed range stops with a message.
  Before 0.1.13, `runstate.py marks --ids 501 502` silently checked only 501.
- MCP tools may be deferred. Load them in one ToolSearch call:
  `select:mcp__lightcraft__render_preview,mcp__lightcraft__set_develop,mcp__lightcraft__get_develop,mcp__lightcraft__export`.

## Which photos

- From a cull run: `python -I "$LC_SCRIPTS/runstate.py" picks "$RUN" [--day 2025-06-14]` lists the picks
  with their file names.
- Confirm the list with the user before editing more than 5 photos. If the user asks for "N picks"
  without naming them, choose one pick per group (different scenes) and mix day and night.
- Skip photos that already have edits (`edited: true`) unless the user says otherwise. A redo of
  photos edited in an earlier round first reverts them (see Revert), using the `edits.jsonl` record.

## Before the first change to a photo

0. Once per session (or batch), before the first edit: save the marks, for the check at the end
   (see "Marks" under Batches): `"$CLI" run --connect catalog.query limit=100000 > "$SP/marks-before.json"`.

1. Record its history: `"$CLI" run --connect history.list id=ID | python -I "$LC_SCRIPTS/lcjson.py" cursor`
   prints the `cursor`, which is `null` if it was never edited. Record it **before every step you may
   take back** (a straightening, a mask), not only before the first: in testing, a worker ran
   `crop.autoStraighten` on six photos in one loop before reading their cursors.
2. Note its masks: `"$CLI" run --connect develop.get id=ID | python -I "$LC_SCRIPTS/lcjson.py" masks`
   (`get_develop` is too big for the tool output once a prompt mask exists).
3. Append `{"id":ID,"cursor":<cursor>,"masksBefore":<count>}` to `$RUN/edits.jsonl` with the helper,
   which always writes valid JSON:
   `python -I "$LC_SCRIPTS/editlog.py" "$RUN" start ID <cursor|null> <count> <round>`.
   - Never write the line by hand from Python (`None` and `True` are not JSON). In testing, 19 lines
     written that way broke strict readers. `editlog.py "$RUN" check` lists invalid lines, and
     `check --fix` repairs them (with a backup).
   - Use the durable run folder, not the scratchpad, which a reboot clears.
   - After the photo is finished: `editlog.py "$RUN" done ID <round> [key=value …]`.
   - A rerun skips ids already marked done in the current round.
4. Start **every** CLI call with `library.select 'ids=[ID]'`. Mask, geometry and history commands act
   on the active photo, and the user may click another photo in the GUI.

**Revert:**
- If `cursor` was a number: `library.select 'ids=[ID]' history.restore index=<cursor>`.
- If `cursor` was `null`: `develop.reset 'ids=[ID]'`. This is allowed **only** then, because it returns
  the photo to unedited. Check `enhance.denoise_on` afterwards, and turn denoise off with
  `denoise.toggle id=ID enabled=false` if it is still on.
- **Never use `edit.undo` or `edit.redo`.** They act on the library's global history, not on one
  photo: in testing, an undo after a step that recorded nothing removed another photo's step. To take
  back a step, read `history.list id=ID` (its `cursor`, C) before the step, then
  `library.select 'ids=[ID]' history.restore index=C`.
- A step that returns `changed:false`, or is rejected, recorded nothing: there is nothing to take
  back, so do nothing.

## Per-photo order

**Batch the exports first (speed).** Exports cost about 15 s each at 2000 px, so before editing any
photo of a chunk, export every unedited photo in calls of 5–6 ids (more passes the 120 s tool limit).
- **Export the befores before applying any look,** preset included. In testing, a worker applied the
  preset to the whole chunk first and had to reset every photo and export again.
- **One export batch per tool call.** Four batches in one call ran past 120 s.
```bash
bash "$LC_SCRIPTS/export-ids.sh" "$SP/before2k" before 2000 501 502 503 504 505   # -> before2k/501-before.jpg ...
bash "$LC_SCRIPTS/export-ids.sh" "$SP/before1k" before 1000 501 502 503 504 505
```
`export-ids.sh` names each file `ID-SUFFIX.jpg`: LightCraft has no id token in export names (only
the camera file name), and the helper maps the result's `files` list, which comes in the order of the
ids. Use it for every export of a known id (befores, afters, full-size denoise checks). Ids that
share a camera file name (virtual copies, two cameras) are exported again one at a time, which costs
one extra export each: keep such ids out of a full call of 5–6. The 1000 px
files are the classification and clipping-check renders.
- **Never pipe `app.export` into `head`** or another command that closes early: the export broke
  with "os error 232". Redirect the result to a file instead.
- **When every photo of the chunk gets a 2000 px before anyway** (a small chunk, or a test where all
  photos get review cards), skip the 1000 px export: use the 2000 px befores for `M sheet` and
  `M batch`, and export the afters at 2000 px too, so before and after are measured at the same size. Never reset an edited photo just to get a "before".
- **2000 px befores are required** for every review-list id and every photo that isn't plain (own
  people, a denoise candidate, a tilt). Plain photos may skip the 2000 px before to save time.
- **Also keep the 2000 px before of every photo the report lists under "Needs the user"** (a dim
  subject left alone, a venue question, own or stranger?), so the orchestrator can show it on a card.
  In testing, note cards had no before because only review-list befores were kept.
- **Never upscale a 1000 px render** as a before: the user reviews at 2000 px and at 100 % on a phone.
  In testing, workers sent 1000 px and upscaled befores.
- **A photo flagged late** (a clip rule that stopped on a plain photo) with no 2000 px before: export
  it from history. `library.select 'ids=[ID]' history.list` gives the current cursor C. If the
  recorded cursor is a number R, run `history.restore index=R`, export the 2000 px before, then
  `history.restore index=C`, and confirm with `develop.get` that the edit is back. With a `null`
  cursor there is no unedited step to restore: write "before is 1000 px" on the card instead of
  upscaling. (Not yet tested in a run: compare `develop.get` before and after.) Likewise, apply the look to
every photo that needs nothing else (no mask, no denoise, no straightening), then export their after
renders together the same way. Use a new file name for each working render: a re-export under the
same name can be read back stale.

1. **Classify** from the 1000 px render of the unedited photo. In a batch with a venue table (see
   Batches), the look comes from the table: only check the rest.
   - night street or indoor, light show or black sky, or daylight;
   - whether there is a subject of the user's own people or pets (strangers don't count);
   - whether verticals or a horizon could be tilted (see Straightening).
   - Get the ISO with `photo.allMetadata id=ID` (EXIF "ISO Speed").
2. **Straighten**, if it measures tilted (see Straightening). It comes first because transforms move
   the frame under a mask.
3. **Look**, by scene type (see Looks). A photo whose scene type has no approved look gets **nothing**
   (no look and no mask) until the user approves the sample, unless the user asked for a trial batch
   (see Looks).
4. **Subject lift** for the user's own people and pets: run `lightcraft:face-lift` (see Subject
   lift); its "When to lift" table decides, and it lifts some faces that aren't darker than the
   background (bright daylight faces, a shadow across a face). Then any **local fixes** (see Local
   masks: signs, food, details).
5. **AI Denoise**, if ISO `denoise.iso_candidate` (default 3200) or above and grain shows at 100 % (see AI Denoise).
6. **Clipping check** (see Clipping check).
7. **After render:** export at 1000 px and Read it.

## Looks

Apply a look with `set_develop {id, values: {...}}`, where `values` takes slider ids. The looks are in
the preferences file:
- `look.night`: night or high-ISO street scenes, and dim indoor venues.
- `look.light_show`: parades, fireworks, buildings lit against a dark sky. It is `look.night` with a
  few values changed, because with shadows +30 a black sky turns blotchy grey. On a night parade,
  blacks -20 and -10 crushed the trees and the crowd, while -2 kept them and the sky stayed black. The
  foreground clip check (see Clipping check) adjusts it per photo.
- `look.daylight`.
- `look.scene_map`: which look other scene types reuse. With the defaults, a night skyline over water
  with a cloudy sky gets the light-show look, because the night look's shadows +30 turned a cloudy sky
  brown-grey. A dim venue gets the night look at any ISO.
  - **Classify by the light, not the place:**
    - A dim interior (a temple or shrine hall, a shop, a restaurant, an arcade) is a dim venue, so it
      gets `look.night`, even when lanterns or lit displays are in frame. In testing, a dim temple
      interior got the light-show look by mistake.
    - `look.light_show` is for a lit subject against a black or night sky that fills a large part of
      the frame: a lit gate, tower or skyline, fireworks, a parade.
    - A night street with lit signs and no large area of sky is a night scene.
    - A covered area at dusk that still reads bright (whole-frame mean 100 or more, ISO 800 or
      lower) isn't settled yet. Use `look.night` and put the venue's first photo on the review list
      with `decide` "Night or daylight look for <venue>?".
  - **Write the venue and its look on one line** in the report, so the next chunk matches it.
    Ambiguous venues go on the review list as above.
  - Treat every photo from one venue the same way. In testing, one restaurant was edited in one chunk
    and left unedited in the next.
  - The exception is a venue the user asked to leave unedited.

**Looks as presets (speed).** Apply a look to many photos in one call instead of one `set_develop`
each:
1. Once per run, save each approved look as a LightCraft preset holding only its own values:
   `preset.saveRecipe name="LC look.night" group="lightcraft" 'recipe=[{"id":"light.shadows","value":30},…]'`.
   - A recipe takes plain develop controls only, with no white balance, geometry or crop. Set any of
     those with `set_develop` per photo.
   - **Check the presets against the preferences at the start of every run** (the preferences may
     have changed since they were saved):
     ```bash
     "$CLI" run --connect preset.export path="$SP/looks.lcpreset" group=lightcraft
     python -I "$LC_SCRIPTS/looks.py" presets "$PREFS" "$SP/looks.lcpreset"
     ```
     It prints `OK`, `MISSING` (save it with the recipe it prints) or `DIFF` with the changed values.
   - **LightCraft never updates a preset in place.** Saving a changed recipe under the same name
     makes a second preset with the same name and the id `…-2` (tested), and anything still holding
     the old id keeps applying the old values. On a `DIFF`: `preset.delete id=<old id>`, save the
     recipe again, take the new id from the result, run `looks.py presets` again until every look is
     `OK`, and give workers the new id.
   - **Photos already edited keep the old values** (a preset copies values; it is not a link). When a
     look changed, list the photos edited with it in earlier rounds (`edits.jsonl`, `look=` on the
     done lines) and offer the user a redo; never redo them unasked.
   - Saving an unchanged recipe under the same name returns the existing preset. Use `presets.list`
     to find an id.
2. Record each photo's history cursor first, as usual (see "Before the first change to a photo").
   Then apply the look to every photo of that look in the chunk with one call:
   `preset.apply id=<presetId> 'ids=[501,502,503,…]'`.
3. **The first time in a run, check one photo with `develop.get`.** Every look value must be set and
   nothing else changed. If it isn't, fall back to `set_develop` per photo and say so in the report.
4. Per-photo extras (blacks from a clip fix, denoise noise reduction, white balance) still go through
   `set_develop` afterwards.

**Before using a look,** check that it is `approved: true`. If not, show one sample and wait for
approval (see New looks). The `lift.mask.*` values have the same gate: if one isn't approved, show the
first masked photo of that kind and wait before masking the rest.

**Daylight adjustments:**
- **Flat or overcast frame:** dehaze 6.
- **Lens already darkens the corners:** vignette 0. Decide it once per venue and lens with
  `M corners` on the unedited renders (3 or more frames): only a `MEDIAN … lens_darkening=likely` line
  counts. `unsure` or `no` keeps the look's vignette; say which in the report.
- **Dark frame:** if the mean of the whole frame (`M mean -Region 0,1,0,1`) is under 100, add
  `light.exposure` `exposure.boost` (see Global exposure boosts).
- **Shaded lower half still near-black:** if the bottom half stays near-black (mean under 40), raise
  shadows to 35. If it is still under 40, add a linear-gradient mask over the bottom half:
  `library.select 'ids=[ID]' mask.add kind=linear 'start=[0.5,1.0]' 'end=[0.5,0.55]' name=Ground`,
  then `mask.adjust id=N 'values={"exposure":0.4}'`.
  - The effect is full at `start` and fades out by `end`.
  - Check it like a subject mask: briefly set +3, export, read, then set the real value.
  - If the command is rejected, skip it and report the bottom-half mean.

**White balance (night or indoor tungsten):** if neutral areas (white walls, shirts, signs) read
clearly orange, lower the global white balance by `wb.night_cooler_percent` (default 5–10 %) and check again. The control is `wb.temp`,
in Kelvin: one night street went from the as-shot 2698 K to 2500 K. Never set a warmer white balance at
night. (Mask `temp` values are a relative shift, not Kelvin.)
- White balance is a visual judgment. Say so in the report and give the Kelvin before→after.
- Also add the `exposure.boost` if the frame still looks dim; see Global exposure boosts.

**Global exposure boosts:** this covers the dark frame, the dim tungsten frame and the face far darker
than the background (Subject lift).
- At most `exposure.boost` (default +0.25) in total per photo, whatever the scene type. If one boost was already added, add no
  other.
- **Blown gate for every boost** (the same as the face-shadow fix): keep it only if the whole frame's
  blown % rises by less than 0.5 points and no face box goes over 2 % blown. Otherwise take it off
  and say so. In the all-photos run the boost came off again on 5 sunlit plaza frames for this.
- **When the user asks for more exposure, that overrides the cap.** Step `exposure.on_request_step`
  at a time and report the blown %.
- **"Lift the highlights" (or "brighter") on a dark light-show subject** means brighter lights, not
  the Highlights slider: on a mid-dark float (subject mean about 15) `light.highlights` barely moves
  it (14.7 -> 15.8). Raise exposure (+0.5) and set `light.whites` 10, then check blown on the
  subject. In testing, whites +40/45 with exposure +0.5 brightened 19 dark castle frames, but the
  user then asked for whites 10 on all of them: whites barely moves the subject mean (0–1 point) and
  only adds glare on lamps and lit stone. The user's request overrides "never raise exposure on a
  light show". A worker that finds a subject this dark (mean under about **16**) leaves it and lists
  it under "Needs the user", offering "Brighten (exposure +0.5, whites 10)". In testing the user
  brightened frames at 8.5–15.6 and kept most frames at 16–20 as they were.
- Run `M clip` right after adding it, and remove it if blown rose by more than 0.5 points.
  - **Night scenes with lit signs or lamps** (`exposure.night_signs_ignore_blown`): measure blown with `-Region` boxes that leave out the
    signs and lamps. Blown inside signs doesn't count. Keep the boost even when the whole-frame blown
    rises. In testing, the user accepted rises of 1.6 and 2.8 points, all of it inside signs.

**New looks:**
- Any look not marked `approved: true` in the preferences is proposed. A scene type that fits none of the looks above needs one.
- Show the user one sample and wait for approval before editing more of that scene type.
- In a **trial batch** that the user explicitly asked for, apply the proposed look to every photo of
  that type, and say in the report that it is unapproved.
- When the user approves a look, set `approved: true` for it in the preferences file. Add a new
  scene type to `look.scene_map`, or a new `look.<name>` with its values.

## Subject lift (people, pets)

The lift has its own skill, **`lightcraft:face-lift`**. It covers whether a face needs a lift and
how to measure it, a shadow across a face, the SAM 3 and Auto Mask paths, the mask values and
ladders, and the edge checks.
- **Main session:** invoke it with the Skill tool (`lightcraft:face-lift`; a copy used
  without the plugin is `face-lift`).
- **Batch worker, or no Skill tool:** Read `<base>/../face-lift/SKILL.md`, where `<base>`
  is this skill's base directory. Name that file in every worker brief.
- The setup, history record and look from this skill carry over. Afterwards come back here for local
  fixes, denoise, the clipping check and the after render.

## Local masks: signs, food, details

These came from user requests in testing. Do them only when the user asks, or when the condition below is
clearly met. Make the mask as in Path A of `lightcraft:face-lift`, check coverage with the magenta
overlay, then set the values.

- **A bright sign or billboard competing with the people:** darken the sign a little **and** lift the
  people a little.
  - Mask the sign with **clicked points** (`kind=object`). The prompt "billboard" also took every
    other sign.
  - Values: `local.sign` (default `{"exposure":-0.3,"highlights":0,"saturation":-15}`, or -25 on a
    pale or white screen).
  - Highlights -20 turned a near-white screen saturated cyan (R 225→177). Check the sign's colour with
    `rgb.py` before→after: it should get darker while keeping its R/G/B balance. Measure colour on
    2000 px exports.
  - Raise the people's mask exposure by +0.1.
- **Food that should look rich** (raw meat that "was very red in real life"): describe mask such as
  `'text=raw beef'`, with `local.food` (default `{"saturation":35,"temp":-6,"hue":-5}`; tested range:
  saturation 30–40, temp -5 to -8, hue -5 to -6).
  - Judge it by eye at 100 % so it doesn't go neon. Fat and plate must stay unchanged.
  - The rest of the photo keeps whatever the user decided (it may stay unedited).
- **A detail lost in shadow** (lanterns merging with dark tree trunks): clicked points on that detail
  only, `local.detail` (default `{"exposure":0.45,"shadows":20}`, stepping to 0.65).
  - "A bit more lift" means +15–20 % on that detail. In testing, 0.30 gave +10 %, 0.45 barely moved it,
    and 0.65 gave +16 %.
  - Check that nothing next to it changes.

## Bystander removal (opt-in)

Only when the user asks for it on named photos: for example, strangers in the background of a posed photo.
LightCraft has no generative removal, only the spot tool (`spot.add`), so the patches are copied from
nearby texture.

1. **Before you start:** record the history cursor as in "Before the first change to a photo".
   Export at 2000 px, and get the bystanders' outline from `M grid` around them.
2. **Use `mode=clone` with an explicit source**, one spot per vertical strip of about 0.02 of the long
   edge. Each spot's `points` run down the strip:
   `library.select 'ids=[ID]' spot.add mode=clone 'points=[[x,y0],[x,y1]]' size=0.02 'source=[dx,dy]'`.
   - `remove` and `fill` (content-aware) smeared in tests. Next to the subject, `remove` pulled the
     subject's jacket colour into the patch.
   - Pick a source offset (normalized `[dx,dy]`) that lands on plain background **away from the
     subject**, at least the spot's radius from the subject's edge. The empty path or hedge beside the
     bystander works well.
   - **Long lines** (fence rails, path edges, curbs) crossing behind the bystander: split the strokes
     above and below the line. For the part on the line, shift the source along the line's slope, for
     example `[0.07,0.025]` for a curb that rises 0.035 per 0.1, so the line continues.
   - Check what each source lands on. One copied a dark post into the patch; move it with
     `spot.update index=N 'source=[dx,dy]'`.
   - Fix leftovers (a head, a hat, a shoulder next to the subject) with small spots of about 0.01.
     Fix a bad patch with `spot.update`, or `spot.delete index=N` and redo it.
3. **Never paint over the subject.** Where a bystander overlaps the subject's outline, stop the spot
   a little short and accept a faint trace.
4. **Check** with a 2000 px before | after (`sbs.py`) of the area, and at 100 % on a 6000 px export (4000 while GPU rendering is on, see Setup)
   (one file per call; it takes 25–30 s, and a slow one made the app unreachable for a few minutes).
5. **Report honestly:**
   - Small or blurred figures against repeating texture (bamboo, foliage) come out clean at normal
     size.
   - Figures standing across long straight lines leave stepped rails or a doubled edge at 100 %.
   - Figures overlapping the subject leave a trace.
   - Suggest a crop instead when it would remove them more cleanly.
   - For a removal the spot tool can't do cleanly, suggest handing the photo to PhotoCraft (next section).
     PhotoCraft's `photocraft:remove-bystander` skill handles these: on 329 (_RDF4833, November 2026)
     it removed a small man half hidden behind the subject's arm and a woman standing right against
     her jacket, both clean at full view with the jacket edge untouched.

## Hand-off to PhotoCraft

PhotoCraft is ArtCraft's pixel editor (layers, retouching). LightCraft hands it a rendered copy. Only on
the user's request for named photos, because each hand-off writes a large file and adds a library photo.

```bash
"$CLI" run --connect library.select 'ids=[ID]' photo.editInPhotoCraft
```

It takes no parameters and acts on the selected photo. It needs the GUI (`--connect`).

**Before the hand-off, check that the photo has no copy yet:** `query_photos` with
`{"text":"<name>"}` lists the raw and any `<name>-Edit.psd` copy. If a copy exists, reopen it instead
(see "A second hand-off" below).

Tested on 531 (_RDF5035.ARW) and 329 (_RDF4833.ARW), November 2026:
- **It took 22–28 s.** If PhotoCraft wasn't running, it started it with the copy open.
- **A sleeping external drive fails it fast:** on 329 the first try returned
  `"error":"invalid parameters for \`photo.editExternal\`: E:\...\_RDF4833-Edit.psd: The device is not
  ready. (os error 21)"` at once. It wrote no file and added no library photo. Once `Test-Path` on the
  raw answered (the drive was awake), a second try worked. Unlike the duplicate failure below, this
  one is safe to retry once, after checking that no `-Edit.psd` was written.
- **It wrote `<name>-Edit.psd` next to the raw** (`E:\Photos\...\_RDF5035-Edit.psd`, 144 MB for a 24 MP
  raw): 16-bit RGB, one flat image, no layers, no compression. The LightCraft edits are rendered in. On
  531 the look and the 0.30 face lift matched LightCraft's own export: mean 68 against 66, average
  per-pixel difference 6 of 255. A crop wasn't tested (531 has none).
- **It added the PSD to the library as a new photo** and returned its id:
  `{"copies":[{"id":1451,"original":531,"path":"...-Edit.psd"}],"id":1451,"original":531}`.
  Record that id with the original in your notes.
- **The original's develop settings and history stay as they were.**
- **The copy's develop settings are all zero.** The edits are already in its pixels, so never apply a
  look or a lift to the copy; that would double them. Batch runs (cull, face lift, looks) must skip
  copies. Their ids aren't in a cull run's `people-by-photo.json`, so a batch built from it skips them
  already.
- **Later LightCraft edits to the original don't reach the PSD**, since it's a render. Finish the
  LightCraft edit first, then hand off.
- **Edits made in PhotoCraft** belong to PhotoCraft's own tools or skill. This skill only does the
  hand-off. Leave the PhotoCraft window to the user, or to a PhotoCraft skill if one is installed:
  `photocraft:mcp` (start, round trip) and `photocraft:remove-bystander` (strangers).
  - **Do the PhotoCraft step in this session** when the `mcp__photocraft__*` tools are here (both
    MCP servers registered in user scope, see `lightcraft:mcp`): load the PhotoCraft skill and run
    the round trip yourself. If they're missing, ask the user to run `/photocraft:mcp start` and open
    a new session, rather than briefing another one.
  - **When another session does the PhotoCraft work anyway,** send it the original and copy ids, the PSD
    path, the user's own words, and where the person is, in normalized coordinates read from a
    `render_photo` of the copy. "Sarah's left arm" is the viewer's right. Also tell it not to hand
    the photo off again. The PhotoCraft skill backs up the PSD and runs the `photo.reload` itself;
    ask it to say when it's done.
  - **The hand-off's own PhotoCraft window can hold stale pixels.** The PhotoCraft skill edits in a
    separate control PhotoCraft, so the window the hand-off opened still shows the old PSD. Tell the
    user to close it without saving, or it would overwrite the edit.
  - **Check the result in LightCraft:** `render_photo` the copy and the original at 1600 px and
    compare the area.
- **After PhotoCraft saves the PSD,** run `photo.reload ids=[COPY] wait=true` on the copy (under 0.5 s).
  LightCraft then shows the saved pixels: a red box painted in PhotoCraft showed up in the next export,
  and putting the old file back (with an older timestamp) and reloading brought back the original
  exactly. The reload doesn't change the copy's develop settings. PhotoCraft saves 16-bit
  RLE-compressed, so the file about doubles (144 → 287 MB).
- **A second hand-off of the same photo fails** (tested twice, with and without a PhotoCraft
  running): the CLI prints `"error":"invalid parameters for \`photo.editExternal\`: the edit copy could
  not be added"` and `1 command(s) failed`, after about 25 s. It still writes `<name>-Edit-2.psd`,
  byte-identical to the first copy, but adds no library photo and doesn't open PhotoCraft. Most
  likely LightCraft refuses a duplicate of a file it already has. So hand a photo off once and
  reopen the existing copy in PhotoCraft instead. After a failure, tell the user about the stray
  `-Edit-2.psd` (don't delete it unasked), and keep the whole CLI output: never rerun the hand-off
  just to read the error.

`photo.openOriginalInExternal` ("Open Original in Other Editor (RAW, no copy)") is the other entry in
Photo › Edit In. It hands over the raw file itself: no copy, and none of the LightCraft edits.

Don't hand off a photo while a batch run is going: the command changes the selection.

## AI Denoise (high ISO)

ISO `denoise.iso_candidate` (default 3200) or above makes a photo a **candidate**. Judge each candidate on 100 % crops.

1. **Find the grain.** Export the candidate at full size (see Gotchas: 1–2 per call). Crop a mid-tone
   area: sky, a wall, or skin. Name the crop region in the report.
2. **Skip** if that mid-tone area shows no visible grain. For example, a black sky plus a lit, clean
   subject (a floodlit castle at ISO 4000): denoising would only soften the stonework.
   - **Decide once per venue, ISO and look, not per frame.** A night-look carrousel and a light-show
     castle in the same venue are separate decisions: judge each on a frame with mid-tone surfaces
     (a wall, a canopy, skin), not on a black sky. The first candidate at an ISO in a venue sets
     the decision (denoise at the amount, or skip) for every frame at that ISO in that venue, so one
     parade isn't half denoised. In testing, one chunk skipped black-sky parade frames and the next
     denoised them all. Write the decision into the report, so the next chunk of the venue follows it.
3. **Turn it on** with `denoise.toggle id=ID enabled=true` (it starts at 50 %, and it queues the
   render itself, so a `denoise.queue` right after returns `added: 0`; that's fine). Set the amount with
   `set_develop {id, settings: {enhance: {denoise: N}}}`.
   - **Avoid double noise reduction:** while AI Denoise is on, set the look's `detail.nrLuminance` to
     10 and `detail.nrColor` to 15. Stacking it with the night look's 35 made the skin waxy and the
     background painterly on a night portrait.
   - On a masked night face that still shows fine speckle at 100 %, use `detail.nrLuminance` 20.
4. **Choose the amount by the crop:** the lowest of `denoise.amounts` (default 50, 65 and 75 %) that is clean at 100 %.
   - **Full ladder once per ISO level per run (speed):** render 0/50/65/75 only on the first
     candidate at each ISO level (for example 3200, 4000, 6400) in the whole run, and append
     `{"iso":6400,"amount":65,"id":ID}` to `$RUN/denoise-ladder.jsonl`. Read that file before the
     first denoised photo of a chunk.
   - **Later candidates at a recorded ISO:** one check per ISO **per chunk**, not per photo.
     - Set the recorded amount straight away on every candidate at that ISO.
     - Make **one** full-size export at that amount, on the frame of that ISO with the most mid-tone
       sky or shadow, and cut one 100 % crop of a mid-tone area. Every other frame at that ISO gets
       the amount with no export of its own. A photo with own people's faces still gets its own
       skin crop.
     - In testing, a full-size check on every parade photo took 1.2 minutes per photo; one check
       per ISO took 0.7–1.0.
     - Make no 0 % render and no second full-size export.
     - Step up one amount only if grain still shows in that crop.
     - Skip-the-grain-check (step 2) also uses this same single export, so the first full-size export
       of a photo serves both.
     - A review-list photo that needs a 0 % comparison for the user is the only exception.
   - Set `detail.nrLuminance` 10 and `detail.nrColor` 15 **before** rendering the 0 % strip, so every
     strip has the same noise reduction.
   - Measured so far: ISO 3200 was clean at 50 %, ISO 4000 at 50 %, and ISO 5000 and 6400 needed 65 %.
   - **People frames under tungsten need more:** at ISO 4000 the user asked for 75 % on a portrait
     where 50 % left grain on the skin and the wall. On own people at ISO 4000 and above, check the
     skin crop at 65 and 75 % as well, and offer the higher one on the card.
   - Judge both a mid-tone area (sky or wall) and skin.
   - If 65 and 75 look alike, take 65.
   - On a night portrait at ISO 6400, 50 % left grain in the sky, 65 % was clean, and 75 % made the skin waxy.
5. **Render it:** run `denoise.queue 'ids=[…]'` after every amount change. The cached picture is
   for the old amount. Then poll `denoise.status` until `queued` is 0 and `running` is null.
   - **Wait with the helper, in the background, not in repeated foreground calls (tokens):**
     ```bash
     rm -f "${SP:?}/denoise.done"
     bash "$LC_SCRIPTS/denoise-wait.sh" "$SP" --ids 501,502,503   # as a background tool call; polls every 20 s
     # ... measure the frames that don't need denoise, write review lines ...
     until [ -f "$SP/denoise.done" ]; do sleep 5; done; cat "$SP/denoise.done"; rm -f "${SP:?}/denoise.done"
     ```
     The marker says `done after Ns on gpu|cpu` (or `TIMEOUT …` after an hour). **Always pass
     `--ids`** (the photos you just changed): it then also waits until each one's own
     `denoise.status id=N` state is `ready` (`idle` means denoise is off). Without it, an empty queue
     looks "done" before the app has queued the new render, or long after it finished. Don't hand-write the
     loop: in testing, an unquoted `$CLI` killed one silently. In testing, workers also spent many
     turns on 180 s foreground polls. The helper must have exited before the report (see "finish
     with nothing running").
   - **A plain `sleep N` in a foreground call is blocked** for workers; the `until` loop above is the
     way to wait. **Keep each foreground wait under about 170 s:** a foreground call that runs past
     180 s is moved to the background. For a longer wait, run the helper as a background tool call
     and poll its marker with short foreground calls:
     `timeout 170 bash -c 'until [ -f "$0/denoise.done" ]; do sleep 5; done' "$SP"; ls "$SP/denoise.done"`
     (repeat until the file is listed).
   - **Speed:** on an entry-level GPU (MX130) 21 frames took about 7 minutes (about 20 s each); on the
     CPU 22 frames took about 25 minutes. If it runs on the CPU, see GPU rendering in Setup. The
     built-in denoiser needs no download.
   - **On the CPU it is much slower.** LightCraft can stop answering ("drew no frame") for 5–6
     minutes while it runs. Wait and keep polling `denoise.status`. Don't start another export, mask
     or denoise job, and don't restart LightCraft. In testing it always recovered by itself.
   - Set the amount only through `set_develop` (`enhance.denoise`). `denoise.toggle` ignores any
     amount you pass it.

## Clipping check

Run `M clip` on the 1000 px render before any edit and on the after render.
- **On a denoised photo, measure the after render only once denoise has finished** (the
  `denoise-wait.sh` marker, see AI Denoise). AI Denoise turns noisy near-black into exact 0: in
  testing, crushed on a castle rose 4–5 points after denoise that the before-denoise render didn't
  show. Raising blacks to 0 barely changed it (5.35 → 5.25), so there, flag it, don't chase it.
- If **blown** rose by more than 0.5 percentage points, lower `light.highlights` by 15 and check
  again.
- If **crushed** rose by more than 0.5 points, raise `light.blacks` by 8 and check again.
- **Light show or black-sky scene:** a black sky is intended, so measure crushed only on the lit
  subject and the ground around it (`-Region` drawn on the grid around them), never a fixed half of the
  frame. On a row of lit lanterns the bottom half held black night sky on the right, so the rule raised blacks to
  0 for nothing; the user judged the result fine. If crushed rose by more than 2
  points there, raise `light.blacks` by 8 and check again. Never raise blacks above 0 in a light
  show; at 0, stop and report.
  - The look starts at blacks −5, so a dim float or building on a black sky often needs blacks 0
    (one step). Measure only on the lit subject's box; a whole-frame crushed rise on black sky
    doesn't count. In testing, whole-frame crushed rose 2–6 points on parade frames whose floats
    rose under 1.
  - If crushed on the subject still rose more than 2 points at blacks 0, add a "Flagged edits" card
    with the numbers. Never raise exposure on a light show to fix it.
  - **Blown on a light show:** most blown pixels are lamps, bulbs and saturated blue or purple light,
    which `light.highlights` doesn't bring back. Try highlights 15 lower than the look's value
    **once** (the light-show look is at -60, so -75); if blown on the subject
    didn't fall by at least 0.3 points, put the value back and add a "Flagged edits" card with the
    numbers. In testing, highlights -75 left blown at 4.24 % against 4.25 %.
  - **Subject got darker:** if the subject's mean after the look is under 16 **and** more than 10 %
    lower than before, list it under "Needs the user" with both means (it may need the "brighter"
    fix, see Global exposure boosts), and keep its 2000 px before. A small drop is normal: the user
    called a floodlit castle that went from 24.3 to 22.1 fine, and the light-show look takes dim
    frames with a navy sky down hard (14.7 → 9.2).
- Each fix runs at most 2 times; then stop and report the numbers.

## Straightening

Follow `straighten` in the preferences:
- `any_tilt` (default): align tilted photos, including street scenes, busy scenes and photos with
  people. In testing, the user asked for this on 9 photos that a "facades only" rule had skipped. Skip
  only close-ups and portraits where no vertical or horizon is visible.
- `facades_only`: only a building facade or horizon seen roughly straight on.
- `off`: never.

1. If `get_develop` shows `geometry.upright` is not `off` and you did not set it, don't touch it.
2. **Measure:** export `library.select 'ids=[ID]' app.export path="$SP/off.jpg" longEdge=1500`.
   - Fit 2 long true verticals (poles, building edges, door frames) with `lfit.py`, using
     coordinates from `M grid`. Fit the horizon with `lfit.py` on that line.
   - `M tilt` (n ≥ 2000) is a cross-check only.
   - **Busy night scenes** (lit buildings, few clean edges): `lfit.py` can disagree with itself
     (0.33 / -1.09 / 4.04° on one night facade, with few inliers). There, try
     `library.select 'ids=[ID]' crop.autoStraighten` first, re-export, and check it with `lfit.py`.
     In testing it gave -2.44° and the lines then measured level; the user approved it.
     Read the `history.list` cursor before it, so it can be taken back with `history.restore` (see
     Revert). If it returns `changed:false`, it did nothing: don't undo anything.
   - **`crop.autoStraighten` is unstable across a burst:** on five near-identical carrousel frames it
     gave -3.0 to -4.6°. Measure one angle per burst (or per venue set shot from one spot) on its
     clearest frame, apply that same angle to the others, and re-measure one of them.
   - **Don't use `crop.autoStraighten` on views looking down** (a street from a window, a rooftop
     view): there it gave small angles the other way from the kerb's `lfit.py` fit (+0.47° against
     -2.0°). Fit a kerb, a building edge or a window column with `lfit.py`, or make a tilt sheet.
   - **Lines that fan out from perspective** (carrousel poles, a wide angle close to a subject): no
     rotation makes them all vertical. Rotate only by what a centre vertical or the horizon says, and
     when nothing central settles it, leave it: say "perspective, left as is" in the report rather
     than adding a tilt card. A building that leans in from both sides is a keystone (below).
   - **Light-show and night frames still get this check.** A floodlit castle against a black sky is
     not exempt: in testing the user asked for alignments on 4 castle frames that had none.
   - **When the measurements can't settle it** (tapered towers, `lfit.py` and `crop.autoStraighten`
     disagreeing or failing): make a tilt preview sheet and let the user pick:
     ```bash
     LCX tiltprev.py -In "$SP/ID-before.jpg" -Out "$SP/ID-tilt.jpg" -Region "0.2,0.8,0,1" -Cols 2
     ```
     The default angles are -6, -4, -2, 0, +2, +4, +6 (positive = clockwise, as `crop.straighten`),
     each tile with vertical guide lines. Put the sheet on a card with a `decide` listing the angles,
     and apply the pick with `crop.straighten`. When the user hesitates between two (for example "+2,
     +5.5 might look correct"), make a second sheet in 1° steps around them. In testing, the user's
     final picks were +2 to +5.5°, so start with the wide range, not ±2°.
   - Under 0.3° on both verticals, or on the horizon: already straight, stop.
3. **Which case:**
   - **Plain roll** (verticals on both sides lean the same way): **rotate** with
     `library.select 'ids=[ID]' crop.straighten angle=<deg>` (-45 to 45, positive = clockwise; it
     keeps the largest crop). Try the measured correction, re-export, re-measure, and flip the sign if
     it got worse. It worked on 5 of 5 test photos (0.7–3.8°, 0.9–4.4 % crop per edge).
     `crop.straighten` (and `develop.set` `crop.angle`) keep the crop inside the photo by themselves,
     so no blank corners show (in testing +5.5° cost a 6.1 % crop per edge, which the user accepted).
     - When a smaller angle saves important content and keeps the verticals within ±0.7°, use it:
       1.8° instead of 2.5° kept a sign board in frame.
   - **Keystone** (camera tilted up: left verticals lean one way, right ones the other, for example
     -5° and +3°): rotation can't fix it. Use `library.select 'ids=[ID]' geometry.upright mode=vertical`.
     On two street views it brought both sides within ±0.25°, with an 8–9 % crop per edge that the user
     accepted.
     - If that fails, try `geometry.guides 'guides=[[x0,y0,x1,y1],[x0,y0,x1,y1]]'` with one long
       vertical on each side. A `transform: null` result is normal; judge only by the measured tilt.
   - **Sloping landscape** (verticals level, but the lawn or tree line slopes several degrees):
     rotate by `straighten.landscape_fraction` of the visible slope (default **half**), keeping trees
     and people within `straighten.max_lean_deg` (default 2.5°) of upright. In testing, the user
     accepted 2.5° on two park views with a 5–6° slope.
   - Keep `geometry.upright mode=auto` out of the default path: it once rotated 4.1° and left pillars
     leaning 0.6°.
4. Keep the correction only if it measures better. Otherwise take it back with `history.restore` to
   the cursor read before it (never `edit.undo`), and add a `decide` with the
   numbers, and a test render if one exists.
5. If you keep a correction, read the crop it cost:
   `"$CLI" run --connect develop.get id=ID | python -I "$LC_SCRIPTS/lcjson.py" crop` prints the angle,
   `crop_per_edge` (the largest edge cut, in % of the frame) and `constrain_crop`. Report that number
   instead of estimating it from the angle, and say what the crop cuts off. A crop over 5 % (over 12 %
   for a keystone `geometry.upright`), or one that cuts into the main subject, gets a `decide`.
   - After `geometry.upright` or `geometry.guides` (transforms, not a crop rotation),
     `constrain_crop` must be `true` so no blank edges show. Only the MCP tool sets it:
     `set_develop {id, settings: {geometry: {constrain_crop: true}}}`; `develop.set` from the CLI
     rejects `geometry.constrain_crop` ("unknown control"). Check it with `lcjson.py crop`.

## Batches (more than 5 photos)

Hand the batch to `sonnet` subagents with a brief file, one worker at a time (LightCraft has one
active photo).
- **Chunk size:** about 25–30 photos when most are plain (look only), and about 15–20 when many need
  masks or denoise. What fills a worker's context is mostly the images it reads, so keep plain photos
  numeric (see Lean workers below).
- Give each chunk its own folder.
- **Tell the user, before the first chunk,** what they may do in LightCraft while workers run (see
  "Using LightCraft while a run is going" in the plugin README): view only; scroll, zoom and pan the
  photo on screen; no clicking other photos, no filter, source or album changes, no minimizing, no
  dialogs, no rating or editing. Suggest looking between chunks or at the review pages instead.
  If the user says they clicked a photo during a chunk, run `history.list` on that photo and on the
  worker's active photo at that time after the chunk ends, and undo any step that isn't theirs or the
  worker's intended one (`history.restore` to the step before it).

**Venue table (orchestrator, before the first chunk).** Classify the venues once, so workers don't
classify every photo:
1. Split the day into venues by capture time (a gap of about 10 minutes or more, or a clear change of
   place on the cull's 640 px sheets or 1000 px exports).
   - **Look at every 6th–8th photo of a venue**, not only its first: export them at 480 px in calls
     of about 7 and Read them. A time gap misses a change of place inside a range. In testing, dad
     and the boy under a dim wooden canopy fell inside "outdoor stage show, daylight", and a dusk ride
     frame inside a daylight carrousel range, because only the first photo of each range was seen.
   - Split a range where the light or the place changes, even with no time gap.
2. Give each venue one look by the rules in Looks, and write `$RUN/venues-<day>.txt` with one line
   per venue: `<first id>-<last id> | <venue> | <look> | <why>`. For example
   `630-650 | Asakusa street, night | look.night | lit signs, no large sky`.
3. Give each worker the lines for its ids.
   - The worker uses the table's look.
   - If a photo clearly doesn't fit its venue's look (a different scene inside the range), the worker
     uses the right look and lists the id in the report.
   - If a whole venue looks wrong, the worker keeps the table's look and adds a review card. It never
     re-decides a venue on its own.

**Lean workers (speed).** Write this into the brief:
- **Plain photos** (look only: no own people to lift, ISO below the denoise candidate, not tilted)
  are judged on the numbers alone: `M clip` before and after, `M tilt` or `lfit.py`, and the whole-frame
  mean. Don't Read their renders. Apply their look with the preset in one call and export their afters
  together.
- **Read images only** for:
  - photos with own people (face boxes, grids, coverage checks, mask edges);
  - denoise crops;
  - straightening fits;
  - review-list photos;
  - any photo whose numbers look odd: blown or crushed rising past the clip rules, or a mean far from
    the rest of its venue.
- **Each Read is one small file:** a grid or crop PNG, an `M sheet` contact sheet, or a 1000 px
  render. Never a 2000 or 6000 px file.
- **Classify from contact sheets:** `M sheet` of 9 before1k renders per Read, not one Read per photo.
- **Numbers in one call:** write every before/after box of the chunk into one list and run `M batch`
  once, instead of one `M mean` / `M clip` per box.

Subagents aren't told the skill's base directory, so list in the brief:
- this skill's base directory as an absolute path (forward slashes), so the worker can `source` the
  Setup line, plus `RUN`, its `SP` folder and the preferences path (`$PREFS`), and tell it to read the
  Setup section first;
- the ids, and that **every** id gets the full edit, not only the ones on the review list. In
  testing, one worker edited only its 3 review ids and reported the chunk done. For a redo, say
  whether to revert first, or (as for a user's "Change" note) to add to the current edit, with a
  new round tag;
- which looks are approved, and whether this is a trial batch for proposed looks; the venue-table
  lines for its ids and the preset id of each look; the day's people list (always, even when
  recognition is usable) and whether recognition is usable (see lightcraft:cull, "Whose faces count");
  when it is, the `people-by-photo.json` lines for its ids (`people.py "$RUN" --ids 1165-1197`), so
  the worker makes no face calls of its own;
- that the report ends with **"Improvements"**: at most 6 lines on what would make the skill faster,
  use fewer tokens, or give better results. The orchestrator collects them for the next skill update;
- the path of `lightcraft:face-lift/SKILL.md` (the lift step; workers Read it, see Subject lift);
- the review material and `review.jsonl` (see Showing results);
- the report: at most 15–25 lines, with no images;
- that the worker never uses `edit.undo`/`edit.redo` (global, not per photo; take steps back with
  `history.restore`, see Revert), and runs image helpers only through `M`/`LCX`, never `python -I`;
- the largest export it may make: `longEdge` 6000, or 4000 when GPU rendering is on with an
  entry-level GPU (see Setup);
- that the worker never changes `app.gpu` or `denoise.settings`, and reports the denoise device
  (`denoise-wait.sh` prints it);
- **finish with nothing running:** no background shell job of its own, no export, `denoise.status`
  with `queued` 0 and `running` null, and `segment.model.status` with `busy: false`. Say so in the
  report. In testing, one worker reported while its own background job was still running.

**Time:** a chunk of 20 took 30–55 minutes on an entry-level laptop GPU. A plain photo takes about
1 minute; a masked one 2–10 minutes (each SAM 3 segmentation or added point takes about 60 s); about
20 s more per denoised photo on the GPU, about 70 s on the CPU. In testing, a chunk of 22 fireworks
frames with 4 masked portraits took 40 minutes with GPU denoise. Tell the user the estimate up front.

**Stopping a chunk, or pausing for the user.** When the user wants LightCraft back mid-chunk, or a
chunk must stop:
- Stop the worker and every background command of yours (exports, polls, mask jobs). Wait until
  `denoise.status` shows `queued` 0 and `running` null and `segment.model.status` shows `busy: false`.
- A worker applies the look to the whole chunk first, so a stopped chunk has touched every id. Revert
  the whole chunk from `edits.jsonl` (see Revert), not only the photos it finished, then run the
  cull-marks check below. Restart the chunk later from a fresh folder.
- List for the user anything left half done that isn't reverted (for example a photo you were testing
  at a different value), and tell them when LightCraft is free.

**The orchestrator, when the worker reports:**
- Stop the worker if it says background work is still running (one worker kept running after its
  report).
- **End-of-batch check, for every edited id**, with the helper (it reads keys with `.get()`, so a
  missing `denoise_on` reads as off):
  ```bash
  mkdir -p "$SP/dev"; for id in <the chunk's ids>; do "$CLI" run --connect develop.get id=$id > "$SP/dev/$id.json"; done
  python -I "$LC_SCRIPTS/looks.py" check "$PREFS" "$SP/dev"
  ```
  It names each photo's look and fails a mask with `exposure >= 2`, `amount` other than 100, an
  overlay left on, or no values, and denoise stacked with the look's full noise reduction.
  - The daylight cap (`lift.daylight_mask_max`, shadows 15) applies only to photos with the
    daylight look.
  - A mask on a photo with `look.night` or `look.light_show` follows the night ladder: shadows up to
    `lift.shadows_max`, and exposure up to `lift.mask_limit`. Don't flag it as over the daylight cap.
  - The face lift picks its ladder by the **scene**, not the look. A photo whose report notes "look is
    X, scene is Y" is checked by hand against the scene's ladder (see lightcraft:face-lift, Mask
    values); a looks.py FAIL or pass on it doesn't count.
  - **Take the ids from the list you gave the worker,** written to a file when you launch it. In
    testing, a check read an older chunk file after the day was re-split and scanned the wrong ids.
  - Workers run the same check on their own ids before they report.
- **Marks:** editing must not change any rating or flag. Before the first edit of the batch, save
  `"$CLI" run --connect catalog.query limit=100000 > "$SP/marks-before.json"`. Never skip this check;
  it must report 0 marks changed for the batch's ids:
  ```bash
  "$CLI" run --connect catalog.query limit=100000 > "$SP/now.json"
  python -I "$LC_SCRIPTS/runstate.py" marks "$SP/marks-before.json" "$SP/now.json" --ids <the batch's ids>
  ```
  This works with or without a cull run. With one, `runstate.py check "$RUN" "$SP/now.json"` is extra
  information only: it also lists ratings the user changed since the cull, which aren't the edit's.
- Look at a few results yourself before sending them.

## Showing results to the user

**At the computer: a review page** (preferred for any batch). `review.py` in `$LC_SCRIPTS`
builds one self-contained, responsive HTML page: before/after side by side filling the screen, the
crops, what changed, and an answer per photo. The user presses "Copy my decisions" and pastes the text
into the chat; then apply each answer (Approve → mark the look approved in Looks; Revert → see Revert;
Change → ask what to change if the note doesn't say).
1. **The worker** exports `ID-before.jpg` (unedited) and `ID-after.jpg` at **2000 px** (1000 px is
   soft on a wide monitor), makes the crops below, and appends one line per photo to `review.jsonl` in
   its folder:
   ```json
   {"id":501,"file":"IMG_0501","title":"Night portrait","changes":["Night look","SAM 3 mask, face +23 %","AI Denoise 65 %"],
    "crops":[["501-dn.png","Denoise 0 / 50 / 65 / 75 %"],["501-edge.png","Mask edge at 100 %"]],
    "decide":{"q":"Use the Night look for blue hour?","options":["Approve","Change","Revert this photo"]},"group":"New looks"}
   ```
   - `changes` holds short plain sentences with the key numbers, not the full report.
   - **Every card names its look** in `title` or the first `changes` line ("Night look",
     "Daylight look"). For a photo left unedited, write "Unedited, no look yet", show a sample of the
     proposed look as a crop, and add a `decide`. In testing, the user couldn't tell what the "after"
     of an unedited photo was.
   - **Every photo listed under "Needs the user" is covered by a card with a `decide`** (group
     "Needs the user"): its own card, or the venue card below. In testing, a worker kept a photo's
     before and after but wrote no card, so the user never saw the question.
   - **One card per venue for a repeated question.** When 3 or more frames of one venue need the same
     question (the castle stays dark: brighten it?), make **one** card: the darkest frame's 2000 px
     before/after and sbs, its id as the card's `id`, an `M sheet` of the afters of the others as a
     crop, `changes` listing every id with its subject mean, and the decide "for all N frames"
     (options "Fine as is", "Brighten all", "Brighten some (note the ids)"). In testing, a per-frame
     card for 23 dim castle frames meant 23 near-identical questions. Frames with their own extra
     problem (a flag) still get their own card.
   - Add `decide` (and a `group`) only when the user must choose: a proposed look, a lift stopped
     at its limit short of the target, a failed mask, a crop over 5 % (over 12 % for a keystone `geometry.upright`
     correction: the user accepted 8–12 % per edge on four street views), a clip rule that stopped, a failed straightening, a
     photo left without a look. Other photos get Fine / Change automatically.
   - **Leave `group` out of a card without a `decide`:** it only sorts decision cards.
   - **Every photo the chunk changed gets a card**, including plain look-only photos and redo
     rounds. In testing, a redo round wrote no card for one changed photo, so the user never saw it.
     Count: the ids you edited = the lines in `review.jsonl`.
   - **A grain finding gets its crop:** when the report says grain remains (or a denoise amount was
     chosen on a crop), that 100 % crop goes on the photo's card. In testing, a card showed only a
     face crop for a wall the report called grainy.
2. **The orchestrator** builds the page from all chunk folders, then opens it in the browser pane:
   ```bash
   python -I "$LC_SCRIPTS/review.py" "$SP/review.html" "$SP"/chunk* --title "<day> review"
   ```
   Fix every `WARNING` (missing file, bad line) before showing it.

**On a phone:** the user often reviews away from the laptop, where the review page can't be opened. A
downscaled before/after sheet can't be zoomed, so the user can't judge noise or detail from it.
- **Standard output, every batch** (unless `review.phone_sbs` is false): the worker makes one `ID-sbs.jpg` per photo with
  `LCX sbs.py -Before ID-before.jpg -After ID-after.jpg -Region <the area that changed> -Out ID-sbs.jpg`
  (whole frame `0,1,0,1` for looks and straightening, the faces for a lift). Send these with the
  file-sending tool, listing the ids in order, and ask for verdicts by id.
- **The overall look:** before/after pairs at about 1000 px.
- **Noise, sharpness and mask edges:** send **100 % crops cut from a full-size export**
  (`longEdge=6000`, or 4000 while GPU rendering is on, then `M crops -Region <~0.2 × 0.2>`).
  - Stack the versions being compared.
  - **Every version must have identical develop settings except the one being compared.** Make them
    in one sitting by changing only that setting between exports.
  - **Label each strip with its version.** `M crops` prints the file name, so name the files
    `ID-dn0.jpg`, `ID-dn50.jpg`, `ID-dn75.jpg`.
  - **Same position:** cut every strip with the same `-Region` from exports at the same `longEdge`.
    Before sending, check that each strip shows the same detail at the same place, and re-export if
    one is shifted.
  - **Full ladder:** show 0/50/65/75 on the first photo at each ISO level in the run (see AI
    Denoise); other photos show 0 % against the chosen amount.
  - **A denoise crop on a review card is 0 % against the chosen amount, both with the look applied**
    (a full-size export with `enhance.denoise` 0, then the amount). It is not the unedited photo: a
    full-size unedited before would need a reset. Label it so: "100 % crop: denoise 0 % (top) /
    50 % (bottom), same look".
- Send them with the file-sending tool and name the photos by their file name. These same crops go in
  the review page.

## Report

For each photo, report:
- what changed: look; global exposure boost and why; white balance Kelvin before→after; mask path
  and values; denoise amount; geometry;
- face and background means with their regions, the lift %, clip numbers before→after, and tilt;
- the paths to the before/after renders.

A batch worker writes the full report to `report.md` and the page data to `review.jsonl`, and returns
no images; the orchestrator builds the review page or sends the files.

Never claim a photo is brighter, cleaner or straight without a measurement.

## Gotchas

- `geometry.upright` is a command. Setting `{geometry: {upright: …}}` through `set_develop` only
  stores the mode.
- `set_develop` takes `values` (slider ids) and `settings` (nested, e.g. `{enhance: {denoise: 50}}`)
  in one call. The `settings` part is applied without any acknowledgement in the result, so check it
  with `develop.get` once per chunk (`looks.py check` reads the dumps).
- `develop.get` leaves out `enhance.denoise_on` when denoise is off: read it with `.get()`, never
  `["denoise_on"]`.
- **Apply develop values with the MCP `set_develop` tool.** The CLI `develop.set id=ID …` returns
  `ok` but doesn't apply the values. Check with `develop.get` if in doubt.
- Exports reflect the current develop state, including a +3 coverage check left in place.
- **Full-size exports** (`longEdge=6000`; at most 4000 while GPU rendering is on, see Setup) take 25–30 s each. Export 1–2 per call: a call of 8 timed
  out. The export then kept running in the background, and for about a minute every request failed
  with "drew no frame". Wait for `library.state` to answer `"ok":true` before the next call.
- **One export call at a time**, never two in parallel (also not for the "before" renders): each
  call selects its photos, and LightCraft has one selection.
- Mask commands take the mask's `id` (from `activeMask` or `masks[].id`, starting at 1), not its
  position in the `masks` list: `id=0` fails with "no mask 0".
- The linear gradient `mask.add kind=linear 'start=[0.5,1.0]' 'end=[0.5,0.55]'` works (tested): full at the bottom edge, gone by y 0.55.
- `develop.get id=ID` from the CLI returns the same settings as `get_develop`. Denoise lives in
  `enhance.denoise` / `enhance.denoise_on`. Mask values are in `masks[].adjust` (`exposure`,
  `amount`, `temp`…).
- **Measure colour on 2000 px exports.** 1000 px renders gave clearly different sign colours.
- **Re-exports under the same file name can be read back stale.** Use a new name for every working
  render.
- **`mask.add` and `mask.addComponent` can stay `pending` for minutes,** and a single CLI call can run
  past 180 s. Poll `"$CLI" run --connect develop.get id=ID | python -I "$LC_SCRIPTS/lcjson.py" seg NAME` until
  READY equals PARTS (`kind=subject` masks never get `seg` data; see lightcraft:face-lift). Never TaskStop a running mask
  command: one stopped call later reset a mask to +3.
