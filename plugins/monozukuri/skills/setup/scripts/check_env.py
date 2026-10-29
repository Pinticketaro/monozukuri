"""monozukuri の環境チェック。足りないものと、テストレンダリングの結果を表で出す。
結果は ~/.cache/monozukuri/env.json にも保存する（日本語フォントの場所、three.js の場所）。
使い方: python3 check_env.py [--no-render] [--lang ja|en]
  言葉（表・メッセージ・テストレンダリング）は --lang、無ければ環境変数 MONOZUKURI_LANG、どれも無ければ ja。
"""
import importlib
import json
import os
import subprocess
import sys
import tempfile

CACHE = os.environ.get("MONOZUKURI_CACHE", os.path.expanduser("~/.cache/monozukuri"))
PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
RENDER = os.path.join(PLUGIN, "skills", "review-page", "scripts", "render_model.py")

# 日本語が出せるフォント（見つかった順に使う）
CJK_FONTS = ["Noto Sans CJK JP", "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic", "IPAexGothic",
             "Noto Sans JP", "Source Han Sans JP", "Noto Sans CJK TC", "Noto Sans CJK SC", "Noto Sans CJK KR"]


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


def same_python(path):
    """path の Python が今の Python と同じ環境か。仮想環境は実体（realpath）が元の Python と同じなので、sys.prefix で比べる"""
    try:
        r = subprocess.run([path, "-c", "import sys; print(sys.prefix)"], capture_output=True, text=True, timeout=30)
        return r.returncode == 0 and os.path.realpath(r.stdout.strip()) == os.path.realpath(sys.prefix)
    except Exception:
        return os.path.realpath(path) == os.path.realpath(sys.executable)


def main():
    try:
        # CadQuery は trimesh（が読む cascadio）より先に読む。逆だと macOS では終わるときに落ちる（Abort trap）
        import cadquery  # noqa: F401
    except Exception:
        pass
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
        except Exception:
            row(label, False if required else None, L("未インストール", "not installed"))

    env = {"python": sys.executable, "three_dir": None, "cjk_font": None, "cjk_font_path": None}
    three = os.path.join(CACHE, "three", "node_modules", "three")
    if os.path.isfile(os.path.join(three, "build", "three.module.js")):
        env["three_dir"] = three
        row("three.js", True, three)
    else:
        row("three.js", False, L("setup.sh を実行", "run setup.sh"))

    try:
        from matplotlib import font_manager
        names = {}
        for f in font_manager.findSystemFonts():
            try:
                names.setdefault(font_manager.FontProperties(fname=f).get_name(), f)
            except Exception:
                pass
        for n in CJK_FONTS:
            if n in names:
                env["cjk_font"], env["cjk_font_path"] = n, names[n]
                break
        # 英語のときは図に日本語が出ないので、無くても任意
        found = env["cjk_font"] is not None
        row(L("日本語フォント", "Japanese font"), found if found or LANG == "ja" else None,
            env["cjk_font"] or L("見つからない（図の日本語が□になる）", "not found (Japanese text in figures shows as boxes)"))
    except Exception as e:
        row(L("日本語フォント", "Japanese font"), False, str(e))

    os.makedirs(CACHE, exist_ok=True)
    json.dump(env, open(os.path.join(CACHE, "env.json"), "w"), ensure_ascii=False, indent=2)

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
            cmd = [sys.executable, RENDER, f"{stl}:#7a9a88", "--out", out, "--title", L("テストレンダリング", "Test render")]
            # render_model.py が --lang を受けるときだけ渡す（古い版でも動くように）
            h = subprocess.run([sys.executable, RENDER, "--help"], capture_output=True, text=True, timeout=60)
            if "--lang" in h.stdout:
                cmd += ["--lang", LANG]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                               env=dict(os.environ, MONOZUKURI_LANG=LANG))
            ok = r.returncode == 0 and os.path.getsize(out) > 10000
            row(L("テストレンダリング", "Test render"), ok, out if ok else (r.stderr.strip().splitlines() or [L("失敗", "failed")])[-1])
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
    import shutil
    sys_py = shutil.which("python3")
    if not sys_py or not same_python(sys_py):
        print(L(f"monozukuri のスクリプトは、python3 の代わりに次の Python で実行してください：\n  {sys.executable}",
                f"Run the monozukuri scripts with this Python instead of python3:\n  {sys.executable}"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
