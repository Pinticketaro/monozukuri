"""monozukuri: モック・プレビュー環境のセットアップ（macOS・Linux・Windows）。

使い方
  python setup.py [--no-cad] [--lang ja|en] [--venv <フォルダ> | --no-venv] [--python <Python>] [--rebuild-venv] [--no-uv]
    （mac・Linux は python3 setup.py。Windows は python setup.py。Python が無ければ uv run --python 3.12 --no-project setup.py）
  --no-cad   cadquery（モックの STEP エクスポート用。数百MB）を入れない。--with-cad は旧い書き方で、無視される
  --lang     表示の言葉（ja / en）。無ければ環境変数 MONOZUKURI_LANG、どれも無ければ ja
  --venv     仮想環境の場所（既定：macOS と Windows は ~/.monozukuri/venv、Linux は使わない）
  --no-venv  仮想環境を使わず、この Python に直接入れる
  --python   その Python に直接入れる（conda など）。環境変数 MONOZUKURI_PYTHON でも指定できる。uv は使わない
  --rebuild-venv  仮想環境を消してから作り直す（STEP が使えない版の Python で作った古い仮想環境を作り直すとき）
  --no-uv    uv を使わず、元の Python で仮想環境を作る（0.8.0 までの動き）
Python の版：仮想環境を作るとき、元の Python が STEP まで使える範囲（下の SUPPORTED）の外なら、uv で Python 3.12 を
  ~/.monozukuri/python に用意して、それで仮想環境を作る（PC の Python には触らない）。uv が無ければ ~/.monozukuri/bin に入れる。
  どちらで作ったか（uv／base）は仮想環境の monozukuri.json に書き、check_env.py が env.json の python_source にコピーする。
何度実行しても安全（入っているものは飛ばす）。最後に check_env.py が表とテストレンダリングの結果を出す。
環境変数（前からあるもの）：MONOZUKURI_VENV（仮想環境の場所）、MONOZUKURI_CACHE（three.js と env.json の場所。
  既定 ~/.cache/monozukuri）、BASE_PYTHON（仮想環境を作る元の Python）、PYTHON（macOS・Linux だけ。--python と同じ）。
Windows では PYTHON を読まない（Node.js のビルドなど、ほかの用途で設定されていることが多いため）。

English
  Sets up everything the monozukuri mock and review-page scripts need, then runs check_env.py.
    python setup.py [--no-cad] [--lang ja|en] [--venv DIR | --no-venv] [--python PYTHON] [--rebuild-venv] [--no-uv]
  Default venv: ~/.monozukuri/venv on macOS and Windows; none on Linux. If the base Python is outside the range that can
  export STEP, uv gets Python 3.12 into ~/.monozukuri/python for the venv (your own Python is left as it is).
  --rebuild-venv deletes and recreates the venv; --no-uv keeps the 0.8.0 behaviour. Safe to run again.
"""
import argparse
import glob
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import sysconfig

THREE_VER = "0.160.0"
HERE = os.path.dirname(os.path.abspath(__file__))
WIN = os.name == "nt"
MZ_HOME = os.path.join(os.path.expanduser("~"), ".monozukuri")    # 仮想環境の既定の場所。uv と、uv が用意する Python も置く

# STEP まで確実に使える Python の版（両端を含む）と、範囲外のときに uv で用意する版。check_env.py もここを読む。
# 調べた結果（2026-11-23。PyPI のパッケージ（wheel）と、uv pip compile --only-binary :all: で OS ごとに解決して確かめた）：
#   cadquery 2.8.0 は Python 3.11 以上で、cadquery-ocp 7.9.3.1.1 を使う。cadquery-ocp 7.9.3.1.1 は cp310〜cp314
#     （macOS arm64・x86_64、Windows x64、Linux x86_64（glibc 2.31 以上）・aarch64）。8.0.1.1.0 は cp311〜cp314。
#   vtk 9.6.2・nlopt 2.11.0 は cp314 まで。numba 0.68.1 は cp315 まで（macOS x86_64 は無い）。casadi 3.8.2 は cp311 の abi3。
#   cascadio 0.1.1 は cp310・cp311 と cp312 の abi3（3.12 以上）。manifold3d 3.5.5 は cp315 まで。
#   → 3.15：cadquery-ocp・vtk・nlopt が無い。pip は OCP を依存に書いていない古い cadquery 2.3.0 まで下がり、入っても読み込めない。
#   → 3.14：macOS x86_64 だけ numba・nlopt が無く、cadquery 2.3.0 まで下がる（ほかの OS は入る）。
#   → 3.10：cadquery 2.7.0 まで（2.8.0 は 3.11 以上）。Python 3.10 のサポートは 2026-10 に終わった。
#   どの OS でも cadquery-ocp の付いた cadquery が入る 3.11〜3.13 を範囲にし、uv では 3.12（GitHub Actions の Windows で確かめている版）を用意する。
SUPPORTED = ((3, 11), (3, 13))
PREFERRED = "3.12"
MIN_RUN = (3, 10)              # monozukuri のスクリプトが動く Python（範囲外でも、STL のモックと確認ページは使える）
CAD_REQ = "cadquery>=2.4"      # 2.4 より前は OCP を依存に書いていない。入ったのに読み込めない cadquery まで下がらないように
MARKER = "monozukuri.json"     # 仮想環境の中に置く記録（python_source）
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


