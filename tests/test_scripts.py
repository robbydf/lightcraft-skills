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


def load_mcp_script():
    import importlib.util
    spec = importlib.util.spec_from_file_location("lightcraft_mcp", os.path.join(SCRIPTS, "lightcraft-mcp.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class FakeClaude:
    """`claude mcp get/add/remove` over an in-memory {scope: (command, args)}."""

    def __init__(self, entries):
        self.entries = dict(entries)
        self.calls = []

    def __call__(self, args, timeout=60, **kw):
        self.calls.append(args[1:])
        verb = args[2]
        if verb == "get":
            for scope in ("local", "project", "user"):
                if scope in self.entries:
                    c, a = self.entries[scope]
                    out = f"lightcraft:\n  Scope: {scope.title()} config\n  Command: {c}\n  Args: {a}\n"
                    return subprocess.CompletedProcess(args, 0, out.encode(), b"")
            return subprocess.CompletedProcess(args, 1, b"", b"No MCP server")
        if verb == "add":
            scope = args[args.index("-s") + 1]
            rest = args[args.index("--") + 1:]
            self.entries[scope] = (rest[0], " ".join(rest[1:]))
            return subprocess.CompletedProcess(args, 0, b"", b"")
        if verb == "remove":
            scope = args[args.index("-s") + 1]
            return subprocess.CompletedProcess(args, 0 if self.entries.pop(scope, None) else 1, b"", b"")
        raise AssertionError(args)


class McpRegistration(unittest.TestCase):
    CLI = os.path.abspath("lc/lightcraft-cli.exe")
    ADDR = "127.0.0.1:7980"
    RIGHT = (CLI, "mcp --connect 127.0.0.1:7980")

    def go(self, entries, scope="user"):
        from types import SimpleNamespace
        from unittest import mock
        m = load_mcp_script()
        fake = FakeClaude(entries)
        with mock.patch.object(m, "run", fake), mock.patch.object(m, "say"):
            rc = m.register(SimpleNamespace(Scope=scope), "claude", self.CLI, self.ADDR)
        return rc, fake

    def test_default_scope_is_user(self):
        m = load_mcp_script()
        from unittest import mock
        with mock.patch.object(m, "find", return_value=""), mock.patch.object(m, "say"):
            self.assertEqual(m.main(["start", "-LightCraftDir", "nowhere"]), 9)
        with open(os.path.join(SCRIPTS, "lightcraft-mcp.py"), encoding="utf-8") as f:
            line = [l for l in f if '"-Scope"' in l and "add_argument" in l][0]
        self.assertIn('default="user"', line)

    def test_new_user_registration(self):
        rc, fake = self.go({})
        self.assertEqual((rc, fake.entries), (0, {"user": self.RIGHT}))

    def test_right_user_entry_is_kept(self):
        rc, fake = self.go({"user": self.RIGHT})
        self.assertEqual(rc, 0)
        self.assertFalse([c for c in fake.calls if c[1] in ("add", "remove")])

    def test_local_entry_moves_up_to_user(self):
        rc, fake = self.go({"local": self.RIGHT})
        self.assertEqual((rc, fake.entries), (0, {"user": self.RIGHT}))

    def test_local_entry_over_right_user_one_is_removed(self):
        rc, fake = self.go({"local": ("old.exe", "mcp --connect 127.0.0.1:1"), "user": self.RIGHT})
        self.assertEqual((rc, fake.entries), (0, {"user": self.RIGHT}))

    def test_stale_user_entry_is_replaced(self):
        rc, fake = self.go({"user": (self.CLI, "mcp --connect 127.0.0.1:1")})
        self.assertEqual((rc, fake.entries), (0, {"user": self.RIGHT}))

    def test_wrong_project_entry_is_left_to_the_user(self):
        rc, fake = self.go({"project": ("x.exe", "mcp")})
        self.assertEqual((rc, fake.entries), (6, {"project": ("x.exe", "mcp")}))

    def test_local_scope_still_works(self):
        rc, fake = self.go({"user": ("old.exe", "mcp")}, scope="local")
        self.assertEqual((rc, fake.entries), (0, {"user": ("old.exe", "mcp"), "local": self.RIGHT}))


class McpStop(unittest.TestCase):
    def go(self, disconnect):
        from types import SimpleNamespace
        from unittest import mock
        m = load_mcp_script()
        fake = FakeClaude({"user": ("cli.exe", "mcp --connect 127.0.0.1:7980")})
        killed = []
        with mock.patch.object(m, "run", fake), mock.patch.object(m, "say"), \
                mock.patch.object(m, "claude_cmd", return_value="claude"), \
                mock.patch.object(m, "bridge_pids", return_value=[11, 12]), \
                mock.patch.object(m, "kill", killed.append), \
                mock.patch.object(m, "gui_pids", return_value=[]):
            rc = m.stop(SimpleNamespace(Disconnect=disconnect, Force=False, TimeoutSec=1))
        return rc, fake, killed

    def test_plain_stop_keeps_registration_and_bridges(self):
        rc, fake, killed = self.go(False)
        self.assertEqual((rc, killed), (0, []))
        self.assertIn("user", fake.entries)

    def test_disconnect_removes_both(self):
        rc, fake, killed = self.go(True)
        self.assertEqual((rc, killed, fake.entries), (0, [11, 12], {}))


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
        # a reversed range must not turn into an empty filter (which would check every photo)
        code, out = run("runstate.py", "marks", self.p0, now, "--ids", "3-1")
        self.assertNotEqual(code, 0)
        self.assertIn("bad range", out)

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


class BurstTimes(unittest.TestCase):
    def test_parse_time_old_python_forms(self):
        from bursts import parse_time
        self.assertEqual(parse_time("2026-01-01T10:00:00.5").microsecond, 500000)
        self.assertEqual(parse_time("2026-01-01T10:00:00Z").hour, 10)
        self.assertEqual(parse_time("2026-01-01T10:00:00.123456789+09:00").microsecond, 123456)
        self.assertLess(parse_time("2026-01-01T10:00:00Z"), parse_time("2026-01-01T10:00:01"))


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
        code, out = run("editlog.py", run_dir, "done-ids", "r1", "--ids", "1-4")
        self.assertIn("todo: 2,3,4", out)
        for bad in ("x", "4-2"):
            code, out = run("editlog.py", run_dir, "done-ids", "r1", "--ids", bad)
            self.assertNotEqual(code, 0)
            self.assertNotIn("Traceback", out)
            self.assertNotIn("done:", out)
        code, out = run("editlog.py", os.path.join(tempfile.mkdtemp(), "none"), "done-ids", "r1")
        self.assertNotEqual(code, 0)
        self.assertIn("not a run folder", out)


def git_bash():
    """A POSIX bash, never Windows' WSL launcher (System32\bash.exe), or None."""
    import shutil
    for b in (os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Git", "bin", "bash.exe"), shutil.which("bash")):
        if b and os.path.exists(b) and "system32" not in b.lower():
            return b
    return None


@unittest.skipUnless(git_bash(), "no bash")
class DenoiseWaitIds(unittest.TestCase):
    def ids(self, *args):
        sp = tempfile.mkdtemp()
        subprocess.run([git_bash(), os.path.join(SCRIPTS, "denoise-wait.sh"), sp, *args],
                       env=dict(os.environ, DENOISE_WAIT_PARSE_ONLY="1"), capture_output=True, timeout=60)
        with open(os.path.join(sp, "denoise.done"), encoding="utf-8") as f:
            return f.read().strip()

    def test_lists_and_ranges(self):
        self.assertEqual(self.ids("--ids", "1", "2,3", "--max", "5"), "ids=1,2,3")
        self.assertEqual(self.ids("--ids", "501-503", "9"), "ids=501,502,503,9")
        for bad in ("x", "5-1", "1-2-3", "-4", "*", "12345678901"):
            self.assertIn("denoise-wait: --ids", self.ids("--ids", bad), bad)


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

    def test_utf8_last_line_and_null_rect(self):
        # UTF-8 from the CLI must not be read as the ANSI code page (python -I ignores PYTHONUTF8)
        r = {"masks": [{"id": 4, "name": "光 Subject é", "components": [{"shape": {"seg": "x"}}]}],
             "crop": {"geometry": {"angle": 0, "rect": {"x0": None, "x1": None, "y0": 0.1, "y1": 0.9}}}}
        dev = json.dumps({"command": "develop.get", "ok": True, "result": r}, ensure_ascii=False).encode("utf-8")
        p = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "lcjson.py"), "masks"],
                           input=dev, capture_output=True)
        self.assertEqual((p.returncode, p.stdout.strip()), (0, b"1"), p.stderr)
        code, out = self.pipe("crop", json.dumps({"command": "develop.get", "ok": True, "result": r}))
        self.assertEqual(code, 0, out)
        self.assertIn("crop_per_edge=10.0%", out)
        # an earlier failed line for the same command doesn't hide a later good one
        bad = json.dumps({"command": "history.list", "ok": False, "error": "busy"})
        good = json.dumps({"command": "history.list", "ok": True, "result": {"cursor": 2}})
        self.assertEqual(self.pipe("cursor", bad + "\n" + good), (0, "2"))


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


