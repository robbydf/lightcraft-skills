---
name: lightcraft-cull
description: Use when the user asks to cull, pick, choose the best of, rate, reject or judge photos in LightCraft (ArtCraft), e.g. "pick the best from each burst", "cull the whole library", "go through yesterday's shots", "which ones should I keep".
---

# lightcraft-cull

**Culling** gives each photo one of three outcomes: the best frame of each burst, or a usable single
photo, gets 3 stars; an unusable photo gets the reject flag; everything else stays unmarked.

**Editing** is not part of this skill: use the `lightcraft-edit` skill afterwards. It lists a run's picks
with `runstate.py picks`.

## Setup

- LightCraft must be running with the bridge (the `lightcraft-mcp` skill, `start`). The window must
  stay **un-minimized** for the whole run: a minimized window stops drawing, and every request then
  fails with "the app drew no frame".
- **Tell the user before the run** what they may do in LightCraft meanwhile (see "Using LightCraft
  while a run is going" in the plugin README): view only, no clicking other photos, no filter, source
  or album changes, no minimizing, no dialogs, no rating. The pre-flight `library.state` check fails on
  any filter change, and `runstate.py check` reports any rating the user changes as a mismatch.
- Run CLI commands **from Bash**. Windows PowerShell 5.1 strips the `"` inside JSON arguments.
  Shell variables don't persist between tool calls, so start every Bash call with:
  ```bash
  source "<base>/../../scripts/lc-env.sh"   # <base> = this skill's base directory, written with forward slashes (C:/Users/...); sets CLI, LC_SCRIPTS, RUNS, PREFS, M
  RUN="$RUNS/<library name>"   # durable; one per library, named by the user (LightCraft does not report a name)
  SP="<session scratchpad>/cull"; mkdir -p "$SP"               # throwaway renders; never next to originals
  ```
  `lc-env.sh` finds LightCraft by itself. If it says it can't, ask the user for the install folder and
  write `LIGHTCRAFT_DIR=<folder>` to `~/.claude/lightcraft/config.env`.
  Use forward slashes in CLI `path=`/`dir=` values. Trim long export output with `| cut -c1-120`.
- **Preferences:** read `$PREFS` (`~/.claude/lightcraft/preferences.md`) before the first cull.
  - If it doesn't exist, copy `preferences.example.md` from the plugin root there, show the user the
    Cull section, and ask them to confirm or change it.
  - If a key this skill needs is missing, ask the user and offer to add the answer.
  - The values below in `backticks` such as `reject.sharp_ratio` are those keys.
- Helpers (all in `$LC_SCRIPTS`):
  - `bursts.py` groups photos and can drop groups already in the log and split the rest into chunks.
  - `runstate.py` holds the durable state: baseline, log, check, summary and rollback.
  - `measure.ps1` modes: `sharp` (sharpness), `tilt`, `mean` (brightness 0–255), `crops` (up to 4
    files stacked into one PNG) and `grid`. `-Region x0,x1,y0,y1` takes fractions of the frame, and
    `-Out` must end in `.png`.

## Rules (from the preferences file)

The marks are fixed: a pick is 3 stars and a reject is the reject flag. `runstate.py` checks and rolls
back exactly these marks. The thresholds are `burst.gap_seconds`, `reject.sharp_ratio`,
`reject.cap_percent` and `reject.exposure` in the preferences; the defaults are shown here. Record shots
follow `record_shots` (default: unmarked).

| Outcome | When | Mark (always with explicit `ids`) |
|---|---|---|
| **Pick** | The best frame of a burst. A single photo that passes the reject test **and the moment test** (below). Bursts over 10 frames: one pick per distinct framing or moment. Two near-equal frames: both. | `photo.rate rating=3` |
| **Reject** | Passes the reject test below, whether in a burst or a single | `photo.flag flag=reject` |
| **Unmarked** | Usable but not a pick: weaker moment, a main person not looking at the camera in a posed photo, odd eyes, visible blur on a face at 100 %, an unflattering face, or **any doubt** (including eyes that may be closed). Closed eyes are a reject: see (d). Also **plain or record shots** (maps, signs, info boards, menus, timetables, tickets, phone screens, shots taken only to remember a detail), even when sharp | nothing (list doubts as `unsure`; log record shots with reason "record shot") |

**Food is not a record shot** (`record_shots.food`, default `keep`). Food, food displays, shop
counters, market stalls and sweets in a shop window are judged like any other photo, even with price
labels in frame. Menus stay record shots. In testing, the user reversed the un-pick of a mochi display
("I am capturing the foods available in Japan, not available at home") and asked for every food
record shot of the trip to be picked and edited, but not the menu.

**Whose faces count.** Every face rule here (the moment test, the face check, closed eyes (d)) and in
the panel applies only to **the user's own people**: the family or friends the photo is of. Strangers'
faces are part of the scene: a crowd street is a scene photo, whatever the faces in it do. In testing,
the panel voted to drop a crowd street for the faces in it, and the user kept it: "the faces here are
not our faces, this is just a scene". Decide who is whose, in this order:
1. **Named faces.** If faces are named in LightCraft (`faces.suggest 'ids=[…]'` returns a
   `suggestion` with a name for some face, or `people.own` in the preferences lists names), a face
   suggested as one of those names is the user's own. Unnamed faces with no suggestion are strangers.
2. **Otherwise, the day's people list.** Before culling a day, look at its posed photos (people
   stopped and facing the camera): those are the user's people. Write one line per day naming them by
   clothing, such as "woman in white shirt and rust skirt; boy in dark jacket", and give it to every
   worker and panel reviewer for that day. People wear the same clothes all day, so the list holds
   across that day's photos.
