"""monozukuri の環境チェック。足りないものと、テストレンダリングの結果を表で出す。
結果は ~/.cache/monozukuri/env.json にも保存する（環境変数 MONOZUKURI_CACHE があればそこ。
日本語フォントの場所、three.js の場所、使う Python。python_posix は区切りを / にした同じパス）。
最後の行に、monozukuri のスクリプトを実行する Python を出す（「…次の Python で実行する: <パス>」。空白があれば " で囲む）。
使い方: python check_env.py [--no-render] [--lang ja|en]
  言葉（表・メッセージ・テストレンダリング）は --lang、無ければ環境変数 MONOZUKURI_LANG、どれも無ければ ja。
"""
import importlib
import json
import os
import subprocess
import sys
import tempfile

# PowerShell は ~ を展開しない。相対パスは今の作業フォルダからの絶対パスにする（テストレンダリングは別のフォルダで実行する）
CACHE = os.path.abspath(os.path.expanduser(os.environ.get("MONOZUKURI_CACHE") or "~/.cache/monozukuri"))
SKILLS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # スキルのフォルダが並ぶ所
RENDER = os.path.join(SKILLS, "monozukuri-review-page", "scripts", "render_model.py")

# 日本語が出せるフォント（見つかった順に使う）。Meiryo・BIZ UDGothic・MS Gothic は Windows で Yu Gothic が無いとき
CJK_FONTS = ["Noto Sans CJK JP", "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic", "IPAexGothic",
             "Noto Sans JP", "Source Han Sans JP", "Meiryo", "BIZ UDGothic", "MS Gothic",
             "Noto Sans CJK TC", "Noto Sans CJK SC", "Noto Sans CJK KR"]


def resolve_lang(explicit=None, data=None):
    for v in (explicit, data, os.environ.get("MONOZUKURI_LANG")):
        if v in ("ja", "en"):
            return v
    return "ja"


def lang_arg(argv):
    """--lang en / --lang=en を拾う（無ければ None）"""
    for i, a in enumerate(argv):
        if a == "--lang" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--lang="):
            return a.split("=", 1)[1]
    return None


LANG = resolve_lang(lang_arg(sys.argv[1:]))


def L(ja, en):
    return en if LANG == "en" else ja


rows = []


def row(name, ok, note=""):
    rows.append((name, "OK" if ok else (L("任意", "opt") if ok is None else "NG"), note))


def import_note(mod, e):
    """読み込めなかった理由。入っていなければ「未インストール」。入っているのに読めないとき
    （Windows の DLL load failed、足りない依存パッケージなど）はエラーの文をそのまま出す"""
    if isinstance(e, ModuleNotFoundError) and e.name == mod:      # manifold3d._manifold が無いなどは、入っているのに読めない
        return L("未インストール", "not installed")
    msg = next((s.strip() for s in str(e).splitlines() if s.strip()), "")
    return L("読み込めない: ", "cannot load: ") + f"{type(e).__name__}: {msg}"[:300]


def find_cjk_font():
    """日本語フォントの (名前, ファイル)。同じ名前のファイルが複数ある（ウエイト違い）ときは標準のウエイト（400）に
    いちばん近いものを、同じならパスの順で選ぶ（findSystemFonts の順は実行ごとに変わるので並べ替える）"""
    from matplotlib import font_manager
    found = {}
    for f in sorted(font_manager.findSystemFonts()):
        try:
            n = font_manager.FontProperties(fname=f).get_name()
        except Exception:
            continue
        if n not in CJK_FONTS:
            continue
        try:
            e = font_manager.ttfFontProperty(font_manager.get_font(f))
            w = abs(e.weight - 400) if isinstance(e.weight, int) else 0
            key = (w, e.style != "normal", f)
        except Exception:
            key = (1000, True, f)
        if n not in found or key < found[n]:
            found[n] = key
    for n in CJK_FONTS:
        if n in found:
            return n, found[n][2]
    return None, None


