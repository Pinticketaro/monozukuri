"""プロジェクト共通：寸法ファイルの読み込み、版番号、出力先。

寸法ファイルは params/params_vNN.json。1つの版の寸法はこのファイルだけに書く（ほかのスクリプトに数値を直接書かない）。
  params … 形の寸法（モックで決める）
  fab    … 加工の値（カーフ・実板厚・クリアランス・インサート穴など）。status が「初期値」のものは
           試し片（tools/coupons.py）で測って「実測」に置き換える
  P = load("v03").P      → P.outer_w のように値だけで使える
  load().labels          → 項目名（寸法表・差分に使う）
  load().lang            → 表示の言語（"ja" か "en"。寸法ファイルの meta.lang、無ければ環境変数 MONOZUKURI_LANG、無ければ "ja"）
版を省くと、いちばん新しい版を使う。

English: shared helpers for the project tools. Reads the params file params/params_vNN.json (the only place
where one version's dimensions are written), finds versions, and makes output folders.
  params … shape dimensions (decided with the mock)
  fab    … fabrication values (kerf, real sheet thickness, clearance, insert holes). Values with status
           "initial" are measured with coupons (tools/coupons.py) and replaced with "measured" values
  load("v03").P.outer_w  → a value;  load().labels → item names;  load().lang → "ja" or "en"
  Language: --lang ja|en on the command line > meta.lang in the params file > env MONOZUKURI_LANG > "ja".
Without a version, the latest one is used.
"""
import glob
import json
import os
import re
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS = os.path.join(ROOT, "params")

MSG = {
    "ja": {"no_params": "params/ に寸法ファイルがありません",
           "assembly": "組み立て（全部品）",
           "step_bad": "{name}: STEP {se} / メッシュ {me}",
           "step_count": "{sdir}（STEP {n}個）",
           "step_check": "STEP の大きさの確認:", "step_ok": "すべて一致", "step_ng": "ずれあり → ",
           "step_skip": "STEP は省きました（CadQuery がありません。setup スキルの `setup.sh` で入ります）",
           "question": "問いの候補:", "qtype": "（{t}）", "note": "注意:"},
    "en": {"no_params": "No params file in params/",
           "assembly": "Assembly (all parts)",
           "step_bad": "{name}: STEP {se} / mesh {me}",
           "step_count": "{sdir} ({n} STEP files)",
           "step_check": "STEP size check:", "step_ok": "all match", "step_ng": "mismatch -> ",
           "step_skip": "Skipped STEP (CadQuery is not installed. The setup skill's `setup.sh` installs it)",
           "question": "Question candidate:", "qtype": "({t})", "note": "Note:"},
}


def resolve_lang(explicit=None, data=None):
    """表示の言語を決める：明示（--lang）> データ（meta.lang など）> 環境変数 MONOZUKURI_LANG > "ja"。"""
    for v in (explicit, data, os.environ.get("MONOZUKURI_LANG")):
        if v in ("ja", "en"):
            return v
    return "ja"


def lang_from_argv():
    """コマンドの引数に --lang ja / --lang en（--lang=en も可）があればそれ、なければ None。"""
    a = sys.argv[1:]
    for i, x in enumerate(a):
        if x == "--lang" and i + 1 < len(a):
            return a[i + 1]
        if x.startswith("--lang="):
            return x.split("=", 1)[1]
    return None


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
        raise SystemExit(MSG[resolve_lang(lang_from_argv())]["no_params"])
    return vs[-1]


def version_from_argv():
    """コマンドの引数に v03 のような版があればそれ、なければ最新。"""
    for a in sys.argv[1:]:
        if re.fullmatch(r"v\d+", a):
            return a
    return latest()


def load(ver=None, lang=None):
    """lang を渡すとそれを優先する（--lang の値など）。無ければ寸法ファイルの meta.lang → 環境変数 → "ja"。"""
    ver = ver or latest()
    path = os.path.join(PARAMS, f"params_{ver}.json")
    d = json.load(open(path, encoding="utf-8"))
    # params（形の寸法）と fab（試し片で決める加工の値：カーフ・実板厚・クリアランスなど）を1つにまとめて使う
    items = {**d.get("params", {}), **d.get("fab", {})}
    vals = {k: (v["value"] if isinstance(v, dict) and "value" in v else v) for k, v in items.items()}
    labels = {k: (v.get("label", k) if isinstance(v, dict) else k) for k, v in items.items()}
    units = {k: (v.get("unit", "") if isinstance(v, dict) else "") for k, v in items.items()}
    fab = {k: v for k, v in d.get("fab", {}).items()}
    meta = d.get("meta", {})
    return SimpleNamespace(ver=ver, path=path, meta=meta, lang=resolve_lang(lang, meta.get("lang")),
                           P=SimpleNamespace(**vals), labels=labels, units=units, fab=fab, raw=d)


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