3. **A face counts as the user's own** if it matches the list, or it is clearly the point of the
   photo: large (about 5 % of the frame width or more), in focus, framed as the subject, or looking at
   or reacting to the camera.
4. **Strangers:** passers-by, crowds, staff, performers, people seen from behind, and small or
   edge-cut figures that match no one on the list.
5. **Doubt:** treat the face as the user's own (the stricter reading), and add "own or stranger?" to
   the reason, so it reaches the review list.

If the user wants this reliable, offer once to name their people in LightCraft: a few faces per
person is enough for `faces.suggest`.

**Never:**
- Delete anything, or use the `pick` flag.
- Rate and reject the same photo.
- Change a photo the user marked before the run (`runstate.py protected`: rated or flagged). A photo
  that is only `edited` is **not** protected: cull it normally.
- Edit photos during a cull.
- Call `develop.reset` or `history.clear`.
- Use `photo.analyze` (the GUI's "Assisted Culling") for any decision. With `rejectBelow` or `pickBest`
  it marks photos itself and uses the pick flag. Without them it only scores, but tested on a
  31-frame calibration chunk the scores were useless: 19 frames scored 98–100, the one real reject scored 95.5, a
  sharp park map scored lowest (47.5), and its 10 s look-alike groups don't match the 1 s burst rule.

**Reject test.** Reject only if (a), (c) or (d) holds:
- **(a) Visible fault.** Export at 2000 px and Read a 100 % crop of the subject (region ≤ 0.3 × 0.3).
  It must show doubled edges or streaks (shake), or nothing in the frame in focus. Alternatively, the
  640 px view shows an accidental frame: no subject, the floor, or a lens cap. A blown-out smear
  with no subject, such as a frame of pure light streaks, follows `reject.light_smear`:
  `reject` treats it as a visible-fault reject, `unmarked` leaves it unmarked, and `ask` (or a missing
  key) leaves it unmarked and puts it on the review list.
- **(b) Bursts only, extra condition.** On top of (a), the frame's `sharp` must be below 0.6 × the
  burst's best, using the same subject region. Below 0.6 only means "look at the crop": the crop
  decides. Soft-but-readable frames (faces readable, no streaks) are unmarked `unsure`, not rejects.
- **(c) Exposure** (`reject.exposure`, default below 5 or above 250). `M mean` on the subject is outside it on an unedited render. Anything
  else is recoverable, so it is not a reject.
- **(d) Closed eyes (`reject.closed_eyes`).** A main person's eyes are closed: the lids cover
  the pupils (a blink, or mid-blink). Bursts and singles alike.
  - **Main person:** anyone the frame is about, facing the camera. Bystanders and people in the
    background don't count. In a group shot, one main person with closed eyes is enough.
  - **Confirm on a 100 % crop of the eyes** from the 2000 px export (region ≤ 0.15 × 0.15). The 640 px
    sheet only nominates candidates.
  - **Not a reject:** looking down, eyes narrowed by a smile with the pupils still visible, sunglasses,
    face too small or turned away to see the eyes, or any doubt. These stay unmarked `unsure`.
  - Log reason `"closed eyes"`. In a burst, the pick must have open eyes; if no frame does, the
    best frame stays unmarked `unsure` instead of being rejected, so a burst never ends with nothing.
- **Singles** are never rejected on a number alone. Treat motion blur that may be intentional (light
  trails, panning, night crowds) as not a reject.
- **Cap** (`reject.cap_percent`, default 15 %): if rejects exceed it in a chunk, stop and show the user before marking.

**Reference result (a 1450-frame travel library):** 761 picks, 20 rejects (1.4 %), 117 unsure;
no chunk came near the 15 % cap. Score traps seen: night and fireworks frames score low but are fine
in the crop; a frame with heavy motion streaks can score *highest* (noise and streak edges inflate
`sharp`), so a streaked frame above 0.6 stays unmarked `unsure` and goes on the user's review list.

**Calibration (chunk 1, 31 frames):** 1 reject (3 %), so the 15 % cap stays. Three frames
fell below 0.6 (ratios 0.30, 0.40, 0.43); only the 0.40 one was unusable in its crop, so the ratio is a
trigger for the crop, not a verdict. The `sharp` score must not choose the pick when framing shifts
between frames (the region then covers different content): pick on the crops and the moment.
The user added the record-shot rule after seeing a park map rated 3 stars.

## Cull one group (what a chunk worker does)

Input: group lines from `bursts.py` such as
`burst 5 2025-06-14T16:56:24+02:00 101=IMG_0101 102=IMG_0102 … rated=… flagged=…`.

1. **Skip protected groups.** If any id is in `protected` (shown as `rated=`/`flagged=` from before
   the run), log the group with no new marks and the reason "user-marked", and stop.
2. **Triage sheet.** Export the burst at 640 px without changing the selection, then stack up to 4 per
   sheet and Read each sheet:
   ```bash
   "$CLI" run --connect app.export 'ids=[101,102,103,104]' dir="$SP/g101" longEdge=640 format=jpeg naming='{name}' conflict=overwrite | cut -c1-120
   M crops "$SP"/g101/*.jpg -Region 0,1,0,1 -Out "$SP/g101-sheet1.png"
   ```
   Sort each frame into a candidate, a weaker moment (unmarked) or a possible reject.
   - Bursts over 8 frames: split them into runs of similar framing and handle each run separately.
   - A single that looks fine at 640 px is a **pick** only if it also passes the **moment test** and the
     **face check** (`pick.moment_test`, `pick.face_check`; skip a check that is `false`):
     - **Moment test:** first decide whether the single is **posed** or **candid**.
       - **Posed** (people stopped and face the camera, framed as a portrait or group photo): **every**
         main person looks at the camera, and no face is turned away or hidden (by a hand, an arm,
         another person or an object). If any main person looks away, down or sideways, or has their
         face hidden, the single stays **unmarked**, even when someone else looks at the camera. Log it
         as `unsure`, reason "moment: <what>". In testing, the user dropped every such single.
       - **Candid** (people caught doing something: ordering at a shop, watching an attraction or a
         character, a child reacting to something): looking away is fine, and the single is a pick
         if the face check passes. A face turned fully away still counts as hidden. In testing, the
         user kept all three candid singles the moment test had dropped (ordering at a shop, a boy
         looking at a statue, a toddler looking up).
       - **Not clear which:** unmarked `unsure`, reason "moment: posed or candid?", so it reaches the
         user's review list.
     - **Face check: always on a 100 % crop**, never on the 640 px view alone. Export the single at
       2000 px and crop every main face (region ≤ 0.15 × 0.15). It stays **unmarked** `unsure` if a main
       person shows:
       - **odd eyes:** half-closed, rolled up with eye whites above or below the iris, or oddly turned;
       - **visible blur** on the face at 100 % (motion smear, shake, or focus on the background);
       - an **unflattering face:** mid-chew, mid-speech with the mouth slack, a grimace, or a bad angle.

       In testing, the user un-picked three singles that had passed at 640 px, for the eyes, a bit of
       blur and an unflattering face.
     - **Subject focus:** with the same 2000 px export, also crop the main person's body or the
       main subject (region ≤ 0.3 × 0.3), even when the face reads fine small. If the subject is out of
       focus (soft edges everywhere on the person while the background is crisper, or nothing on the
       subject sharp), the single stays **unmarked** `unsure`, reason "subject out of focus". In
       testing, the user un-picked a full-length portrait for this after it had been picked and edited.
     - **Soft but readable is still a pick.** A face that is a little soft, with no visible blur or
       streaks at 100 %, passes (`pick.soft_but_readable`). In testing, the user kept such frames.
       - **But a defocused or shaken face is not "soft but readable".** If the focus sits on the
         background, or the face shows smear or shake at 100 %, it is visible blur, even when the face
         can still be recognised. This includes high-ISO night frames.
       - In one trip's review the user dropped every unsure single whose only fault was softness on a
         face (4 of 4, night, ISO 6400), and a skyline with camera shake. They kept every unsure single
         whose only fault was the moment: looking away, looking down, or a grimace (4 of 4).
       - So for `unsure` reasons, a blur reason leans drop and a moment reason leans keep. Say which
         one it is in the reason, such as "blur: face defocused" or "moment: looking down", so the
         review sorts them.
     - Scenes where people are only small passers-by don't need either check. Skip steps 3–4 for a
       single.
3. **Sharpness.** Only for bursts, or a doubtful single: export at 2000 px to `$SP/g101-2k` (same
   command, `longEdge=2000 sharpen=none`). Then run `M sharp <files> -Region <subject>`. The score is a
   rank **within one burst only**. Export at most 8 frames per 2000 px call: bigger calls time out,
   and the next few requests fail with "drew no frame" until the app catches up.
   - Put the region on the **subject** (the face for people), not the background. Scores under ~50
     mean the region missed the subject: move it.
   - When framing shifts between frames, the same region covers different content and the score
     can't rank them: decide on the crops and the moment.
4. **Crops.** `M crops <top 3 + any reject candidate> -Region <≤0.3×0.3 on the subject> -Out …`, then
   Read the PNG. The frame where fine detail is readable wins, and a reject candidate must show its
   fault here. When frames are equally sharp, choose on moment: eye contact, expression, whole subject
   in frame.
   - **Every burst pick needs its own 100 % crop of the subject.** Don't pick on the score alone; once
     a 4-pick portrait burst was chosen with the region on the background.
5. **Mark.**
   - Re-query first and check only your ids; don't parse the catalog by hand (a hand parse once read
     1 row):
     ```bash
     "$CLI" run --connect catalog.query limit=100000 > "$SP/now.json"
     python -I "$LC_SCRIPTS/runstate.py" check "$RUN" "$SP/now.json" --ids 101,102,104
     ```
     A `USER-CHANGE` line for one of your ids means the user changed it: drop that id.
   - Then mark: `"$CLI" run --connect photo.rate rating=3 'ids=[…]'` and
     `photo.flag flag=reject 'ids=[…]'`. Mark only ids in your own groups.
