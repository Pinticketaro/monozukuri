"""プロジェクト共通：寸法ファイルの読み込み、版番号、出力先。

寸法ファイルは params/params_vNN.json。1つの版の寸法はこのファイルだけに書く（ほかのスクリプトに数値を直接書かない）。
  params … 形の寸法（モックで決める）
  fab    … 加工の値（カーフ・実板厚・クリアランス・インサート穴など）。status が「初期値」のものは
           試し片（tools/coupons.py）で測って「実測」に置き換える
  P = load("v03").P      → P.outer_w のように値だけで使える
  load().labels          → 項目名（寸法表・差分に使う）
版を省くと、いちばん新しい版を使う。
"""
import glob
import json
import os
import re
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS = os.path.join(ROOT, "params")


def versions():
    vs = []
    for f in glob.glob(os.path.join(PARAMS, "params_v*.json")):
        m = re.search(r"params_(v\d+)\.json$", f)
        if m:
            vs.append(m.group(1))
    return sorted(vs, key=lambda v: int(v[1:]))


def latest():
    vs = versions()
    if not vs:
        raise SystemExit("params/ に寸法ファイルがありません")
    return vs[-1]


def version_from_argv():
    """コマンドの引数に v03 のような版があればそれ、なければ最新。"""
    for a in sys.argv[1:]:
        if re.fullmatch(r"v\d+", a):
            return a
    return latest()


def load(ver=None):
    ver = ver or latest()
    path = os.path.join(PARAMS, f"params_{ver}.json")
    d = json.load(open(path, encoding="utf-8"))
    # params（形の寸法）と fab（試し片で決める加工の値：カーフ・実板厚・クリアランスなど）を1つにまとめて使う
    items = {**d.get("params", {}), **d.get("fab", {})}
    vals = {k: (v["value"] if isinstance(v, dict) and "value" in v else v) for k, v in items.items()}
    labels = {k: (v.get("label", k) if isinstance(v, dict) else k) for k, v in items.items()}
    units = {k: (v.get("unit", "") if isinstance(v, dict) else "") for k, v in items.items()}
    fab = {k: v for k, v in d.get("fab", {}).items()}
    return SimpleNamespace(ver=ver, path=path, meta=d.get("meta", {}), P=SimpleNamespace(**vals),
                           labels=labels, units=units, fab=fab, raw=d)


def prev_version(ver):
    vs = versions()
    i = vs.index(ver) if ver in vs else len(vs)
    return vs[i - 1] if i > 0 else None


def out_dir(ver, *sub):
    d = os.path.join(ROOT, "out", ver, *sub)
    os.makedirs(d, exist_ok=True)
    return d


# ---------------------------------------------------------------- モックを作る（tools/mock.py から呼ぶ）
UP_DIRS = {"z": (0, 0, 1), "-z": (0, 0, -1), "x": (1, 0, 0), "-x": (-1, 0, 0), "y": (0, 1, 0), "-y": (0, -1, 0)}


def overhangs(mesh, deg=45.0, up="z", min_area=1.0):
    """3Dプリントでサポートが要りそうな面を探す。
    印刷の向き up（モデルのどの向きをベッドから上へ向けるか）で立てたとき、下向きで水平からの角度が deg より浅い面。
    ベッドに接する面（部品のいちばん下の面）は除く。つながった面ごとにまとめ、
    [{"area": mm², "angle": 水平からの角度, "z": 高さ, "x": X, "y": Y}, ...] を面積の大きい順に返す（位置はモデルの座標）。"""
    import numpy as np
    import trimesh
    R = trimesh.geometry.align_vectors(UP_DIRS.get(up, UP_DIRS["z"]), (0, 0, 1))
    m = mesh.copy()
    m.apply_transform(R)
    n = m.face_normals
    zmin = m.bounds[0][2]
    on_bed = np.all(m.triangles[:, :, 2] < zmin + 0.05, axis=1)
    down = -n[:, 2] > np.cos(np.radians(deg)) + 1e-9          # 下向き、かつ水平から deg より浅い
    sel = np.nonzero(down & ~on_bed)[0]
    if not len(sel):
        return []
    inset = set(sel.tolist())
    adj = [e for e in mesh.face_adjacency if e[0] in inset and e[1] in inset]
    groups = trimesh.graph.connected_components(adj, nodes=sel, min_len=1)
    out = []
    for g in groups:
        g = np.asarray(list(g))
        area = float(mesh.area_faces[g].sum())
        if area < min_area:
            continue
        c = (mesh.triangles_center[g] * mesh.area_faces[g, None]).sum(axis=0) / area
        ang = float(np.degrees(np.arccos(np.clip(-n[g, 2].min(), -1, 1))))   # いちばん浅い所
        out.append({"area": area, "angle": ang, "x": float(c[0]), "y": float(c[1]), "z": float(c[2])})
    return sorted(out, key=lambda r: -r["area"])


