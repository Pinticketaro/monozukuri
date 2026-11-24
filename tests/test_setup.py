"""monozukuri-setup（setup.py・check_env.py）のテスト。標準ライブラリの unittest だけで動く。

  python tests/test_setup.py           速いテスト（setup.py の関数を直接呼ぶ。pip でパッケージを入れない。数十秒）
  python tests/test_setup.py --full    加えて、範囲外の Python から setup.py を最後まで通す（cadquery を入れる。数分）

本物のホーム（~/.monozukuri・~/.cache/monozukuri）には書かない。HOME・setup.MZ_HOME・MONOZUKURI_CACHE を一時フォルダにする。
uv が Python を取ってくるテストは、ダウンロードを1回で済ませるため ~/.cache/monozukuri-test/python を使い回す。
失敗の場面（古い uv、uv venv の失敗、ダウンロードの失敗）は、偽物の uv（シェルスクリプト）で作る（mac・Linux だけ）。
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "monozukuri", "skills", "monozukuri-setup", "scripts")
WIN = os.name == "nt"
FULL = "--full" in sys.argv
PY_CACHE = os.path.join(os.path.expanduser("~"), ".cache", "monozukuri-test", "python")


def load(name):
    spec = importlib.util.spec_from_file_location(f"mz_{name}", os.path.join(SCRIPTS, f"{name}.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def fake_uv(folder, version="0.13.6", python_rc=0, venv_rc=0):
    """偽物の uv。--version は version、python install は python_rc、venv は venv_rc で終わる"""
    os.makedirs(folder, exist_ok=True)
    p = os.path.join(folder, "uv")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("#!/bin/sh\n"
                f'case "$1" in --version) echo "uv {version}";; python) exit {python_rc};; '
                f'venv) echo "fake: venv failed" >&2; exit {venv_rc};; esac\n')
    os.chmod(p, 0o755)
    return p


# 元の Python から仮想環境を作るテストは、そのテストを動かす Python が MIN_RUN（3.10）以上のときだけ
# （3.9 などでは setup.py が正しく止まるので、作り直しの流れに入らない）
needs_run = unittest.skipIf(sys.version_info[:2] < (3, 10), "元の Python で仮想環境を作るテストは Python 3.10 以上で動かす")


def real_uv():
    """手元の本物の uv（UV_MIN 以上）。無ければ None"""
    s = load("setup")
    c = shutil.which("uv")
    v = s.uv_version(c) if c else None
    return c if v and v >= s.UV_MIN else None


class Base(unittest.TestCase):
    """一時フォルダをホームにして setup.py を読み込む"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mz-test-")
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        env = {"HOME": self.home, "USERPROFILE": self.home, "MONOZUKURI_CACHE": os.path.join(self.tmp, "cache")}
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()
        self.s = load("setup")
        self.s.MZ_HOME = os.path.join(self.home, ".monozukuri")
        self.s.STATE["uv_fail"] = None
        self.s.upgrade_pip = lambda vpy: None          # PyPI に出ない
        self.out = io.StringIO()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, f, *a, **kw):
        """標準出力を拾って呼ぶ。(戻り値, 出力, SystemExit の文)"""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                return f(*a, **kw), buf.getvalue(), None
            except SystemExit as e:
                return None, buf.getvalue(), str(e.code)

    def venv(self, name):
        """元の Python（このテストを動かしている Python）で、pip なしの仮想環境を作る"""
        p = os.path.join(self.tmp, name)
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", p], check=True)
        return p

    def out_of_range(self):
        """このテストの Python を範囲外にする（範囲外の Python が無い PC でも uv の流れを通す）"""
        v = sys.version_info[:2]
        self.s.SUPPORTED = ((v[0], v[1] + 1), (v[0], v[1] + 1))