class ExportPicks(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.cat = os.path.join(self.t, "cat.json")
        d = "2026-11-0"
        catalog(self.cat, [
            {"id": 1, "rating": 3, "captured": d + "1T10:00:00", "edited": True, "fileName": "A1.ARW",
             "kind": "raw"},
            {"id": 12, "rating": 3, "captured": d + "1T10:00:00", "kind": "video"},         # video
            {"id": 2, "rating": 2, "captured": d + "1T10:00:00", "edited": True},           # rating low
            {"id": 3, "rating": 4, "captured": d + "1T10:00:00", "deleted": True},          # deleted
            {"id": 4, "rating": 3, "captured": d + "1T10:00:00", "flag": "reject"},         # rejected
            {"id": 5, "rating": 3, "captured": d + "2T10:00:00", "edited": False},          # own, not edited
            {"id": 6, "rating": 3, "captured": d + "2T10:00:00", "copyOf": 1, "edited": True},  # copy: 1's faces
            {"id": 7, "rating": 5, "captured": d + "2T10:00:00"},                           # other person only
            {"id": 8, "rating": 3, "captured": d + "3T10:00:00"},                           # suggested own
            {"id": 9, "rating": 3, "captured": d + "1T10:00:00"},                           # unnamed only
            {"id": 10, "rating": 3, "captured": d + "3T10:00:00"},                          # no faces
            {"id": 11, "rating": 3, "captured": d + "9T10:00:00", "edited": True},          # out of range
        ])
        self.map = os.path.join(self.t, "people.json")
        with open(self.map, "w", encoding="utf-8") as f:
            json.dump({"1": {"0": "sarah"}, "5": {"0": "Enzo", "1": "unnamed"}, "7": {"0": "Kenji"},
                       "8": {"0": "suggested:Robby"}, "9": {"0": "unnamed"}, "11": {"0": "Sarah"},
                       "3": {"0": "Sarah"}, "4": {"0": "Sarah"}, "2": {"0": "Sarah"}, "12": {"0": "Sarah"}}, f)

    def pick(self, *extra):
        out = os.path.join(self.t, "out.json")
        code, msg = run("export_picks.py", self.cat, self.map, "--people", "Sarah,Enzo,Robby",
                        "--from", "2026-11-01", "--to", "2026-11-05", "--out", out, *extra)
        self.assertEqual(code, 0, msg)
        with open(out, encoding="utf-8") as f:
            return json.load(f)

    def test_selection(self):
        r = self.pick()
        self.assertEqual(r["export"], ["1", "5", "6"])
        self.assertEqual(r["not_edited"], ["5"])
        self.assertEqual(r["others_only"], ["7"])
        self.assertEqual(r["no_faces"], ["10"])
        self.assertEqual([x["id"] for x in r["review"]], ["8", "9"])  # suggested first
        self.assertEqual(r["review"][0]["why"], "suggested:Robby")
        self.assertEqual(r["names"]["1"], "A1.ARW")

    def test_decisions_manifest_force_changed(self):
        dec = os.path.join(self.t, "dec.json")
        with open(dec, "w") as f:
            json.dump({"include": [8], "exclude": [6]}, f)
        man = os.path.join(self.t, "man.jsonl")
        with open(man, "w") as f:
            f.write(json.dumps({"id": 1, "state": "pending"}) + "\n")
            f.write(json.dumps({"id": 1, "state": "done", "hist": "aaa"}) + "\n")
            f.write(json.dumps({"id": 5, "state": "abandoned"}) + "\n")
        sigs = os.path.join(self.t, "sigs.json")
        with open(sigs, "w") as f:
            json.dump({"1": "bbb"}, f)
        r = self.pick("--decisions", dec, "--manifest", man, "--hist-sigs", sigs)
        self.assertEqual(r["export"], ["5", "8"])
        self.assertEqual(r["already_exported"], ["1"])
        self.assertEqual(r["changed"], ["1"])
        with open(man, "a") as f:   # what `export_stage.py force` writes
            f.write(json.dumps({"id": 1, "state": "forced"}) + "\n")
        r = self.pick("--decisions", dec, "--manifest", man)
        self.assertEqual(r["export"], ["1", "5", "8"])

    def test_empty_or_missing_map(self):
        with open(self.map, "w") as f:
            f.write("{}")
        code, out = run("export_picks.py", self.cat, self.map, "--people", "Sarah")
        self.assertNotEqual(code, 0)
        self.assertIn("recognition", out)
        self.assertNotIn("Traceback", out)
        code, out = run("export_picks.py", self.cat, os.path.join(self.t, "nope.json"), "--people", "Sarah")
        self.assertNotEqual(code, 0)
        self.assertIn("not found", out)


class ExportStage(unittest.TestCase):
    JPEG = b"\xff\xd8\xff\xe0" + b"x" * 100

    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.root = os.path.join(self.t, "root")
        self.dest = os.path.join(self.root, "trip")
        self.stg = os.path.join(self.t, ".lc-staging")
        self.raw = os.path.join(self.t, "raw")
        self.man = os.path.join(self.t, "run", "export-gp.jsonl")
        for d in (self.dest, self.raw):
            os.makedirs(d)
        self.picks = os.path.join(self.t, "picks.json")

    def export(self, ids, names, size=(3266, 4899)):
        """A fake app.export result: one raw file per id, named as conflict=unique would."""
        with open(self.picks, "w") as f:
            json.dump({"names": {str(i): n for i, n in zip(ids, names)}}, f)
        out, seen = [], {}
        for i, n in zip(ids, names):
            stem = os.path.splitext(n)[0]
            seen[stem] = seen.get(stem, 0) + 1
            p = os.path.join(self.raw, stem + ("" if seen[stem] == 1 else "-%d" % (seen[stem] - 1)) + ".jpg")
            with open(p, "wb") as f:
                f.write(self.JPEG + str(i).encode())
            out.append({"path": p, "width": size[0], "height": size[1]})
        res = os.path.join(self.t, "result.json")
        with open(res, "w") as f:
            f.write(json.dumps({"ok": True, "result": {"files": out}}) + "\n")
        return res

    def stage(self, res, ids, *extra):
        return run("export_stage.py", "stage", "--result", res, "--dest", self.dest, "--staging", self.stg,
                   "--manifest", self.man, "--picks", self.picks, "--ids", ids, "--max-mp", "16", *extra)

    def lines(self):
        with open(self.man) as f:
            return [json.loads(x) for x in f if x.strip()]

    def test_names_collisions_never_overwrite(self):
        with open(os.path.join(self.dest, "C.jpg"), "wb") as f:
            f.write(b"old")
        res = self.export([1, 2, 3], ["A.ARW", "A.ARW", "C.ARW"])
        code, out = self.stage(res, "1,2,3")
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(os.listdir(self.dest)), ["A-1.jpg", "A-2.jpg", "C-3.jpg", "C.jpg"])
        with open(os.path.join(self.dest, "C.jpg"), "rb") as f:
            self.assertEqual(f.read(), b"old")
        self.assertEqual([e["state"] for e in self.lines()].count("done"), 3)
        self.assertEqual(os.listdir(self.stg), [])
        # next batch: B.jpg is free; A-1.jpg is taken, so photo 4 named A-1 becomes A-1-4
        res = self.export([4, 5], ["A-1.ARW", "B.ARW"])
        code, out = self.stage(res, "4,5")
        self.assertEqual(code, 0, out)
        self.assertIn("A-1-4.jpg", os.listdir(self.dest))
        self.assertIn("B.jpg", os.listdir(self.dest))
        # todo skips done ids; staging a done id again is refused
        code, out = run("export_stage.py", "todo", "--manifest", self.man, "--ids", "1-6")
        self.assertEqual(out.split(), ["6"])
        res = self.export([5], ["B.ARW"])
        code, out = self.stage(res, "5")
        self.assertEqual(code, 2, out)
        self.assertIn("already exported", out)
        # force: 5 is exported again under its own name, B.jpg stays
        code, out = run("export_stage.py", "force", "--manifest", self.man, "--ids", "5,9")
        self.assertEqual(code, 0, out)
        self.assertIn("9: not exported yet", out)
        res = self.export([5], ["B.ARW"])
        code, out = self.stage(res, "5")
        self.assertEqual(code, 0, out)
        self.assertIn("B-5.jpg", os.listdir(self.dest))
        self.assertIn("B.jpg", os.listdir(self.dest))

    def test_count_and_size_mismatch_move_nothing(self):
        res = self.export([1, 2], ["A.ARW", "B.ARW"])
        code, out = self.stage(res, "1,2,3")
        self.assertEqual(code, 2, out)
        self.assertEqual(os.listdir(self.dest), [])
        res = self.export([1], ["A.ARW"], size=(4000, 6000))
        code, out = self.stage(res, "1")
        self.assertEqual(code, 2, out)
        self.assertIn("over 16", out)
        self.assertEqual(os.listdir(self.dest), [])

    def test_reconcile_after_crash(self):
        import hashlib
        os.makedirs(os.path.dirname(self.man))
        with open(os.path.join(self.dest, "G.jpg"), "wb") as f:
            f.write(self.JPEG)
        other = os.path.join(self.dest, "O.jpg")   # a different photo already under that name
        with open(other, "wb") as f:
            f.write(b"someone else")
        os.makedirs(self.stg)
        with open(os.path.join(self.stg, "G.jpg"), "wb") as f:
            f.write(b"leftover")
        h = hashlib.sha1(self.JPEG).hexdigest()
        with open(self.man, "w") as f:
            for i, n in ((1, "G.jpg"), (2, "O.jpg")):
                f.write(json.dumps({"id": i, "file": n, "dest": self.dest, "size": len(self.JPEG),
                                    "sha1": h, "state": "pending"}) + "\n")
        args = ("reconcile", "--dest", self.dest, "--staging", self.stg, "--manifest", self.man)
        code, out = run("export_stage.py", *args)
        self.assertEqual(code, 0, out)
        self.assertEqual({e["id"]: e["state"] for e in self.lines()}, {1: "done", 2: "abandoned"})
        self.assertEqual(os.listdir(self.stg), [])
        self.assertTrue(os.path.isfile(other))
        run("export_stage.py", *args)
        self.assertEqual(len(self.lines()), 4)  # nothing pending any more: no new lines

    def test_check_and_hist(self):
        code, out = run("export_stage.py", "check", "--root", self.root, "--staging", self.stg)
        self.assertEqual(code, 0, out)
        code, out = run("export_stage.py", "check", "--root", self.root,
                        "--staging", os.path.join(self.root, ".lc-staging"))
        self.assertNotEqual(code, 0)
        self.assertIn("inside the export root", out)
        code, out = run("export_stage.py", "check", "--root", self.dest, "--staging", self.stg,
                        "--avoid", self.root)
        self.assertNotEqual(code, 0)
        hist = os.path.join(self.t, "hist.json")
        with open(hist, "w") as f:
            f.write(json.dumps({"ok": True, "result": {"history": ["Import"], "cursor": 0}}) + "\n")
            f.write(json.dumps({"ok": True, "result": {"history": ["Import", "Exposure"], "cursor": 1}}) + "\n")
        sigs = os.path.join(self.t, "sigs.json")
        code, out = run("export_stage.py", "hist", "--out", sigs, "--ids", "7,8", hist)
        self.assertEqual(code, 0, out)
        with open(sigs) as f:
            s = json.load(f)
        self.assertEqual(set(s), {"7", "8"})
        self.assertNotEqual(s["7"], s["8"])
        code, out = run("export_stage.py", "hist", "--out", sigs, "--ids", "7", hist)
        self.assertNotEqual(code, 0)
        # fresh by default, --merge keeps the old signatures; several files are read in order
        h1, h2 = os.path.join(self.t, "h1.json"), os.path.join(self.t, "h2.json")
        for p, cur in ((h1, 0), (h2, 1)):
            with open(p, "w") as f:
                f.write(json.dumps({"ok": True, "result": {"history": ["Import"], "cursor": cur}}) + "\n")
        run("export_stage.py", "hist", "--out", sigs, "--ids", "9", h1)
        with open(sigs) as f:
            self.assertEqual(set(json.load(f)), {"9"})
        run("export_stage.py", "hist", "--merge", "--out", sigs, "--ids", "10,11", h1, h2)
        with open(sigs) as f:
            self.assertEqual(set(json.load(f)), {"9", "10", "11"})
        with open(h2, "w") as f:   # a photo deleted since: skipped, not fatal
            f.write(json.dumps({"ok": False, "error": "no photo 12"}) + "\n")
        code, out = run("export_stage.py", "hist", "--out", sigs, "--ids", "9,12", h1, h2)
        self.assertEqual(code, 0, out)
        with open(sigs) as f:
            self.assertEqual(set(json.load(f)), {"9"})
        man = os.path.join(self.t, "m2.jsonl")   # a complete last line without its newline is kept
        with open(man, "w") as f:
            f.write('{"id": 1, "state": "done"}')
        code, out = run("export_stage.py", "force", "--manifest", man, "--ids", "1")
        self.assertEqual(code, 0, out)
        with open(man) as f:
            self.assertEqual([json.loads(x)["state"] for x in f.read().splitlines()], ["done", "forced"])

    def test_torn_manifest_line_done_edge_and_bad_file(self):
        res = self.export([1], ["A.ARW"])
        self.assertEqual(self.stage(res, "1")[0], 0)
        with open(self.man, "a") as f:
            f.write('{"id": 2, "file": "B.jp')            # a crash in the middle of a line
        code, out = run("export_stage.py", "done", "--manifest", self.man)
        self.assertEqual((code, out.split()[0]), (0, "1"), out)
        self.assertIn("incomplete last line", out)
        res = self.export([2], ["B.ARW"], size=(4000, 2667))
        code, out = run("export_stage.py", "stage", "--result", res, "--dest", self.dest, "--staging", self.stg,
                        "--manifest", self.man, "--picks", self.picks, "--ids", "2", "--edge", "4000")
        self.assertEqual(code, 0, out)
        self.assertIn("removed the incomplete last line", out)
        self.assertEqual(run("export_stage.py", "done", "--manifest", self.man)[1].split(), ["1", "2"])
        with open(self.man) as f:   # every line parses again
            [json.loads(x) for x in f.read().splitlines()]
        res = self.export([3], ["C.ARW"])
        with open(os.path.join(self.raw, "C.jpg"), "wb") as f:
            f.write(b"<html>")
        code, out = self.stage(res, "3")
        self.assertEqual(code, 2, out)
        self.assertIn("not an image", out)

    def test_stage_refuses_staging_inside_dest(self):
        res = self.export([1], ["A.ARW"])
        code, out = run("export_stage.py", "stage", "--result", res, "--dest", self.dest,
                        "--staging", os.path.join(self.dest, ".lc-staging"), "--manifest", self.man,
                        "--picks", self.picks, "--ids", "1")
        self.assertNotEqual(code, 0)
        self.assertIn("overlap", out)


