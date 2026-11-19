"""Check LightCraft looks against the preferences file.

Usage (from Bash, after lc-env.sh):
  # 1. Do the saved look presets still match the preferences? (start of every run)
  "$CLI" run --connect preset.export path="$SP/looks.lcpreset" group=lightcraft
  python -I "$LC_SCRIPTS/looks.py" presets "$PREFS" "$SP/looks.lcpreset"

  # 2. Check edited photos (end of a chunk): one develop.get dump per id, named ID.json
  for id in 501 502; do "$CLI" run --connect develop.get id=$id > "$SP/dev/$id.json"; done
  python -I "$LC_SCRIPTS/looks.py" check "$PREFS" "$SP/dev"

`presets` prints one line per look: OK, MISSING (no preset yet) or DIFF with the changed values,
plus the `preset.saveRecipe` recipe to re-save it. Exit 1 when anything is MISSING or DIFF.
LightCraft never updates a preset in place: saving a changed recipe under the same name makes a
second preset ("...-2"), so on a DIFF delete the old preset first (see the edit skill).

`check` prints one line per photo: which look it carries, exposure, denoise, and every mask, then
`BAD n`. A mask fails at exposure 2 or more, amount other than 100, a colour overlay left on, or no
values at all. The daylight cap (`lift.daylight_mask_max`, shadows 15) applies only to photos with the
daylight look; night and light-show photos use the night ladder (`lift.shadows_max`,
`lift.mask_limit`). Keys absent from develop.get (denoise_on when denoise is off) read as off.
"""
import json
import os
import re
import sys


def snake(s):
    return re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), s)


def load_prefs(path):
    """Return (looks, limits). looks: {name: {"section.key": value}} with slider ids converted to
    develop.get names (detail.nrLuminance -> detail.nr_luminance)."""
    text = open(path, encoding="utf-8-sig").read()
    looks, raw = {}, {}
    pat = re.compile(r"^- `(look\.[a-z_]+)`(.*?)\n\s*```json\n(.*?)```", re.S | re.M)
    for m in pat.finditer(text):
        name, head, body = m.group(1), m.group(2), m.group(3)
        try:
            vals = json.loads(body)
        except ValueError as e:
            sys.exit(f"preferences: {name}: bad JSON ({e})")
        base = None
        if "with these" in head:
            b = re.search(r"`(look\.[a-z_]+)` with these", head + m.group(0))
            base = b.group(1) if b else None
        raw[name] = (base, vals)
    for name, (base, vals) in raw.items():
        merged = {}
        if base:
            if base not in raw:
                sys.exit(f"preferences: {name} is based on {base}, which is missing")
            merged.update(raw[base][1])
        merged.update(vals)
        looks[name] = {".".join(snake(p) for p in k.split(".")): float(v) for k, v in merged.items()}

    def num(key, default):
        m = re.search(r"`" + re.escape(key) + r"`[^0-9\n]*([0-9]+(?:\.[0-9]+)?)", text)
        return float(m.group(1)) if m else default

    limits = {"daylight_mask_max": num("lift.daylight_mask_max", 0.65),
              "shadows_max": num("lift.shadows_max", 40), "mask_limit": num("lift.mask_limit", 1.6)}
    return looks, limits


def flat(settings, prefix=""):
    out = {}
    for k, v in settings.items():
        if isinstance(v, dict):
            out.update(flat(v, prefix + k + "."))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[prefix + k] = float(v)
    return out


def camel(key):
    sec, _, k = key.partition(".")
    return sec + "." + re.sub(r"_([a-z])", lambda m: m.group(1).upper(), k)