class TestVersions(Base):
    def test_preferred_is_in_range(self):
        major, minor = map(int, self.s.PREFERRED.split("."))
        self.assertTrue(self.s.in_range((major, minor)))
        self.assertFalse(self.s.in_range((3, 15)))
        self.assertFalse(self.s.in_range(None))

    def test_uv_request_is_x64_on_windows(self):
        self.assertEqual(self.s.uv_request(), f"cpython-{self.s.PREFERRED}-windows-x86_64-none" if WIN else self.s.PREFERRED)


class TestDelete(Base):
    def test_refuses_folder_that_is_not_a_venv(self):
        d = os.path.join(self.tmp, "notvenv")
        os.makedirs(d)
        open(os.path.join(d, "keep.txt"), "w").close()
        _, _, err = self.call(self.s.remove_venv, d)
        self.assertIn("pyvenv.cfg", err)
        self.assertTrue(os.path.exists(os.path.join(d, "keep.txt")))

    @unittest.skipIf(WIN, "シンボリックリンクを作るのに権限が要る")
    def test_refuses_link(self):
        v = self.venv("real")
        link = os.path.join(self.tmp, "link")
        os.symlink(v, link)
        _, _, err = self.call(self.s.remove_venv, link)
        self.assertIsNotNone(err)
        self.assertTrue(os.path.isfile(os.path.join(v, "pyvenv.cfg")))

    def test_removes_venv_without_leftovers(self):
        v = self.venv("v")
        ok, _, err = self.call(self.s.remove_venv, v)
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual([p for p in os.listdir(self.tmp) if p.startswith("v")], [])

    def test_clean_old_only_numbered(self):
        v = os.path.join(self.tmp, "v")
        for n in ("v.old-123", "v.old-abc"):
            os.makedirs(os.path.join(self.tmp, n, "x"))
        self.s.clean_old(v)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "v.old-123")))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "v.old-abc")))

    def test_guard_when_base_is_inside_venv(self):
        v = self.venv("v")
        _, _, err = self.call(self.s.guard_delete, v, self.s.venv_python(v))
        self.assertIn("PC の Python", err)
        self.assertTrue(os.path.isfile(os.path.join(v, "pyvenv.cfg")))


