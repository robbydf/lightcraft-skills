---
name: lightcraft-export
description: Use when the user asks to export, share, upload, back up or send finished LightCraft (ArtCraft) photos somewhere, e.g. "export the picks to Google Photos", "export the Japan trip", "send our photos to Google Photos", or runs /lightcraft-export [target] [trip].
---

# lightcraft-export

Exports the **picks** of a trip (rating `export.min_rating`+, default 3) that show **the user's own
people**, at the settings of one **target** (a platform or format), into a folder the target picks up.

- **Read-only on the catalog.** The photos are already culled (`lightcraft-cull`) and edited
  (`lightcraft-edit`). This skill never rates, flags, edits, denoises or names faces.
- **Invocation:** `/lightcraft-export [target] [trip]`, for example `/lightcraft-export`,
  `/lightcraft-export 2026-11 Japan` or `/lightcraft-export google-photos 2026-11 Japan`.
  - **The target is optional; the default is `google-photos`.** The first word is the target only
    when it names a file in `targets/` (`targets/<word>.md`). Otherwise all the words are the trip.
  - **Unknown target:** if the user clearly named a target (said "target", or a word like `instagram`
    or `print`) and there is no such file, say so, list the files in `targets/`, and stop.
  - **No trip:** ask for the date range and a folder name in step 2.
- **Targets** (`<base>/targets/<target>.md`): read the target's file before step 1. It gives the
  `app.export` options, the size rule, the destination and its one-time setup, limits, checks, and what
  the user does afterwards. This file stays platform-neutral; a new platform is a new target file plus
  an `export.<target>.*` block in the preferences.

## Setup

- LightCraft must be running with the bridge (the `lightcraft-mcp` skill, `start`). Keep the window
  **un-minimized**: a minimized window stops drawing, and every request fails with "the app drew no
  frame". On that error, restore the window, wait 10 s and run the same batch again (the manifest
  makes this safe).
- **Tell the user before the export** what they may do in LightCraft meanwhile: look, scroll, zoom.
  No rating, flagging or editing, no dialogs (Export, Settings), no minimizing.
- Run CLI commands **from Bash**, never PowerShell (it strips the `"` inside JSON arguments). Start
  every Bash call with:
  ```bash
  source "<base>/../../scripts/lc-env.sh"   # <base> = this skill's base directory, forward slashes; sets CLI, LC_SCRIPTS, LC_PY, RUNS, PREFS, M
  RUN="$RUNS/<library name>"   # durable, the same folder the cull and edit runs use
  SP="<session scratchpad>/export"; mkdir -p "$SP"
  T=google-photos              # the target
  ```
  Use forward slashes in CLI `dir=`/`path=` values. Never pipe `app.export` into `head`.
- **Preferences** (`$PREFS`, Export section). Shared selection keys: `export.min_rating` (3) and
  `export.people` (default: `people.own`). Target keys `export.<target>.*` are listed in the target's
  file. **Lookup order: `export.<target>.<key>`, then `export.<key>`, then the default.** If a key the
  target needs (such as `export.<target>.root`) is missing, ask and offer to save the answer.
- Helpers (in `$LC_SCRIPTS`): `people.py` (who is in each photo), `export_picks.py` (the selection),
  `export_stage.py` (folder check, edit-history signatures, crash recovery, safe moves into the
  folder) and `export-stage.sh` (the batched export). `runstate.py marks` checks that nothing changed.

## Workflow

1. **Checks before anything is exported.**
   - **Folders.** `ROOT` = `export.<target>.root`. `STG` = `export.<target>.staging`, or by default
     `<parent of ROOT>/.lc-staging`. If ROOT is a drive root there is no parent folder: ask for a
     staging folder on the same drive that is not synced, and save it.
     ```bash
     "$CLI" run --connect library.folders > "$SP/folders.json"   # the library's photo folders
     "$LC_PY" -I "$LC_SCRIPTS/export_stage.py" check --root "$ROOT" --staging "$STG" --avoid "<each folder path>" ...
     ```
     Pass every top-level `path` from `library.folders` as an `--avoid`, so the export never lands
     among the originals.
   - **Face recognition** must be usable, as in the cull skill: `faces.models.list` shows
     `enabled: true` and an `embedder`, and `faces.suggest 'ids=[<a photo with people>]'` shows
     `galleryFaces` above 0. **If not, stop** and tell the user. An export never guesses people from
     clothing, and never turns recognition on or names faces.
   - **GPU:** `"$CLI" run --connect app.gpu wait=false`. Read it, never change it. If `enabled: true`
     on an entry-level GPU (2–4 GB, such as an MX130), use the target's GPU size (for google-photos,
     `edge=4000`) and say so in the report.
