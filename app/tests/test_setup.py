"""Run with:  python -m unittest discover -s tests   (from the app folder)

Exercises the game-mod installer and checker against a fake Titanfall 2 VR folder."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

MOD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "mod")
sys.path.insert(0, MOD_DIR)
import btvoice_setup as setup  # noqa: E402

LAUNCH = {"arguments": ["-profile={profile}", "-novid", "-windowed"], "vrArguments": ["+dof_enable", "0"]}


def make_game(root, with_launch=True, enabled=None):
    os.makedirs(os.path.join(root, "TF2VR", "tools"))
    open(os.path.join(root, setup.LAUNCHER), "w").close()
    if with_launch:
        with open(os.path.join(root, "TF2VR", "tools", "launch.json"), "w") as f:
            json.dump(LAUNCH, f)
    if enabled is not None:
        with open(os.path.join(root, "TF2VR", "enabledmods.json"), "w") as f:
            json.dump(enabled, f)


def run(fn, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = fn(*args)
    return result, out.getvalue()


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.game = self.tmp.name
        self.no_app = mock.patch.object(setup, "app_reachable", lambda: None)
        self.no_app.start()
        self.addCleanup(self.no_app.stop)

    def test_install_copies_the_mod_sets_the_flag_and_is_repeatable(self):
        make_game(self.game, enabled={"TF2VR.BTVoice": False, "Other.Mod": True})
        ok, out = run(setup.install, self.game)
        self.assertTrue(ok, out)
        self.assertTrue(os.path.exists(os.path.join(self.game, "TF2VR", "mods", "TF2VR.BTVoice", "mod.json")))
        launch = json.load(open(os.path.join(self.game, "TF2VR", "tools", "launch.json")))
        self.assertIn("-allowlocalhttp", launch["arguments"])
        self.assertEqual(launch["arguments"][:3], LAUNCH["arguments"], "existing arguments are kept in order")
        self.assertEqual(launch["vrArguments"], LAUNCH["vrArguments"])
        self.assertTrue(os.path.exists(os.path.join(self.game, "TF2VR", "tools", "launch.json.bak")))
        enabled = json.load(open(os.path.join(self.game, "TF2VR", "enabledmods.json")))
        self.assertEqual(enabled, {"TF2VR.BTVoice": True, "Other.Mod": True})
        with open(os.path.join(self.game, "ns_startup_args.txt")) as f:
            self.assertEqual(f.read().split(), ["-allowlocalhttp"])
        ok, _ = run(setup.install, self.game)  # again
        self.assertTrue(ok)
        launch = json.load(open(os.path.join(self.game, "TF2VR", "tools", "launch.json")))
        self.assertEqual(launch["arguments"].count("-allowlocalhttp"), 1)
        with open(os.path.join(self.game, "ns_startup_args.txt")) as f:
            self.assertEqual(f.read().split().count("-allowlocalhttp"), 1)

    def test_check_names_each_problem_on_a_fresh_game_folder(self):
        make_game(self.game)
        ok, out = run(setup.check, self.game)
        self.assertFalse(ok)
        self.assertIn("NOT installed", out)
        self.assertIn("launch flag is not set", out)
        self.assertIn("No game log found", out)

    def test_check_passes_after_install_and_a_good_log(self):
        make_game(self.game)
        run(setup.install, self.game)
        logs = os.path.join(self.game, "TF2VR", "logs")
        os.makedirs(logs)
        with open(os.path.join(logs, "nslog1.txt"), "w") as f:
            f.write("[info] something\n[BTVoice] started. Sending to http://127.0.0.1:5757/api/event.\n")
        ok, out = run(setup.check, self.game)
        self.assertTrue(ok, out)
        self.assertIn("mod loaded and started", out)

    def test_check_reports_a_mod_that_did_not_load_with_the_script_error(self):
        make_game(self.game)
        run(setup.install, self.game)
        logs = os.path.join(self.game, "TF2VR", "logs")
        os.makedirs(logs)
        with open(os.path.join(logs, "nslog1.txt"), "w") as f:
            f.write("[error] COMPILE ERROR undefined variable in bt_voice_sensors.nut line 12\n")
        ok, out = run(setup.check, self.game)
        self.assertFalse(ok)
        self.assertIn("does NOT show the mod starting", out)
        self.assertIn("COMPILE ERROR", out)

    def test_check_flags_a_mod_switched_off_and_a_running_app_that_hears_nothing(self):
        make_game(self.game, enabled={"TF2VR.BTVoice": False})
        with mock.patch.object(setup, "app_reachable", lambda: {"game_seconds": None}):
            ok, out = run(setup.check, self.game)
        self.assertIn("switched OFF", out)
        self.assertIn("received nothing", out)

    def test_check_reports_connected_when_the_app_has_heard_from_the_game(self):
        make_game(self.game)
        run(setup.install, self.game)
        with mock.patch.object(setup, "app_reachable", lambda: {"game_seconds": 3}):
            ok, out = run(setup.check, self.game)
        self.assertIn("It is connected", out)

    def test_the_flag_in_startup_args_alone_counts(self):
        make_game(self.game, with_launch=False)
        with open(os.path.join(self.game, "ns_startup_args.txt"), "w") as f:
            f.write("-something -allowlocalhttp\n")
        _, out = run(setup.check, self.game)
        self.assertIn("launch flag is set in ns_startup_args.txt", out)

    def test_find_game_needs_the_vr_launcher(self):
        make_game(self.game)
        self.assertEqual(setup.find_game(self.game), os.path.normpath(self.game))
        os.remove(os.path.join(self.game, setup.LAUNCHER))
        with mock.patch.object(setup, "_registry_paths", lambda: []):
            self.assertIsNone(setup.find_game(self.game))

    def test_it_asks_for_the_folder_when_it_cannot_find_the_game(self):
        make_game(self.game)
        with mock.patch.object(setup, "find_game", side_effect=[None, os.path.normpath(self.game)]), \
                mock.patch("builtins.input", return_value='"' + self.game + '"'), \
                mock.patch.object(sys, "stdin", mock.Mock(isatty=lambda: True)):
            code, out = run(setup.main, ["x", "check"])
        self.assertIn("Type or paste the folder", out)
        self.assertEqual(code, 1)  # the check itself finds problems in an empty game folder, but it did run
        self.assertIn("Found the Titanfall 2 VR folder", out)

    def test_it_does_not_hang_waiting_for_input_when_nobody_is_there(self):
        with mock.patch.object(setup, "find_game", return_value=None), \
                mock.patch.object(sys, "stdin", mock.Mock(isatty=lambda: False)):
            code, out = run(setup.main, ["x", "check"])
        self.assertEqual(code, 1)
        self.assertIn("Could not find the Titanfall 2 VR folder", out)

    def test_the_clickable_files_exist_and_point_at_real_files(self):
        root = os.path.join(MOD_DIR, "..")
        for vbs, target in (("START_BT_VOICE.vbs", "START_BT_VOICE.bat"), ("INSTALL_BT_MOD.vbs", os.path.join("mod", "install_mod.bat")),
                            ("CHECK_BT_MOD.vbs", os.path.join("mod", "check_mod.bat"))):
            with open(os.path.join(root, vbs), newline="") as f:
                text = f.read()
            self.assertIn("\r\n", text)
            self.assertIn(os.path.basename(target), text)
            self.assertTrue(os.path.exists(os.path.join(root, target)), target)

    def test_the_mod_sends_to_the_address_the_app_listens_on(self):
        with open(os.path.join(MOD_DIR, "TF2VR.BTVoice", "mod", "scripts", "vscripts", "bt_voice_sensors.nut")) as f:
            self.assertIn("http://127.0.0.1:5757/api/event", f.read())


if __name__ == "__main__":
    unittest.main()
