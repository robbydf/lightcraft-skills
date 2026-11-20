"""Tests for the helper scripts: synthetic images and JSON in a temp folder, no LightCraft needed.

Run from the repo root (Pillow and numpy are needed for the image tests, which skip without them):
  python -E -m unittest discover -s tests -v        (python3 on macOS / Linux)
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

try:
    import numpy  # noqa: F401
    from PIL import Image, ImageDraw
    HAVE_IMG = True
except ImportError:
    HAVE_IMG = False


def run(script, *args, env=None):
    """Run a script with this interpreter (-E keeps --user site packages); returns (code, stdout+stderr)."""
    e = dict(os.environ, **(env or {}))
    r = subprocess.run([sys.executable, "-E", os.path.join(SCRIPTS, script), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8", env=e)
    return r.returncode, r.stdout + r.stderr


def catalog(path, photos):
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"ok": True, "result": {"photos": photos}}) + "\n")


class LcArgs(unittest.TestCase):
    def test_fix_argv(self):
        from lcargs import fix_argv
        out = fix_argv(["a.jpg", "-region", "0,1,0,1", "-ANGLES", "-6,-4", "-force"],
                       ["-Region", "-Angles"], ["-Force"])
        self.assertEqual(out, ["a.jpg", "-Region=0,1,0,1", "-Angles=-6,-4", "-Force"])


class RunState(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.run = os.path.join(self.t, "run")
        day = "2026-01-01T10:00:0"
        self.p0 = os.path.join(self.t, "p0.json")
        catalog(self.p0, [{"id": 1, "captured": day + "0"}, {"id": 2, "captured": day + "0"},
                          {"id": 3, "captured": day + "1"}, {"id": 4, "rating": 2, "captured": day + "5"}])
        self.assertEqual(run("runstate.py", "init", self.run, self.p0)[0], 0)

    def log(self, e):
        return run("runstate.py", "log", self.run, json.dumps(e))

    def amend(self, e):
        return run("runstate.py", "amend", self.run, json.dumps(e))

    def test_log_amend_check_summary_rollback(self):
        self.assertEqual(self.log({"group": 1, "ids": [1, 2, 3], "picks": [1], "rejects": [3], "unsure": [2]})[0], 0)
        self.assertNotEqual(self.log({"group": 1, "ids": [1, 2, 3], "picks": [], "rejects": []})[0], 0)
        code, out = self.amend({"ids": [1, 2], "picks": [2], "unpick": [1], "reason": {"2": "panel 3-0 keep"}})
        self.assertEqual(code, 0, out)
        for bad in ({"ids": [3], "picks": [3]},          # rejected
                    {"ids": [4], "picks": [4]},          # not logged / protected
                    {"ids": [2], "picks": [2]},          # already a pick
                    {"ids": [1], "unpick": [1]},         # not a pick any more
                    {"ids": [2], "unpick": [1]}):        # unpick not in ids
            self.assertNotEqual(self.amend(bad)[0], 0, bad)
        now = os.path.join(self.t, "now.json")
        catalog(now, [{"id": 1}, {"id": 2, "rating": 3}, {"id": 3, "flag": "reject"}, {"id": 4, "rating": 2}])
        code, out = run("runstate.py", "check", self.run, now)
        self.assertEqual(code, 0, out)
        code, out = run("runstate.py", "summary", self.run)
        self.assertIn('"picks": 1', out)
        self.assertIn('"unsure": 0', out)
        self.assertNotIn("UNSURE", out)
        self.assertIn("AMEND", out)
        code, out = run("runstate.py", "rollback", self.run)
        self.assertIn("'ids=[2]'", out)
        code, out = run("runstate.py", "picks", self.run)
        self.assertEqual(out.split()[1], "2")

    def test_marks(self):
        same = run("runstate.py", "marks", self.p0, self.p0, "--ids", "1,2")
        self.assertEqual(same[0], 0, same[1])
        now = os.path.join(self.t, "now.json")
        catalog(now, [{"id": 1, "rating": 3}, {"id": 2}, {"id": 3}, {"id": 4, "rating": 2}])
        self.assertEqual(run("runstate.py", "marks", self.p0, now)[0], 1)
        self.assertEqual(run("runstate.py", "marks", self.p0, now, "--ids", "2,3")[0], 0)
        self.assertEqual(run("runstate.py", "marks", self.p0, now, "--ids", "99")[0], 1)  # unknown id
        code, out = run("runstate.py", "marks", self.p0, now, "--ids")
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", out)

    def test_marks_ids_spaces_and_ranges(self):
        now = os.path.join(self.t, "now2.json")
        catalog(now, [{"id": 1}, {"id": 2}, {"id": 3, "rating": 3}, {"id": 4, "rating": 2}])
        # 3 changed: space-separated ids must all be checked (before 0.1.13 only the first was)
        code, out = run("runstate.py", "marks", self.p0, now, "--ids", "1", "3")
        self.assertEqual(code, 1, out)
        self.assertIn("compared 2 photos", out)
        self.assertEqual(run("runstate.py", "marks", self.p0, now, "--ids", "1-3")[0], 1)
        self.assertEqual(run("runstate.py", "marks", self.p0, now, "--ids", "1 2")[0], 0)
        code, out = run("runstate.py", "marks", self.p0, now, "--ids", "1,x")
        self.assertNotEqual(code, 0)
        self.assertNotIn("Traceback", out)

    def test_bad_input_no_traceback(self):
        for args in (("log", self.run), ("log", self.run, '{"group":1,"ids":[],"picks":[],"rejects":[]}')):
            code, out = run("runstate.py", *args)
            self.assertNotEqual(code, 0)
            self.assertNotIn("Traceback", out)


class Bursts(unittest.TestCase):
    def test_log_with_amend_lines(self):
        t = tempfile.mkdtemp()
        photos = os.path.join(t, "p.json")
        catalog(photos, [{"id": 1, "fileName": "A.jpg", "captured": "2026-01-01T10:00:00"},
                         {"id": 2, "fileName": "B.jpg", "captured": "2026-01-01T10:00:00.5"},
                         {"id": 5, "fileName": "C.jpg", "captured": "2026-01-01T11:00:00"}])
        log = os.path.join(t, "log.jsonl")
        with open(log, "w", encoding="utf-8") as f:
            f.write('{"group":1,"ids":[1,2],"picks":[1],"rejects":[]}\n')
            f.write('{"amend":true,"ids":[2],"picks":[2],"unpick":[]}\n')
        code, out = run("bursts.py", photos, "--log", log)
        self.assertEqual(code, 0, out)
        self.assertIn("5=C", out)
        self.assertNotIn("1=A", out)


class EditLog(unittest.TestCase):
    def test_init_start_done_check(self):
        run_dir = os.path.join(tempfile.mkdtemp(), "lib")
        self.assertNotEqual(run("editlog.py", run_dir, "start", 1, "null", 0, "r1")[0], 0)
        self.assertNotEqual(run("editlog.py", "relative/x", "init")[0], 0)
        self.assertEqual(run("editlog.py", run_dir, "init")[0], 0)
        self.assertEqual(run("editlog.py", run_dir, "start", 1, "null", 0, "r1")[0], 0)
        self.assertEqual(run("editlog.py", run_dir, "done", 1, "r1", "look=night", "denoise=50")[0], 0)
        code, out = run("editlog.py", run_dir, "start", "x", "null", 0, "r1")
        self.assertNotEqual(code, 0)
        self.assertNotIn("Traceback", out)
        with open(os.path.join(run_dir, "edits.jsonl"), encoding="utf-8") as f:
            lines = [json.loads(l) for l in f]
        self.assertEqual(lines[1], {"id": 1, "done": True, "round": "r1", "look": "night", "denoise": 50})
        with open(os.path.join(run_dir, "edits.jsonl"), "a", encoding="utf-8") as f:
            f.write("{'id': None}\nnot json\n")
        self.assertEqual(run("editlog.py", run_dir, "check")[0], 1)
        self.assertEqual(run("editlog.py", run_dir, "check", "--fix")[0], 1)  # one line is not repairable


class EditLogDoneIds(unittest.TestCase):
    def test_done_ids(self):
        run_dir = os.path.join(tempfile.mkdtemp(), "lib")
        run("editlog.py", run_dir, "init")
        for i in (1, 2):
            run("editlog.py", run_dir, "start", i, "null", 0, "r1")
        run("editlog.py", run_dir, "done", 1, "r1")
        run("editlog.py", run_dir, "done", 2, "r2")
        code, out = run("editlog.py", run_dir, "done-ids", "r1", "--ids", "1", "2,3")
        self.assertEqual(code, 0, out)
        self.assertIn("done: 1", out)
        self.assertIn("todo: 2,3", out)


class LcJson(unittest.TestCase):
    def pipe(self, what, text, *extra):
        r = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "lcjson.py"), what, *extra],
                           input=text, capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr).strip()

    def test_cursor_blank_line_and_select(self):
        sel = json.dumps({"command": "library.select", "ok": True, "result": {"selected": 1}})
        hist = json.dumps({"command": "history.list", "ok": True, "result": {"cursor": 7, "history": []}})
        self.assertEqual(self.pipe("cursor", "\n" + sel + "\n" + hist + "\n"), (0, "7"))
        null = json.dumps({"command": "history.list", "ok": True, "result": {"cursor": None}})
        self.assertEqual(self.pipe("cursor", null), (0, "null"))
        code, out = self.pipe("cursor", "")
        self.assertEqual(code, 1)
        bad = json.dumps({"command": "history.list", "ok": False, "error": "no photo"})
        self.assertIn("no photo", self.pipe("cursor", bad)[1])

    def test_crop_masks_seg(self):
        r = {"crop": {"geometry": {"angle": 2.0, "rect": {"x0": 0.025, "x1": 0.975, "y0": 0.02, "y1": 0.98}}},
             "geometry": {"constrain_crop": False, "upright": "off"},
             "masks": [{"id": 3, "name": "Subject", "components": [{"shape": {"seg": "x"}}, {"shape": {}}]}]}
        dev = json.dumps({"command": "develop.get", "ok": True, "result": r})
        code, out = self.pipe("crop", dev)
        self.assertEqual(code, 0, out)
        self.assertIn("angle=2.0 crop_per_edge=2.5%", out)
        self.assertIn("constrain_crop=false", out)
        self.assertEqual(self.pipe("masks", dev), (0, "1"))
        self.assertEqual(self.pipe("seg", dev, "Subject"), (0, "3 2 1"))
        self.assertEqual(self.pipe("seg", dev, "Other"), (0, "none 0 0"))


class FindLightCraft(unittest.TestCase):
    def test_env_dir(self):
        from find_lightcraft import CLI_NAME
        d = tempfile.mkdtemp()
        open(os.path.join(d, CLI_NAME), "w").close()
        home = tempfile.mkdtemp()
        code, out = run("find_lightcraft.py", env={"LIGHTCRAFT_DIR": d, "LIGHTCRAFT_HOME": home})
        self.assertEqual(code, 0, out)
        self.assertEqual(os.path.normcase(out.strip()), os.path.normcase(d))
        code, out = run("find_lightcraft.py", "--dir", d, env={"LIGHTCRAFT_HOME": home})
        self.assertEqual(os.path.normcase(out.strip()), os.path.normcase(d))


class FindLightCraftHelp(unittest.TestCase):
    def test_help_and_usage(self):
        code, out = run("find_lightcraft.py", "--help")
        self.assertEqual(code, 0)
        self.assertIn("Usage", out)
        self.assertEqual(run("find_lightcraft.py", "--bogus")[0], 2)


class ReviewPage(unittest.TestCase):
    def test_other_drive_falls_back_to_file_url(self):
        import importlib
        from unittest import mock
        review = importlib.import_module("review")
        t = tempfile.mkdtemp()
        d = os.path.join(t, "chunk")
        os.makedirs(d)
        for n in ("5-before.jpg", "5-after.jpg"):
            open(os.path.join(d, n), "wb").close()
        with open(os.path.join(d, "review.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"id": 5, "title": "x"}) + "\n")
        out = os.path.join(t, "page.html")

        def boom(*a, **k):
            raise ValueError("path is on mount 'D:', start on mount 'C:'")
        with mock.patch.object(review.os.path, "relpath", boom), mock.patch.object(sys, "argv", ["review.py", out, d]):
            with self.assertRaises(SystemExit) as e:
                review.main()
            self.assertIn(e.exception.code, (0, None))
        with open(out, encoding="utf-8") as f:
            self.assertIn("file:", f.read())


@unittest.skipUnless(HAVE_IMG, "needs Pillow and numpy")
class ImageHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = tempfile.mkdtemp()
        im = Image.new("RGB", (800, 600), (90, 90, 90))
        d = ImageDraw.Draw(im)
        d.line([(400, 0), (420, 600)], fill=(255, 255, 255), width=4)  # leans ~1.9 deg
        d.rectangle([0, 0, 99, 99], fill=(255, 255, 255))
        cls.a = os.path.join(cls.t, "a [1].jpg")  # brackets: a real file, not a glob
        im.save(cls.a, quality=95)
        cls.b = os.path.join(cls.t, "b.jpg")
        im.save(cls.b, quality=95)

    def test_measure_modes(self):
        for args in (("sharp", self.a, "-Region", "0,1,0,1"), ("tilt", self.a),
                     ("mean", self.a, "-Region", "0.5,1,0.5,1"), ("clip", self.a, "-Region", "0,1,0,1")):
            code, out = run("measure.py", *args)
            self.assertEqual(code, 0, out)
        code, out = run("measure.py", "mean", self.a, "-Region", "0.6,0.7,0.6,0.7")
        self.assertIn("mean=90", out)
        code, out = run("measure.py", "clip", self.a, "-Region", "0,0.125,0,0.1667")
        self.assertRegex(out, r"blown=(9\d|100)\.")
        for mode, n in (("crops", 1), ("grid", 1), ("sheet", 2)):
            out_png = os.path.join(self.t, f"{mode}.png")
            files = [self.a, self.b][:n]
            code, out = run("measure.py", mode, *files, "-Region", "0,1,0,1", "-Out", out_png) if mode != "sheet" \
                else run("measure.py", mode, *files, "-Out", out_png)
            self.assertEqual(code, 0, out)
            self.assertTrue(os.path.isfile(out_png))

    def test_batch_list(self):
        lst = os.path.join(self.t, "list.txt")
        with open(lst, "w", encoding="utf-8") as f:
            f.write(f"{os.path.basename(self.a)}|0.6,0.7,0.6,0.7|rel\n{self.b}|0,1,0,1|abs\nnope.jpg|0,1,0,1\n")
        code, out = run("measure.py", "batch", lst)
        self.assertIn("rel  mean=90", out)
        self.assertIn("abs  mean=", out)
        self.assertIn("missing file", out)

    def test_native_path(self):
        from lcimg import native_path
        if os.name == "nt":
            self.assertEqual(native_path("/c/Users/x"), "C:/Users/x")
        else:
            self.assertEqual(native_path("/c/Users/x"), "/c/Users/x")

    def test_lfit_rgb(self):
        code, out = run("lfit.py", self.a, 0.502, 0.02, 0.527, 0.98)  # guide along the drawn line
        self.assertEqual(code, 0, out)
        slope = float(out.split("slope_deg=")[1].split()[0])
        self.assertAlmostEqual(abs(slope), 1.9, delta=0.3)
        code, out = run("rgb.py", self.a, "0.6,0.7,0.6,0.7")
        self.assertEqual(code, 0, out)

    def test_sbs_tiltprev(self):
        o = os.path.join(self.t, "s.jpg")
        code, out = run("sbs.py", "-Before", self.a, "-After", self.b, "-Region", "0,1,0,1", "-Out", o)
        self.assertEqual(code, 0, out)
        with Image.open(o) as im:
            self.assertLessEqual(im.size[0], 1600)
        o = os.path.join(self.t, "t.jpg")
        code, out = run("tiltprev.py", "-In", self.a, "-Out", o, "-Angles", "-2,0,2", "-W", "300")
        self.assertEqual(code, 0, out)
        with Image.open(o) as im:
            self.assertEqual(im.size[0], 300)

    def test_corners(self):
        import numpy as np
        h, w = 400, 600
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / np.sqrt(2)
        vig = (150 * (1 - 0.6 * r ** 2)).astype("uint8")
        fs = []
        for n, arr in (("v", vig), ("f", np.full((h, w), 150, "uint8"))):
            for k in range(3):
                p = os.path.join(self.t, f"c{n}{k}.png")
                Image.fromarray(np.stack([arr] * 3, -1)).save(p)
                fs.append(p)
        code, out = run("measure.py", "corners", *fs[:3])
        self.assertEqual(code, 0, out)
        self.assertIn("MEDIAN of 3", out)
        self.assertIn("lens_darkening=likely", out.splitlines()[-1])
        code, out = run("measure.py", "corners", *fs[3:])
        self.assertIn("lens_darkening=no", out.splitlines()[-1])

    def test_isolated_hint(self):
        r = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, r'%s'); import lcimg" % SCRIPTS],
                           capture_output=True, text=True)
        if r.returncode:  # numpy/Pillow only in user site: the hint must name the cause
            self.assertIn("-I", r.stderr + r.stdout)


if __name__ == "__main__":
    unittest.main()