def ver_text(v):
    return f"{v[0]}.{v[1]}" if v else "?"


def range_text():
    (a, b), (c, d) = SUPPORTED
    return f"{a}.{b}〜{c}.{d}" if LANG == "ja" else f"{a}.{b}-{c}.{d}"


def in_range(v):
    """STEP まで使える範囲（SUPPORTED）の版か"""
    return bool(v) and SUPPORTED[0] <= tuple(v[:2]) <= SUPPORTED[1]


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


def full_version(py):
    """その Python の版（3.12.8 など）。分からなければ空"""
    try:
        r = run([py, "-c", "import platform; print(platform.python_version())"], timeout=60)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def venv_python(venv):
    return os.path.join(venv, "Scripts", "python.exe") if WIN else os.path.join(venv, "bin", "python")


def rmtree(path):
    """フォルダを消す（Windows の読み取り専用のファイルも）。消せなければ OSError（使用中のファイル、リンクなど）"""
    def retry(func, p, exc):
        e = exc[1] if isinstance(exc, tuple) else exc
        # Windows の読み取り専用のファイルだけ、書けるようにしてもう一度消す。リンクのエラーなどはそのまま止める
        # （mac・Linux ではファイルの書き込みの権限は消せるかに関係しない）
        if not WIN or not isinstance(e, PermissionError) or func in (os.path.islink, os.lstat, os.open, os.scandir):
            raise e
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, **({"onexc": retry} if sys.version_info >= (3, 12) else {"onerror": retry}))