6. **Log.** Only after both marks returned `ok`, log every group, including groups with no marks.
   Then delete the renders with `rm -rf "${SP:?}"/g101*` (a bare `"$SP"/…` glob is blocked by the
   safety check).
   ```bash
   python -I "$LC_SCRIPTS/runstate.py" log "$RUN" '{"group":101,"ids":[101,102,103,104,105],"picks":[101,104],"rejects":[102,103],"unsure":[],"reason":{"102":"shake: doubled edges in crop","103":"shake"},"sharp":{"101":303,"102":293}}'
   ```
   `group` must be the group's first id. Log record shots with reason "record shot".

**Worker extras:**
- LightCraft is already running: don't start, stop or minimize it.
- On "drew no frame", wait ~10 s and retry with a smaller batch. If it persists for over 2 minutes,
  stop and report.
- **Report:** at most 15 lines, with no images:
  - the counts (picks, rejects, unsure, record shots, user-marked groups);
  - each reject with its reason and sharp ratio;
  - each unsure id with its reason;
  - confirmation that the step-5 check ran.

## Full-library run (orchestrator)

The orchestrator never views photos itself; it hands batches of groups (chunks) to subagents, one at
a time, and checks their results.

1. **Preflight:**
   - `"$CLI" run --connect library.state` must show `source.kind: "all"`, an empty filter and
     `visibleCount` equal to the library total. In the empty filter every field is null or false,
     except the default `rating: 0, ratingOp: "atLeast"`. An unknown or ignored filter key silently returns the
     whole view.
   - Save the catalog: `"$CLI" run --connect catalog.query limit=100000 > "$SP/photos.json"`, then
     `python -I "$LC_SCRIPTS/runstate.py" init "$RUN" "$SP/photos.json"`. This happens once per run; `init`
     refuses to overwrite.
   - Show the user the `protected` list and the plan, and confirm they want subagents used.
