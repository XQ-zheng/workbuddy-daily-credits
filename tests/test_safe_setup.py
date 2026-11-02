"""Offline regression tests: fake tokens, temporary files, mocked official APIs only."""

import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import wb_auth
import claim_all
import setup_auth

TOKEN = "a" * 48 + "." + "b" * 48 + "." + "c" * 48
ACCESS = "d" * 48 + "." + "e" * 48 + "." + "f" * 48
ROTATED = "g" * 48 + "." + "h" * 48 + "." + "i" * 48


class SafeSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = str(Path(self.temp.name) / "checkin-rt.json")
        self.auth = Path(self.temp.name) / "auth.info"
        self.patches = [
            mock.patch.object(wb_auth, "DEFAULT_RT_FILE", self.config),
            mock.patch.object(wb_auth, "AUTH_CANDIDATES", [str(self.auth)]),
            # Any accidental real network access fails the test.
            mock.patch.object(wb_auth.urllib.request, "urlopen", side_effect=AssertionError("real network forbidden")),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)
        wb_auth._SECRETS.clear()

    def local_auth(self, value):
        self.auth.write_text(json.dumps({"auth": {"refreshToken": value}}), encoding="utf-8")

    def capture(self, fn, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                result = fn(*args)
            except SystemExit as exc:
                result = exc.code
        output = stdout.getvalue() + stderr.getvalue()
        for token in (TOKEN, ACCESS, ROTATED):
            self.assertNotIn(token, output)
        return result, output

    def test_export_save_does_not_print_or_return_token(self):
        self.local_auth(TOKEN)
        code, output = self.capture(wb_auth.main, ["--export-rt", "--save"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output)["saved"])
        self.assertEqual(wb_auth.read_rt(), TOKEN)
        metadata = wb_auth.save_rt(TOKEN)
        self.assertNotIn("rt", metadata)
        self.assertEqual(list(Path(self.temp.name).glob(".checkin-*")), [])
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(os.stat(self.config).st_mode), 0o600)

    def test_export_without_save_is_masked_and_does_not_save(self):
        self.local_auth(TOKEN)
        code, output = self.capture(wb_auth.main, ["--export-rt"])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(output)["saved"])
        self.assertFalse(Path(self.config).exists())

    def test_token_arguments_including_equals_are_rejected_without_echo(self):
        for fn, args in ((wb_auth.main, ["--setup-rt", TOKEN]),
                         (wb_auth.main, ["--setup-rt=" + TOKEN]),
                         (setup_auth.main, [TOKEN]),
                         (setup_auth.main, ["--gui=" + TOKEN])):
            with self.subTest(args=args[:1]):
                code, _ = self.capture(fn, args)
                self.assertNotEqual(code, 0)
        self.assertFalse(Path(self.config).exists())

    def test_noninteractive_encrypted_state_never_prompts_or_checks(self):
        self.local_auth({"$wbEncrypted": 1, "envelope": "fake"})
        with mock.patch.object(wb_auth, "prompt_rt") as prompt, mock.patch.object(claim_all, "run") as check:
            result, code = setup_auth.run(non_interactive=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "need_local_input")
        self.assertIn("不支持", result["export"]["tried"][0]["reason"])
        prompt.assert_not_called()
        check.assert_not_called()
        self.assertFalse(Path(self.config).exists())

    def test_missing_file_is_not_reported_as_encryption(self):
        result = wb_auth.export_rt_from_local_state()
        self.assertEqual(result["tried"], [])
        self.assertNotIn("已加密", result["hint"])

    def test_permission_failure_is_distinguished_and_not_echoed(self):
        self.local_auth(TOKEN)
        with mock.patch("builtins.open", side_effect=PermissionError(TOKEN)):
            result = wb_auth.export_rt_from_local_state()
        self.assertIn("PermissionError", result["tried"][0]["reason"])
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_unreadable_existing_config_does_not_prompt_or_export(self):
        wb_auth.save_rt(TOKEN)
        real_open = open
        def selective_open(path, *args, **kwargs):
            if str(path) == self.config:
                raise PermissionError("fake locked config")
            return real_open(path, *args, **kwargs)
        with mock.patch("builtins.open", side_effect=selective_open), \
                mock.patch.object(wb_auth, "prompt_rt") as prompt, \
                mock.patch.object(wb_auth, "export_rt_from_local_state") as export, \
                mock.patch.object(claim_all, "run") as check:
            result, code = setup_auth.run(non_interactive=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "config_error")
        prompt.assert_not_called()
        export.assert_not_called()
        check.assert_not_called()
        self.assertEqual(wb_auth.read_rt(), TOKEN)

    def test_corrupt_existing_config_is_not_overwritten(self):
        Path(self.config).write_text("not-json", encoding="utf-8")
        with mock.patch.object(wb_auth, "prompt_rt") as prompt:
            result, code = setup_auth.run()
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "config_error")
        self.assertEqual(Path(self.config).read_text(encoding="utf-8"), "not-json")
        prompt.assert_not_called()

    def test_plaintext_auto_export_runs_check_only(self):
        self.local_auth(TOKEN)
        with mock.patch.object(claim_all, "run", return_value=({"status": "ok", "earned": 0}, 0)) as check:
            code, output = self.capture(setup_auth.main, ["--non-interactive"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["status"], "ready")
        self.assertEqual(wb_auth.read_rt(), TOKEN)
        check.assert_called_once_with(["--check"])

    def test_existing_config_is_not_overwritten_or_prompted(self):
        wb_auth.save_rt(TOKEN)
        self.local_auth(ROTATED)
        with mock.patch.object(wb_auth, "export_rt_from_local_state") as export, \
                mock.patch.object(wb_auth, "prompt_rt") as prompt, \
                mock.patch.object(claim_all, "run", return_value=({"status": "auth_failed"}, 2)) as check:
            result, code = setup_auth.run(non_interactive=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "check_failed")
        self.assertTrue(result["configured"])
        self.assertEqual(wb_auth.read_rt(), TOKEN)
        prompt.assert_not_called()
        export.assert_not_called()
        check.assert_called_once_with(["--check"])

    def test_hidden_input_calls_installed_save_then_check(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=True), \
                mock.patch.object(wb_auth.getpass, "getpass", return_value=TOKEN) as prompt, \
                mock.patch.object(claim_all, "run", return_value=({"status": "ok"}, 0)) as check:
            code, output = self.capture(setup_auth.main, [])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["source"], "local_input")
        self.assertEqual(wb_auth.read_rt(), TOKEN)
        prompt.assert_called_once()
        check.assert_called_once_with(["--check"])

    def test_getpass_warning_cannot_fall_back_to_plain_input(self):
        def unsafe_fallback(*args):
            warnings.warn("Cannot hide input", wb_auth.getpass.GetPassWarning)
            self.fail("A warning must abort before fallback can read anything")
        with mock.patch.object(sys.stdin, "isatty", return_value=True), \
                mock.patch.object(wb_auth.getpass, "getpass", side_effect=unsafe_fallback):
            result = wb_auth.prompt_rt()
        self.assertEqual(result["error"], "hidden_input_unavailable")
        self.assertFalse(Path(self.config).exists())

    def test_noninteractive_low_level_never_reads_input(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=False), \
                mock.patch.object(wb_auth.getpass, "getpass") as prompt:
            result = wb_auth.prompt_rt()
        prompt.assert_not_called()
        self.assertEqual(result["error"], "hidden_input_unavailable")

    def test_cancel_and_invalid_token_never_check_or_save(self):
        for value in (KeyboardInterrupt(), EOFError(), "not-a-token"):
            kwargs = {"side_effect": value} if isinstance(value, BaseException) else {"return_value": value}
            with mock.patch.object(sys.stdin, "isatty", return_value=True), \
                    mock.patch.object(wb_auth.getpass, "getpass", **kwargs), \
                    mock.patch.object(claim_all, "run") as check:
                result, code = setup_auth.run()
            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "setup_incomplete")
            check.assert_not_called()
            self.assertFalse(Path(self.config).exists())

    def test_gui_collects_in_password_field_and_never_in_output(self):
        fake_tk = mock.MagicMock()
        fake_tk.simpledialog.askstring.return_value = TOKEN
        with mock.patch.dict(sys.modules, {"tkinter": fake_tk, "tkinter.simpledialog": fake_tk.simpledialog}), \
                mock.patch.object(claim_all, "run", return_value=({"status": "ok"}, 0)) as check:
            code, _ = self.capture(setup_auth.main, ["--gui"])
        self.assertEqual(code, 0)
        self.assertEqual(fake_tk.simpledialog.askstring.call_args.kwargs["show"], "*")
        fake_tk.Tk.return_value.destroy.assert_called_once()
        self.assertEqual(wb_auth.read_rt(), TOKEN)
        check.assert_called_once_with(["--check"])

    def test_unavailable_gui_does_not_check(self):
        with mock.patch.dict(sys.modules, {"tkinter": None}), mock.patch.object(claim_all, "run") as check:
            result, code = setup_auth.run(gui=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["input"]["error"], "local_input_failed")
        check.assert_not_called()

    def test_gui_cancel_preserves_existing_config_when_replacing(self):
        wb_auth.save_rt(TOKEN)
        fake_tk = mock.MagicMock()
        fake_tk.simpledialog.askstring.return_value = None
        with mock.patch.dict(sys.modules, {"tkinter": fake_tk, "tkinter.simpledialog": fake_tk.simpledialog}), \
                mock.patch.object(claim_all, "run") as check:
            result, code = setup_auth.run(gui=True, replace=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["input"]["error"], "input_cancelled")
        self.assertEqual(wb_auth.read_rt(), TOKEN)
        check.assert_not_called()

    def test_failed_atomic_replace_keeps_original_and_cleans_temporary_file(self):
        wb_auth.save_rt(TOKEN)
        with mock.patch.object(wb_auth.os, "replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                wb_auth.save_rt(ROTATED)
        self.assertEqual(wb_auth.read_rt(), TOKEN)
        self.assertEqual(list(Path(self.temp.name).glob(".checkin-*")), [])

    def test_explicit_replace_uses_new_input_and_checks(self):
        wb_auth.save_rt(TOKEN)
        with mock.patch.object(sys.stdin, "isatty", return_value=True), \
                mock.patch.object(wb_auth.getpass, "getpass", return_value=ROTATED), \
                mock.patch.object(claim_all, "run", return_value=({"status": "ok"}, 0)):
            result, code = setup_auth.run(replace=True)
        self.assertEqual(code, 0)
        self.assertEqual(wb_auth.read_rt(), ROTATED)

    def test_check_has_no_activity_mutations_and_rotates_local_token(self):
        wb_auth.save_rt(TOKEN)
        calls = []
        def fake_request(url, method="GET", token=None, body=None, headers=None):
            calls.append((method, url))
            if url.endswith(wb_auth.REFRESH_PATH):
                return 200, {"code": 0, "data": {"accessToken": ACCESS, "refreshToken": ROTATED}}
            if url.endswith("checkin-activity-status"):
                return 200, {"code": 0, "data": {"today_checked_in": False, "daily_credit": 100, "total_credits": 800}}
            if url.endswith("/tasks"):
                return 200, {"code": 0, "data": {"tasks": [
                    {"task_code": "eligible", "title": "fake", "accept_status": "completed", "reward_credit": 100},
                    {"task_code": "new", "accept_status": "not_accepted"}]}}
            if url.endswith("/travel/status"):
                return 200, {"code": 0, "data": {"state": "arrived", "reward_credit": 10}}
            if url.endswith("/streak"):
                return 200, {"code": 0, "data": {"redemption_status": {"tiers": [{"tier": 14, "status": "available", "credit": 50}]}}}
            if url.endswith("/lottery/chances"):
                return 200, {"code": 0, "data": {"balance": 3}}
            self.fail("Unexpected activity request: " + url)
        with mock.patch.object(wb_auth, "_request", side_effect=fake_request):
            code, output = self.capture(setup_auth.main, ["--non-interactive"])
        self.assertEqual(code, 0)
        result = json.loads(output)["check"]
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["earned"], 0)
        self.assertEqual(wb_auth.read_rt(), ROTATED)
        posts = [url for method, url in calls if method == "POST"]
        self.assertTrue(posts)
        self.assertTrue(all(url.endswith((wb_auth.REFRESH_PATH, "checkin-activity-status")) for url in posts))

    def test_output_redacts_echoed_tokens_and_sensitive_keys(self):
        wb_auth.remember_secret(TOKEN)
        code, output = self.capture(wb_auth.print_result, {
            "refreshToken": TOKEN, "access_token": "opaque-sensitive",
            "msg": "server echoed " + TOKEN, "nested": [{"rt": TOKEN, "msg": ACCESS}]})
        self.assertNotIn("opaque-sensitive", output)
        self.assertEqual(json.loads(output)["access_token"], "***")

    def test_long_error_token_is_redacted_before_truncation(self):
        long_token = "header" + "x" * 500 + "." + "y" * 500 + ".signature"
        wb_auth.remember_secret(long_token)
        res = wb_auth._maybe_json("server echoed " + long_token)
        self.assertNotIn(long_token[:100], res["msg"])
        self.assertIn("***", res["msg"])
        with mock.patch.object(wb_auth, "_request", return_value=(500, [long_token])):
            res = wb_auth.refresh_access_token(TOKEN)
        self.assertNotIn(long_token[:100], res["msg"])
        self.assertIn("***", res["msg"])


if __name__ == "__main__":
    unittest.main()