2. **Trip.** Ask for (or take from the arguments) the date range `FROM`..`TO` (`YYYY-MM-DD`, compared
   with the camera's own date) and the folder name, e.g. `2026-11 Japan`. `DEST="$ROOT/<folder>"`.
   The folder name is one plain folder: no `/`, `\` or `..` (ask again if it has them).
3. **Data** (fresh each run, in `$SP`, so the cull's files in `$RUN` stay untouched):
   ```bash
   "$CLI" run --connect catalog.query limit=100000 > "$SP/marks-before.json"
   mkdir -p "$SP/faces"; rm -f "$SP"/faces/faces-*.json
   for n in Sarah Enzo Robby; do "$CLI" run --connect faces.person name="$n" more=0 > "$SP/faces/faces-$n.json"; done
   "$CLI" run --connect faces.unnamed limit=20000 > "$SP/faces/faces-unnamed.json"
   "$LC_PY" -I "$LC_SCRIPTS/people.py" "$SP/faces" "$SP"/faces/faces-*.json
   ```
   Use the names from `export.people`. **Stop** if `people.py` reports faces "not listed" or "cut off by
   the limit" (raise the limit and run it again), or if a `faces.person` result shows `ready: false` or
   `pendingPhotos` above 0. In that case recognition is still working: wait, then run step 3 again.
   - **Edit signatures of photos exported before** (to notice re-edits). Skip this on the first run;
     a missing signatures file just means nothing is flagged as changed.
     ```bash
     rm -f "$SP"/hist-now*.json
     done_ids=$("$LC_PY" -I "$LC_SCRIPTS/export_stage.py" done --manifest "$RUN/export-$T.jsonl")
     set -- $done_ids; k=0; files=()
     while [ $# -gt 0 ]; do   # at most 100 history.list commands per CLI call
       k=$((k+1)); hl=(); n=0
       while [ $# -gt 0 ] && [ $n -lt 100 ]; do hl+=(history.list id="$1"); shift; n=$((n+1)); done
       "$CLI" run --connect "${hl[@]}" > "$SP/hist-now-$k.json"; files+=("$SP/hist-now-$k.json")
     done
     [ -n "$done_ids" ] && "$LC_PY" -I "$LC_SCRIPTS/export_stage.py" hist --out "$SP/hist-now-sigs.json" \
       --ids "${done_ids// /,}" "${files[@]}"
     ```
4. **Select and confirm.**
   ```bash
   "$LC_PY" -I "$LC_SCRIPTS/export_picks.py" "$SP/marks-before.json" "$SP/faces/people-by-photo.json" \
     --people Sarah,Enzo,Robby --min-rating 3 --from FROM --to TO \
     --manifest "$RUN/export-$T.jsonl" --hist-sigs "$SP/hist-now-sigs.json" \
     --decisions "$RUN/export-$T-decisions.json" --out "$SP/picks.json"
   ```
   Show the user the table per day (new, already exported, review, no faces, not edited) and the
   totals. Then:
   - **Review list** (`review`: only a *suggested* own face, or unnamed faces only): export those
     photos at 640 px, `suggested:` first, 6 ids per call:
     `bash "$LC_SCRIPTS/export-ids.sh" "$SP/review" r 640 <ids>` (files `ID-r.jpg`, so a sheet label
     names the id). Show them with `M sheet` (9 per sheet;
     one sheet set per day when there are many). Ask: include none, all, by day, or by photo. Write the
     answer to `$RUN/export-$T-decisions.json` (`{"include": [...], "exclude": [...]}`) and run step 4
     again.
   - **`not_edited`** picks would export as untouched renders: list them and ask whether to keep them
     in the export.
   - **`changed`**: photos edited again since their export. They are not exported again on their own.
     If the user wants them again: `export_stage.py force --manifest "$RUN/export-$T.jsonl" --ids <ids>`,
     then rerun step 4. A forced photo gets a new file `NAME-ID`, the old file stays, and the user
     deletes the old copy on the platform.
   - `no_faces`, `others_only` (only other named people) and `no_date` (no capture date while a date
     range is set) are not exported; give their counts.

   **Wait for the user's OK** before step 5.
5. **Export** in the background: one tool call that runs the whole list, with a progress line per
   batch. Never more than one export at a time.
   ```bash
   ids=$("$LC_PY" -I -c "import json,sys;print(','.join(json.load(open(sys.argv[1]))['export']))" "$SP/picks.json")
   BATCH=3 bash "$LC_SCRIPTS/export-stage.sh" "$SP/raw" "$DEST" "$STG" \
     "$RUN/export-$T.jsonl" "$SP/picks.json" mp=16 <the target's app.export options> -- $ids > "$SP/export.log" 2>&1
   ```
   Use `run_in_background`, and read `$SP/export.log` when the job ends.
   - A failed batch stops the job: read its line, fix the cause, and run **the same command** again.
     Ids already done in the manifest are skipped, so the rerun resumes where it stopped.
   - With GPU rendering on (step 1), use `edge=4000` instead of `mp=16`.
   - Batches: 3 ids per call at 16 MP (about 17 s per photo on the CPU in testing). On a timeout,
     use `BATCH=2`.
6. **Check.**
   - Every id in `export` has a `done` line in the manifest (last line per id).
   - Run the target's file checks on 3 sample files (pixel size, colour profile, EXIF date/GPS).
   - Nothing in the catalog changed:
     ```bash
     "$CLI" run --connect catalog.query limit=100000 > "$SP/now.json"
     "$LC_PY" -I "$LC_SCRIPTS/runstate.py" marks "$SP/marks-before.json" "$SP/now.json"   # must exit 0
     ```
   - Report: the folder, the number of files, the review decisions, and the target's "after" steps
     for the user.
7. **Rerun / resume.** Run the same steps. Done ids land in `already_exported`. `export-stage.sh`
   first settles `pending` lines from a crash: `done` when the file in the folder has the same size
   and hash (it is not exported again), otherwise `abandoned`, and the photo is exported again.

## Never

- Rate, flag, edit, denoise, reset, rename, move or delete photos, or name faces.
- Overwrite or delete anything in the export root (Drive or another syncer would upload a duplicate,
  or delete the copy on the platform). A forced re-export always gets a new name.
- Stage files inside the export root, or write `result.json`, logs or manifests there.
- Change `app.gpu`, face recognition or LightCraft settings.
- Upload, sign in or change settings on the platform: the target's "after" steps are the user's.