2. **Chunks:** `python -I "$LC_SCRIPTS/bursts.py" "$SP/photos.json" --gap <burst.gap_seconds> --log "$RUN/log.jsonl" --chunks --out "$SP" > "$SP/chunks.jsonl"`.
   - Use the same `--gap` for the whole run: changing it regroups the photos, and logged groups no
     longer match.
   - Each chunk has at most 25 groups or 120 frames, and a chunk never crosses a day.
   - A tail of ≤ 6 frames is folded into the previous chunk.
   - `--out` writes `$SP/chunkN.txt` for the workers. Numbers change on every regeneration, so
     regenerate only between chunks.
3. **Calibration:** the first chunk runs in the main session, not a subagent. Show the user the picks,
   every reject with its crop, and the unsure list. Tune the reject numbers above and get an OK.
4. **Run the chunks one at a time,** smallest days first. They must be sequential because LightCraft
   has one active photo. Each chunk goes to a fresh `sonnet` subagent with this prompt:
   (`<SK>` is this skill's base directory, as an absolute path. Subagents aren't told it, so write it
   out in full.)
   > You are a lightcraft-cull chunk worker. `<base>` in the skill is `<SK>`. Read `<SK>/SKILL.md` sections "Setup", "Rules" and "Cull
   > one group" and follow them exactly. RUN=`<RUN>`. Your groups (one per line) are in
   > `<SP>/chunkN.txt`. Your SP folder: SP=`<SP>/wN`. Cull every group, then return the short report.

   Run it in the background, and check each chunk before starting the next.