@unittest.skipIf(WIN, "偽物の uv はシェルスクリプト")
class TestUv(Base):
    def test_old_uv_is_skipped(self):
        fake_uv(os.path.join(self.tmp, "bin"), version="0.1.0")
        with mock.patch.dict(os.environ, {"PATH": os.path.join(self.tmp, "bin") + os.pathsep + "/usr/bin:/bin"}):
            uv, old = self.s.find_uv()
        self.assertIsNone(uv)
        self.assertEqual(old, "0.1.0")

    def test_new_uv_is_found(self):
        p = fake_uv(os.path.join(self.tmp, "bin"))
        with mock.patch.dict(os.environ, {"PATH": os.path.join(self.tmp, "bin") + os.pathsep + "/usr/bin:/bin"}):
            self.assertEqual(self.s.find_uv()[0], p)

    def test_uv_env_drops_conflicting_settings(self):
        with mock.patch.dict(self.s.CHILD_ENV, {"UV_PYTHON_PREFERENCE": "only-system", "UV_MANAGED_PYTHON": "1",
                                                "UV_VENV_CLEAR": "1", "HTTPS_PROXY": "http://proxy"}):
            env = self.s.uv_env()
        self.assertEqual(env["UV_PYTHON_PREFERENCE"], "only-managed")
        self.assertNotIn("UV_MANAGED_PYTHON", env)
        self.assertNotIn("UV_VENV_CLEAR", env)
        self.assertEqual(env["HTTPS_PROXY"], "http://proxy")          # プロキシの設定は残す
        self.assertEqual(env["UV_PYTHON_INSTALL_BIN"], "0")

    def with_fake(self, **kw):
        fake_uv(os.path.join(self.tmp, "bin"), **kw)
        return mock.patch.dict(os.environ, {"PATH": os.path.join(self.tmp, "bin") + os.pathsep + "/usr/bin:/bin"})

    @needs_run
    def test_download_failure_falls_back_and_marks_wanted_uv(self):
        self.out_of_range()
        v = os.path.join(self.tmp, "venv")
        with self.with_fake(python_rc=1):
            vpy, out, err = self.call(self.s.make_venv, v, sys.executable)
        self.assertIsNone(err)
        self.assertTrue(os.path.exists(vpy))
        self.assertIn("ダウンロードできる所で", out)
        self.assertEqual(self.s.read_marker(v), {"python_source": "base", "wanted_uv": True})

    @needs_run
    def test_wanted_uv_rebuild_failure_does_not_return_a_deleted_venv(self):
        self.out_of_range()
        v = os.path.join(self.tmp, "venv")
        with self.with_fake(python_rc=1):
            self.call(self.s.make_venv, v, sys.executable)
        self.s.STATE["uv_fail"] = None
        with self.with_fake(venv_rc=1):                               # 次の実行：Python は取れたが uv venv が失敗
            vpy, out, err = self.call(self.s.make_venv, v, sys.executable)
        self.assertIsNone(err)
        self.assertTrue(os.path.exists(vpy), out)
        self.assertIn("uv で作り直します", out)
        self.assertNotIn("wanted_uv", self.s.read_marker(v))          # 毎回作り直さない

    @needs_run
    def test_wanted_uv_with_in_range_base_says_so(self):
        self.out_of_range()
        v = os.path.join(self.tmp, "venv")
        with self.with_fake(python_rc=1):
            self.call(self.s.make_venv, v, sys.executable)
        # 次の実行：仮想環境の Python は範囲外（3.99）のまま、元の Python は範囲内（3.12）
        self.s.SUPPORTED = ((3, 0), (3, 50))
        with mock.patch.object(self.s, "py_version", side_effect=lambda p: (3, 99) if p.startswith(v) else (3, 12)):
            vpy, out, err = self.call(self.s.make_venv, v, sys.executable)
        self.assertIn("今の PC の Python 3.12 で作り直します", out)
        self.assertNotIn("uv で作り直します", out)

    @needs_run
    def test_broken_link_venv_is_rebuilt(self):
        v = self.venv("venv")
        py = self.s.venv_python(v)
        os.remove(py)
        os.symlink("/nonexistent/python", py)
        vpy, out, err = self.call(self.s.make_venv, v, sys.executable, use_uv=False)
        self.assertIn("あるが動かないので作り直します", out)
        self.assertTrue(os.path.exists(vpy))

    def test_non_venv_folder_stops_before_uv(self):
        self.out_of_range()
        d = os.path.join(self.tmp, "h")
        os.makedirs(d)
        open(os.path.join(d, "keep.txt"), "w").close()
        with self.with_fake():
            _, _, err = self.call(self.s.make_venv, d, sys.executable)
        self.assertIn("仮想環境ではないフォルダ", err)
        self.assertTrue(os.path.exists(os.path.join(d, "keep.txt")))


class TestHints(Base):
    def test_step_hint_blames_version_only_for_missing(self):
        with mock.patch.object(self.s, "py_version", return_value=(3, 15)):
            _, out, _ = self.call(self.s.step_hint, "py", "missing", "venv", "", True)
            self.assertIn("範囲（", out)
            _, out, _ = self.call(self.s.step_hint, "py", "ImportError: DLL load failed", "venv", "", True)
            self.assertEqual(out, "")
            _, out, _ = self.call(self.s.step_hint, "py", "ModuleNotFoundError: No module named 'OCP'", "direct", "python", True)
            self.assertIn("--python は外す", out)

    def test_check_env_cad_fix(self):
        c = load("check_env")
        dll = ImportError("DLL load failed while importing _OCP")
        self.assertIn("VCRedist", c.cad_fix("base", True, dll, False, "3.12"))
        if not WIN:
            self.assertIn("libgl1", c.cad_fix("base", False, ImportError("libGL.so.1: cannot open"), False, "3.12"))
        missing = ModuleNotFoundError("No module named 'cadquery'", name="cadquery")
        ocp = ModuleNotFoundError("No module named 'OCP'", name="OCP")
        self.assertIn("--no-cad", c.cad_fix("uv", True, missing, False, "3.12"))
        self.assertIn("--venv", c.cad_fix("direct", False, ocp, False, "3.12"))
        self.assertIn("ダウンロードできる所", c.cad_fix("base", False, ocp, True, "3.12"))
        self.assertIn("--rebuild-venv", c.cad_fix("base", False, ocp, False, "3.12"))

    def test_check_env_python_source(self):
        c = load("check_env")
        with mock.patch.dict(os.environ, {"MONOZUKURI_PYTHON_SOURCE": "direct"}):
            self.assertEqual(c.python_source({"python_source": "uv"}), "direct")
        os.environ.pop("MONOZUKURI_PYTHON_SOURCE", None)
        self.assertEqual(c.python_source({"python_source": "uv"}), "uv")


