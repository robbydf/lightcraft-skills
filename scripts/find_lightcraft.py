"""Print the folder that holds LightCraft's CLI (lightcraft-cli.exe on Windows, lightcraft-cli elsewhere).

Order: --dir argument, $LIGHTCRAFT_DIR, LIGHTCRAFT_DIR in <LIGHTCRAFT_HOME>/config.env, then per system:
  Windows: the uninstall entries in the registry, then Program Files / Program Files (x86) /
           %LOCALAPPDATA%\\Programs (ArtCraft\\LightCraft or LightCraft)
  macOS:   /Applications and ~/Applications: LightCraft.app, ArtCraft/LightCraft.app (Contents/MacOS)
  Linux:   lightcraft-cli on PATH, /opt/lightcraft, /opt/LightCraft, /opt/ArtCraft/LightCraft,
           ~/.local/share/lightcraft, ~/.local/opt/lightcraft
Exit 1 (and print nothing) if none is found, 2 on a usage error. Standard library only.
Usage: python find_lightcraft.py [--dir <folder>] | --help
"""
import glob
import os
import re
import shutil
import sys

WIN = os.name == "nt"
MAC = sys.platform == "darwin"
CLI_NAME = "lightcraft-cli.exe" if WIN else "lightcraft-cli"
NAME_RE = re.compile(r"LightCraft|ArtCraft", re.I)


def has_cli(d):
    return bool(d) and os.path.isfile(os.path.join(d, CLI_NAME))


def lc_home():
    h = os.environ.get("LIGHTCRAFT_HOME")
    return h if h else os.path.join(os.path.expanduser("~"), ".claude", "lightcraft")


def from_config():
    cfg = os.path.join(lc_home(), "config.env")
    found = ""
    try:
        with open(cfg, encoding="utf-8-sig") as fh:
            for line in fh:
                m = re.match(r'^\s*LIGHTCRAFT_DIR\s*=\s*"?([^"]+?)"?\s*$', line)
                if m:
                    found = m.group(1)
    except OSError:
        pass
    return found


def windows_candidates():
    out = []
    try:
        import winreg
    except ImportError:
        return out
    roots = [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")]
    for hive, path in roots:
        try:
            root = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with root:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(root, sub) as k:
                        def val(n):
                            try:
                                return str(winreg.QueryValueEx(k, n)[0])
                            except OSError:
                                return ""
                        if NAME_RE.search(val("DisplayName")):
                            if val("InstallLocation"):
                                out.append(val("InstallLocation"))
                            icon = re.sub(r'"|,\d+$', "", val("DisplayIcon"))
                            if icon:
                                out.append(os.path.dirname(icon))
                except OSError:
                    continue
    for var in ("ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(var):
            out += [os.path.join(os.environ[var], "ArtCraft", "LightCraft"), os.path.join(os.environ[var], "LightCraft")]
    if os.environ.get("LOCALAPPDATA"):
        p = os.path.join(os.environ["LOCALAPPDATA"], "Programs")
        out += [os.path.join(p, "ArtCraft", "LightCraft"), os.path.join(p, "LightCraft")]
    return out


def mac_candidates():
    out = []
    for apps in ("/Applications", os.path.expanduser("~/Applications")):
        for app in ("LightCraft.app", "ArtCraft/LightCraft.app", "ArtCraft LightCraft.app"):
            out.append(os.path.join(apps, app, "Contents", "MacOS"))
        out += [os.path.join(p, "Contents", "MacOS") for p in sorted(glob.glob(os.path.join(apps, "*LightCraft*.app")))]
    return out


def linux_candidates():
    home = os.path.expanduser("~")
    return ["/opt/lightcraft", "/opt/LightCraft", "/opt/ArtCraft/LightCraft", "/usr/lib/lightcraft",
            os.path.join(home, ".local", "share", "lightcraft"), os.path.join(home, ".local", "opt", "lightcraft")]


def candidates(arg):
    c = [arg, os.environ.get("LIGHTCRAFT_DIR", ""), from_config()]
    if WIN:
        c += windows_candidates()
    elif MAC:
        c += mac_candidates()
    else:
        c += linux_candidates()
    on_path = shutil.which(CLI_NAME)
    if on_path:
        c.append(os.path.dirname(os.path.realpath(on_path)))
    return [x for x in c if x]


def find(arg=""):
    for c in candidates(arg):
        if has_cli(c):
            return os.path.abspath(c)
        # Search two levels deeper only inside a LightCraft/ArtCraft folder, never a drive root or Program Files.
        if os.path.isdir(c) and NAME_RE.search(os.path.basename(os.path.normpath(c))):
            base = os.path.normpath(c).count(os.sep)
            for root, dirs, fs in os.walk(c):
                if CLI_NAME in fs:
                    return os.path.abspath(root)
                if root.count(os.sep) - base >= 2:
                    dirs[:] = []
    return ""


def main(argv):
    arg = ""
    if argv and argv[0].lower() in ("-h", "--help", "-help", "/?"):
        print(__doc__)
        return
    if len(argv) == 2 and argv[0].lower() in ("--dir", "-dir"):
        arg = argv[1]
    elif argv:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    d = find(arg)
    if not d:
        sys.exit(1)
    print(d)


if __name__ == "__main__":
    main(sys.argv[1:])
