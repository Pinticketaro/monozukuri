"""monozukuri の環境チェック。足りないものと、テスト描画の結果を表で出す。
結果は ~/.cache/monozukuri/env.json にも保存する（日本語フォントの場所、three.js の場所）。
使い方: python3 check_env.py [--no-render]
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

rows = []


def row(name, ok, note=""):
    rows.append((name, "OK" if ok else ("任意" if ok is None else "NG"), note))


def main():
    try:
        # CadQuery は trimesh（が読む cascadio）より先に読む。逆だと macOS では終わるときに落ちる（Abort trap）
        import cadquery  # noqa: F401
    except Exception:
        pass
    row("Python", sys.version_info[:2] >= (3, 10), f"{sys.version.split()[0]}  {sys.executable}")
    for mod, label, required in [("numpy", "numpy", True), ("shapely", "shapely（2Dの形）", True),
                                 ("matplotlib", "matplotlib（断面・平面図）", True),
                                 ("manifold3d", "manifold3d（モックの立体）", True),
                                 ("trimesh", "trimesh（STL/OBJ/STEPの読み込み）", True),
                                 ("networkx", "networkx（断面・平面図で輪郭をたどる）", True),
                                 ("PIL", "Pillow（画像の比較）", True),
                                 ("playwright", "playwright（外観の描画）", True),
                                 ("cascadio", "cascadio（STEPの読み込み）", False),
                                 ("cadquery", "cadquery（モックの STEP 書き出し。無いと STL だけ）", False)]:
        try:
            m = importlib.import_module(mod)
            row(label, True, getattr(m, "__version__", ""))
        except Exception:
            row(label, False if required else None, "未インストール")

    env = {"python": sys.executable, "three_dir": None, "cjk_font": None, "cjk_font_path": None}
    three = os.path.join(CACHE, "three", "node_modules", "three")
    if os.path.isfile(os.path.join(three, "build", "three.module.js")):
        env["three_dir"] = three
        row("three.js", True, three)
    else:
        row("three.js", False, "setup.sh を実行")

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
        row("日本語フォント", env["cjk_font"] is not None, env["cjk_font"] or "見つからない（図の日本語が□になる）")
    except Exception as e:
        row("日本語フォント", False, str(e))

    os.makedirs(CACHE, exist_ok=True)
    json.dump(env, open(os.path.join(CACHE, "env.json"), "w"), ensure_ascii=False, indent=2)

    if "--no-render" not in sys.argv and env["three_dir"]:
        try:
            import trimesh
            tmp = tempfile.mkdtemp()
            stl = os.path.join(tmp, "cube.stl")
            trimesh.creation.box((60, 40, 20)).export(stl)
            out = os.path.join(tmp, "test.png")
            r = subprocess.run([sys.executable, RENDER, f"{stl}:#7a9a88", "--out", out, "--title", "テスト描画"],
                               capture_output=True, text=True, timeout=180)
            ok = r.returncode == 0 and os.path.getsize(out) > 10000
            row("テスト描画", ok, out if ok else (r.stderr.strip().splitlines() or ["失敗"])[-1])
        except Exception as e:
            row("テスト描画", False, str(e))

    w = max(len(r[0]) for r in rows)
    for name, st, note in rows:
        print(f"{st:3}  {name.ljust(w)}  {note}")
    bad = [r for r in rows if r[1] == "NG"]
    print("\n準備できています" if not bad else f"\n{len(bad)}件の不足があります")
    import shutil
    sys_py = shutil.which("python3")
    if not sys_py or os.path.realpath(sys_py) != os.path.realpath(sys.executable):
        print(f"monozukuri のスクリプトは、python3 の代わりに次の Python で実行してください：\n  {sys.executable}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