def cmd_presets(prefs, export):
    looks, _ = load_prefs(prefs)
    presets = json.load(open(export, encoding="utf-8-sig")).get("presets", [])
    by_name = {}
    for p in presets:
        by_name.setdefault(p.get("name", ""), []).append(p)
    bad = 0
    for name, want in looks.items():
        found = by_name.get("LC " + name, [])
        recipe = json.dumps([{"id": camel(k), "value": v} for k, v in want.items()])
        if not found:
            print(f"{name}: MISSING (save it: preset.saveRecipe name=\"LC {name}\" group=lightcraft 'recipe={recipe}')")
            bad += 1
            continue
        if len(found) > 1:
            print(f"{name}: {len(found)} presets named \"LC {name}\": {', '.join(p['id'] for p in found)}"
                  " (keep the one that matches, delete the rest)")
            bad += 1
        for p in found:
            have = flat(p.get("settings", {}))
            diffs = [f"{k} {have.get(k)} -> {v}" for k, v in want.items() if have.get(k) != v]
            diffs += [f"{k} {v} (not in preferences)" for k, v in have.items() if k not in want]
            if diffs:
                print(f"{name}: DIFF {p['id']}: " + "; ".join(diffs))
                print(f"  re-save: preset.delete id={p['id']}, then preset.saveRecipe name=\"LC {name}\""
                      f" group=lightcraft 'recipe={recipe}'")
                bad += 1
            else:
                print(f"{name}: OK {p['id']}")
    sys.exit(1 if bad else 0)


def which_look(dev, looks):
    """The look whose global values the photo matches best (per-photo fixes change a few keys)."""
    f = flat({k: dev.get(k, {}) for k in ("light", "effects", "color", "detail", "vignette")})
    best, score = None, -1
    for name, want in looks.items():
        s = sum(1 for k, v in want.items() if f.get(k) == v) / max(len(want), 1)
        if s > score:
            best, score = name, s
    return (best if score >= 0.5 else None), score


def cmd_check(prefs, d):
    looks, lim = load_prefs(prefs)
    files = sorted((f for f in os.listdir(d) if re.fullmatch(r"\d+\.json", f)), key=lambda f: int(f[:-5]))
    if not files:
        sys.exit(f"no ID.json files in {d}")
    bad = 0
    for fn in files:
        pid = fn[:-5]
        try:
            j = json.load(open(os.path.join(d, fn), encoding="utf-8-sig"))
            dev = j.get("result", j)
            if not isinstance(dev, dict) or "light" not in dev:
                raise ValueError(j.get("error", "no develop settings"))
        except Exception as e:
            print(pid, "NO DEVELOP", e)
            bad += 1
            continue
        look, _ = which_look(dev, looks)
        day = look == "look.daylight"
        light, enh = dev.get("light", {}), dev.get("enhance", {})
        dn = f"denoise {enh.get('denoise', 0):g}" if enh.get("denoise_on") else "denoise off"
        probs, desc = [], []
        for k, m in enumerate(dev.get("masks") or []):
            a = m.get("adjust", {})
            ex, sh, am = a.get("exposure", 0), a.get("shadows", 0), a.get("amount", 100)
            desc.append(f"{m.get('name', '?')}:e{ex:g}/s{sh:g}")
            if ex >= 2:
                probs.append(f"mask{k} exposure {ex:g}")
            if am != 100:
                probs.append(f"mask{k} amount {am:g}")
            if a.get("tint", 0) >= 50 or a.get("saturation", 0) >= 50:
                probs.append(f"mask{k} colour overlay left on")
            if not any(abs(v) > 0 for kk, v in a.items() if kk != "amount" and isinstance(v, (int, float))):
                probs.append(f"mask{k} has no values (stray)")
            if day and (ex > lim["daylight_mask_max"] or sh > 15):
                probs.append(f"mask{k} above the daylight cap (e{ex:g} s{sh:g}): check the report's reason")
            if not day and (ex > lim["mask_limit"] or sh > lim["shadows_max"]):
                probs.append(f"mask{k} above the night ladder (e{ex:g} s{sh:g})")
        if enh.get("denoise_on") and (dev.get("detail", {}).get("nr_luminance", 0) > 20):
            probs.append(f"denoise on with nr_luminance {dev['detail']['nr_luminance']:g} (double NR)")
        line = (f"{pid} {look or 'no look'} | exp {light.get('exposure', 0):g} blacks {light.get('blacks', 0):g}"
                f" hl {light.get('highlights', 0):g} | {dn} | masks {len(desc)} {' '.join(desc)}")
        print(line, "|", "OK" if not probs else "FAIL " + "; ".join(probs))
        bad += bool(probs)
    print("BAD", bad)


def main(a):
    if len(a) == 3 and a[0] == "presets":
        cmd_presets(a[1], a[2])
    elif len(a) == 3 and a[0] == "check":
        cmd_check(a[1], a[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
