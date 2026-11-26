---
name: face-lift
description: Use when a person's or pet's face in a LightCraft (ArtCraft) photo needs lifting or a shadow on it lessened, e.g. "brighten his face", "the face is too dark", "lessen the shadow on her face", "lift the kids". lightcraft:edit also calls it for its subject-lift step.
---

# lightcraft:face-lift

Lift the faces of the user's own people (and pets) with a mask, and lessen a shadow across a face.
This is the subject-lift step of `lightcraft:edit`, kept as its own skill.

## Setup

- **Called from lightcraft:edit:** its Setup, history record ("Before the first change to a photo")
  and look are already done. Keep the same `RUN`, `SP` and round. When the lift is finished, go back
  to lightcraft:edit for local fixes, denoise, the clipping check and the after render.
- **Used on its own** (the user asks only for a face lift): first follow lightcraft:edit's **Setup**
  and **Before the first change to a photo**, including how to revert (Read
  `<base>/../edit/SKILL.md`). Its Setup line works from here unchanged:
  `source "<base>/../../scripts/lc-env.sh"`, with `<base>` being this skill's base directory.
  Don't apply a look unless the user asks; measure on the photo as it is. Where this skill says
  "look applied, no mask", read "as it is, no lift mask".
- **The photo already has a lift mask** (`Subject` from an earlier round, or a person mask the user
  made by hand; common when the user asks again): don't delete it and don't add a second one
  (`seg-chain.sh` refuses when a `Subject` mask exists). Record the history cursor, measure the
  "before" with that mask's `amount` at 0, set `amount` back to 100, and step that mask's values. If
  the report or `edits.jsonl` shows an earlier shadow fix added `lift.face_shadow_global`, the
  "before" still includes it: say so, and don't add it again. Delete it only when it has to be
  remade (it fails the coverage check, or the user asks), and only after the cursor is recorded.
  - **Check coverage for each main face**, not just the mask as a whole. Old masks often cover one
    person only: in the all-photos run, two masks covered Enzo but not Sarah, the largest face. Add the
    missing person to **the same mask** with `mask.addComponent id=N op=add kind=prompt 'text=…'` (or
    clicked points), wait for its `seg` data as in Path A, then step the mask.
  - **The table now says "no mask" but a lift mask exists:** keep it. If it's above the ladder's cap
    (0.50 for the bright ladder), lower it to the cap. Otherwise leave its values as they are. Ask about
    it on the review card ("old lift kept although the face is X % above the background: keep?").
  - **The old mask already puts the face above the target but still under the background** (a dark
    daylight face at 88–94 % against the 75–85 % aim): keep it. The ladder doesn't step down. Lower a
    mask only when the face reads above the background (on the dark-face target) or the mask is over
    its ladder's cap, and then only to the highest step that fits.
  - **Judge an old mask's coverage by the gain on each face box** (the same box measured on the render
    with `amount` 0 and with 100): a covered face gains, an uncovered one stays at about 0 %. The
    colour overlay is hard to read on dark faces.
  - A mask you step or extend gets `temp 0`. Leave the temp of a mask you keep untouched.
- **A photo the user edited by hand, with no look** (their own exposure, highlights, denoise or hand
  mask; in a batch run): leave it untouched and report it. A look would overwrite their values, and a
  second noise reduction would stack on theirs.
- **Order in a batch:** the look first, then the global `exposure.boost` decision (lightcraft:edit,
  Global exposure boosts), and only then the no-mask render and the ladder. The boost changes every
  face number, so deciding it after the ladder means redoing both (one chunk redid 10 photos).
- Names in `backticks` such as `lift.mask.daylight` are keys in the preferences file (`$PREFS`).
  `M`, `LCX`, `$CLI` and the helpers are described in lightcraft:edit's Setup.
- Every CLI call starts with `library.select 'ids=[ID]'`. Never use `edit.undo` or `edit.redo`; take
  a step back with `history.restore` (lightcraft:edit, Revert).

## When to lift

Measure as in "Measure" below. Decide by the scene's light (daylight, or night / dim indoor) and the face reading, in this order.
The first rule that fits wins:

