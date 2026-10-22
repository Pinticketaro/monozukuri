"""部分試作（3つめの関所）：モデルの一部分だけを切り出して、先に刷って・切って実物と合わせる。
例：USB の切り欠きの角、ネジ受け1つ、中身の角、分割した継ぎ目。全体を刷る前に、取り合いを安く確かめる。

範囲の決め方（座標はモデルのまま。平面図・断面図の目盛りと同じ mm）
  --box x0,y0,z0,x1,y1,z1        箱で指定
  --around x,y[,z] --size w,d[,h]  点のまわり（高さを省くと全高）
  --region usb                     寸法ファイルの meta.regions.usb = {"box": [x0,y0,z0,x1,y1,z1], "note": "…"}
  --list                           部品ごとの範囲（mm）を出すだけ。どこを切るか決めるときに

出力：out/<版>/partial/<名前>/
  NN_<キー>.stl     切り出した部品（3Dプリント用。範囲の面で平らに切ってある）
  NN_<キー>.step    STEP が元にあり CadQuery が入っていれば、正確なソリッドで切ったもの（Fusion で開ける）
  scene.json        切り出した部品の一覧（作り方・材料を引き継ぐ。review-page・fab_check にそのまま渡せる）
  fab/              レーザーの板が含まれていれば、その部分の SVG / DXF と 3MF（export_fab.py）
  preview.png       全体の中のどこを切り出したか（全体は薄く、切り出した所に濃い色）
  pieces.png        切り出した部品だけの外観
  partial.md        範囲・大きさ・何を確かめるか
使い方
  python3 tools/cut_region.py v05 --name usb --around 80,52 --size 30,20
  python3 tools/cut_region.py v05 --region usb --parts frame
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fabkit as fk  # noqa: E402


def floats(s, n=None):
    v = [float(x) for x in s.split(",")]
    if n and len(v) not in n:
        raise SystemExit(f"数の個数が違います: {s}")
    return v


def cut_mesh(mesh, lo, hi):
    """箱との共通部分。manifold3d で切り、だめなら6つの平面で切って蓋をする。"""
    try:
        import manifold3d as m3
        mm = m3.Manifold(m3.Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
                                 tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))
        if str(mm.status()).endswith("NoError") and not mm.is_empty():
            bx = m3.Manifold.cube(list(np.subtract(hi, lo))).translate(list(lo))
            r = (mm ^ bx).to_mesh()
            return trimesh.Trimesh(np.asarray(r.vert_properties)[:, :3], np.asarray(r.tri_verts), process=True)
    except Exception:
        pass
    m = mesh.copy()
    for ax in range(3):
        n = np.zeros(3)
        n[ax] = 1
        o = np.zeros(3)
        o[ax] = lo[ax]
        m = m.slice_plane(o, n, cap=True)
        if m.is_empty:
            return m
        o[ax] = hi[ax]
        m = m.slice_plane(o, -n, cap=True)
        if m.is_empty:
            return m
    return m


def cut_step(src, lo, hi, out):
    """STEP（正確なソリッド）を箱で切る。CadQuery が無い・失敗したら False"""
    try:
        import cadquery as cq
        shp = cq.importers.importStep(src)
        bx = cq.Workplane("XY").box(*np.subtract(hi, lo), centered=False).translate(tuple(lo))
        r = shp.intersect(bx)
        if not r.vals() or r.val().Volume() <= 1e-6:
            return False
        cq.exporters.export(r, out, exportType="STEP")
        return True
    except Exception:
        return False


def step_source(part):
    f = part["file"]
    if f.lower().endswith((".step", ".stp")):
        return f
    # モックの parts/NN_key.stl には step/NN_key.step が対になっている
    d, b = os.path.split(f)
    cand = os.path.join(os.path.dirname(d), "step", os.path.splitext(b)[0] + ".step")
    return cand if os.path.exists(cand) else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    fk.add_common_args(ap)
    ap.add_argument("--name", help="切り出しの名前（英数字。フォルダ名になる）")
    ap.add_argument("--box")
    ap.add_argument("--around")
    ap.add_argument("--size")
    ap.add_argument("--region")
    ap.add_argument("--parts", help="キーをカンマ区切りで（既定：範囲にかかる部品すべて。加工しない部品は除く）")
    ap.add_argument("--with-none", action="store_true", help="加工しない部品（中身など）も含める（合わせの確認用）")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()

    prj = fk.open_project(a)
    meshes = {p["key"]: prj.mesh(p) for p in prj.parts}
    allb = np.array([m.bounds for m in meshes.values()])
    gmin, gmax = allb[:, 0, :].min(axis=0), allb[:, 1, :].max(axis=0)
    if a.list:
        print(f"全体 X {gmin[0]:.1f}〜{gmax[0]:.1f}  Y {gmin[1]:.1f}〜{gmax[1]:.1f}  Z {gmin[2]:.1f}〜{gmax[2]:.1f} mm")
        for p in prj.parts:
            b = meshes[p["key"]].bounds
            print(f"  {p['key']:<16} {p['name']}（{fk.PROCESS_LABEL[p['process']]}）  X {b[0][0]:.1f}〜{b[1][0]:.1f}  "
                  f"Y {b[0][1]:.1f}〜{b[1][1]:.1f}  Z {b[0][2]:.1f}〜{b[1][2]:.1f}")
        for k, r in (prj.meta.get("regions") or {}).items():
            print(f"  範囲 {k}: {r.get('box')} {r.get('note', '')}")
        return

    note = ""
    if a.region:
        r = (prj.meta.get("regions") or {}).get(a.region)
        if not r:
            raise SystemExit(f"寸法ファイルの meta.regions に {a.region} がありません")
        lo, hi = r["box"][:3], r["box"][3:]
        note = r.get("note", "")
        name = a.name or a.region
    elif a.box:
        v = floats(a.box, (6,))
        lo, hi = v[:3], v[3:]
        name = a.name
    elif a.around and a.size:
        c = floats(a.around, (2, 3))
        s = floats(a.size, (2, 3))
        lo = [c[0] - s[0] / 2, c[1] - s[1] / 2, (c[2] - s[2] / 2) if len(c) == 3 and len(s) == 3 else gmin[2] - 1]
        hi = [c[0] + s[0] / 2, c[1] + s[1] / 2, (c[2] + s[2] / 2) if len(c) == 3 and len(s) == 3 else gmax[2] + 1]
        name = a.name
    else:
        raise SystemExit("範囲を --box か --around と --size か --region で指定してください（--list で部品の範囲がわかる）")
    if not name:
        raise SystemExit("--name を付けてください（例 usb、corner）")
    lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)

    out = os.path.join(prj.root, "out", prj.ver, "partial", name)
    os.makedirs(out, exist_ok=True)
    want = set(a.parts.split(",")) if a.parts else None
    scene = {"title": f"{prj.title} 部分試作「{name}」", "up": "z", "views": ["iso", "back", "top"], "parts": [], "notes": []}
    rows, made = [], []
    for p in prj.parts:
        if want and p["key"] not in want:
            continue
        if not want and p["process"] == "none" and not a.with_none:
            continue
        m = meshes[p["key"]]
        b = m.bounds
        if np.any(b[1] < lo) or np.any(b[0] > hi):
            continue
        piece = cut_mesh(m, lo, hi)
        if piece.is_empty or piece.volume < 1e-3:
            continue
        fn = f"{p['i'] + 1:02d}_{p['key']}.stl"
        piece.export(os.path.join(out, fn))
        sp = {"file": fn, "name": p["name"], "key": p["key"], "color": p["color"], "opacity": p["opacity"],
              "process": p["process"], "material": p["material"]}
        if p.get("t"):
            sp["t"] = p["t"]
        if p.get("print"):
            sp["print"] = p["print"]
        scene["parts"].append(sp)
        src = step_source(p)
        st = cut_step(src, lo, hi, os.path.join(out, fn[:-4] + ".step")) if src else False
        ex = piece.extents
        rows.append(f"| {p['name']} | {fk.PROCESS_LABEL[p['process']]} | {ex[0]:.1f}×{ex[1]:.1f}×{ex[2]:.1f} | "
                    f"{piece.volume / 1000:.1f} cm³ | {'あり' if st else '—'} |")
        made.append(p)
    if not made:
        raise SystemExit("範囲にかかる部品がありません（--list で部品の範囲を見る）")
    sj = os.path.join(out, "scene.json")
    json.dump(scene, open(sj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # レーザーの板が入っていれば、その部分の加工データも
    here = os.path.dirname(os.path.abspath(__file__))
    fabdir = os.path.join(out, "fab")
    if any(p["process"] in ("laser", "fdm") for p in made):
        cmd = [sys.executable, os.path.join(here, "export_fab.py"), "--root", prj.root, "--scene", sj, "--out", fabdir]
        if prj.params_path:
            cmd += ["--params", prj.params_path]
        subprocess.run(cmd, capture_output=True, text=True)

    # どこを切り出したかの外観
    png = None
    rs = fk.render_script()
    if rs and not a.no_render:
        specs = []
        tmp = os.path.join(out, "_whole")
        os.makedirs(tmp, exist_ok=True)
        hl = {"laser": "#2f7fc8", "fdm": "#e0703a", "none": "#6b6f73"}     # 切り出す所は作り方ごとの濃い色
        for p in prj.parts:
            f = os.path.join(tmp, f"{p['key']}.stl")
            meshes[p["key"]].export(f)
            specs.append(f"{f}:#c9ccc6:0.12")
        pieces = [f"{os.path.join(out, sp['file'])}:{hl.get(sp['process'], '#e0703a')}:0.95" for sp in scene["parts"]]
        png = os.path.join(out, "preview.png")
        r = subprocess.run([sys.executable, rs, *specs, *pieces, "--out", png, "--views", "iso,top,side",
                            "--title", f"{scene['title']}（青＝レーザー、橙＝3Dプリントの切り出す所）"], capture_output=True, text=True)
        if r.returncode != 0:
            png = None
        close = os.path.join(out, "pieces.png")
        subprocess.run([sys.executable, rs, *[f"{os.path.join(out, sp['file'])}:{sp['color']}:{sp['opacity']}" for sp in scene["parts"]],
                        "--out", close, "--views", "iso,back,top", "--title", f"{scene['title']}（切り出した部品）"],
                       capture_output=True, text=True)
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    md = [f"# {scene['title']}", "", note, "",
          f"範囲：X {lo[0]:.1f}〜{hi[0]:.1f}、Y {lo[1]:.1f}〜{hi[1]:.1f}、Z {lo[2]:.1f}〜{hi[2]:.1f} mm（モデルの座標）", "",
          "| 部品 | 作り方 | 大きさ | 体積 | STEP |", "|---|---|---|---|---|"] + rows + [
          "", "## 確かめること", "",
          "- 実物の部品（基板・USB ケーブル・ネジ・中身）を当てて、入るか・ガタつかないか・干渉しないか",
          "- USB-C はいちばん太いケーブルで（切り欠きはケーブル側の太さで決まる）",
          "- ネジ受けはインサートを入れてネジを締め、割れ・空回りがないか",
          "- 本番と同じ材料・同じ設定で作る。結果は写真（定規と一緒に）と `measurements/実測.md` に残し、確認ページに「部分試作」の版として載せる",
          "", "切り口は範囲の面で平らに切ってある。刷るときは切り口をベッドに向けると支えが要らないことが多い。"]
    if os.path.isdir(fabdir):
        md += ["", "加工データ：`fab/`（fab.md を参照）"]
    open(os.path.join(out, "partial.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(out)
    for r_ in rows:
        print(" ", r_)
    if png:
        print(" ", png)


if __name__ == "__main__":
    main()
