---
name: lightcraft-edit
description: Use when the user asks to edit, develop, retouch or adjust photos in LightCraft (ArtCraft), e.g. "edit the picks from June 14", "brighten the person on the left", "the subject is too dark", "fix the exposure", "straighten this building", "denoise this", or "apply my night look".
---

# lightcraft-edit

Edit only the photos the user names, or a scene type they approved for a batch. Picks come from a
`lightcraft-cull` run, or from ids the user gives. Never rate, flag or reject here: that belongs to
`lightcraft-cull`.

## Setup

- LightCraft must be running with the bridge: use the `lightcraft-mcp` skill (`start`). Keep the window
  un-minimized, or requests fail with "the app drew no frame".
- Run CLI commands **from Bash**: Windows PowerShell 5.1 strips the `"` inside JSON arguments.
  Variables don't persist between calls, so start every Bash call with:
  ```bash
  source "<base>/../../scripts/lc-env.sh"   # <base> = this skill's base directory, written with forward slashes (C:/Users/...); sets CLI, LC_SCRIPTS, RUNS, PREFS, M, PSX
  RUN="$RUNS/<library name>"   # the cull run's folder; ask the user if unsure
  SP="<session scratchpad>/edit"; mkdir -p "$SP"
  ```
  If `lc-env.sh` can't find LightCraft, ask the user for the install folder and write
  `LIGHTCRAFT_DIR=<folder>` to `~/.claude/lightcraft/config.env`.
  - Use forward slashes in `path=`.
  - **Paths in Python:** `$RUN`, `$SP`, `$CLI` and `$LC_SCRIPTS` may be msys paths (`/c/Users/...`).
    Bash converts them only when they are passed as **arguments** to a program, so pass them that way
    (`python -I script.py "$RUN"`). Never write them inside Python code (a heredoc or `python -c`):
    there use a Windows-style path (`cygpath -m "$RUN"` gives `C:/Users/...`). Never call `$CLI` from
    a Python subprocess; run CLI commands from Bash. In testing, a worker hit both.
  - `M` modes:
    - `mean`: brightness 0–255.
    - `clip`: % blown (any channel at 255) and % crushed (all channels at 0).
    - `tilt`.
    - `crops`: at most 4 files.
    - `sheet`: a contact sheet of up to 12 whole frames, `-Cols` across (default 3), each labelled
      with its file name. 9 per sheet reads well: classify 25 frames in 3 Reads, e.g.
      `M sheet $(ls "$SP"/before1k/*.jpg | head -9) -Out "$SP/sheet1.png"`.
    - `batch`: one list file, one measurement per line: `<image>|x0,x1,y0,y1[|label]` (relative
      images are read from the list's folder). Prints mean, blown and crushed for every line in a
      single PowerShell start. Use it for before/after numbers on a whole chunk: about 100 separate
      `M` calls were the slowest part of a chunk in testing.
    - `grid`.
  - `-Region x0,x1,y0,y1` takes fractions of the frame, and `-Out` must end in `.png`. `M mean`
    always needs `-Region` (use `0,1,0,1` for the whole frame).
- **Preferences:** read `$PREFS` (`~/.claude/lightcraft/preferences.md`) before the first edit.
  - If it doesn't exist, copy `preferences.example.md` from the plugin root there, and tell the user
    that every look and value is still unapproved.
  - If a key this skill needs is missing, ask the user and offer to add the answer.
  - Names in `backticks` such as `look.night` or `lift.mask_limit` are those keys.
- Helpers in `$LC_SCRIPTS`, run with `PSX <script> <args>`. Give the script name only
  (`PSX sbs.ps1 …`): `PSX` adds the folder, so a full path fails with "-File parameter does not exist".
  - `lfit.ps1 <file> x0 y0 x1 y1`: line fit on one long edge (a pole, a roofline), returns its angle in
    degrees. More reliable than `M tilt`, which responds only 20–60 % to a real rotation on busy scenes.
  - `rgb.ps1 <file> x0,x1,y0,y1`: mean R/G/B of a region, for colour checks (signs, food, skin).
  - `sbs.ps1 -Before <f> -After <f> -Region x0,x1,y0,y1 -Out <f.jpg>`: a labelled BEFORE | AFTER
    side-by-side for viewing on a phone, at most 1600 px wide.
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

1. Record its history: `"$CLI" run --connect history.list id=ID` gives `cursor`, which is `null` if it
   was never edited.
2. Note its masks: `get_develop {id}` → `masks`.
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
- Use `edit.undo` only immediately after a single step of your own.

## Per-photo order

**Batch the exports first (speed).** Exports cost about 15 s each at 2000 px, so before editing any
photo of a chunk, export every unedited photo in calls of 5–6 ids (more passes the 120 s tool limit):
```bash
"$CLI" run --connect app.export 'ids=[501,502,503,504,505]' dir="$SP/before2k" longEdge=2000 format=jpeg naming='{name}' conflict=overwrite
"$CLI" run --connect app.export 'ids=[501,502,503,504,505]' dir="$SP/before1k" longEdge=1000 format=jpeg naming='{name}' conflict=overwrite
```
Then rename `before2k/<file>.jpg` to `ID-before.jpg`. The 1000 px files are the classification and
clipping-check renders. Never reset an edited photo just to get a "before".
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
4. **Subject lift**, only if measured darker (see Subject lift). Then any **local fixes** (see Local
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
   - Saving the same recipe under the same name returns the existing preset, so this is safe to repeat.
     Use `presets.list` to find its id.
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
- **Lens already darkens the corners:** vignette 0.
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
- **When the user asks for more exposure, that overrides the cap.** Step `exposure.on_request_step`
  at a time and report the blown %.
- **"Lift the highlights" (or "brighter") on a dark light-show subject** means brighter lights, not
  the Highlights slider: on a mid-dark float (subject mean about 15) `light.highlights` barely moves
  it (14.7 -> 15.8). Raise `light.whites` (+40) and then exposure (+0.5) and check blown on the
  subject. In testing this gave +56 % with blown 0, and the user approved it. The user's request
  overrides "never raise exposure on a light show". A worker that finds a float this dark (subject
  mean under about 20) leaves it and lists it under "Needs the user".
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

**Target:**
- **Face already reads 60 or more** (look applied, no mask): lift it by `lift.bright_face` (default **+15–25 %**).
  - **In daylight this applies even when the face matches the background.** The 5 % gate below is for
    darker faces only. A face that reads the same as the background still looks dull in daylight. Skip
    the lift only when the face is clearly brighter, more than 5 % above the background mean.
    - In testing, two daylight portraits had faces at the background mean and got no mask. On review,
      the user asked for both: "face needs to be brightened up a bit".
  - Start at `lift.mask.bright_face` (default `{"exposure":0.20,"shadows":15,"temp":0}`), not at the
    daylight value. On the same portraits, 0.45 gave +38 %, 0.25 gave +24 %, 0.15 gave +17 %, and
    0.20 gave +20 %. The user approved 0.20.
  - Step the mask exposure by 0.05 to land inside the target.
  - Only the user's own people get a lift. Strangers in a crowd or street scene are part of the scene,
    so no mask (see lightcraft-cull, "Whose faces count").
- **Darker faces at night:** lift until the face reaches `lift.dark_face`
  (default **at least 75–80 % of the background mean**), with no % ceiling.
  - In testing, the user asked for more lift on night faces in three review rounds. Faces at about
    55 % of the background were still too dark, and 70–77 % was accepted.
  - Faces that are near-silhouettes (under 20) may need the mask at its limit. Report what you reached.
- **Darker faces in daylight** (under 60 with the look applied): aim for `lift.daylight_dark_face`
  (default **about 75–85 % of the background mean, never above it**), but **the mask cap wins**: stop
  at `lift.daylight_mask_max` even when the face is still short, and report the ratio. Use the
  daylight ladder below, not the night one.
  - In testing (overcast bamboo grove, dark hair against dark foliage), shadows 40 plus exposure up to
    1.05 brought faces to 85–94 with a visible halo, and the user said the lift was too much. The
    standard 0.45 / shadows 15 (0.65 on the darkest face) gave faces of 43–76, 52–95 % of the
    background, and the user accepted all five.
- At night the goal is a face at least as bright as the background. Report the face/background ratio.

**Measure** on a render with the look applied and no mask. Report each box's region.
- **Face:** a box on the skin of the forehead and cheeks: from just under the eyebrows to just
  above the mouth, and between the outer corners of the eyes. Leave out hair, eyes, eyebrows,
  shadowed eye sockets, glasses and specular highlights. Read the box off an `M grid` of the face,
  never a guess from the 1000 px view.
  - **Record the box** (x0,x1,y0,y1) in `report.md` and in the photo's `review.jsonl` `changes`.
  - **A redo uses the recorded box.** In testing, two workers measured the same face as 84 and 59 with
    different boxes. The first number led to "no mask needed", and the user then asked for a lift.
- **Background:** exactly 2 boxes of the same size beside the subject, on surfaces of ordinary
  brightness (foliage, ground, walls of a normal colour).
  - Never use white stone, snow, white walls, signs, lamps, lit windows or sky.
  - Each box must read 50–130 on the no-mask render; move it if not. On one portrait the boxes sat on
    white granite (130–144) and made the face look far darker than it was.
  - **No surface reads 50–130** (a dark night scene): use the 2 brightest ordinary surfaces and say
    so. Then mask only if the face reads under 50.
  - **Sunlit scene where every ordinary surface reads above 130** (sunlit gravel or stone): use the 2
    ordinary surfaces closest to the range and say so.
  - Compare the face with the mean of the 2 boxes.
- **Strangers get no mask (speed and intent).** Only the user's own people are subjects (see
  lightcraft-cull, "Whose faces count": recognised names when face recognition is on and faces are
  named, else the day's people list by clothing). Don't
  measure or mask strangers, crowds, staff or performers. Report "no own people in frame: scene" and
  move on.
- **Several people:** decide on the **darkest main-subject face**, and one mask covers all of them.
  Faces narrower than about 1.5 % of the frame width get no mask. Report them.
- **Mask only if the face is more than `lift.mask_if_darker_percent` (default 5 %) darker than the
  background mean**. The exception is a daylight face of 60 or more, which follows the bright-face rule
  in Target above.
  Within 5 %, or brighter, no mask; report both numbers. Decide this from the numbers before making a
  mask, never by masking and then deleting. For example, an indoor portrait whose face was already
  brighter got no mask.

**First, check for SAM 3** (once per batch): `"$CLI" run --connect segment.model.status`.
- `available: true` and `installed: true` → use **Path A (SAM 3)**.
- Otherwise, or if Path A fails its coverage check twice on a photo → use **Path B (Auto Mask brush)**.
  Never start the model download yourself (`segment.model.download` needs the user's licence
  acceptance); the user installs it.

**Mask values** (both paths): `mask.adjust id=N 'values={...}'`
- **Daylight:** `lift.mask.daylight` (default `{"exposure":0.45,"shadows":15,"temp":0}`). In testing,
  a warmth of +3 made subjects look too warm.
- **Night:** `lift.mask.night` (default `{"exposure":0.30,"shadows":15,"temp":0}`). This is the start
  value. Night scenes are already tungsten-warm, so start low and step up to the target.
- **Skin still reads warm** with temp 0: set mask `temp` to `lift.warm_skin_temp` (default -4). The
  change is subtle: face R−B drops by only about 1 point.
- **Black or navy clothing** turns grey under the mask (it rises more than 50 %): set mask `shadows`
  to 5.
- **Adjusting the lift on a dark face in daylight:** keep mask `shadows` at 15 (5 on black
  clothing). Step only the mask exposure, by 0.1, from 0.45 up to `lift.daylight_mask_max` (default
  0.65). Stop at the daylight target above, or at that cap, and report a face that is still short.
  Never use the shadows ladder in daylight: lifted shadows turn dark hair grey against dark foliage,
  which reads as a halo.
- **Adjusting the lift on a dark face at night** (night or dim indoor scenes only): **shadows first.**
  - Raise mask `shadows` from 15 in steps of about 8, up to `lift.shadows_max` (default 40), at the
    current exposure.
  - Only when shadows reach that maximum and the face is still short of the target, step the mask
    exposure up by 0.1.
  - Stop shadows early if one face overshoots: on one photo, 40 gave +25 % where "a bit more" was
    asked, so 28 was kept.
  - In testing, shadows 32–40 alone lifted faces 10–15 % on three night portraits. On the darkest
    faces, shadows 40 plus more exposure lifted them 60–95 %. The user approved all of them.
  - On a bright face (60 or more), step the mask exposure by 0.1 instead.
  - The hard limit is `lift.mask_limit` (default **1.6**); never 2 or above.
  - At each step, check at 100 % for halos at the mask edge and for noise or blotches on the face.
    Stop at the last clean step and report which limit stopped you.
  - In testing, 0.7 brought one face from 64 to 70.5 (77 % of the background) with a clean edge, and
    0.85 showed no halos on two others.
- **Face far darker than the background at the limit:** add the global `exposure.boost` (see
  Global exposure boosts in Looks) and report the gap.
- **Flat, veiled face:** the trigger is an overcast scene where the face looks grey and low-contrast
  at 100 % after the lift. Set mask `shadows` to 0 and add `"dehaze":10,"clarity":10` (both are
  valid mask settings) instead of more exposure. The mask's shadow lift causes the veil, and clarity plus contrast alone
  did not fix it on an overcast forest portrait.
  - It worked on a bamboo-grove portrait (mask exposure 0.35, face +17.5 %).
  - **Not when the mask exposure is already 0.65 or more:** without the shadow lift the face got
    darker, and the user preferred the old version (lift +12.5 % → +9.5 %). There, keep the shadows
    and report the veil.
- **No mask path works** (SAM 3 fails twice, the brush spills, `kind=subject` takes the whole
  foreground): delete every attempt, keep no mask, and report the face and background means. The user
  accepted this on a small figure in front of a dark panel, where every method failed.

### Picking points (both paths)

Export `library.select 'ids=[ID]' app.export path="$SP/ID.jpg" longEdge=1500`, then run
`M grid "$SP/ID.jpg" -Region <around subject> -Out "$SP/ID-grid.png"`. Read the PNG and take the
coordinates from it: fractions of the full frame, as the grid labels show.

### Path A: SAM 3 mask

1. Load the model for the photo and wait until it is ready:
   `library.select 'ids=[ID]' segment.prepare`, then repeat `segment.model.status` (a few seconds
   apart) until `loaded: true`, `busy: false` and `analyzing: false`. Allow about 60 s on first load.
2. Make the mask (the result's `activeMask` is N; if it says `pending`, repeat `get_develop {id}` until
   the mask appears in `masks`):
   - **Preferred: describe each main person** (tested). Use 2–4 words: who they are plus their
     clothing colour, such as "man in red shirt", "girl in blue jacket" or "woman in black top". Make the first person's mask with
     `library.select 'ids=[ID]' mask.add kind=prompt 'text=man in red shirt' name=Subject`, then add each
     other person **to the same mask** with
     `library.select 'ids=[ID]' mask.addComponent id=N op=add kind=prompt 'text=girl in blue jacket'`.
     Both calls return `pending`. Poll `get_develop {id}` until the new component has its `seg` data.
     - Allow 20–40 s for the first prompt, and up to about 4 min for each added one: the app also
       re-processes the earlier parts.
     - Never use a sentence-long prompt: one found nothing in 4½ min.
     - A generic prompt such as "man and woman" also takes every passer-by who matches. That's why each
       prompt names clothing.
     - Exclude points (`mask.objectPoint`) **don't work** on a prompt mask ("the mask has no Object
       selection"). Fix spill by deleting the mask and using a more specific prompt or clicked points.
   - **Fallback: clicked points** read from a grid (see "Picking points"). Use it when a prompt finds
     nothing, catches the wrong people, or fails the coverage check twice:
     `mask.add kind=object 'points=[[x,y],[x,y]]' 'exclude=[[x,y]]' name=Subject`.
     Add or remove parts later with `mask.objectPoint id=N x=… y=…` (`exclude=true` to remove).
   - One obvious person or animal: `library.select 'ids=[ID]' mask.add kind=subject name=Subject`.
   - Optional, for hair and fine edges: `mask.refineDetail id=N`. It runs in the background, so poll
     `segment.model.status` until `busy: false`.
3. **Coverage check:** set `mask.adjust id=N 'values={"exposure":3}'`, export and read it. The subject
   should be blown out and the background unchanged.
   - Where +3 is hard to read (it often only brightens the subject a little), use a colour overlay instead:
     `mask.adjust id=N 'values={"tint":100,"saturation":100,"exposure":1}'`. Everything masked turns
     magenta. Set the real values afterwards, the same as after +3.
   - Fix spill with `mask.objectPoint … exclude=true` (clicked-point masks only).
   - **Never leave the +3 value.**
   - If the mask is still wrong after two fixes, run `mask.delete id=N` and use Path B.
4. Set the mask values above, then measure.
5. In the report, say which path made the mask.
6. After an aborted step, check `masks` for a stray mask and delete it.

### Path B: Auto Mask brush (no SAM 3)

1. Get coordinates as in "Picking points".
2. Run `library.select 'ids=[ID]' mask.add kind=brush name=Subject`; the result's `activeMask` is N.
   Then add strokes with `mask.brushStroke id=N 'points=[[x,y],…]' size=0.02 autoMask=true`.
   - `size` is a fraction of the long edge, 0.02–0.03.
   - Cover the head, torso, arms and legs, keeping each stroke inside the subject.
3. **Coverage check:** as in Path A step 3. Erase spill with
   `mask.brushStroke id=N … erase=true autoMask=true size=0.01`. If you abandon the mask, run
   `mask.delete id=N`.
4. Set the mask values above, then measure.
   - Before/after: export with `"amount":0`, then set `"amount":100` again and export. **Always end
     at amount 100.**
   - Check the edges with `M crops` at 100 %.

**Edge crops (both paths):** centre each 100 % crop on the mask boundary against a mid or bright
background, with at least 30 % of the crop being background. Crops placed inside the subject showed no
halo in testing even when there was one.
- **Check at true 100 %, not on a 2000 px render,** for the strongest mask in each batch and for any
  mask with exposure above 0.6: export that photo at `longEdge=6000` (one per call), and centre the
  crop where dark hair meets a dark background (foliage, shade). That edge is where halos show first.
  In testing, 2000 px edge crops passed five portraits whose halo the user saw on the review page.

## Local masks: signs, food, details

These came from user requests in testing. Do them only when the user asks, or when the condition below is
clearly met. Make the mask as in Path A, check coverage with the magenta overlay, then set the values.

- **A bright sign or billboard competing with the people:** darken the sign a little **and** lift the
  people a little.
  - Mask the sign with **clicked points** (`kind=object`). The prompt "billboard" also took every
    other sign.
  - Values: `local.sign` (default `{"exposure":-0.3,"highlights":0,"saturation":-15}`, or -25 on a
    pale or white screen).
  - Highlights -20 turned a near-white screen saturated cyan (R 225→177). Check the sign's colour with
    `rgb.ps1` before→after: it should get darker while keeping its R/G/B balance. Measure colour on
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
4. **Check** with a 2000 px before | after (`sbs.ps1`) of the area, and at 100 % on a 6000 px export
   (one file per call; it takes 25–30 s, and a slow one made the app unreachable for a few minutes).
5. **Report honestly:**
   - Small or blurred figures against repeating texture (bamboo, foliage) come out clean at normal
     size.
   - Figures standing across long straight lines leave stepped rails or a doubled edge at 100 %.
   - Figures overlapping the subject leave a trace.
   - Suggest a crop instead when it would remove them more cleanly.

## AI Denoise (high ISO)

ISO `denoise.iso_candidate` (default 3200) or above makes a photo a **candidate**. Judge each candidate on 100 % crops.

1. **Find the grain.** Export the candidate at full size (see Gotchas: 1–2 per call). Crop a mid-tone
   area: sky, a wall, or skin. Name the crop region in the report.
2. **Skip** if that mid-tone area shows no visible grain. For example, a black sky plus a lit, clean
   subject (a floodlit castle at ISO 4000): denoising would only soften the stonework.
   - **Decide once per venue and ISO, not per frame.** The first candidate at an ISO in a venue sets
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
   - Judge both a mid-tone area (sky or wall) and skin.
   - If 65 and 75 look alike, take 65.
   - On a night portrait at ISO 6400, 50 % left grain in the sky, 65 % was clean, and 75 % made the skin waxy.
5. **Render it:** run `denoise.queue 'ids=[…]'` after every amount change. The cached picture is
   for the old amount. Then poll `denoise.status` until `queued` is 0 and `running` is null.
   - **Wait in one background loop, not in repeated foreground calls (tokens):** run a Bash loop in
     the background that polls `denoise.status` every 20 s and exits when `queued` is 0 and
     `running` is null, and do other work (numbers, review lines) meanwhile. In testing, workers
     spent many turns on 180 s foreground polls. The loop must end before the report (see "finish
     with nothing running").
   - The built-in denoiser on the GPU takes about 1 minute per photo, and it needs no download.
   - **On the CPU it is much slower.** LightCraft can stop answering ("drew no frame") for 5–6
     minutes while it runs. Wait and keep polling `denoise.status`. Don't start another export, mask
     or denoise job, and don't restart LightCraft. In testing it always recovered by itself.
   - Set the amount only through `set_develop` (`enhance.denoise`). `denoise.toggle` ignores any
     amount you pass it.

## Clipping check

Run `M clip` on the 1000 px render before any edit and on the after render.
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
   - Fit 2 long true verticals (poles, building edges, door frames) with `lfit.ps1`, using
     coordinates from `M grid`. Fit the horizon with `lfit.ps1` on that line.
   - `M tilt` (n ≥ 2000) is a cross-check only.
   - **Busy night scenes** (lit buildings, few clean edges): `lfit.ps1` can disagree with itself
     (0.33 / -1.09 / 4.04° on one night facade, with few inliers). There, try
     `library.select 'ids=[ID]' crop.autoStraighten` first, re-export, and check it with `lfit.ps1`.
     In testing it gave -2.44° and the lines then measured level; the user approved it.
   - Under 0.3° on both verticals, or on the horizon: already straight, stop.
3. **Which case:**
   - **Plain roll** (verticals on both sides lean the same way): **rotate** with
     `library.select 'ids=[ID]' crop.straighten angle=<deg>` (-45 to 45, positive = clockwise; it
     keeps the largest crop). Try the measured correction, re-export, re-measure, and flip the sign if
     it got worse. It worked on 5 of 5 test photos (0.7–3.8°, 0.9–4.4 % crop per edge).
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
4. Keep the correction only if it measures better. Otherwise revert and add a `decide` with the
   numbers, and a test render if one exists.
5. If you keep a correction, run `set_develop {id, settings: {geometry: {constrain_crop: true}}}` and
   say what the crop cuts off. If it cuts into the main subject, add a `decide`.

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
  are judged on the numbers alone: `M clip` before and after, `M tilt` or `lfit.ps1`, and the whole-frame
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
  recognition is usable) and whether recognition is usable (see lightcraft-cull, "Whose faces count");
  when it is, the `people-by-photo.json` lines for its ids (`people.py "$RUN" --ids 1165-1197`), so
  the worker makes no face calls of its own;
- that the report ends with **"Improvements"**: at most 6 lines on what would make the skill faster,
  use fewer tokens, or give better results. The orchestrator collects them for the next skill update;
- the review material and `review.jsonl` (see Showing results);
- the report: at most 15–25 lines, with no images;
- **finish with nothing running:** no background shell job of its own, no export, `denoise.status`
  with `queued` 0 and `running` null, and `segment.model.status` with `busy: false`. Say so in the
  report. In testing, one worker reported while its own background job was still running.

**Time:** a chunk of 20 took 30–55 minutes on an entry-level laptop GPU. A plain photo takes about
1 minute; a masked one 2–10 minutes (each SAM 3 segmentation or added point takes about 60 s); about
1 more minute per denoised photo. Tell the user the estimate up front.

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
- **End-of-batch check, for every edited id:** run `develop.get`. Fail if any mask has
  `exposure >= 2` or `amount` other than 100.
  - The daylight cap (`lift.daylight_mask_max`, shadows 15) applies only to photos with the
    daylight look.
  - A mask on a photo with `look.night` or `look.light_show` follows the night ladder: shadows up to
    `lift.shadows_max`, and exposure up to `lift.mask_limit`. Don't flag it as over the daylight cap.
- **Cull marks:** editing must not change any rating or flag. Never skip this check; it must report
  0 mismatches and 0 changes outside the run:
  ```bash
  "$CLI" run --connect catalog.query limit=100000 > "$SP/now.json"
  python -I "$LC_SCRIPTS/runstate.py" check "$RUN" "$SP/now.json"
  ```
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
   - Add `decide` (and a `group`) only when the user must choose: a proposed look, a lift stopped
     at its limit short of the target, a failed mask, a crop over 5 % (over 12 % for a keystone `geometry.upright`
     correction: the user accepted 8–12 % per edge on four street views), a clip rule that stopped, a failed straightening, a
     photo left without a look. Other photos get Fine / Change automatically.
2. **The orchestrator** builds the page from all chunk folders, then opens it in the browser pane:
   ```bash
   python -I "$LC_SCRIPTS/review.py" "$SP/review.html" "$SP"/chunk* --title "<day> review"
   ```
   Fix every `WARNING` (missing file, bad line) before showing it.

**On a phone:** the user often reviews away from the laptop, where the review page can't be opened. A
downscaled before/after sheet can't be zoomed, so the user can't judge noise or detail from it.
- **Standard output, every batch** (unless `review.phone_sbs` is false): the worker makes one `ID-sbs.jpg` per photo with
  `sbs.ps1 -Before ID-before.jpg -After ID-after.jpg -Region <the area that changed> -Out ID-sbs.jpg`
  (whole frame `0,1,0,1` for looks and straightening, the faces for a lift). Send these with the
  file-sending tool, listing the ids in order, and ask for verdicts by id.
- **The overall look:** before/after pairs at about 1000 px.
- **Noise, sharpness and mask edges:** send **100 % crops cut from a full-size export**
  (`longEdge=6000`, then `M crops -Region <~0.2 × 0.2>`).
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
  with `develop.get` once per chunk.
- **Apply develop values with the MCP `set_develop` tool.** The CLI `develop.set id=ID …` returns
  `ok` but doesn't apply the values. Check with `develop.get` if in doubt.
- Exports reflect the current develop state, including a +3 coverage check left in place.
- **Full-size exports** (`longEdge=6000`) take 25–30 s each. Export 1–2 per call: a call of 8 timed
  out. The export then kept running in the background, and for about a minute every request failed
  with "drew no frame". Wait for `library.state` to answer `"ok":true` before the next call.
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
  past 180 s. Poll `get_develop` until the component has its `seg` data. Never TaskStop a running mask
  command: one stopped call later reset a mask to +3.
