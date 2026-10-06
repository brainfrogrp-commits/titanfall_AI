"""Install and check the BTVoice game mod.

    btvoice_setup.py install [path to the Titanfall 2 folder]
    btvoice_setup.py check   [path to the Titanfall 2 folder]

With no path it looks for the Titanfall 2 VR install by itself. `check` explains
in plain words why the app is not receiving anything from the game.
"""

import glob
import json
import os
import re
import shutil
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MOD_NAME = "TF2VR.BTVoice"
MOD_SOURCE = os.path.join(HERE, MOD_NAME)
LAUNCHER = "Titanfall2VRLauncher.exe"  # the VR installer puts this in the game folder
PROFILE = "TF2VR"
FLAG = "-allowlocalhttp"
APP_STATUS = "http://127.0.0.1:5757/api/status"


# ------------------------------------------------------------ finding the game

def _registry_paths():
    if os.name != "nt":
        return []
    import winreg

    found = []
    for hive, key, value in (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Respawn\Titanfall2", "Install Dir"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Respawn\Titanfall2", "Install Dir"),
    ):
        try:
            with winreg.OpenKey(hive, key) as k:
                found.append(winreg.QueryValueEx(k, value)[0])
        except OSError:
            pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            steam = winreg.QueryValueEx(k, "SteamPath")[0]
        found.append(os.path.join(steam, "steamapps", "common", "Titanfall2"))
        vdf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf):
            with open(vdf, encoding="utf-8", errors="replace") as f:
                for lib in re.findall(r'"path"\s+"([^"]+)"', f.read()):
                    found.append(os.path.join(lib.replace("\\\\", "\\"), "steamapps", "common", "Titanfall2"))
    except OSError:
        pass
    return found


def find_game(explicit=None):
    candidates = [explicit] if explicit else []
    candidates += _registry_paths()
    candidates += [
        r"C:\Program Files\EA Games\Titanfall2",
        r"C:\Program Files (x86)\EA Games\Titanfall2",
        r"C:\Program Files (x86)\Origin Games\Titanfall2",
        r"C:\Program Files (x86)\Steam\steamapps\common\Titanfall2",
        r"C:\Program Files\Steam\steamapps\common\Titanfall2",
    ]
    for path in candidates:
        if path and os.path.exists(os.path.join(path, LAUNCHER)):
            return os.path.normpath(path)
    return None


# ------------------------------------------------------------------ helpers

def say(level, text):
    print(f"[{level}] {text}")