def overhang_notes(name, mesh, deg, up="z"):
    regs = overhangs(mesh, deg, up)
    if not regs:
        return []
    where = "、".join(f"高さ{r['z']:.0f}mm（X{r['x']:+.0f}・Y{r['y']:+.0f}付近）約{r['area']:.0f}mm²"
                     for r in regs[:3]) + (f" ほか{len(regs) - 3}か所" if len(regs) > 3 else "")
    flat = min(r["angle"] for r in regs)
    face = "下向きの面" + (f"（印刷の向き {up}）" if up != "z" else "")
    return [f"{name}の{face}にサポートが要りそう：{where}（水平から{flat:.0f}°。張り出し{deg:g}°より浅い）"]


def run_mock(build):
    """mock.py の build() を受け取り、部品ごとの STL・scene.json・STEP を書き出す。
    build(prm) は (部品のリスト, 注意のリスト) を返す。部品は (表示名, 形, 色, 不透明度, 英字のキー) か、
    6つめにオプションの dict を付けたもの：{"print": False}（3Dプリントしない部品：中身・既製品・レーザーの板など。
    張り出しを調べない）、{"up": "-z"}（印刷の向き。z・-z・x・-x・y・-y。既定は z＝モデルの上がそのまま上）。
    印刷の向きは寸法ファイルの meta に "print_up": {"キー": "-z"} と書いてもよい（こちらが優先）。
    寸法ファイルの meta.process が laser でなければ、3Dプリントする部品のサポートが要りそうな面を調べて注意に足す
    （しきい値は fab の overhang_deg、無ければ 45°）。"""
    import geom
    ver = version_from_argv()
    want_step = "--no-step" not in sys.argv
    prm = load(ver)
    parts, notes = build(prm)
    parts = [tuple(p) + ({},) if len(p) == 5 else tuple(p) for p in parts]

    pdir = out_dir(ver, "parts")
    scene = {"title": f"{prm.meta.get('title', '')} {ver}", "up": "z", "views": ["iso", "back", "side"], "parts": []}
    for i, (name, solid, color, opacity, key, _opt) in enumerate(parts):
        fn = f"{i + 1:02d}_{key}.stl"
        geom.export_stl(solid, os.path.join(pdir, fn))
        scene["parts"].append({"file": f"parts/{fn}", "name": name, "key": key, "color": color, "opacity": opacity,
                               "roughness": 0.3 if opacity < 1 else 0.8})

    # 3Dプリントの張り出し（サポートが要りそうな面）
    if prm.meta.get("process") != "laser":
        deg = float(getattr(prm.P, "overhang_deg", 45))
        ups = prm.meta.get("print_up", {})
        for name, solid, _c, _o, key, opt in parts:
            if opt.get("print", True):
                notes += overhang_notes(name, geom.to_trimesh(solid), deg, ups.get(key, opt.get("up", "z")))

    scene["notes"] = notes
    sp = os.path.join(out_dir(ver), "scene.json")
    json.dump(scene, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(sp)

    if want_step and geom.has_cad():
        sdir = out_dir(ver, "step")
        index = []
        asm = os.path.join(sdir, f"assembly_{ver}.step")
        geom.export_assembly([(k, s, c, o) for _n, s, c, o, k, _opt in parts], asm)
        index.append({"src": os.path.relpath(asm, ROOT), "name": "組み立て（全部品）", "file": f"assembly_{ver}.step"})
        bad = []
        for i, (name, solid, _c, _o, key, _opt) in enumerate(parts):
            fp = os.path.join(sdir, f"{i + 1:02d}_{key}.step")
            geom.export_step(solid, fp)
            ok, se, me = geom.check_step(solid, fp)
            if not ok:
                bad.append(f"{name}: STEP {se} / メッシュ {me}")
            index.append({"src": os.path.relpath(fp, ROOT), "name": name, "file": os.path.basename(fp)})
        json.dump(index, open(os.path.join(sdir, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{sdir}（STEP {len(index)}個）")
        print("STEP の大きさの確認:", "すべて一致" if not bad else "ずれあり → " + " / ".join(bad))
    elif want_step:
        print("STEP は省きました（CadQuery がありません。setup スキルの `setup.sh` で入ります）")

    for n in notes:
        print("注意:", n["q"] if isinstance(n, dict) else n)