| Scene | Face (look, no mask) | Decision |
|-------|----------------------|----------|
| any | shadow across it (see "Shadow across the face") | lift, shadow fix |
| daylight | **near blown**: 190 or more, or the face box already over 0.5 % blown (`M clip`) | no mask |
| daylight | **160 or more** | lift, bright-face ladder |
| daylight | 60–160, **more than 25 % above** the background mean | no mask |
| daylight | 60–160, otherwise | lift, bright-face ladder |
| daylight | **under 60** | lift, dark daylight face (always) |
| night | more than 5 % darker than the background mean | lift, dark night face |
| night | within 5 %, or brighter | no mask |

- Only the user's own people get a lift. Strangers in a crowd or street scene are part of the scene,
  so no mask (see lightcraft:cull, "Whose faces count").
- The "60 or more" rows are for daylight only. A night face takes the shadow row first, then only
  the 5 % gate (in testing a night face of 125 against a background of 68 had no clear answer under
  the old wording).
- **Why 25 % in daylight:** the background mean moves with the boxes, so a narrow margin flips the
  decision. A face 8 % above the background (photo #90) was lifted and kept; faces 32–37 % above
  (#15, #83) got no mask and were kept. #764 sits on the 160 line (its face boxes read 152–170,
  background about 148, so +3–15 %): read at 160 or more it takes the 160 row, read below it takes
  the "otherwise" row, and both say lift, on the same ladder.
- **Why every daylight face under 60 is lifted:** a backlit face under a large sky (#833, face 57) read
  88 % of a background of dark trees, because sky can't be a background box; the user kept the lift.
  The bamboo-grove faces of 43–76 were all lifted and kept too.
- **Why near-blown faces get no mask:** a sunlit face of 208 was already 0.8 % blown with no mask.
  At 0.10 it went to 3.4 % blown and at 0.20 to 6.9 %, past the ladder's 2 % gate on the first step.
  Check `M clip` on the face box before making a mask, so you never mask and then delete.
- **The night 5 % gate in a scene full of signs and lights** (Dotonbori, Glico, a lit canal) flips
  with the background box. Compare the face with the plain surface right beside the person (ground or
  wall, see Measure), and in a series let the majority of frames decide.
- **Scene light when it is unclear:** a covered arcade or shopping street with lit signs and no sky
  in view counts as night. An outdoor street after sunset counts as night even when shop light falls
  on the face.

**Targets for each lift:**
- **Daylight face of 60 or more:** lift it by `lift.bright_face` (default **+15–25 %**).
  - A face that reads the same as the background still looks dull in daylight. In testing, two
    daylight portraits had faces at the background mean and got no mask; on review the user asked for
    both: "face needs to be brightened up a bit". A face clearly brighter than the background (#15 at
    119 vs 90, #83 at 148 vs 108) got no mask, and the user kept that.
  - Start at `lift.mask.bright_face` (default `{"exposure":0.20,"shadows":15,"temp":0}`), not at the
    daylight value. On the same portraits, 0.45 gave +38 %, 0.25 gave +24 %, 0.15 gave +17 %, and
    0.20 gave +20 %. The user approved 0.20.
  - Step the mask exposure by **0.10**, then by 0.05 for the last step into the target. Gain per step
    varies: on a two-person frame at about 105, 0.20 gave +9 %, 0.35 +14 %, 0.40 +16 %.
  - **The bright-face ladder stops at 0.50**, even below the target, and earlier if a face box would
    show more than 2 % blown. Measure that on skin, not on glasses glints (see Measure). If a skin box
    is already near or over 2 % before the mask, keep the mask at the start step, even when another,
    darker face on the same mask stays short. Flag the card ("lift held at X: one face already near
    blown, the other still at Y % of the background"). Never go past 0.50 to chase the %. On a face of 150 or more, flag the
    review card ("bright face, lift stopped at 0.50: OK?"). In testing, an overcast close-up at 165 got
    +8.8 % at 0.65; the user called it marginal ("might be a bit blown out") and set it to 0.50. A
    close-up at 188 got +8.9 % at 0.50, and the user kept it. Every kept bright-face lift so far sits at
    0.40–0.50.
- **Darker faces at night:** lift until the face reaches `lift.dark_face`
  (default **at least 75–80 % of the background mean**), with no % ceiling.
  - In testing, the user asked for more lift on night faces in three review rounds. Faces at about
    55 % of the background were still too dark, and 70–77 % was accepted.
  - A face of 55 against a lit street (night, black sweater) got the start value 0.30 and went to 69
    (+25 %); the user asked for "a little bit" of lift and said 0.30 "looks right".
  - Faces that are near-silhouettes (under 20) may need the mask at its limit. Report what you reached.
  - **Silhouettes often can't reach 75 %.** In the all-photos run, canal and street silhouettes (faces
    23–35) reached only 57–72 % at shadows 40 and exposure 1.30–1.50, with little gain per step above
    1.3. Stop new masks at **1.50**, report the ratio, and then consider the global `exposure.boost`
    (a separate step, under its own blown gate). 1.6 stays the hard limit for masks already there.
- **Darker faces in daylight** (under 60 with the look applied): aim
  for `lift.daylight_dark_face` (default **about 75–85 % of the background mean, never above it**), but **the mask cap wins**: stop
  at `lift.daylight_mask_max` even when the face is still short, and report the ratio. Use the
  daylight ladder below, not the night one.
  - **"Never above the background" wins over "always lift".** A face under 60 that already reads
    within about 10 % of the background (a dark scene, faces of 53 against 58) takes the bright-face
    ladder from 0.20, not the dark-face start.
  - A backlit face at 54 against trees and lawn (63 % of the background) got the 0.45 mask and reached
    82 %, and the user kept it.
  - In testing (overcast bamboo grove, dark hair against dark foliage), shadows 40 plus exposure up to
    1.05 brought faces to 85–94 with a visible halo, and the user said the lift was too much. The
    standard 0.45 / shadows 15 (0.65 on the darkest face) gave faces of 43–76, 52–95 % of the
    background, and the user accepted all five.
- At night the goal is a face at least as bright as the background. Report the face/background ratio.
- **A shadow across the face** (day or night): see "Shadow across the face" below. It gets a lift even
  when the background comparison says no mask.

## Shadow across the face

The face is lit unevenly: shade from a canopy, roof, hat or tree falls across it, or the light comes
from behind or from one side. Typically the forehead or one cheek catches the light while the nose,
upper lip and the other cheek stay dark.

**Trigger:** on the render with the look and no mask, measure two boxes on the face, read off an
`M grid` like the face box:
- **Compare cheek with cheek**, both boxes at the same height, beside the nose:
  - **Lit box:** the brighter cheek. No shine: skin with any blown pixels is not the lit box.
  - **Shadow box:** the darker cheek.
  - Use the forehead as the lit box only when the light falls from above (a hat brim or canopy edge
    across the face) and both cheeks are in the shade. Keep it clear of the hairline and check its
    edges against the grid ticks: in testing, hair or shine got into 5 forehead boxes (one moved the
    ratio from 0.58 to 0.48, one read 232 because it caught sky).
  - Never use the upper lip, chin or eye socket. They sit under the nose or brow and read as shadow
    on almost any face (an upper lip read 0.48 against the forehead where the cheeks read 0.82).
- Leave out eyes, nostrils, lips, hair and ears in both boxes.
- Each box at least about 3 % of the frame width (smaller boxes swing with the placement).
- If the shadow box reads **under half of the lit box**, the face has a shadow across it: lift it
  with the values below, whatever the background boxes say. The background can be useless here: a
  dark bench or seat back on one side and bright sky on the other.
- **Borderline (0.45–0.55):** measure a second cheek pair, a little higher or lower, and
  decide on both. In testing, the same face read 0.44 and 0.51, and 0.45 and 0.57, with different
  boxes. Lift if either pair reads under 0.5 and say so.
- Record both boxes (both pairs when borderline) and their means in `report.md` and `review.jsonl`,
  like the face box.

**The fix** (the user's own edit on `_RDF5383`, a boy on an open-sided train under a striped canopy,
bright sky behind; the user's edit of 2026-11-19, adopted here 2026-11-22):
1. A subject mask on the person (Path A or B below) at `lift.mask.face_shadow` (default
   `{"exposure":0.45,"shadows":15,"temp":0}`).
2. **Plus a global `light.exposure` +0.25** on the whole photo (`lift.face_shadow_global`). This
   counts as the photo's one `exposure.boost` (lightcraft:edit, Global exposure boosts): don't add
   another. If the photo already carries a global boost, the mask alone does it.
   - **Blown gate:** keep the global only if the whole frame's blown % rises by less than 0.5 points
     and no face box has more than 2 % blown. Otherwise set it back and keep the mask alone at 0.45.
     At night, measure the frame's blown % with `-Region` boxes that leave out signs and lamps, as in
     lightcraft:edit's Global exposure boosts.
     In hard sun (three people, one face half in shade) the global took the frame from 0.17 to
     2.85 % blown and a forehead to 21 %; mask alone gave 1.49 %, and the user kept that, even with
     one face at 7 % blown. Report the blown % of each face box; don't lower the mask for it.
3. **Don't raise the mask instead of adding the global exposure.** The user tried the mask at 0.65,
   with and without the global +0.25, and went back to 0.45 plus +0.25. A strong mask makes the face
   stand apart from the person and the scene; the global step lifts the sweater, the shade and the
   seats with it.

What it did on `_RDF5383` (2000 px, daylight look applied before):

| Box | Before | Mask 0.65 only | Mask 0.45 + global 0.25 (kept) |
|-----|--------|----------------|--------------------------------|
| Face (under the eyes) | 55 | 86 | 88 |
| Lit cheek | 92 | 129 | 131 |
| Shadow cheek | 29 | 55 | 56 |
| Shadow / lit | 0.32 | 0.42 | 0.43 |
| Sweater | 29 | 50 | 52 |
| Sky blown | 2.02 % | 2.03 % | 2.19 % |

- The face went up about 60 %, more than the bright-face target. The user chose it: a shadowed face
  needs the shadow side lifted, and the lit side follows.
- The shadow never goes away completely (0.43 on that photo). Don't chase the ratio with a stronger
  mask, a higher mask `shadows` value or a second mask on the dark cheek. Report the before → after
  ratio.
- In that run the worker judged "no lift was needed" on this photo: the face was compared with a dark
  seat back and the sky. The user then lifted it by hand. That is why the shadow trigger doesn't
  depend on the background.
- **Tested 2026-11-22, all kept by the user:** hard sun on one side with three people (mask only,
  see the blown gate; ratio 0.45 → 0.51), and a covered market with a boost already on the photo (mask
  only; 0.44 → 0.49). A night face read 0.77 and needed no shadow lift.
- **Not tried yet:** a night photo with a real shadow across the face. In a search of about 35 Japan
  photos none turned up; most night faces read brighter than the background, so the night ladder
  rarely runs. To test it, ask the user to point at a photo. Use the same values, and put the
  photo on the review list with `decide` "Shadow on the face lessened: OK?".

## Measure

Measure on a render with the look applied and no mask. Report each box's region.
- **Face:** a box on the skin of the forehead and cheeks: from just under the eyebrows to just
  above the mouth, and between the outer corners of the eyes. Leave out hair, eyes, eyebrows,
  shadowed eye sockets, glasses and specular highlights. Read the box off an `M grid` of the face,
  never a guess from the 1000 px view.
  - **Faster: start from LightCraft's face rectangle** when the cull saved one
    (`$RUN/faces-<Name>.json` from lightcraft:cull's people step; `result.confirmed[]` entries whose
    `photo` is the id, `rect` in full-frame fractions x0,x1,y0,y1). Use **x0+0.15w to x1−0.15w and
    y0+0.38h to y0+0.70h** as the face box, then check it on the image as below. In the all-photos run
    this replaced the slowest step, finding faces by eye. A lower band (0.42–0.78) landed on nose and
    mouth. A name tagged twice in one photo can leave another person without a rect: find that one by
    eye.
  - **Glasses:** the band lands on the lenses, and glints read as blown (1–3 % on one face). Move the
    box onto the cheek below the lens.
  - **Record the box** (x0,x1,y0,y1) in `report.md` and in the photo's `review.jsonl` `changes`.
  - **Check each box on the image before measuring:** draw the face and background boxes on the
    2000 px render and look. Grid tick labels sit at the line, not at the image edge, and in the
    all-photos run three face boxes landed on background. That only showed later as a 0 % gain.
  - **A face box under about 20 px wide on the 2000 px render** is too small for a reliable mean: no
    mask, report it (this is the 1.5 % rule below). Measure small faces on a 2000 px crop, never on a
    600 px contact sheet.
  - **A redo uses the recorded box.** In testing, two workers measured the same face as 84 and 59 with
    different boxes. The first number led to "no mask needed", and the user then asked for a lift.
- **Background:** 2 boxes of the same size (a third when they disagree, see below) beside the subject, on surfaces of ordinary
  brightness (foliage, ground, walls of a normal colour).
  - Take the **nearest such surface on the left and on the right** of the subject, at about face
    height, each box about the size of the face box. Don't shop around for boxes: in testing, a
    backlit face read 95 % of the background against a dark hedge and 63 % against the trees and lawn,
    which flips the decision. Name both surfaces in the report.
  - Never use white stone, snow, white walls, signs, lamps, lit windows or sky.
  - Each box must read 50–130 on the no-mask render; move it if not. On one portrait the boxes sat on
    white granite (130–144) and made the face look far darker than it was.
  - **No surface reads 50–130** (a dark night scene): use the 2 brightest ordinary surfaces and say
    so. Then mask only if the face reads under 50.
  - **Crowded night streets, a lit canal** (signs, lamps and crowds everywhere): there is no ordinary
    surface at face height. Use the ground or a plain wall beside the person (pavement, brick) and
    name the surfaces.
  - **Sunlit scene where every ordinary surface reads above 130** (sunlit gravel or stone): use the 2
    ordinary surfaces closest to the range and say so.
  - **Daylight in deep shade where every ordinary surface reads under 50** (dark foliage, shaded
    rock): use the 2 brightest ordinary surfaces, say so, and decide with the daylight rows as usual.
    The night rule's "mask only under 50" doesn't apply in daylight.
  - Compare the face with the mean of the 2 boxes. **If one box reads more than 1.5 times the other**,
    add a third box (the next-nearest ordinary surface) and use the median of the three. In testing,
    dark foliage (69) beside light wood (119) decided a face's row on its own.
  - **One surface under 50 and one above 130** (a dark hedge beside sunlit pavement): that is the
    1.5 times case above, so add the third box and take the median. In a series, the
    near-identical-frames rule then decides for all frames.
  - **One box in range and one under 50** (at night): take the in-range box plus the next-brightest
    ordinary surface, and say so.
- **Strangers get no mask (speed and intent).** Only the user's own people are subjects (see
  lightcraft:cull, "Whose faces count": recognised names when face recognition is on and faces are
  named, else the day's people list by clothing). Don't
  measure or mask strangers, crowds, staff or performers. Report "no own people in frame: scene" and
  move on.
  - **A "suggested:" name in the people list can be wrong.** In the all-photos run, two photos
    listed as showing a family member held only strangers (a crowd at a gate, a girl with a deer). Go
    by what's in the frame.
- **Faces turned away or hidden:** when only the back of a head shows, or the face is fully hidden,
  that person has no face to measure. If no other main face is visible, no mask. When a hand or a
  cheek is visible, measure that skin instead and lift as usual: a hand over a face read 117 → 136
  at 0.40, and the user's review decides.
- **Measure with `M` only** (measure.py `mean`, `clip`, `batch`), never with a mean of your own: a
  plain PIL mean of the same box gave a different number, which can move a face across a row.
- **Several people:** decide on the **darkest main-subject face**, and one mask covers all of them.
  Run the cheek-to-cheek shadow test on **every** main-subject face: one shadowed face triggers the
  shadow fix for the shared mask (in hard sun, only one of three faces read under 0.5).
  - **Main subjects:** the person with the largest face, plus anyone whose face is at least half that
    width and who isn't standing behind someone else. A person in the back (behind a stroller, behind
    the main person) is not a main subject. In testing, a mother behind a stroller (face 66) would have
    decided the photo for a lift; the boy in front (127) gave no mask, and the user kept that.
  - Faces narrower than about 1.5 % of the frame width get no mask. Report them.
- **Near-identical frames** (a burst, or a run of shots from one spot): decide once, on the frame
  where the faces are clearest, and give every frame of the series the same decision and ladder start.
  In the all-photos run, 11 frames from one spot split between lift and no mask, because one
  background box on dark foliage flipped single frames across the 25 % line. When the frames of a
  series still disagree, **the majority decides**, and the clearest frame sets the ladder start.
- **Decide with the table in "When to lift".** The night 5 % is `lift.mask_if_darker_percent`; the daylight 25 % is fixed. Report the
  face and background numbers and the table row you used. Decide this from the numbers before making a
  mask, never by masking and then deleting. For example, an indoor portrait whose face was already
  brighter got no mask.

## Which mask path

First, check for SAM 3 (once per batch): `"$CLI" run --connect segment.model.status`.
- `available: true` and `installed: true` → use **Path A (SAM 3)**.
- Otherwise, or if Path A fails its coverage check twice on a photo → use **Path B (Auto Mask brush)**.
  Never start the model download yourself (`segment.model.download` needs the user's licence
  acceptance); the user installs it.

## Mask values

Both paths: `mask.adjust id=N 'values={...}'`
- **Daylight or night values and ladder:** pick them by the scene's light, and say which in the report.
  The look on the photo can disagree (an earlier run gave an overcast daytime close-up `look.night`).
  Take the look from `looks.py check` (`mkdir -p "$SP/dev"; "$CLI" run --connect develop.get id=ID >
  "$SP/dev/ID.json"; python -I "$LC_SCRIPTS/looks.py" check "$PREFS" "$SP/dev"`), and when it disagrees with the scene, use the scene's ladder
  and note "look is X, scene is Y" in the report and in the review card, so the user can fix the
  look.
  - `looks.py check` picks the cap by the look, not the scene. On such a photo it can FAIL a correct
    night-ladder mask as "above the daylight cap", or pass a daylight mask over the cap. Check that
    photo by hand against the scene's ladder, and leave the mask as it is when it fits; say so in the
    report.
- **Daylight:** `lift.mask.daylight` (default `{"exposure":0.45,"shadows":15,"temp":0}`). In testing,
  a warmth of +3 made subjects look too warm.
- **Night:** `lift.mask.night` (default `{"exposure":0.30,"shadows":15,"temp":0}`). This is the start
  value. Night scenes are already tungsten-warm, so start low and step up to the target.
- **Skin still reads warm** with temp 0: set mask `temp` to `lift.warm_skin_temp` (default -4). The
  change is subtle: face R−B drops by only about 1 point.
- **Black or navy clothing** turns grey under the mask (it rises more than 50 % **and** by more than
  about 15 points; a skirt going from 5 to 11 is +110 % but only 6 points, so ignore it): set mask `shadows`
  to 5. Measure it first; don't change it on the look of the clothes alone. The shadow fix keeps 15
  unless the clothing measures grey (two black-shirt people stayed fine at 15 in testing).
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
  "Global exposure boosts" in lightcraft:edit's Looks) and report the gap.
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

## Picking points (both paths)

Export `library.select 'ids=[ID]' app.export path="$SP/ID.jpg" longEdge=1500`, then run
`M grid "$SP/ID.jpg" -Region <around subject> -Out "$SP/ID-grid.png"`. Read the PNG and take the
coordinates from it: fractions of the full frame, as the grid labels show.
- **Read x and y from the tick labels, not by eye from the cell count:** `-Region` is `x0,x1,y0,y1`,
  and the grid labels are full-frame fractions. In testing, first readings of 3 face boxes were off.
  Check a face box with `M mean` before using its numbers.

## Path A: SAM 3 mask

**Long calls:** run `seg-wait.sh` and `seg-chain.sh` with the Bash tool's `run_in_background`, never
with `&` inside a command, and then wait with short polls. A tool call is moved to the background at
about 180 s whatever timeout you set, and a script started with `&` keeps running unseen: in testing a
worker thought the chain had died, started a second one and got two masks. Before starting a chain
again, check `masks` and the `.done` file. **Before starting `seg-chain.sh`, check that
`segment.model.status` shows `analyzing: false`**: a chain started while the app was still analyzing
the previous photo failed with TIMEOUT after 240 s, and the failure shows only in the `.done` file.
Timings seen: `seg-wait.sh` 55–240 s, and longer on the first load of a new photo (the default wait
is 600 s; in the all-photos run a 240 s wait timed out twice), one added prompt up to about 4 min, a
3-person chain about 8 min. In the all-photos run a chain took 3–9 min per photo, mostly the model
load. **Run no other LightCraft command while a chain runs**, not even an export of another photo:
every call starts with `library.select`, and a selection change mid-chain can put a mask step on
the wrong photo. Run the chains of a batch back to back, and measure before or after them.
`seg-chain.sh` runs `seg-wait.sh` itself, so skip step 1 below when you use the chain.

**Reading values:** `get_develop` returns about 376 KB once a prompt mask exists, too big for the tool
output. Read with the CLI and `lcjson.py`:
- `"$CLI" run --connect develop.get id=ID | python -I "$LC_SCRIPTS/lcjson.py" seg Subject` prints
  `MASKID PARTS READY` (READY = parts with `seg` data).
- `… | python -I "$LC_SCRIPTS/lcjson.py" masks` prints the mask count.
- For values, save it (`… develop.get id=ID > "$SP/dID.json"`) and read the file.

1. Load the model for the photo and wait until it is ready: `bash "$LC_SCRIPTS/seg-wait.sh" ID` in
   the background (runs `segment.prepare`, then polls `segment.model.status` until `loaded: true`,
   `busy: false` and `analyzing: false`; prints `ready after Ns`). Don't hand-poll the status: each
   poll costs a turn.
   Check that the new mask component has its `seg` data before the coverage check (prompt and
   clicked-point masks only, see `kind=subject` below).
2. Make the mask (the result's `activeMask` is N; if it says `pending`, read `develop.get` as above
   until the mask appears in `masks`):
   - **Preferred: describe each main person** (tested). Use 2–4 words: who they are plus their
     clothing colour, such as "man in red shirt", "girl in blue jacket" or "woman in black top". Make the first person's mask with
     `library.select 'ids=[ID]' mask.add kind=prompt 'text=man in red shirt' name=Subject`, then add each
     other person **to the same mask** with
     `library.select 'ids=[ID]' mask.addComponent id=N op=add kind=prompt 'text=girl in blue jacket'`.
     Both calls return `pending`. Poll `develop.get` until the new component has its `seg` data.
     **For two or more people use the helper**, as a `run_in_background` tool call, then short polls:
     ```bash
     bash "$LC_SCRIPTS/seg-chain.sh" "$SP" ID Subject "man with glasses" "boy in dark jacket"
     timeout 170 bash -c 'until [ -f "$0/seg-ID.done" ]; do sleep 5; done' "$SP"; cat "$SP/seg-ID.done"   # repeat until MASK=N …
     ```
     It loads SAM 3, adds each prompt to one mask and waits for each part's `seg` data. Then do the
     coverage check.
     - **A prompt that finds nothing stays `pending` for ever, with no error** (tested: "lamp post",
       "wall clock" on a frame with neither). A part with no `seg` data after about 5 min was not
       found: use a more specific prompt, or clicked points.
     - Allow 20–40 s for the first prompt, and up to about 4 min for each added one: the app also
       re-processes the earlier parts.
     - Never use a sentence-long prompt: one found nothing in 4½ min.
     - A generic prompt such as "man and woman" also takes every passer-by who matches. That's why each
       prompt names clothing.
     - Exclude points (`mask.objectPoint`) **don't work** on a prompt mask ("the mask has no Object
       selection"). Fix spill by deleting the mask and using a more specific prompt or clicked points.
   - **Dark silhouettes at night** (face under about 20): go straight to clicked points. A prompt
     such as "boy in gray jacket" found nothing on one and only gave up after about 7 minutes.
   - **Small faces in a crowd** (a portrait in front of a busy night scene, other people in similar
     clothes nearby): go straight to clicked points. In testing, "woman in white top" also took a
     girl in pink behind her, and clicked points were faster and cleaner on 4 portraits. At night,
     "man in black sweater" also took a passer-by in black far behind him; three clicked points with
     one exclude point on the passer-by gave a clean mask at once.
   - **Fallback: clicked points** read from a grid (see "Picking points"). Use it when a prompt finds
     nothing, catches the wrong people, or fails the coverage check twice:
     `mask.add kind=object 'points=[[x,y],[x,y]]' 'exclude=[[x,y]]' name=Subject`.
     Add or remove parts later with `mask.objectPoint id=N x=… y=…` (`exclude=true` to remove).
   - **For one person, prefer a prompt too** ("woman in white jacket"). `kind=subject`
     (`library.select 'ids=[ID]' mask.add kind=subject name=Subject`) is quicker but less reliable: on a
     backlit portrait it took the whole frame. Use it for one obvious animal, or when a prompt finds
     nothing.
     - **A `kind=subject` component never gets a `seg` key**, so a wait for `seg` data never ends (a
       tester waited 4 min). Wait about 20 s, until `segment.model.status` shows `busy: false`, then
       do the coverage check.
     - If the coverage check lights up the whole frame, run `mask.delete id=N` and make a prompt mask
       with the person's clothing colour. That counts as the first fix, not a Path B fallback.
   - Optional, for hair and fine edges: `mask.refineDetail id=N`. It runs in the background, so poll
     `segment.model.status` until `busy: false`.
3. **Coverage check:** first wait until the mask is ready, or an adjust made before that is lost
   (tested; `mask.add` can still be pending while the app is analyzing):
   - Prompt and clicked-point masks: until `lcjson.py seg Subject` shows READY equal to PARTS.
   - `kind=subject`: it never gets `seg` data; wait until `segment.model.status` shows `busy: false`.
   - Path B brush masks: no wait.

   Then, for every kind, set `mask.adjust id=N 'values={"exposure":3}'`, export and read it. The
   subject should be blown out and the background unchanged.
   - Where +3 is hard to read (it often only brightens the subject a little), use a colour overlay instead:
     `mask.adjust id=N 'values={"tint":100,"saturation":100,"exposure":1}'`. Everything masked turns
     magenta, or red-orange on warm tungsten frames (tested on a 2641 K carrousel frame): judge the
     coloured area's edge against the unmasked part, not the hue. Set the real values afterwards, the
     same as after +3.
   - Fix spill with `mask.objectPoint … exclude=true` (clicked-point masks only).
   - **Never leave the +3 value or the overlay.** The overlay sets `tint`, `saturation` and
     `exposure` together. After the check, set the real values, export again, and confirm them with
     `develop.get`: in the all-photos run an overlay check made after a mask was stepped stayed on two
     photos until `looks.py check` caught it.
   - If the mask is still wrong after two fixes, run `mask.delete id=N` and use Path B.
4. Set the mask values above, then measure.
5. In the report, say which path made the mask.
6. After an aborted step, check `masks` for a stray mask and delete it.

## Path B: Auto Mask brush (no SAM 3)

1. Get coordinates as in "Picking points".
2. Run `library.select 'ids=[ID]' mask.add kind=brush name=Subject`; the result's `activeMask` is N.
   Then add strokes with `mask.brushStroke id=N 'points=[[x,y],…]' size=0.02 autoMask=true`.
   - `size` is a fraction of the long edge, 0.02–0.03.
   - Cover the head, torso, arms and legs, keeping each stroke inside the subject.
3. **Coverage check:** as in Path A step 3, with no `seg` wait. Erase spill with
   `mask.brushStroke id=N … erase=true autoMask=true size=0.01`. If you abandon the mask, run
   `mask.delete id=N`.
4. Set the mask values above, then measure.
   - Before/after: export with `"amount":0`, then set `"amount":100` again and export. **Always end
     at amount 100.**
   - Check the edges with `M crops` at 100 %.

## Edge crops (both paths)

Centre each 100 % crop on the mask boundary against a mid or bright
background, with at least 30 % of the crop being background. Crops placed inside the subject showed no
halo in testing even when there was one.
- **Check at true 100 %, not on a 2000 px render,** for the strongest mask in each batch and for any
  mask with exposure above 0.6: export that photo at `longEdge=6000` (4000 while GPU rendering is on, see lightcraft:edit's Setup; one per call), and centre the
  crop where dark hair meets a dark background (foliage, shade). That edge is where halos show first.
  In testing, 2000 px edge crops passed five portraits whose halo the user saw on the review page.

## Report

For each photo: the mask path and its final values, any global exposure added and why, the face and
background boxes with their means, the lift %, and for a shadowed face the lit and shadow boxes with
the shadow / lit ratio before → after. Name the limit that stopped a ladder. Never claim a face is
brighter without a measurement. Called from lightcraft:edit, these lines go into its report and
`review.jsonl` `changes`.