def overhang_notes(name, mesh, deg, up="z", lang="ja"):
    regs = overhangs(mesh, deg, up)
    if not regs:
        return []
    flat = min(r["angle"] for r in regs)
    if lang == "en":
        where = "; ".join(f"height {r['z']:.0f}mm (near X{r['x']:+.0f}, Y{r['y']:+.0f}), about {r['area']:.0f}mm²"
                          for r in regs[:3]) + (f"; {len(regs) - 3} more" if len(regs) > 3 else "")
        face = "downward faces" + (f" (print orientation {up})" if up != "z" else "")
        return [f"{name}: {face} likely need support: {where} "
                f"({flat:.0f}° from horizontal; shallower than the {deg:g}° overhang limit)"]
    where = "、".join(f"高さ{r['z']:.0f}mm（X{r['x']:+.0f}・Y{r['y']:+.0f}付近）約{r['area']:.0f}mm²"
                     for r in regs[:3]) + (f" ほか{len(regs) - 3}か所" if len(regs) > 3 else "")
    face = "下向きの面" + (f"（印刷の向き {up}）" if up != "z" else "")
    return [f"{name}の{face}にサポートが要りそう：{where}（水平から{flat:.0f}°。張り出し{deg:g}°より浅い）"]


def run_mock(build):
    """mock.py の build() を受け取り、部品ごとの STL・scene.json・STEP を書き出す。
    build(prm) は (部品のリスト, 注意のリスト) を返す。部品は (表示名, 形, 色, 不透明度, 英字のキー) か、
    6つめにオプションの dict を付けたもの：{"print": False}（3Dプリントしない部品：中身・既製品・レーザーの板など。
    張り出しを調べない）、{"up": "-z"}（印刷の向き。z・-z・x・-x・y・-y。既定は z＝モデルの上がそのまま上）。
    印刷の向きは寸法ファイルの meta に "print_up": {"キー": "-z"} と書いてもよい（こちらが優先）。
    寸法ファイルの meta.process が laser でなければ、3Dプリントする部品のサポートが要りそうな面を調べて注意に足す
    （しきい値は fab の overhang_deg、無ければ 45°）。
    表示の言語は prm.lang（寸法ファイルの meta.lang。--lang ja|en で上書きできる）。scene.json の "lang" にも書く。"""
    import geom
    ver = version_from_argv()
    want_step = "--no-step" not in sys.argv
    prm = load(ver, lang=lang_from_argv())
    msg = MSG[prm.lang]
    parts, notes = build(prm)
    parts = [tuple(p) + ({},) if len(p) == 5 else tuple(p) for p in parts]

    pdir = out_dir(ver, "parts")
    scene = {"title": f"{prm.meta.get('title', '')} {ver}", "lang": prm.lang, "up": "z", "views": ["iso", "back", "side"],
             "parts": []}
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
                notes += overhang_notes(name, geom.to_trimesh(solid), deg, ups.get(key, opt.get("up", "z")), lang=prm.lang)

    scene["notes"] = notes
    sp = os.path.join(out_dir(ver), "scene.json")
    json.dump(scene, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(sp)

    if want_step and geom.has_cad():
        sdir = out_dir(ver, "step")
        index = []
        asm = os.path.join(sdir, f"assembly_{ver}.step")
        geom.export_assembly([(k, s, c, o) for _n, s, c, o, k, _opt in parts], asm)
        index.append({"src": os.path.relpath(asm, ROOT), "name": msg["assembly"], "file": f"assembly_{ver}.step"})
        bad = []
        for i, (name, solid, _c, _o, key, _opt) in enumerate(parts):
            fp = os.path.join(sdir, f"{i + 1:02d}_{key}.step")
            geom.export_step(solid, fp)
            ok, se, me = geom.check_step(solid, fp)
            if not ok:
                bad.append(msg["step_bad"].format(name=name, se=se, me=me))
            index.append({"src": os.path.relpath(fp, ROOT), "name": name, "file": os.path.basename(fp)})
        json.dump(index, open(os.path.join(sdir, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(msg["step_count"].format(sdir=sdir, n=len(index)))
        print(msg["step_check"], msg["step_ok"] if not bad else msg["step_ng"] + " / ".join(bad))
    elif want_step:
        print(msg["step_skip"])

    for n in notes:
        if isinstance(n, dict):
            print(msg["question"], n.get("q", ""), msg["qtype"].format(t=n.get("type", "")))
        else:
            print(msg["note"], n)