@unittest.skipUnless(real_uv(), "uv（0.5.0 以上）が無い")
class TestRealUv(Base):
    """本物の uv で、範囲外の元の Python から PREFERRED の仮想環境を作る（Python は ~/.cache/monozukuri-test を使い回す）"""

    def test_uv_venv(self):
        os.makedirs(PY_CACHE, exist_ok=True)
        os.makedirs(self.s.MZ_HOME)
        os.symlink(PY_CACHE, os.path.join(self.s.MZ_HOME, "python"), target_is_directory=True)
        v = os.path.join(self.tmp, "venv")
        real = self.s.py_version
        # 元の Python だけを範囲外（3.99）に見せる（このテストの Python が PREFERRED と同じ版でも、uv の流れを通す）
        with mock.patch.object(self.s, "py_version", side_effect=lambda p: (3, 99) if p == sys.executable else real(p)):
            vpy, out, err = self.call(self.s.make_venv, v, sys.executable)
        self.assertIsNone(err, out)
        self.assertEqual(self.s.py_version(vpy), tuple(map(int, self.s.PREFERRED.split("."))))
        self.assertEqual(self.s.read_marker(v), {"python_source": "uv"})
        r = subprocess.run([vpy, "-m", "pip", "--version"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)                  # ensurepip で pip が入っている


def out_of_range_python():
    """範囲外の Python（3.15 など）。uv が知っているものを探す。無ければ None"""
    uv = real_uv()
    s = load("setup")
    for ver in ("3.15", "3.14", "3.10"):
        if uv and not s.in_range(tuple(map(int, ver.split(".")))):
            r = subprocess.run([uv, "python", "find", ver], capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
    return None


@unittest.skipUnless(FULL, "--full のときだけ")
class TestFull(unittest.TestCase):
    """範囲外の Python から setup.py を最後まで通し、cadquery が読み込めることを確かめる（本物のホームの uv の Python を使う）"""

    def test_setup_from_out_of_range_python(self):
        py = out_of_range_python()
        if not py:
            self.skipTest("範囲外の Python が無い（uv python install 3.15 で入れる）")
        tmp = tempfile.mkdtemp(prefix="mz-full-")
        try:
            env = dict(os.environ, MONOZUKURI_CACHE=os.path.join(tmp, "cache"))
            three = os.path.join(os.path.expanduser("~"), ".cache", "monozukuri", "three")
            if os.path.isdir(three):
                shutil.copytree(three, os.path.join(tmp, "cache", "three"))
            v = os.path.join(tmp, "venv")
            r = subprocess.run([py, os.path.join(SCRIPTS, "setup.py"), "--venv", v], env=env,
                               capture_output=True, text=True, encoding="utf-8", timeout=3600)
            self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
            with open(os.path.join(tmp, "cache", "env.json"), encoding="utf-8") as f:
                e = json.load(f)
            self.assertEqual(e["python_source"], "uv")
            vpy = os.path.join(v, "Scripts", "python.exe") if WIN else os.path.join(v, "bin", "python")
            r = subprocess.run([vpy, "-c", "import cadquery, OCP"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(argv=[a for a in sys.argv if a != "--full"], verbosity=2)