class ExportPicksEdges(unittest.TestCase):
    def test_missing_sigs_torn_manifest_dates(self):
        t = tempfile.mkdtemp()
        cat, pm, man = (os.path.join(t, n) for n in ("c.json", "p.json", "m.jsonl"))
        catalog(cat, [{"id": 1, "rating": 3, "captured": "2026-11-01T10:00:00"}, {"id": 2, "rating": 3}])
        with open(pm, "w") as f:
            json.dump({"1": {"0": "Sarah"}, "2": {"0": "Sarah"}}, f)
        with open(man, "w") as f:
            f.write('{"id": 1, "state": "done"}\n{"id": 9, "sta')
        out = os.path.join(t, "o.json")
        code, msg = run("export_picks.py", cat, pm, "--people", "Sarah", "--manifest", man,
                        "--hist-sigs", os.path.join(t, "none.json"), "--from", "2026-11-01", "--out", out)
        self.assertEqual(code, 0, msg)
        self.assertIn("incomplete last line", msg)
        with open(out) as f:
            r = json.load(f)
        self.assertEqual((r["already_exported"], r["no_date"], r["export"]), (["1"], ["2"], []))
        code, msg = run("export_picks.py", cat, pm, "--people", "Sarah", "--from", "2026-1-01")
        self.assertNotEqual(code, 0)
        self.assertIn("YYYY-MM-DD", msg)