def main():
    for _s in (sys.stdout, sys.stderr):        # Windows のパイプは ANSI コードページになるので UTF-8 にそろえる
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    early = {}
    try:
        # CadQuery は trimesh（が読む cascadio）より先に読む。逆だと macOS では終わるときに落ちる（Abort trap）
        import cadquery  # noqa: F401
    except Exception as e:
        early["cadquery"] = e          # 2回目の読み込みより、1回目のエラーのほうが元の理由
    row("Python", sys.version_info[:2] >= (3, 10), f"{sys.version.split()[0]}  {sys.executable}")
    for mod, label, required in [("numpy", "numpy", True),
                                 ("shapely", L("shapely（2Dの形）", "shapely (2D shapes)"), True),
                                 ("matplotlib", L("matplotlib（断面・平面図）", "matplotlib (sections, plan views)"), True),
                                 ("manifold3d", L("manifold3d（モックの立体）", "manifold3d (mock solids)"), True),
                                 ("trimesh", L("trimesh（STL/OBJ/STEPの読み込み）", "trimesh (reading STL/OBJ/STEP)"), True),
                                 ("networkx", L("networkx（断面・平面図で輪郭をたどる）",
                                                "networkx (tracing outlines for sections, plan views)"), True),
                                 ("PIL", L("Pillow（画像の比較）", "Pillow (image comparison)"), True),
                                 ("playwright", L("playwright（外観のレンダリング）", "playwright (rendering the 3D views)"), True),
                                 ("cascadio", L("cascadio（STEPの読み込み）", "cascadio (reading STEP)"), False),
                                 ("cadquery", L("cadquery（モックの STEP エクスポート。無いと STL だけ）",
                                                "cadquery (STEP export of mocks; without it, STL only)"), False)]:
        try:
            m = importlib.import_module(mod)
            row(label, True, getattr(m, "__version__", ""))
        except Exception as e:
            row(label, False if required else None, import_note(mod, early.get(mod, e)))

    env = {"python": sys.executable, "python_posix": sys.executable.replace(os.sep, "/"),
           "three_dir": None, "cjk_font": None, "cjk_font_path": None}
    three = os.path.join(CACHE, "three", "node_modules", "three")
    if os.path.isfile(os.path.join(three, "build", "three.module.js")):
        env["three_dir"] = three
        row("three.js", True, three)
    else:
        row("three.js", False, L("monozukuri-setup スキルを実行", "run the monozukuri-setup skill"))

    try:
        env["cjk_font"], env["cjk_font_path"] = find_cjk_font()
        # 英語のときは図に日本語が出ないので、無くても任意
        found = env["cjk_font"] is not None
        row(L("日本語フォント", "Japanese font"), found if found or LANG == "ja" else None,
            env["cjk_font"] or L("見つからない（図の日本語が□になる）", "not found (Japanese text in figures shows as boxes)"))
    except Exception as e:
        row(L("日本語フォント", "Japanese font"), False, str(e))

    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, "env.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)

    if "--no-render" not in sys.argv and env["three_dir"]:
        try:
            import numpy as np
            import trimesh
            tmp = tempfile.mkdtemp()
            stl = os.path.join(tmp, "steps.stl")
            # 段差・斜面・面取りのある形（影と、右側面の図の明暗を確かめる）
            T = trimesh.transformations.translation_matrix
            hull = lambda pts: trimesh.convex.convex_hull(np.array(pts, dtype=float))
            trimesh.util.concatenate([
                trimesh.creation.box((60, 40, 8), T((0, 0, 4))),
                trimesh.creation.box((60, 26, 8), T((0, 7, 12))),
                hull([[-30, 8, 16], [30, 8, 16], [-30, 20, 16], [30, 20, 16],             # いちばん上の段（右端を45°で面取り）
                      [-30, 8, 24], [22, 8, 24], [-30, 20, 24], [22, 20, 24]]),
                hull([[-30, -20, 8], [30, -20, 8], [-30, -6, 8], [30, -6, 8], [-30, -6, 16], [30, -6, 16]]),   # 手前の斜面
            ]).export(stl)
            out = os.path.join(tmp, "test.png")
            # 部品は tmp からの相対パスで渡し、tmp で実行する。「ファイル:色」の : と
            # Windows のドライブ文字（C:\...）がぶつからないように
            cmd = [sys.executable, RENDER, f"{os.path.basename(stl)}:#7a9a88", "--out", out,
                   "--title", L("テストレンダリング", "Test render")]
            # 子プロセスも UTF-8 で出す（Windows のパイプは ANSI コードページ）。three.js はここで確かめた場所を
            # 絶対パスで渡す（render_model.py は THREE_DIR を MONOZUKURI_CACHE より先に見る）
            child_env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", MONOZUKURI_LANG=LANG,
                             MONOZUKURI_CACHE=CACHE, THREE_DIR=three)
            # render_model.py が --lang を受けるときだけ渡す（古い版でも動くように）
            h = subprocess.run([sys.executable, RENDER, "--help"], capture_output=True, encoding="utf-8",
                               errors="replace", timeout=60, env=child_env)
            if "--lang" in (h.stdout or ""):
                cmd += ["--lang", LANG]
            r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=180,
                               cwd=tmp, env=child_env)
            ok = r.returncode == 0 and os.path.isfile(out) and os.path.getsize(out) > 10000
            if os.name == "nt":
                # Windows: 8.3 の短い名前や、Microsoft Store 版 Python の TEMP のリダイレクトを、実際の場所に直す
                out = os.path.realpath(out)
            row(L("テストレンダリング", "Test render"), ok,
                out if ok else ((r.stderr or "").strip().splitlines() or [L("失敗", "failed")])[-1])
        except Exception as e:
            row(L("テストレンダリング", "Test render"), False, str(e))

    w = max(len(r[0]) for r in rows)
    for name, st, note in rows:
        print(f"{st:3}  {name.ljust(w)}  {note}")
    bad = [r for r in rows if r[1] == "NG"]
    if not bad:
        print(L("\n準備できています", "\nReady"))
    else:
        print(L(f"\n{len(bad)}件の不足があります", f"\n{len(bad)} item is missing" if len(bad) == 1 else f"\n{len(bad)} items are missing"))
    # 最後の行。AI が読み取って、プロジェクトのスクリプトをこの Python で実行する（空白があれば " で囲む）。
    # Windows では区切りを / にする（Git Bash は引用符の外の \ を消す。PowerShell と python.exe は / を受け付ける）
    py = env["python_posix"] if os.name == "nt" else sys.executable
    py = f'"{py}"' if " " in py else py
    print(L(f"monozukuri のスクリプトは次の Python で実行する: {py}",
            f"Run the monozukuri scripts with this Python: {py}"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
