# LightCraft skill preferences

Copy this file to `~/.claude/lightcraft/preferences.md` (or `$LIGHTCRAFT_HOME/preferences.md`) and
edit it. The skills read it before culling or editing.
- If a key is missing, the skill asks you and offers to add your answer here.
- Values marked `approved: false` (the looks and the `lift.mask.*` values) are starting points: the
  skill shows you a sample first, and you approve it before the skill uses that value on a batch.
- When you approve a look or a value during a session, the skill updates this file and sets
  `approved: true`.

Keys are written as `` `key`: value ``. JSON values are slider ids for `set_develop` or mask settings
for `mask.adjust`.

## Cull

- `burst.gap_seconds`: 1 (frames this close together form one burst)
- `reject.sharp_ratio`: 0.6 (in a burst, a frame below this share of the burst's best sharpness only *triggers* a crop check; the crop decides)
- `reject.cap_percent`: 15 (stop and ask if rejects pass this share of a chunk)
- `reject.exposure`: subject mean below 5 or above 250 on an unedited render
- `reject.light_smear`: ask (a frame of pure light streaks with no subject: `reject`, `unmarked`, or `ask` = put it on the review list)
- `reject.closed_eyes`: true (a main person's lids cover the pupils)
- `pick.moment_test`: true (posed people photos: every main person looks at the camera, with no face hidden or turned away; otherwise unmarked. Candid shots of people doing something may look away)
- `pick.face_check`: true (singles: a 100 % face crop; odd eyes, visible blur or an unflattering face mean unmarked)
- `pick.soft_but_readable`: pick (slightly soft, no visible blur at 100 %)
- `record_shots`: unmarked (maps, signs, menus, timetables, tickets, phone screens)
- `record_shots.food`: keep (food, food displays, shop counters and stalls are judged like any photo; menus stay record shots)
- `people.own`: [] (names of the user's people as named in LightCraft's People view; used only when face recognition is on and faces are named. Otherwise, and for any face it doesn't name: the day's people list by clothing)
- `panel`: trial (`off`, `trial` = show the panel's changes before applying them, or `on`)
- `panel.trial_days`: 2

## Edit: looks

- `look.night` (night or high-ISO street, dim indoor venue), approved: false
  ```json
  {"light.highlights": -45, "light.shadows": 30, "light.whites": 5, "light.blacks": -12,
   "light.contrast": 12, "effects.clarity": 10, "effects.dehaze": 8, "color.vibrance": 12,
   "detail.nrLuminance": 35, "detail.nrColor": 35, "detail.sharpenAmount": 45,
   "detail.sharpenMasking": 45, "vignette.amount": -10}
  ```
- `look.light_show` (parades, fireworks, lit buildings against a black sky): `look.night` with these
  changes, approved: false
  ```json
  {"light.shadows": 10, "light.blacks": -5, "light.highlights": -60}
  ```
- `look.daylight`, approved: false
  ```json
  {"light.highlights": -30, "light.shadows": 25, "light.whites": 5, "light.blacks": -8,
   "light.contrast": 15, "effects.clarity": 10, "effects.dehaze": 4, "color.vibrance": 20,
   "detail.nrLuminance": 15, "detail.nrColor": 15, "detail.sharpenAmount": 40,
   "detail.sharpenMasking": 40, "vignette.amount": -8}
  ```
- `look.scene_map` (scene types that reuse a look), approved: false
  - blue hour or dusk: `look.night`
  - night skyline over water, cloudy dark sky: `look.light_show`
  - fluorescent-lit interior at low ISO: `look.daylight`, keeping the as-shot white balance when whites read neutral
  - daylight under a glass roof or canopy: `look.daylight`
  - dim indoor venue (bar, restaurant, exhibit), any ISO: `look.night`; every photo from one venue is treated the same way
- `wb.night_cooler_percent`: 5–10 (if neutral areas read orange at night; never warmer)

## Edit: exposure

- `exposure.boost`: 0.25 (global boost for a dark frame or a face far darker than the background; at most this, once per photo)
- `exposure.on_request_step`: 0.1 (when you ask for more exposure, this overrides the boost cap)
- `exposure.night_signs_ignore_blown`: true (in night scenes, highlights blown inside signs and lamps don't count)

## Edit: subject lift (people, pets)

- `lift.mask_if_darker_percent`: 5 (mask only if the face is this much darker than the background)
- `lift.bright_face`: +15–25 % (face already 60 or more)
- `lift.dark_face`: at least 75–80 % of the background mean (night)
- `lift.daylight_dark_face`: about 75–85 % of the background mean, never above it; the mask cap below wins
- `lift.daylight_mask_max`: 0.65 (daylight: keep mask shadows 15 and step exposure only, up to this)
- `lift.mask.daylight`: `{"exposure":0.45,"shadows":15,"temp":0}`, approved: false
- `lift.mask.bright_face`: `{"exposure":0.20,"shadows":15,"temp":0}` (start value for a face of 60 or more), approved: false
- `lift.mask.night`: `{"exposure":0.30,"shadows":15,"temp":0}` (start value), approved: false
- `lift.warm_skin_temp`: -4
- `lift.mask_limit`: 1.6 (never 2 or above)
- `lift.shadows_max`: 40 (night only: dark faces get mask shadows raised to this first, then exposure)

## Edit: local masks

- `local.sign`: `{"exposure":-0.3,"highlights":0,"saturation":-15}` (-25 on a pale screen); people mask +0.1
- `local.food`: `{"saturation":35,"temp":-6,"hue":-5}`
- `local.detail`: `{"exposure":0.45,"shadows":20}`, step to 0.65; "a bit more" = +15–20 %

## Edit: AI Denoise

- `denoise.iso_candidate`: 3200 (and above, judged on 100 % crops)
- `denoise.amounts`: 50, 65, 75 (the lowest that's clean at 100 %)

## Edit: straightening

- `straighten`: any_tilt (`any_tilt` = streets and people included, `facades_only`, or `off`)
- `straighten.landscape_fraction`: 0.5 (rotate sloping landscapes by this share of the slope)
- `straighten.max_lean_deg`: 2.5 (trees and people after a landscape rotation)

## Review

- `review.phone_sbs`: true (also make a BEFORE | AFTER image per photo for phones)

## Export

Lookup order: `export.<target>.<key>`, then `export.<key>`, then the default shown. Targets live in
`skills/lightcraft-export/targets/` (default target: `google-photos`).

- `export.min_rating`: 3 (picks at this rating and above)
- `export.people`: the `people.own` names (a pick is exported when one of them is named on a face)
- `export.google-photos.root`: the folder Google Drive for desktop backs up to Google Photos, e.g. `D:/Photos/GooglePhotos` (no default)
- `export.google-photos.staging`: `<parent of root>/.lc-staging` (same drive, never inside the backed-up folder)
