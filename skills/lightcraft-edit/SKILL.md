---
name: lightcraft-edit
description: Use when the user asks to edit, develop, retouch or adjust photos in LightCraft (ArtCraft), e.g. "edit the picks from June 14", "brighten my son", "the subject is too dark", "fix the exposure", "straighten this building", "denoise this", or "apply my night look".
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
  source "<base>/../../scripts/lc-env.sh"   # <base> = this skill's base directory; sets CLI, LC_SCRIPTS, RUNS, PREFS, M, PSX
  RUN="$RUNS/<library name>"   # the cull run's folder; ask the user if unsure
  SP="<session scratchpad>/edit"; mkdir -p "$SP"
  ```
  If `lc-env.sh` can't find LightCraft, ask the user for the install folder and write
  `LIGHTCRAFT_DIR=<folder>` to `~/.claude/lightcraft/config.env`.
  - Use forward slashes in `path=`.
  - `M` modes:
    - `mean`: brightness 0–255.
    - `clip`: % blown (any channel at 255) and % crushed (all channels at 0).
    - `tilt`.
    - `crops`: at most 4 files.
    - `grid`.
  - `-Region x0,x1,y0,y1` takes fractions of the frame, and `-Out` must end in `.png`. `M mean`
    always needs `-Region` (use `0,1,0,1` for the whole frame).
- **Preferences:** read `$PREFS` (`~/.claude/lightcraft/preferences.md`) before the first edit.
  - If it doesn't exist, copy `preferences.example.md` from the plugin root there, and tell the user
    that every look and value is still unapproved.
  - If a key this skill needs is missing, ask the user and offer to add the answer.
  - Names in `backticks` such as `look.night` or `lift.mask_limit` are those keys.
- Helpers in `$LC_SCRIPTS`, run with `PSX <script> <args>`:
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
3. Append `{"id":ID,"cursor":<cursor>,"masksBefore":<count>}` to `$RUN/edits.jsonl`.
   - Use the durable run folder, not the scratchpad, which a reboot clears.
   - After the photo is finished, add `{"id":ID,"done":true,…}`.
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
clipping-check renders. Never reset an edited photo just to get a "before". Likewise, apply the look to
every photo that needs nothing else (no mask, no denoise, no straightening), then export their after
renders together the same way. Use a new file name for each working render: a re-export under the
same name can be read back stale.

1. **Classify** from the 1000 px render of the unedited photo:
   - night street or indoor, light show or black sky, or daylight;
   - whether there is a people or pet subject;
   - whether verticals or a horizon could be tilted (see Straightening).
   - Get the ISO with `photo.allMetadata id=ID` (EXIF "ISO Speed").
2. **Straighten**, if it measures tilted (see Straightening). It comes first because transforms move
   the frame under a mask.
3. **Look**, by scene type (see Looks). A photo whose scene type has no approved look gets **nothing**
   (no look and no mask) until the user approves the sample, unless the user asked for a trial batch
   (see Looks).
4. **Subject lift**, only if measured darker (see Subject lift). Then any **local fixes** (see Local
   masks: signs, food, details).
5. **AI Denoise**, if ISO 3200 or above and grain shows at 100 % (see AI Denoise).
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
  - Treat every photo from one venue the same way. In testing, one restaurant was edited in one chunk
    and left unedited in the next.
  - The exception is a venue the user asked to leave unedited.

**Before using a look,** check that it is `approved: true`. If not, show one sample and wait for
approval (see New looks).

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
- **Darker faces, which includes most night portraits:** lift until the face reaches `lift.dark_face`
  (default **at least 75–80 % of the background mean**), with no % ceiling.
  - In testing, the user asked for more lift on night faces in three review rounds. Faces at about
    55 % of the background were still too dark, and 70–77 % was accepted.
  - Faces that are near-silhouettes (under 20) may need the mask at its limit. Report what you reached.
- The user's wish is a face at least as bright as the background. Report the face/background ratio.

**Measure** on a render with the look applied and no mask. Report each box's region.
- **Face:** a box on the forehead and cheeks.
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
- **Several people:** decide on the **darkest main-subject face**, and one mask covers all of them.
  Faces narrower than about 1.5 % of the frame width get no mask. Report them.
- **Mask only if the face is more than `lift.mask_if_darker_percent` (default 5 %) darker than the
  background mean.**
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
- **Adjusting the lift:** step the mask exposure by 0.1 from the start value toward the target.
  - Above 0.85, raise mask `shadows` (up to `lift.shadows_above_0_85`, default 40) before adding more
    exposure, because very dark faces respond better to shadows.
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

## AI Denoise (high ISO)

The user's rule: ISO 3200 or above makes a photo a **candidate**. Judge each candidate on 100 % crops.

1. **Find the grain.** Export the candidate at full size (see Gotchas: 1–2 per call). Crop a mid-tone
   area: sky, a wall, or skin. Name the crop region in the report.
2. **Skip** if that mid-tone area shows no visible grain. For example, a black sky plus a lit, clean
   subject (a floodlit castle at ISO 4000): denoising would only soften the stonework.
3. **Turn it on** with `denoise.toggle id=ID enabled=true` (it starts at 50 %). Set the amount with
   `set_develop {id, settings: {enhance: {denoise: N}}}`.
   - **Avoid double noise reduction:** while AI Denoise is on, set the look's `detail.nrLuminance` to
     10 and `detail.nrColor` to 15. Stacking it with the night look's 35 made the skin waxy and the
     background painterly on a night portrait.
   - On a masked night face that still shows fine speckle at 100 %, use `detail.nrLuminance` 20.
4. **Choose the amount by the crop:** the lowest of 50, 65 and 75 % that is clean at 100 %.
   - **Full ladder once per ISO level per run (speed):** render 0/50/65/75 only on the first
     candidate at each ISO level (for example 3200, 4000, 6400) in the whole run, and append
     `{"iso":6400,"amount":65,"id":ID}` to `$RUN/denoise-ladder.jsonl`. Later candidates at that ISO
     start at the recorded amount and render **only 0 % and that amount**. Step up only if grain
     still shows. Read that file before the first denoised photo of a chunk.
   - Set `detail.nrLuminance` 10 and `detail.nrColor` 15 **before** rendering the 0 % strip, so every
     strip has the same noise reduction.
   - Measured so far: ISO 3200 was clean at 50 %, ISO 4000 at 50 %, and ISO 5000 and 6400 needed 65 %.
   - Judge both a mid-tone area (sky or wall) and skin.
   - If 65 and 75 look alike, take 65.
   - On a night portrait at ISO 6400, 50 % left grain in the sky, 65 % was clean, and 75 % made the skin waxy.
5. **Render it:** run `denoise.queue 'ids=[…]'` after every amount change. The cached picture is
   for the old amount. Then poll `denoise.status` until `queued` is 0 and `running` is null.
   - The built-in denoiser on the GPU takes about 1 minute per photo, and it needs no download.

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

Hand the batch to `sonnet` subagents with a brief file, **one chunk of about 20 photos per worker**,
one worker at a time (LightCraft has one active photo). A worker's context fills up after about 20
edited photos. Give each chunk its own folder. List in the brief:
- the ids, and for a redo, that they must be reverted first;
- which looks are approved, and whether this is a trial batch for proposed looks;
- the review material and `review.jsonl` (see Showing results);
- the report: at most 15–25 lines, with no images.

**Time:** a chunk of 20 took 30–55 minutes on an entry-level laptop GPU. A plain photo takes about
1 minute; a masked one 2–10 minutes (each SAM 3 segmentation or added point takes about 60 s); about
1 more minute per denoised photo. Tell the user the estimate up front.

**The orchestrator, when the worker reports:**
- Stop the worker if it says background work is still running (one worker kept running after its
  report).
- **End-of-batch check, for every edited id:** run `develop.get`. Fail if any mask has
  `exposure >= 2` or `amount` other than 100.
- **Cull marks:** editing must not change any rating or flag. Never skip this check; it must report
  0 mismatches and 0 changes outside the run:
  ```bash
  "$CLI" run --connect catalog.query limit=100000 > "$SP/now.json"
  python -I "$LC_SCRIPTS/runstate.py" check "$RUN" "$SP/now.json"
  ```
- Look at a few results yourself before sending them.

## Showing results to the user

**At the computer: a review page** (preferred for any batch). `review.py` in this skill's folder
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
     at its limit short of the target, a failed mask, a crop over 5 %, a clip rule that stopped, a failed straightening, a
     photo left without a look. Other photos get Fine / Change automatically.
2. **The orchestrator** builds the page from all chunk folders, then opens it in the browser pane:
   ```bash
   python -I "$LC_SCRIPTS/review.py" "$SP/review.html" "$SP"/chunk* --title "<day> review"
   ```
   Fix every `WARNING` (missing file, bad line) before showing it.

**On a phone:** the user often reviews away from the laptop, where the review page can't be opened. A
downscaled before/after sheet can't be zoomed, so the user can't judge noise or detail from it.
- **Standard output, every batch:** the worker makes one `ID-sbs.jpg` per photo with
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