def read_json(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def launch_json_path(game):
    return os.path.join(game, PROFILE, "tools", "launch.json")


def startup_args_path(game):
    return os.path.join(game, "ns_startup_args.txt")


def flag_in_launch_json(game):
    path = launch_json_path(game)
    if not os.path.exists(path):
        return None
    try:
        return FLAG in read_json(path).get("arguments", [])
    except (OSError, ValueError):
        return None


def flag_in_startup_args(game):
    path = startup_args_path(game)
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8", errors="replace") as f:
        return FLAG in f.read().split()


# ------------------------------------------------------------------ install

def install(game):
    ok = True
    target = os.path.join(game, PROFILE, "mods", MOD_NAME)
    try:
        shutil.copytree(MOD_SOURCE, target, dirs_exist_ok=True)
        say("OK", f"Copied the mod to {target}")
    except PermissionError:
        say("PROBLEM", "Windows would not let this write to the game folder. Close the game, then run this again "
                       "as administrator (right-click PowerShell, Run as administrator).")
        return False

    # the VR launcher passes the arguments in launch.json to the game, so that is where the flag has to go
    path = launch_json_path(game)
    if os.path.exists(path):
        try:
            data = read_json(path)
            if FLAG not in data.get("arguments", []):
                shutil.copyfile(path, path + ".bak")
                data.setdefault("arguments", []).append(FLAG)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                say("OK", f"Added {FLAG} to {path} (backup saved as launch.json.bak)")
            else:
                say("OK", f"{FLAG} was already in launch.json")
        except (OSError, ValueError) as e:
            say("PROBLEM", f"Could not edit {path}: {e}")
            ok = False
    else:
        say("NOTE", f"{path} was not found; the VR mod may not be fully installed yet")

    # belt and braces: Northstar also reads extra launch arguments from this file
    if not flag_in_startup_args(game):
        try:
            with open(startup_args_path(game), "a", encoding="utf-8") as f:
                f.write(FLAG + "\n")
            say("OK", f"Added {FLAG} to ns_startup_args.txt")
        except OSError as e:
            say("NOTE", f"Could not write ns_startup_args.txt ({e}); launch.json should be enough")

    # a mod listed as disabled in the profile stays disabled
    enabled_path = os.path.join(game, PROFILE, "enabledmods.json")
    if os.path.exists(enabled_path):
        try:
            enabled = read_json(enabled_path)
            if enabled.get(MOD_NAME) is not True:
                enabled[MOD_NAME] = True
                with open(enabled_path, "w", encoding="utf-8") as f:
                    json.dump(enabled, f, indent=2)
                say("OK", "Marked the mod as enabled in enabledmods.json")
        except (OSError, ValueError) as e:
            say("NOTE", f"Could not update enabledmods.json: {e}")
    print("\nNow close the game completely and start it again. Mods are only loaded when it starts.")
    return ok


# -------------------------------------------------------------------- check

def newest_log(game):
    patterns = [
        os.path.join(game, PROFILE, "logs", "*.txt"),
        os.path.join(game, PROFILE, "logs", "*.log"),
        os.path.join(game, "R2Northstar", "logs", "*.txt"),
    ]
    files = [f for p in patterns for f in glob.glob(p)]
    return max(files, key=os.path.getmtime) if files else None


def interesting_log_lines(path, limit=14):
    wanted = re.compile(r"btvoice|bt_voice_sensors|script error|compile error|nshttp|allowlocalhttp|"
                        r"http request|private network", re.IGNORECASE)
    lines, started = [], False
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "[BTVoice] started" in line:
                started = True
            if wanted.search(line):
                lines.append(line.rstrip())
    return started, lines[-limit:]


def app_reachable():
    try:
        with urllib.request.urlopen(APP_STATUS, timeout=2) as r:
            return json.load(r)
    except Exception:
        return None


def check(game):
    problems = 0
    say("OK", f"Found the Titanfall 2 VR folder: {game}")

    mod_json = os.path.join(game, PROFILE, "mods", MOD_NAME, "mod.json")
    script = os.path.join(game, PROFILE, "mods", MOD_NAME, "mod", "scripts", "vscripts", "bt_voice_sensors.nut")
    if os.path.exists(mod_json) and os.path.exists(script):
        say("OK", f"The mod is installed in {os.path.dirname(mod_json)}")
    else:
        say("PROBLEM", f"The mod is NOT installed where the game looks for it ({os.path.join(game, PROFILE, 'mods', MOD_NAME)}). "
                       "Run install_mod.bat.")
        problems += 1

    in_json, in_args = flag_in_launch_json(game), flag_in_startup_args(game)
    if in_json or in_args:
        where = " and ".join(n for n, v in (("launch.json", in_json), ("ns_startup_args.txt", in_args)) if v)
        say("OK", f"The {FLAG} launch flag is set in {where}")
    else:
        say("PROBLEM", f"The {FLAG} launch flag is not set anywhere, so the game blocks the mod from reaching this app. "
                       "Run install_mod.bat. (A VR mod update can reset launch.json, so run it again after updating.)")
        problems += 1

    enabled_path = os.path.join(game, PROFILE, "enabledmods.json")
    if os.path.exists(enabled_path):
        try:
            state = read_json(enabled_path).get(MOD_NAME)
            if state is False:
                say("PROBLEM", "The mod is switched OFF in enabledmods.json. Run install_mod.bat to switch it on.")
                problems += 1
            else:
                say("OK", "The mod is not switched off" + ("" if state else " (it is not listed, which means enabled)"))
        except (OSError, ValueError):
            pass

    log = newest_log(game)
    if not log:
        say("NOTE", "No game log found yet. Start the game once, load a level, then run this check again.")
    else:
        age = int((time.time() - os.path.getmtime(log)) / 60)
        say("OK", f"Newest game log: {log} (updated {age} minutes ago)")
        try:
            started, lines = interesting_log_lines(log)
        except OSError as e:
            started, lines = False, []
            say("NOTE", f"Could not read the log while the game is using it ({e}). Close the game and check again.")
        if started:
            say("OK", "The log shows the mod loaded and started ([BTVoice] started).")
        else:
            say("PROBLEM", "The log does NOT show the mod starting. The game did not load it: it is in the wrong "
                           "folder, switched off, or has a script error (see the lines below, if any).")
            problems += 1
        for line in lines:
            print("      log: " + line[:220])

    status = app_reachable()
    if status is None:
        say("NOTE", "The BT voice app is not running right now, so I could not ask it what it has received.")
    elif status.get("game_seconds") is None:
        say("PROBLEM", "The app is running but has received nothing from the game yet.")
        problems += 1
    else:
        say("OK", f"The app last heard from the game {status['game_seconds']} seconds ago. It is connected.")

    print()
    if problems == 0:
        print("Everything looks right. If the app still shows nothing, start the game fresh after running install_mod.bat "
              "and send the text above to Claude.")
    else:
        print(f"{problems} problem(s) found above. Fix those, restart the game completely, and run this check again.")
    return problems == 0


def main(argv):
    if len(argv) < 2 or argv[1] not in ("install", "check"):
        print(__doc__)
        return 2
    game = find_game(argv[2] if len(argv) > 2 else None)
    if not game:
        say("PROBLEM", f"Could not find the Titanfall 2 VR folder (the one containing {LAUNCHER}). "
                       'Run this again with the path, for example: install_mod.bat "C:\\Program Files\\EA Games\\Titanfall2"')
        return 1
    return 0 if (install(game) if argv[1] == "install" else check(game)) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