5. **After each chunk:**
   - Re-query the catalog and run `runstate.py check "$RUN" "$SP/photos-now.json"`.
   - Stop on any `MISMATCH`, on rejects over `reject.cap_percent`, or on a "drew no frame" error.
   - Report any `USER-CHANGE` to the user.
   - Delete `<SP>/wN`. Collect each borderline call the worker reports for the final review list:
     a reject on sight or on exposure, a streaked frame left unsure, or a soft pick.
5b. **Borderline panel (`panel`: skip it when `off`).** After each chunk, before marking anything
    new, send the borderline photos to a panel of 3 Sonnet reviewers. Borderline means:
    - the worker's `unsure` list, excluding record shots and user-marked groups;
    - soft picks;
    - near-equal frames;
    - reject candidates near the 0.6 threshold.

    How to run it:
    1. **The orchestrator exports** them at 2000 px (5–6 per call) into `$SP/panelN/raw`, then copies
       them to `$SP/panelN/photos/P01.jpg …` in a shuffled order. Keep the label → id key in
       `$SP/panelN-key.txt`, outside the photos folder.
    2. **Start 3 fresh `sonnet` subagents in parallel** (run in the background). They only read images,
       so they don't need LightCraft and can run at the same time. Prompt:
       > Read `<SK>/panel-brief.md` and follow it exactly, with PHOTOS=`<SP>/panelN/photos`, SCRIPTS=`<$LC_SCRIPTS as an absolute path>` and
       > OUT=`<SP>/panelN/<role name>`. Your role name: `<name>`. Your ROLE: `<role>`.

       The 3 roles:
       - **technical:** focus and blur, whether the subject is sharp at 100 %;
       - **people:** expression and how flattering the face is, and, in posed photos, whether everyone looks at the camera;
       - **eyes:** a tight crop of every main face, checking open, half-closed or rolled eyes, eye
         whites showing, and the gaze.
    3. **Votes:**
       - 3–0 or 2–1 keep: the photo becomes a pick (`photo.rate rating=3`) if it was unsure.
       - 3–0 drop: it stays unmarked; a soft pick loses its stars (`photo.rate rating=0`, only on this
         run's own marks).
       - Any 2–1 drop goes on the user's review list unchanged, **with the drop voters' reasons**
         (the reason field may never be empty: a card that only says "panel voted 2-1 to drop" gives
         the user nothing to judge).
       - The panel never rejects. Rejects follow only the reject test.
    4. **Log** each change with `runstate.py log`, reason "panel 3-0 keep" or similar, then run
       `check`.

    Test result (23 photos one user judged):
    - The panel matched 16 of the user's 18 calls, with 0 wrong drops.
    - The cull alone matched 13: it left three soft-but-readable frames unmarked that the user kept.
    - The panel's 2 misses were "not looking at the camera", which wasn't in its brief then; that rule
      has since been added.
    - Second trial day (30 photos): the panel matched the user on 27. All 3 misses were candid
      singles dropped for "not looking at the camera" (one 3–0, two 2–1); the posed/candid split was
      added to the brief after that.

    **Trial** (`panel: trial`): show the user the panel's changes for the first `panel.trial_days` days
    before applying them without asking. Keep it at 3 reviewers unless misses turn out to be random rather than one rule missing
    from the brief.
6. **After each day:** show `runstate.py summary "$RUN"` for that day (picks, rejects with reasons,
   unsure) and wait for the user's OK before the next day, unless the user said to run without
   stopping.
7. **Resume** in any session: re-export `photos.json` and rerun step 2. Logged groups are skipped.
   - If a worker was stopped mid-chunk, run `check` first. A `USER-CHANGE` on that chunk's ids means
     a group was marked but not logged: undo those marks or log the group before continuing.
8. **At the end:** run a full `check`, then confirm `bursts.py --gap … --log … --chunks` reports 0 groups
   remaining. Show the totals per day, the rejects and the review list.
9. **Undo:** `runstate.py rollback "$RUN" [--day D]` prints the commands that remove only this run's
   marks. Show them to the user before running them.

Measured costs (reference run: 1450 frames in 670 groups):
- Exports take about 1 s per frame at 640 px and about 4 s at 2000 px.
- The run took about 35 chunks: the calibration chunk in the main session, the rest in Sonnet
  workers.
- Each chunk took 3–18 minutes: about 3–6 minutes for 30–50 frames, and 15–18 minutes for 90–120
  frames of big bursts. Each worker used about 85–170k tokens.
- Delete renders after each group is logged.