FAKE_CLI = r'''#!/usr/bin/env bash
# fake lightcraft-cli for export-stage.sh: history.list and app.export only
shift 2   # run --connect
if [ "$1" = history.list ]; then
  for a in "$@"; do case "$a" in id=*) echo '{"ok":true,"result":{"history":["Import"],"cursor":0}}' ;; esac; done
  exit 0
fi
ids=; dir=
for a in "$@"; do case "$a" in ids=*) ids="${a#ids=[}"; ids="${ids%]}" ;; dir=*) dir="${a#dir=}" ;; esac; done
echo "$ids" >> "$FAKE_LOG"
files=
for i in ${ids//,/ }; do
  printf '\xff\xd8\xff\xe0 photo %s' "$i" > "$dir/P$i.jpg"
  files="$files{\"path\":\"$dir/P$i.jpg\",\"width\":4899,\"height\":3266},"
done
echo "{\"command\":\"app.export\",\"ok\":true,\"result\":{\"files\":[${files%,}]}}"
'''


@unittest.skipUnless(git_bash(), "no bash")
class ExportStageWrapper(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp()
        j = lambda *p: os.path.join(self.t, *p).replace("\\", "/")
        self.raw, self.dest, self.stg, self.man, self.picks = j("raw"), j("root", "trip"), j("stg"), j("m.jsonl"), j("p.json")
        self.log = j("cli.log")
        self.cli = j("fake-cli.sh")
        with open(self.cli, "w", newline="\n") as f:
            f.write(FAKE_CLI)
        os.chmod(self.cli, 0o755)
        with open(self.picks, "w") as f:
            json.dump({"names": {str(i): "N%d.ARW" % i for i in range(1, 10)}}, f)

    def wrap(self, *args, batch="3", size="mp=16"):
        env = dict(os.environ, EXPORT_STAGE_CLI=self.cli, FAKE_LOG=self.log, BATCH=batch)
        r = subprocess.run([git_bash(), os.path.join(SCRIPTS, "export-stage.sh"), self.raw, self.dest, self.stg,
                            self.man, self.picks, size, "format=jpeg", *args],
                           env=env, capture_output=True, text=True, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def calls(self):
        if not os.path.isfile(self.log):
            return []
        with open(self.log) as f:
            return f.read().split()

    def test_batches_rerun_and_crash_resume(self):
        code, out = self.wrap("--", "1,2", "3-4")
        self.assertEqual(code, 0, out)
        self.assertIn("batch 2/2", out)
        self.assertEqual(self.calls(), ["1,2,3", "4"])
        self.assertEqual(sorted(os.listdir(self.dest)), ["N1.jpg", "N2.jpg", "N3.jpg", "N4.jpg"])
        code, out = self.wrap("--", "1-4")
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to do", out)
        # a crash after the file reached the folder but before its done line: no second export
        import hashlib
        p = os.path.join(self.dest, "N5.jpg")
        with open(p, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0 photo 5")
        with open(self.man, "a") as f:
            f.write(json.dumps({"id": 5, "file": "N5.jpg", "dest": self.dest, "size": os.path.getsize(p),
                                "sha1": hashlib.sha1(open(p, "rb").read()).hexdigest(), "state": "pending"}) + "\n")
        code, out = self.wrap("--", "5,6")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.calls()[-1], "6")
        self.assertNotIn("N5-5.jpg", os.listdir(self.dest))

    def test_bad_input_fails_loudly(self):
        self.assertIn("BATCH", self.wrap("--", "1", batch="0")[1])
        self.assertIn("SIZE", self.wrap("--", "1", size="16")[1])
        self.assertIn("missing --", self.wrap("1")[1])
        with open(self.man, "w") as f:
            f.write("garbage\n{\"id\": 1, \"state\": \"done\"}\n")
        code, out = self.wrap("--", "1")
        self.assertEqual(code, 1, out)
        self.assertNotIn("nothing to do", out)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