def is_link(path):
    """シンボリックリンクか、Windows のジャンクションか"""
    if os.path.islink(path):
        return True
    try:
        return bool(getattr(os.lstat(path), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    except OSError:
        return False


def server_hint():
    return L("（確認ページのサーバーがこの仮想環境の Python で動いていれば、先に serve_review.py --stop で止める）",
             " (if the review server runs with this venv's Python, stop it first with serve_review.py --stop)") if WIN else ""


def is_venv(path):
    return os.path.isfile(os.path.join(path, "pyvenv.cfg"))


def under(p, folder):
    """p が folder の中か（リンクをたどる前とたどった後の両方で見る）"""
    for f in (os.path.abspath, os.path.realpath):
        a, b = os.path.normcase(f(p)), os.path.normcase(f(folder))
        if a == b or a.startswith(b.rstrip(os.sep) + os.sep):
            return True
    return False


def delete_blocked(venv, base):
    """この仮想環境を消せない理由（消せるなら空）。元の Python がその中にある、または（Windows で）setup.py 自身が
    その中の Python で動いている（Windows では使用中の python.exe を消せず、元の Python を消すと作り直せない）"""
    if under(base, venv) or (WIN and under(sys.prefix, venv)):
        cmd = ("python" if WIN else "python3") + " scripts/setup.py --rebuild-venv"
        return L(f"この仮想環境の Python で setup.py を実行しているので、仮想環境を消せません。PC の Python で実行してください: {cmd}",
                 f"setup.py is running with this virtual environment's Python, so it cannot delete it. "
                 f"Run it with your own Python: {cmd}")
    return ""


def guard_delete(venv, base):
    """消せないときは、何も消さずに止める"""
    why = delete_blocked(venv, base)
    if why:
        sys.exit("!! " + why)


ARM_MSG = ("!! ARM64 版の Python では、manifold3d・cadquery などのパッケージが入りません。"
           "x64 版の Python（python.org の「Windows installer (64-bit)」）を入れて、それで実行し直してください",
           "!! Packages such as manifold3d and cadquery have no builds for ARM64 Python. Install the x64 Python "
           "(python.org \"Windows installer (64-bit)\") and run this again with it")


def arm_stop():
    """Windows の ARM64 版の Python から仮想環境を作るなら、（何かを消す前に）止める"""
    if WIN and sysconfig.get_platform() == "win-arm64":
        sys.exit(L(*ARM_MSG))


def remove_venv(venv, soft=False):
    """仮想環境を消す。先に名前を変えてから消す（Windows で使用中のファイルがあれば、名前を変える所で何も消さずに止まる）。
    仮想環境に見えないフォルダ（pyvenv.cfg が無い）とリンクは消さずに止める。
    soft のときは、名前を変えられなければ止めずに False を返す（今の仮想環境をそのまま使う）"""
    if not os.path.lexists(venv):
        return True
    if is_link(venv):
        sys.exit(L(f"!! {venv} はリンクなので消しません。リンク先の仮想環境の場所を --venv で指定してください",
                   f"!! {venv} is a link, so it is not deleted. Pass the real folder with --venv"))
    if not is_venv(venv):
        sys.exit(L(f"!! {venv} は仮想環境に見えない（pyvenv.cfg が無い）ので消しません。--venv の場所を確かめてください",
                   f"!! {venv} does not look like a virtual environment (no pyvenv.cfg), so it is not deleted. "
                   "Check the --venv path"))
    old = f"{venv}.old-{os.getpid()}"
    try:
        os.rename(venv, old)
    except OSError as e:
        why = L(f"仮想環境を消せませんでした{'（使っているプログラムがある）' if WIN else ''}: {e}",
                f"Could not delete the virtual environment{' (a program is using it)' if WIN else ''}: {e}") + server_hint()
        if soft:
            msg("注意: " + why, "Note: " + why)
            return False
        sys.exit("!! " + why)
    try:
        rmtree(old)
    except OSError:
        msg(f"注意: 古い仮想環境が一部残りました（{old}）。次に setup.py を実行したときに消します",
            f"Note: part of the old virtual environment is left ({old}). The next setup.py run deletes it")
    return True


def discard(venv):
    """uv が途中まで作って使えなかった仮想環境を消す（消せなければそのまま。次の作り直しで --clear する）"""
    try:
        if is_venv(venv) and not is_link(venv):
            old = f"{venv}.old-{os.getpid()}"
            os.rename(venv, old)
            rmtree(old)
    except OSError:
        pass


def clean_old(venv):
    """前の --rebuild-venv で消しきれなかった <venv>.old-<番号> を消す（消せなければそのまま）"""
    for p in glob.glob(glob.escape(venv) + ".old-*"):
        if os.path.basename(p)[len(os.path.basename(venv)) + 5:].isdigit() and os.path.isdir(p) and not is_link(p):
            try:
                rmtree(p)
            except OSError:
                pass


def read_marker(venv):
    try:
        with open(os.path.join(venv, MARKER), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def write_marker(venv, source, wanted_uv=False):
    """どちらで作ったか（uv／base）を仮想環境に書く。check_env.py が env.json の python_source にコピーする。
    wanted_uv は「範囲外なので uv を使いたかったが、使えずに元の Python で作った」。次の実行で uv が使えれば作り直す"""
    d = {"python_source": source}
    if wanted_uv:
        d["wanted_uv"] = True
    try:
        with open(os.path.join(venv, MARKER), "w", encoding="utf-8", newline="\n") as f:
            json.dump(d, f)
            f.write("\n")
    except OSError:
        pass


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


# ---------------------------------------------------------------- uv（範囲外の Python のとき）
UV_EXE = "uv.exe" if WIN else "uv"
UV_MIN = (0, 5, 0)          # これより古い uv は使わない（uv python・UV_PYTHON_INSTALL_DIR・Python の指定の形がそろった版）
STATE = {"uv_fail": None}   # この実行で uv を使えなかった理由：no_uv（uv が無い）／download（Python を取れない）／venv


def uv_version(uv):
    """uv の版 (0, 13, 6)。動かなければ None"""
    try:
        r = run([uv, "--version"], timeout=60)
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", r.stdout or "") if r.returncode == 0 else None
        return tuple(int(x) for x in m.groups()) if m else None
    except (OSError, subprocess.SubprocessError):
        return None


def find_uv():
    """uv を探す：PATH、~/.monozukuri/bin、公式のインストーラの置き場所（~/.local/bin。入れた直後で PATH が古くても見つける）。
    UV_MIN より古い uv は使わない。(uv のパス, 飛ばした古い uv の版) を返す"""
    old, seen = "", set()
    for c in (shutil.which("uv"), os.path.join(MZ_HOME, "bin", UV_EXE),
              os.path.join(os.path.expanduser("~"), ".local", "bin", UV_EXE)):
        if not c or not os.path.isfile(c) or os.path.normcase(os.path.realpath(c)) in seen:
            continue
        seen.add(os.path.normcase(os.path.realpath(c)))
        v = uv_version(c)
        if v and v >= UV_MIN:
            return c, ""
        if v:
            old = ".".join(map(str, v))
    return None, old


def uv_installer():
    """uv の公式のインストーラ（setup.py からは実行しない。案内だけ）"""
    return ('powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"' if WIN
            else "curl -LsSf https://astral.sh/uv/install.sh | sh")


def install_uv(base):
    """元の Python で ~/.monozukuri/uv-boot に小さな仮想環境を作って pip で uv を入れ、~/.monozukuri/bin にコピーする
    （uv のパッケージは Python の版によらず入る）。入れられなければ案内を出して None"""
    boot = os.path.join(MZ_HOME, "uv-boot")
    dst = os.path.join(MZ_HOME, "bin", UV_EXE)
    msg("uv を入れます（~/.monozukuri/bin）", "Installing uv (~/.monozukuri/bin)")
    err = ""
    try:
        if os.path.lexists(boot):
            rmtree(boot)
        r = run([base, "-m", "venv", boot], timeout=600)
        bpy = venv_python(boot)
        if r.returncode == 0 and os.path.exists(bpy):
            r = run([bpy, "-m", "pip", "install", "-q", "--disable-pip-version-check", f"uv>={'.'.join(map(str, UV_MIN))}"],
                    timeout=900)
            if r.returncode == 0:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(os.path.dirname(bpy), UV_EXE), dst)
        err = (r.stdout + r.stderr).strip()
    except (OSError, subprocess.SubprocessError) as e:
        err = str(e)
    finally:
        try:
            if os.path.lexists(boot):
                rmtree(boot)
        except OSError:
            pass
    v = uv_version(dst) if os.path.isfile(dst) else None
    if v and v >= UV_MIN:
        return dst
    if err:
        print(err, file=sys.stderr, flush=True)
    msg("!! uv を入れられませんでした。公式のインストーラで入れてから、もう一度実行してください: " + uv_installer(),
        "!! Could not install uv. Install it with the official installer, then run this again: " + uv_installer())
    return None


# PC の uv の設定のうち、Python の選び方・置き場所・仮想環境の作り方に関わるもの（こちらで決めた値とぶつかるので外す）
UV_DROP = ("UV_VENV_CLEAR", "UV_VENV_SEED", "UV_PYTHON", "UV_PYTHON_ARCH", "VIRTUAL_ENV", "UV_PYTHON_PREFERENCE",
           "UV_MANAGED_PYTHON", "UV_NO_MANAGED_PYTHON", "UV_PYTHON_DOWNLOADS", "UV_PYTHON_INSTALL_DIR",
           "UV_PYTHON_INSTALL_BIN", "UV_PYTHON_INSTALL_REGISTRY")


def uv_env():
    """uv を動かす環境変数。Python は ~/.monozukuri/python に置き、PC の PATH（~/.local/bin）・Windows のレジストリ・
    uv のキャッシュには何も足さない。PC の uv の設定（uv.toml と上の UV_DROP の環境変数）に左右されない。
    UV_PYTHON_PREFERENCE=only-managed は古い uv でも使える書き方（UV_MANAGED_PYTHON と一緒には使えない）"""
    env = {k: v for k, v in CHILD_ENV.items() if k not in UV_DROP}
    env.update(UV_PYTHON_INSTALL_DIR=os.path.join(MZ_HOME, "python"), UV_PYTHON_INSTALL_BIN="0",
               UV_PYTHON_INSTALL_REGISTRY="0", UV_NO_CACHE="1", UV_NO_CONFIG="1", UV_PYTHON_PREFERENCE="only-managed",
               UV_PYTHON_DOWNLOADS="automatic")
    return env


def uv_run(cmd, env, timeout):
    """uv を動かす。証明書のエラー（社内のプロキシが通信を検査している環境など）なら、OS の証明書を使ってもう一度"""
    try:
        r = run(cmd, env=env, timeout=timeout)
        if r.returncode and re.search(r"certificate|UnknownIssuer|invalid peer", r.stdout + r.stderr, re.I):
            r = run(cmd, env=dict(env, UV_SYSTEM_CERTS="1", UV_NATIVE_TLS="1"), timeout=timeout)
        return r
    except (OSError, subprocess.SubprocessError) as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def uv_request():
    """uv に頼む Python。Windows は x64 を指定する（ARM64 の PC で uv が ARM64 版を選ぶと、cadquery などが入らない）"""
    return f"cpython-{PREFERRED}-windows-x86_64-none" if WIN else PREFERRED


def uv_fail(reason, out, ja, en):
    if out:
        print(out.strip(), file=sys.stderr, flush=True)
    msg(ja, en)
    STATE["uv_fail"] = reason
    return None


def uv_venv(venv, base, v, remove=False, soft=False):
    """uv で PREFERRED の Python を用意して、それで仮想環境を作る。remove のときは、Python を用意できてから今の仮想環境を消す
    （ダウンロードできないときに、動いている仮想環境を失わないため）。作れなければ STATE["uv_fail"] に理由を入れて None"""
    if os.path.isdir(venv) and not is_link(venv) and not is_venv(venv) and os.listdir(venv):
        sys.exit(L(f"!! {venv} は仮想環境ではないフォルダで、中にファイルがあります。--venv で、まだ無い場所か空のフォルダを指定してください",
                   f"!! {venv} is a folder with files that is not a virtual environment. "
                   "Pass --venv a path that does not exist yet, or an empty folder"))
    msg(f"PC の Python {ver_text(v)} では STEP のエクスポートに要る cadquery が確実には入らないので、"
        f"monozukuri 用に Python {PREFERRED} を用意します（~/.monozukuri/python。PC の Python には触りません）",
        f"cadquery (needed to export STEP) may not install on your Python {ver_text(v)}, so monozukuri gets its own "
        f"Python {PREFERRED} (~/.monozukuri/python; your own Python is left as it is)")
    uv, old = find_uv()
    if not uv and old:
        msg(f"uv {old} は古いので、monozukuri 用に新しい uv を ~/.monozukuri/bin に入れます（PC の uv には触りません）",
            f"uv {old} is too old, so monozukuri installs a newer uv in ~/.monozukuri/bin (your own uv is left as it is)")
    uv = uv or install_uv(base)
    if not uv:
        STATE["uv_fail"] = "no_uv"
        return None
    msg(f"uv: {uv}", f"uv: {uv}")
    env, req = uv_env(), uv_request()
    r = uv_run([uv, "python", "install", req], env, 1800)
    if r.returncode:
        return uv_fail("download", r.stdout + r.stderr,
                       f"!! uv で Python {PREFERRED} を用意できませんでした（理由は上の uv のメッセージ。ダウンロードにはネットワークが要ります）",
                       f"!! uv could not get Python {PREFERRED} (see uv's message above; the download needs the network)")
    if remove and not remove_venv(venv, soft=soft):
        STATE["uv_fail"] = "busy"          # 今の仮想環境を消せなかった（そのまま使う）
        return None
    if os.path.isdir(venv) and not is_link(venv) and not os.listdir(venv):
        os.rmdir(venv)
    os.makedirs(os.path.dirname(venv), exist_ok=True)
    r = uv_run([uv, "venv", "--python", req, venv], env, 900)
    vpy = venv_python(venv)
    if r.returncode or not in_range(py_version(vpy)):
        discard(venv)
        return uv_fail("venv", r.stdout + r.stderr, "!! uv で仮想環境を作れませんでした（上のメッセージを確認）",
                       "!! uv could not create the virtual environment (see the message above)")
    if WIN:
        p = run([vpy, "-c", "import sysconfig; print(sysconfig.get_platform())"], timeout=60).stdout.strip()
        if p != "win-amd64":
            discard(venv)
            return uv_fail("venv", "", f"!! uv が用意した Python が x64 版ではありません（{p}）",
                           f"!! The Python that uv got is not x64 ({p})")
    # pip は PyPI からではなく、その Python に入っている ensurepip から入れる（社内のミラーだけの環境でも通る）
    r = run([vpy, "-m", "ensurepip", "--upgrade"], timeout=600)
    if r.returncode:
        discard(venv)
        return uv_fail("venv", r.stdout + r.stderr, "!! 仮想環境に pip を入れられませんでした",
                       "!! Could not install pip into the virtual environment")
    return vpy


# ---------------------------------------------------------------- 仮想環境
def upgrade_pip(vpy):
    r = run([vpy, "-m", "pip", "install", "-q", "--upgrade", "pip"], timeout=600)
    if r.returncode:
        print(r.stderr, file=sys.stderr)
        msg("!! pip を新しくできませんでした（続けます）", "!! Could not upgrade pip (continuing)")


def uv_done(venv, vpy):
    upgrade_pip(vpy)
    write_marker(venv, "uv")
    msg(f"作りました（uv の Python {full_version(vpy)}）", f"Created (uv's Python {full_version(vpy)})")
    return vpy


def make_venv(venv, base, use_uv=True, rebuild=False):
    """仮想環境を用意して、その Python のパスを返す。作れなければ止める。
    元の Python が範囲外なら（use_uv のとき）uv で PREFERRED の Python を用意して作り、だめなら元の Python で作る"""
    vpy = venv_python(venv)
    say(f"Python の仮想環境（{venv}）", f"Python virtual environment ({venv})")
    clean_old(venv)
    builds_from_base = not use_uv or in_range(py_version(base))     # 元の Python で作ることになるか
    if rebuild and os.path.lexists(venv):
        msg("消して作り直します（--rebuild-venv）", "Deleting and recreating it (--rebuild-venv)")
        guard_delete(venv, base)
        if builds_from_base:
            arm_stop()
        remove_venv(venv)
    clear = False
    if os.path.lexists(vpy) or is_venv(venv):
        vv = py_version(vpy)
        if vv and use_uv and not in_range(vv) and read_marker(venv).get("wanted_uv"):
            # 前の実行で uv を使えず、範囲外の元の Python で作ったもの。作り直せるなら作り直し、だめなら今のまま使う
            bv = py_version(base)
            how_ja = f"今の PC の Python {ver_text(bv)} で作り直します" if in_range(bv) else "uv で作り直します"
            how_en = f"rebuilding it from your Python {ver_text(bv)}" if in_range(bv) else "rebuilding it with uv"
            msg(f"あります（Python {ver_text(vv)}。前の実行で uv を使えずに、PC の Python で作ったもの）。{how_ja}",
                f"Already exists (Python {ver_text(vv)}, made from your Python because uv was not available last time); "
                f"{how_en}")
            why = delete_blocked(venv, base)
            if why or (in_range(bv) and WIN and sysconfig.get_platform() == "win-arm64"):
                msg("今の仮想環境をそのまま使います" + (f"（{why}）" if why else ""),
                    "Keeping the current virtual environment" + (f" ({why})" if why else ""))
                return vpy
            if in_range(bv):
                if not remove_venv(venv, soft=True):     # 今の元の Python は範囲内なので、下でそれで作る
                    msg("今の仮想環境をそのまま使います", "Keeping the current virtual environment")
                    return vpy
            else:
                uvpy = uv_venv(venv, base, bv, remove=True, soft=True)
                if uvpy:
                    return uv_done(venv, uvpy)
                if os.path.exists(vpy):              # uv が無い・ダウンロードできない・消せない：今のまま
                    msg("今の仮想環境をそのまま使います", "Keeping the current virtual environment")
                    return vpy
                clear = is_venv(venv)                # 消した後に uv が失敗した：下で元の Python で作り直す
        elif vv:
            msg(f"あります（Python {ver_text(vv)}）", f"Already exists (Python {ver_text(vv)})")
            return vpy
        else:
            # Windows の Scripts\python.exe は、元の Python を消すと動かなくなる（ファイルは残る）。mac・Linux ではリンクが切れる
            msg("あるが動かないので作り直します（元の Python を消したか動かした可能性）",
                "Exists but does not run, so it is rebuilt (its base Python was probably removed or moved)")
            guard_delete(venv, base)
            clear = True
    v = py_version(base)
    if use_uv and not in_range(v) and not STATE["uv_fail"]:
        uvpy = uv_venv(venv, base, v, remove=clear and is_venv(venv))
        if uvpy:
            return uv_done(venv, uvpy)
        clear = is_venv(venv)          # 壊れた仮想環境が残っている、または uv が途中まで作ったもの
    if use_uv and not in_range(v) and v and v >= MIN_RUN:
        arm_stop()
        fail = STATE["uv_fail"]
        again = (L("uv を入れてからもう一度 setup.py を実行すると、作り直します", "install uv and run setup.py again to rebuild it")
                 if fail == "no_uv" else
                 L(f"Python {PREFERRED} をダウンロードできる所でもう一度 setup.py を実行すると、作り直します",
                   f"run setup.py again where Python {PREFERRED} can be downloaded to rebuild it")
                 if fail == "download" else
                 L("上のメッセージの原因を直してから setup.py --rebuild-venv を実行すると、uv で作り直します",
                   "fix the cause shown above, then run setup.py --rebuild-venv to rebuild it with uv"))
        msg(f"PC の Python {ver_text(v)} で仮想環境を作ります（STEP は使えないことがあります。STL のモックと確認ページは使えます）。" + again,
            f"Making the virtual environment from your Python {ver_text(v)} (STEP may not work; STL mocks and the "
            f"review page do). Later, {again}")
    if not v or v < MIN_RUN:
        fail = STATE["uv_fail"]
        if not use_uv:
            how_ja, how_en = "--no-uv を外すと、uv で Python 3.12 を用意します。または ", "Without --no-uv, uv gets Python 3.12. Or "
        elif fail == "no_uv":
            how_ja = f"uv を入れてもう一度実行すると、monozukuri 用に Python {PREFERRED} を用意します（{uv_installer()}）。または "
            how_en = f"Install uv and run this again, and it gets Python {PREFERRED} for monozukuri ({uv_installer()}). Or "
        elif fail == "download":
            how_ja = (f"uv はありますが、Python {PREFERRED} のダウンロードにネットワークが要ります。AI のサンドボックスなら、許可を得て"
                      "サンドボックスの外でもう一度実行してください（プロキシの環境は HTTPS_PROXY）。または ")
            how_en = (f"uv is installed, but downloading Python {PREFERRED} needs the network. If the AI sandbox blocks it, "
                      "run this again outside the sandbox with permission (behind a proxy: HTTPS_PROXY). Or ")
        else:
            how_ja = "uv で仮想環境を作れませんでした（上のメッセージ）。--venv で別の場所を指定するか、"
            how_en = "uv could not create the virtual environment (see above). Pass another --venv path, or "
        sys.exit(L("!! Python 3.10 以上が要ります。" + how_ja
                   + ("python.org の Python 3.12 を入れて、py -3.12 scripts/setup.py で実行してください"
                      if WIN else "mac: brew install python@3.12 のあと、BASE_PYTHON=python3.12 で実行してください"),
                   "!! Python 3.10 or newer is required. " + how_en
                   + ("install Python 3.12 from python.org and run py -3.12 scripts/setup.py"
                      if WIN else "mac: brew install python@3.12, then run with BASE_PYTHON=python3.12")))
    if not in_range(v) and not use_uv:
        msg(f"注意: Python {ver_text(v)} は STEP まで使える範囲（{range_text()}）の外です（--no-uv）。"
            "cadquery が入らないことがあります", f"Note: Python {ver_text(v)} is outside the range that can export "
            f"STEP ({range_text()}) (--no-uv). cadquery may not install")
    arm_stop()
    win_python_notes(base)
    os.makedirs(os.path.dirname(venv), exist_ok=True)
    r = run([base, "-m", "venv"] + (["--clear"] if clear else []) + [venv], timeout=600)
    if r.returncode or not os.path.exists(vpy):
        print(r.stdout + r.stderr, file=sys.stderr)
        sys.exit(L("!! 仮想環境を作れませんでした", "!! Could not create the virtual environment") + server_hint())
    upgrade_pip(vpy)
    # uv が無い・ダウンロードできなかったときだけ、次の実行で uv を試す（uv で仮想環境を作れなかったときは、毎回作り直さない）
    write_marker(venv, "base", wanted_uv=use_uv and not in_range(v) and STATE["uv_fail"] in ("no_uv", "download"))
    msg(f"作りました（元の Python: {ver_text(v)}）", f"Created (base Python: {ver_text(v)})")
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
    """import できるか。'ok'／'missing'（そのモジュールが無い）／読み込めないときはエラーの1行。
    cadquery が入っていて、中で使う OCP が無いとき（No module named 'OCP'）は missing ではなくエラーにする"""
    try:
        r = run([py, "-c", f"import {mod}"], timeout=300)
    except subprocess.TimeoutExpired:
        return "timeout"
    if r.returncode == 0:
        return "ok"
    if f"No module named '{mod}'" in r.stderr:
        return "missing"
    return last_line(r.stderr) or "error"


def broken_hint():
    if WIN:
        msg("  DLL を読み込めないときは、Microsoft Visual C++ 再頒布可能パッケージを入れる："
            "winget install -e --id Microsoft.VCRedist.2015+.x64",
            "  If a DLL cannot be loaded, install the Microsoft Visual C++ Redistributable: "
            "winget install -e --id Microsoft.VCRedist.2015+.x64")


def packages(py, with_cad):
    """入れて確かめる。cadquery の状態を返す：'ok'／'skip'（--no-cad）／入らない・読み込めない理由"""
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
    if not with_cad:
        return "skip"
    st = probe(py, "cadquery")
    if st == "missing":
        msg("cadquery を入れる（数分かかります）", "Installing cadquery (takes a few minutes)")
        installed = pip_install(py, [CAD_REQ])
        st = probe(py, "cadquery")
        if st == "ok":
            msg("入れました", "Installed")
        elif not installed or st == "missing":
            msg("!! cadquery を入れられませんでした（モックは STL だけになります）",
                "!! Could not install cadquery (mocks will be STL only)")
        else:
            msg(f"!! cadquery は入ったが読み込めません（モックは STL だけになります）: {st}",
                f"!! cadquery was installed but cannot be loaded (mocks will be STL only): {st}")
            broken_hint()
    elif st != "ok":
        msg(f"!! cadquery は入っているが読み込めません: {st}", f"!! cadquery is installed but cannot be loaded: {st}")
        broken_hint()
    return st


def step_hint(py, cad, mode, how, use_uv):
    """STEP が使えないとき、Python の版が範囲外なら直し方を出す。mode は venv／direct（--python など）／plain（仮想環境なし）。
    how は direct・plain になった理由（python：--python、no-venv：--no-venv）。モジュールが無い（入らない）とき以外は
    版のせいにしない（DLL・共有ライブラリのエラーなど）"""
    if not (cad == "missing" or "No module named" in cad):
        return                     # DLL・共有ライブラリなど、版のせいではないエラー（上にエラーを出してある）
    v = py_version(py)
    if not v or in_range(v):
        return
    head = L(f"  Python {ver_text(v)} は STEP まで使える範囲（{range_text()}）の外です。",
             f"  Python {ver_text(v)} is outside the range that can export STEP ({range_text()}). ")
    if mode == "venv":
        fail = STATE["uv_fail"]
        if fail == "no_uv":
            tail = L(f"uv を入れてから（{uv_installer()}）もう一度 setup.py を実行すると、uv で Python {PREFERRED} の仮想環境に作り直します",
                     f"Install uv ({uv_installer()}) and run setup.py again to rebuild it with Python {PREFERRED} from uv")
        elif fail == "download":
            tail = L(f"Python {PREFERRED} をダウンロードできる所でもう一度 setup.py を実行すると、作り直します",
                     f"Run setup.py again where Python {PREFERRED} can be downloaded to rebuild it")
        elif fail:
            tail = L("上の uv のメッセージの原因を直してから setup.py --rebuild-venv を実行すると、STEP が使えるようになります",
                     "Fix the cause in uv's message above, then run setup.py --rebuild-venv to make STEP work")
        elif not use_uv:
            tail = L("--no-uv を外して setup.py --rebuild-venv を実行すると、STEP が使えるようになります",
                     "Run setup.py --rebuild-venv without --no-uv to make STEP work")
        else:
            tail = L("setup.py --rebuild-venv で作り直すと、STEP が使えるようになります（PC の Python で実行）",
                     "Rebuild it with setup.py --rebuild-venv (run with your own Python) to make STEP work")
    else:
        tail = L(f"--venv ~/.monozukuri/venv を付けて実行すると、uv で Python {PREFERRED} を用意して STEP を使えるようにします",
                 f"Run with --venv ~/.monozukuri/venv and uv gets Python {PREFERRED} so STEP works") \
            + {"python": L("（--python は外す）", " (drop --python)"), "no-venv": L("（--no-venv は外す）", " (drop --no-venv)")}.get(how, "")
    print(head + tail, flush=True)


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
    ap.add_argument("--rebuild-venv", action="store_true")
    ap.add_argument("--no-uv", action="store_true")
    a = ap.parse_args()
    for v in (a.lang, os.environ.get("MONOZUKURI_LANG")):
        if v in ("ja", "en"):
            LANG = v
            break
    cache = os.path.expanduser(os.environ.get("MONOZUKURI_CACHE") or "~/.cache/monozukuri")
    os.makedirs(cache, exist_ok=True)

    # 直接入れる Python：--python、無ければ環境変数（--venv を付けたときは環境変数より --venv を優先）
    env_direct = os.environ.get("MONOZUKURI_PYTHON") or (None if WIN else os.environ.get("PYTHON"))
    direct, how = (a.python, "python") if a.python else ((None if a.venv else env_direct), "env")
    if a.venv and not a.python and env_direct:
        msg("--venv を付けたので、環境変数 MONOZUKURI_PYTHON・PYTHON は使いません",
            "--venv is given, so the MONOZUKURI_PYTHON / PYTHON environment variables are not used")
    if direct:
        mode = "direct"
        py = os.path.expanduser(direct)
        v = py_version(py)
        if not v or v < MIN_RUN:
            sys.exit(L(f"!! {py} は Python 3.10 以上として動きません", f"!! {py} does not run as Python 3.10 or newer"))
        msg(f"{py} に直接入れます（仮想環境と uv は使いません）",
            f"Installing into {py} directly (no virtual environment, no uv)")
    else:
        venv = None if a.no_venv else (a.venv or os.environ.get("MONOZUKURI_VENV"))
        if venv is None and not a.no_venv and sys.platform in ("darwin", "win32"):
            venv = os.path.join(MZ_HOME, "venv")
        if venv:
            mode = "venv"
            base = os.environ.get("BASE_PYTHON")
            if not base:
                # 仮想環境の Python で実行されたら、その元の Python を使う（--rebuild-venv で自分の元を消さないように）
                base = (getattr(sys, "_base_executable", "") if sys.prefix != sys.base_prefix else "") or sys.executable
            base = os.path.expanduser(base)
            py = make_venv(os.path.abspath(os.path.expanduser(venv)), shutil.which(base) or base,
                           use_uv=not a.no_uv, rebuild=a.rebuild_venv)
        else:
            mode, how = "plain", ("no-venv" if a.no_venv else "")
            py = sys.executable
            if sys.version_info[:2] < MIN_RUN:
                sys.exit(L(f"!! Python 3.10 以上が要ります（--venv ~/.monozukuri/venv を付けると、uv で Python {PREFERRED} を用意します）",
                           f"!! Python 3.10 or newer is required (with --venv ~/.monozukuri/venv, uv gets Python {PREFERRED})"))
    if a.rebuild_venv and mode != "venv":
        msg("--rebuild-venv は仮想環境を使うときだけ使えます（無視します）",
            "--rebuild-venv only applies when a virtual environment is used (ignored)")

    cad = packages(py, not a.no_cad)
    if cad not in ("ok", "skip"):
        step_hint(py, cad, mode, how, not a.no_uv)
    chromium(py)
    three(cache)

    say("動作確認", "Checking the setup")
    # 仮想環境でないとき（--python・仮想環境なし）は、そのことを env.json の python_source に残す（仮想環境なら中の記録を読む）
    child = dict(CHILD_ENV, MONOZUKURI_LANG=LANG)
    if mode != "venv":
        child["MONOZUKURI_PYTHON_SOURCE"] = "direct"
    r = subprocess.run([py, os.path.join(HERE, "check_env.py"), "--lang", LANG], env=child)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
