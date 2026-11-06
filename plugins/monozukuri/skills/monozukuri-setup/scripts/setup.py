"""monozukuri: モック・プレビュー環境のセットアップ（macOS・Linux・Windows）。

使い方
  python setup.py [--no-cad] [--lang ja|en] [--venv <フォルダ> | --no-venv] [--python <Python>]
    （mac・Linux は python3 setup.py。Windows は python setup.py、python が無ければ py -3.12 setup.py）
  --no-cad   cadquery（モックの STEP エクスポート用。数百MB）を入れない。--with-cad は旧い書き方で、無視される
  --lang     表示の言葉（ja / en）。無ければ環境変数 MONOZUKURI_LANG、どれも無ければ ja
  --venv     仮想環境の場所（既定：macOS と Windows は ~/.monozukuri/venv、Linux は使わない）
  --no-venv  仮想環境を使わず、この Python に直接入れる
  --python   その Python に直接入れる（conda など）。環境変数 MONOZUKURI_PYTHON でも指定できる
何度実行しても安全（入っているものは飛ばす）。最後に check_env.py が表とテストレンダリングの結果を出す。
環境変数（前からあるもの）：MONOZUKURI_VENV（仮想環境の場所）、MONOZUKURI_CACHE（three.js と env.json の場所。
  既定 ~/.cache/monozukuri）、BASE_PYTHON（仮想環境を作る元の Python）、PYTHON（macOS・Linux だけ。--python と同じ）。
Windows では PYTHON を読まない（Node.js のビルドなど、ほかの用途で設定されていることが多いため）。

English
  Sets up everything the monozukuri mock and review-page scripts need, then runs check_env.py.
    python setup.py [--no-cad] [--lang ja|en] [--venv DIR | --no-venv] [--python PYTHON]
  Default venv: ~/.monozukuri/venv on macOS and Windows; none on Linux. Safe to run again.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import sysconfig

THREE_VER = "0.160.0"
HERE = os.path.dirname(os.path.abspath(__file__))
WIN = os.name == "nt"
PKGS = ["numpy", "scipy", "shapely", "matplotlib", "manifold3d", "trimesh", "networkx", "pillow", "playwright", "cascadio"]
MODULE = {"pillow": "PIL"}
CHILD_ENV = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
LANG = "ja"


def L(ja, en):
    return en if LANG == "en" else ja


def say(ja, en):
    print("\n== " + L(ja, en), flush=True)


def msg(ja, en):
    print(L(ja, en), flush=True)


def run(cmd, **kw):
    """子のプロセスを動かし、出力を UTF-8 で受け取る"""
    kw.setdefault("env", CHILD_ENV)
    return subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", **kw)


def last_line(text):
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def py_version(py):
    """その Python の (メジャー, マイナー)。動かなければ None"""
    try:
        r = run([py, "-c", "import sys; print('%d %d' % sys.version_info[:2])"], timeout=60)
        if r.returncode == 0:
            a, b = r.stdout.split()
            return int(a), int(b)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def venv_python(venv):
    return os.path.join(venv, "Scripts", "python.exe") if WIN else os.path.join(venv, "bin", "python")


def win_python_notes(base):
    """Windows で、元の Python について知っておくこと"""
    if not WIN:
        return
    exe = getattr(sys, "_base_executable", "") or base
    if "WindowsApps" in exe:
        msg("注意: Microsoft Store の Python です。一時フォルダなどの書き込み先が別の場所になることがあります。"
            "python.org の Python か、winget install -e --id Python.Python.3.12 をすすめます",
            "Note: this is the Microsoft Store Python. It may redirect writes to temp folders. "
            "The python.org Python (or winget install -e --id Python.Python.3.12) is recommended")


def make_venv(venv, base):
    """仮想環境を用意して、その Python のパスを返す。作れなければ止める"""
    vpy = venv_python(venv)
    say(f"Python の仮想環境（{venv}）", f"Python virtual environment ({venv})")
    clear = False
    if os.path.exists(vpy):
        if py_version(vpy):
            msg("あります", "Already exists")
            return vpy
        # Windows の Scripts\python.exe は、元の Python を消すと動かなくなる（ファイルは残る）
        msg("あるが動かないので作り直します（元の Python を消したか動かした可能性）",
            "Exists but does not run, so it is rebuilt (its base Python was probably removed or moved)")
        clear = True
    if WIN and sysconfig.get_platform() == "win-arm64":
        sys.exit(L("!! ARM64 版の Python では、manifold3d・cadquery などのパッケージが入りません。"
                   "x64 版の Python（python.org の「Windows installer (64-bit)」）を入れて、それで実行し直してください",
                   "!! Packages such as manifold3d and cadquery have no builds for ARM64 Python. Install the x64 Python "
                   "(python.org \"Windows installer (64-bit)\") and run this again with it"))
    v = py_version(base)
    if not v or v < (3, 10):
        sys.exit(L("!! Python 3.10 以上が要ります。"
                   + ("python.org の Python 3.12 を入れて、py -3.12 scripts/setup.py で実行してください"
                      if WIN else "mac: brew install python@3.12 のあと、BASE_PYTHON=python3.12 で実行してください"),
                   "!! Python 3.10 or newer is required. "
                   + ("Install Python 3.12 from python.org and run py -3.12 scripts/setup.py"
                      if WIN else "mac: brew install python@3.12, then run with BASE_PYTHON=python3.12")))
    if WIN and v not in ((3, 11), (3, 12)):
        msg(f"注意: Python {v[0]}.{v[1]} です。Windows では 3.12 がいちばん確実です（cadquery と cascadio の Windows 用の"
            "パッケージがそろっている）", f"Note: this is Python {v[0]}.{v[1]}. On Windows 3.12 is the safest choice "
            "(cadquery and cascadio have Windows builds for it)")
    win_python_notes(base)
    os.makedirs(os.path.dirname(os.path.abspath(venv)), exist_ok=True)
    r = run([base, "-m", "venv"] + (["--clear"] if clear else []) + [venv], timeout=600)
    if r.returncode or not os.path.exists(vpy):
        print(r.stdout + r.stderr, file=sys.stderr)
        hint = L("（確認ページのサーバーがこの仮想環境の Python で動いていれば、先に serve_review.py --stop で止める）",
                 " (if the review server runs with this venv's Python, stop it first with serve_review.py --stop)") if WIN else ""
        sys.exit(L("!! 仮想環境を作れませんでした", "!! Could not create the virtual environment") + hint)
    r = run([vpy, "-m", "pip", "install", "-q", "--upgrade", "pip"], timeout=600)
    if r.returncode:
        print(r.stderr, file=sys.stderr)
        msg("!! pip を新しくできませんでした（続けます）", "!! Could not upgrade pip (continuing)")
    msg(f"作りました（元の Python: {v[0]}.{v[1]}）", f"Created (base Python: {v[0]}.{v[1]})")
    return vpy


def pip_install(py, pkgs):
    """入れる。外部管理された環境（Debian/Ubuntu の system python）では --break-system-packages を付けて再試行"""
    cmd = [py, "-m", "pip", "install", "-q"]
    if WIN:
        # wheel が無いときにソースからのビルド（コンパイラが要る）に進まず、すぐ止める
        cmd += ["--only-binary", "manifold3d,cadquery-ocp,cascadio"]
    r = run(cmd + pkgs, timeout=3600)
    if r.returncode and "externally-managed" in r.stderr:
        r = run(cmd + ["--break-system-packages"] + pkgs, timeout=3600)
    if r.returncode:
        print(r.stderr.strip(), file=sys.stderr, flush=True)
    return r.returncode == 0


def probe(py, mod):
    """import できるか。'ok'／'missing'／読み込めないときはエラーの1行"""
    try:
        r = run([py, "-c", f"import {mod}"], timeout=300)
    except subprocess.TimeoutExpired:
        return "timeout"
    if r.returncode == 0:
        return "ok"
    if "No module named" in r.stderr:
        return "missing"
    return last_line(r.stderr) or "error"


def broken_hint():
    if WIN:
        msg("  DLL を読み込めないときは、Microsoft Visual C++ 再頒布可能パッケージを入れる："
            "winget install -e --id Microsoft.VCRedist.2015+.x64",
            "  If a DLL cannot be loaded, install the Microsoft Visual C++ Redistributable: "
            "winget install -e --id Microsoft.VCRedist.2015+.x64")


def packages(py, with_cad):
    say("Python パッケージ", "Python packages")
    missing, broken = [], []
    for p in PKGS:
        st = probe(py, MODULE.get(p, p))
        if st == "missing":
            missing.append(p)
        elif st != "ok":
            broken.append((p, st))
    if missing:
        msg("入れる: " + " ".join(missing), "Installing: " + " ".join(missing))
        if not pip_install(py, missing):
            msg("!! 一部のパッケージを入れられませんでした（上のエラーを確認）",
                "!! Some packages could not be installed (see the error above)")
    elif not broken:
        msg("すべて入っています", "All installed")
    for p, err in broken:
        msg(f"!! {p} は入っているが読み込めません: {err}", f"!! {p} is installed but cannot be loaded: {err}")
    if broken:
        broken_hint()
    if with_cad:
        st = probe(py, "cadquery")
        if st == "missing":
            msg("cadquery を入れる（数分かかります）", "Installing cadquery (takes a few minutes)")
            if not pip_install(py, ["cadquery"]):
                msg("!! cadquery を入れられませんでした（モックは STL だけになります）",
                    "!! Could not install cadquery (mocks will be STL only)")
        elif st != "ok":
            msg(f"!! cadquery は入っているが読み込めません: {st}", f"!! cadquery is installed but cannot be loaded: {st}")
            broken_hint()


CHROMIUM_PROBE = ("from playwright.sync_api import sync_playwright\n"
                  "with sync_playwright() as p:\n"
                  "    p.chromium.launch().close()\n")


def chromium(py):
    say("ブラウザ（外観画像のレンダリング用 Chromium）", "Browser (Chromium for rendering the view images)")

    def ok():
        try:
            return run([py, "-c", CHROMIUM_PROBE], timeout=180)
        except subprocess.TimeoutExpired as e:
            return subprocess.CompletedProcess(e.cmd, 1, "", "timeout")
    r = ok()
    if r.returncode == 0:
        msg("Chromium は起動できます", "Chromium starts OK")
        return
    msg("Chromium を入れる", "Installing Chromium")
    i = run([py, "-m", "playwright", "install", "chromium"], timeout=1800)
    r = ok()
    if r.returncode == 0:
        msg("入れました", "Installed")
    else:
        print((i.stderr or "").strip(), file=sys.stderr)
        msg("!! Chromium を起動できません: " + last_line(r.stderr or i.stderr),
            "!! Chromium does not start: " + last_line(r.stderr or i.stderr))
        msg("  AI のサンドボックスがダウンロードを止めていれば、許可を得てサンドボックスの外で実行する（プロキシの環境は HTTPS_PROXY）",
            "  If the AI sandbox blocks the download, run this outside the sandbox with permission (behind a proxy: HTTPS_PROXY)")


def three(cache):
    say(f"three.js {THREE_VER}", f"three.js {THREE_VER}")
    d = os.path.join(cache, "three")
    target = os.path.join(d, "node_modules", "three", "build", "three.module.js")
    if os.path.isfile(target):
        msg(f"入っています: {d}", f"Already installed: {d}")
        return
    npm = (shutil.which("npm.cmd") if WIN else None) or shutil.which("npm")
    if not npm:
        msg("!! npm がありません。Node.js を入れてからもう一度実行してください（"
            + ("winget install -e --id OpenJS.NodeJS.LTS のあと、AI のアプリを開き直す" if WIN
               else "mac: brew install node、Ubuntu: sudo apt install nodejs npm") + "）",
            "!! npm not found. Install Node.js, then run this again ("
            + ("winget install -e --id OpenJS.NodeJS.LTS, then restart the AI app" if WIN
               else "mac: brew install node, Ubuntu: sudo apt install nodejs npm") + ")")
        return
    os.makedirs(d, exist_ok=True)
    pj = os.path.join(d, "package.json")
    if not os.path.exists(pj):
        # package.json が無いと、npm は上のフォルダ（ホームなど）の package.json を探して、そこに入れてしまう
        with open(pj, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"private": True, "description": "three.js for monozukuri"}, f)
            f.write("\n")
    r = run([npm, "install", "--no-audit", "--no-fund", "--loglevel=error", f"three@{THREE_VER}"], cwd=d, timeout=900)
    if r.returncode == 0 and os.path.isfile(target):
        msg(f"入れました: {d}", f"Installed: {d}")
    else:
        print((r.stdout + r.stderr).strip(), file=sys.stderr)
        msg("!! three.js を入れられませんでした（上のエラーを確認）", "!! Could not install three.js (see the error above)")


def main():
    global LANG
    for s in (sys.stdout, sys.stderr):        # Windows のパイプは ANSI コードページになるので UTF-8 にそろえる
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-cad", action="store_true")
    ap.add_argument("--with-cad", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--lang", choices=["ja", "en"])
    ap.add_argument("--venv")
    ap.add_argument("--no-venv", action="store_true")
    ap.add_argument("--python")
    a = ap.parse_args()
    for v in (a.lang, os.environ.get("MONOZUKURI_LANG")):
        if v in ("ja", "en"):
            LANG = v
            break
    cache = os.path.expanduser(os.environ.get("MONOZUKURI_CACHE") or "~/.cache/monozukuri")
    os.makedirs(cache, exist_ok=True)

    direct = a.python or os.environ.get("MONOZUKURI_PYTHON") or (None if WIN else os.environ.get("PYTHON"))
    if direct:
        py = os.path.expanduser(direct)
        v = py_version(py)
        if not v or v < (3, 10):
            sys.exit(L(f"!! {py} は Python 3.10 以上として動きません", f"!! {py} does not run as Python 3.10 or newer"))
        msg(f"{py} に直接入れます（仮想環境は使いません）", f"Installing into {py} directly (no virtual environment)")
    else:
        venv = None if a.no_venv else (a.venv or os.environ.get("MONOZUKURI_VENV"))
        if venv is None and not a.no_venv and sys.platform in ("darwin", "win32"):
            venv = "~/.monozukuri/venv"
        if venv:
            base = os.path.expanduser(os.environ.get("BASE_PYTHON") or sys.executable)
            py = make_venv(os.path.expanduser(venv), shutil.which(base) or base)
        else:
            py = sys.executable
            if sys.version_info[:2] < (3, 10):
                sys.exit(L("!! Python 3.10 以上が要ります", "!! Python 3.10 or newer is required"))

    packages(py, not a.no_cad)
    chromium(py)
    three(cache)

    say("動作確認", "Checking the setup")
    r = subprocess.run([py, os.path.join(HERE, "check_env.py"), "--lang", LANG], env=dict(CHILD_ENV, MONOZUKURI_LANG=LANG))
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
