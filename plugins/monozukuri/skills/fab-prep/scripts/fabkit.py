"""加工の準備（加工データの書き出し・製作前チェック・部分試作の切り出し）で共通に使う道具。

部品ごとの「作り方」は次の順で決まる（先に見つかったもの）。
  1. scene.json の部品の "process"（mock.py が寸法ファイルから写す。人が作ったモデルなら scene.json に直接書く）
  2. 寸法ファイルの meta.parts[キー]
     {"bottom_plate": {"process": "laser", "material": "アクリル", "t": "t_bottom"},
      "frame":        {"process": "fdm",   "material": "PLA", "print": {"flip": true}},
      "content":      {"process": "none"}}
     process … laser（レーザーで切る板）／fdm（3Dプリント）／none（既製品・中身・参考の形。加工しない）
     t       … 板厚のキー（fab の t_*）。レーザーの板だけ
     print   … 刷る向き。{"flip": true}（上下を返す）や {"rot": [x, y, z]}（度）
  3. どちらにも無ければ形から推定する（薄くて平らなら laser、それ以外は fdm）。推定は「推定」と表示する

機材の値（造形範囲・ノズル径・加工範囲・ラボの材料の決まり）は、寸法ファイルの meta.machines
{"laser": "<機材ID>", "fdm": "<機材ID>"} から、プロジェクトの measurements/machines/<ID>.json
（machines スキルが写す）を読む。無ければ寸法ファイルの bed_x・bed_y、ノズル 0.4mm を仮に使う。
単位は mm、Z が上。
"""
import glob
import json
import math
import os
import re
import sys

import numpy as np
import trimesh
from shapely import affinity
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get("MONOZUKURI_CACHE", os.path.expanduser("~/.cache/monozukuri"))
PROCESS_LABEL = {"laser": "レーザー", "fdm": "3Dプリント", "none": "加工しない"}
LEVELS = ["NG", "注意", "確認"]

# ---------------------------------------------------------------- 判断の基準（根拠は new-project スキルの references/fab-requirements.md）
RULE = {
    "edge_ratio": (1.5, "アクリルのネジ穴は、中心から縁まで穴径の1.5倍以上【指針：ACRYLITE】"),
    "line_gap": (0.5, "線どうしの間隔が0.5mm未満だと焼け落ちる【指針】"),
    "detail": (1.0, "細部は1mm以上【指針】"),
    "cutout": (None, "切り抜きの幅は板厚以上【指針：SendCutSend】。はめ込みのスロットなら問題ない"),
    "inner_r": (0.5, "アクリルは内角にR0.5以上を付けると割れにくい【経験則：Ponoko】"),
    "wall": (2.0, "壁はノズル径の2倍以上【指針】"),
    "overhang": (45.0, "オーバーハングは45°まで【指針】"),
    "bridge": (5.0, "ブリッジは5mmまで【指針】（メーカーの30〜40mmは最良条件の値）"),
    "jis": (None, "ボルト穴は JIS B 1001 の2〜3級（M2 2.4〜2.6、M3 3.4〜3.6、M4 4.5〜4.8）【規格】"),
}
JIS = {"M2": (2.2, 2.4, 2.6), "M3": (3.2, 3.4, 3.6), "M4": (4.3, 4.5, 4.8)}

# ---------------------------------------------------------------- 材料の安全（references/fab-safety.md と同じ内容）
BANNED = [
    ("PVC・塩素系", ["pvc", "塩ビ", "塩化ビニ", "ビニール", "合成皮革", "フェイクレザー", "kydex", "カイデックス", "ビニル"]),
    ("ポリカーボネート", ["ポリカーボネート", "polycarbonate", "ポリカ", "lexan", "レキサン"]),
    ("ABS", ["abs"]),
    ("HDPE", ["hdpe", "高密度ポリエチレン"]),
    ("PTFE", ["ptfe", "テフロン", "teflon"]),
    ("ガラス繊維", ["ガラス繊維", "グラスファイバー", "fr4", "fr-4", "gfrp", "ガラエポ"]),
    ("炭素繊維（コート付きは全面禁止）", ["炭素繊維", "カーボン", "cfrp", "carbon"]),
    ("発泡スチロール・HIPS", ["発泡スチロール", "スチロール", "ポリスチレン", "hips", "スタイロ", "eps"]),
]
LAB = [
    ("MDF", ["mdf"]),
    ("POM（デルリン）", ["pom", "デルリン", "delrin", "ジュラコン", "ポリアセタール"]),
    ("EVA フォーム", ["eva"]),
    ("PU フォーム（PORON 系を含む）", ["poron", "ポロン", "ウレタン", "pu", "polyurethane"]),
    ("PET・PETG", ["petg", "pet"]),
    ("ナイロン", ["ナイロン", "nylon", "pa6", "pa12"]),
    ("PP", ["pp", "ポリプロピレン"]),
    ("PLA", ["pla"]),
    ("合板（無処理のものだけ）", ["合板", "ベニヤ", "plywood", "シナ", "ラワン"]),
]
SAFE = ["アクリル", "acrylic", "pmma", "無垢", "紙", "厚紙", "段ボール", "ダンボール", "cardboard", "paper", "コルク", "フェルト"]


def _norm(s):
    return re.sub(r"[\s　・\-_/（）()]", "", str(s or "")).lower()


def _hit(text, words):
    t = _norm(text)
    for w in words:
        w2 = _norm(w)
        if re.fullmatch(r"[a-z0-9]+", w2) and len(w2) <= 4:
            # 短い英字は単語として当たったときだけ（"pet" が "carpet" に当たらないように）
            if re.search(rf"(?<![a-z]){re.escape(w2)}(?![a-z])", t):
                return True
        elif w2 in t:
            return True
    return False


def material_safety(material, rules=None):
    """レーザーで切る材料の判定。戻り値：(レベル or None, 説明)。rules は機材プロファイルの rules"""
    rules = rules or {}
    if not material:
        return "確認", "材料が書かれていない。SDS かリサイクルコードで材料を特定し、寸法ファイルの meta.parts に書く"
    for name in rules.get("banned", []):
        if _hit(material, [name]):
            return "NG", f"「{material}」はこのラボ（機材の決まり）で禁止"
    for name, words in BANNED:
        if _hit(material, words):
            return "NG", f"「{material}」→ {name}：レーザーで切ってはいけない材料（全面禁止）"
    for name, words in LAB:
        if _hit(material, words):
            for ok in rules.get("allowed", []):
                if _hit(material, [ok]) or _hit(ok, words):
                    return None, f"「{material}」→ {name}：ラボで許可済み（機材の決まり）"
            return "確認", f"「{material}」→ {name}：ラボによって可否が分かれる。所属ラボのリストで許可を確かめる"
    if any(_hit(material, [w]) for w in SAFE):
        return None, ""
    return "確認", f"「{material}」は安全表に無い材料。SDS で成分（塩素・フッ素・窒素など）を確かめる"


def is_acrylic(material):
    return _hit(material, ["アクリル", "acrylic", "pmma"])


# ---------------------------------------------------------------- 読み込み
def load_mm(path, fine=False):
    """メッシュとして読み、mm にそろえる。STEP は細かめに分割する（円が角ばると穴の判定やレーザーの輪郭が崩れる）。"""
    kw = {}
    if fine and path.lower().endswith((".step", ".stp")):
        kw = {"tol_linear": 0.01, "tol_angular": 0.1}
    try:
        obj = trimesh.load(path, **kw)
    except TypeError:
        obj = trimesh.load(path)
    units = getattr(obj, "units", None)
    if units and units not in ("millimeters", "mm"):
        obj = obj.convert_units("millimeters")
    if isinstance(obj, trimesh.Scene):
        obj = obj.to_mesh() if hasattr(obj, "to_mesh") else obj.dump(concatenate=True)
    if obj.is_empty:
        raise SystemExit(f"中身が空です: {path}")
    obj.merge_vertices()          # STEP は面ごとに頂点が分かれて読まれるので、つないで閉じた形にする
    return obj


def latest_params(root):
    vs = []
    for f in glob.glob(os.path.join(root, "params", "params_v*.json")):
        m = re.search(r"params_v(\d+)\.json$", f)
        if m:
            vs.append((int(m.group(1)), f))
    return sorted(vs)[-1][1] if vs else None


def machine_lib():
    return os.environ.get("MONOZUKURI_MACHINES", os.path.expanduser("~/.monozukuri/machines"))


def resolve(args):
    """--scene / --params / --root / 版（v03）から、scene.json・寸法ファイル・プロジェクトのフォルダを決める。
    プロジェクトの tools/ から動かすとき（python3 tools/fab_check.py v03）は、tools の1つ上がプロジェクト。"""
    ver = getattr(args, "ver", None)
    root = getattr(args, "root", None)
    if not root:
        up = os.path.dirname(HERE)
        root = up if os.path.isdir(os.path.join(up, "params")) else os.getcwd()
    root = os.path.abspath(root)
    scene = getattr(args, "scene", None)
    if not scene:
        if not ver:
            p = latest_params(root)
            if not p:
                raise SystemExit("版がわかりません。v03 のように版を指定するか --scene を指定してください")
            ver = re.search(r"params_(v\d+)\.json$", p).group(1)
        scene = os.path.join(root, "out", ver, "scene.json")
    scene = os.path.abspath(scene)
    if not os.path.exists(scene):
        raise SystemExit(f"scene.json がありません: {scene}（先に mock.py を実行するか、モデルの scene.json を書く）")
    if not ver:
        m = re.search(r"[/\\](v\d+)[/\\]", scene)
        ver = m.group(1) if m else "v00"
    params = getattr(args, "params", None)
    if not params:
        cand = os.path.join(root, "params", f"params_{ver}.json")
        params = cand if os.path.exists(cand) else latest_params(root)
    return root, ver, scene, params


class Project:
    """scene.json と寸法ファイルを読み、部品ごとの作り方・材料・板厚と、機材の値をそろえる。"""

    def __init__(self, scene_path, params_path=None, root=None, ver=None):
        self.scene_path = scene_path
        self.base = os.path.dirname(scene_path)
        self.scene = json.load(open(scene_path, encoding="utf-8"))
        self.root = root or os.path.dirname(os.path.dirname(self.base))
        self.ver = ver
        self.params_path = params_path
        self.raw = json.load(open(params_path, encoding="utf-8")) if params_path and os.path.exists(params_path) else {}
        self.meta = self.raw.get("meta", {})
        self.fab = self.raw.get("fab", {})
        items = {**self.raw.get("params", {}), **self.fab}
        self.P = {k: (v["value"] if isinstance(v, dict) and "value" in v else v) for k, v in items.items()}
        self.title = self.scene.get("title") or self.meta.get("title", "")
        if ver and ver not in self.title:
            self.title = f"{self.title} {ver}".strip()
        self.machines = self._load_machines()
        self.parts = [self._part(i, p) for i, p in enumerate(self.scene.get("parts", []))]

    # 機材
    def _load_machines(self):
        out = {}
        for kind, mid in (self.meta.get("machines") or {}).items():
            if not mid:
                continue
            for d in (os.path.join(self.root, "measurements", "machines"), machine_lib()):
                f = os.path.join(d, f"{mid}.json")
                if os.path.exists(f):
                    out[kind] = json.load(open(f, encoding="utf-8"))
                    out[kind]["_file"] = f
                    break
            else:
                out[kind] = {"id": mid, "name": mid, "spec": {}, "_missing": True}
        return out

    def fdm_spec(self):
        """(造形範囲 X, Y, Z, ノズル径, 出どころの説明)"""
        m = self.machines.get("fdm")
        s = (m or {}).get("spec", {})
        bx = s.get("bed_x", self.P.get("bed_x"))
        by = s.get("bed_y", self.P.get("bed_y"))
        bz = s.get("bed_z", self.P.get("bed_z"))
        nz = s.get("nozzle", self.P.get("nozzle", 0.4))
        src = f"機材 {m.get('name', m.get('id'))}" if m and not m.get("_missing") else "寸法ファイル（機材が未登録。ノズルは0.4mmと仮定）"
        return bx, by, bz, float(nz), src

    def laser_spec(self):
        m = self.machines.get("laser")
        s = (m or {}).get("spec", {})
        wx = s.get("work_x", self.P.get("laser_x"))
        wy = s.get("work_y", self.P.get("laser_y"))
        src = f"機材 {m.get('name', m.get('id'))}" if m and not m.get("_missing") else "寸法ファイル"
        return wx, wy, src

    def laser_rules(self):
        return (self.machines.get("laser") or {}).get("rules", {})

    def fab_item(self, key):
        f = self.fab.get(key)
        return f if isinstance(f, dict) else {}

    def kerf(self, material=None, nominal=None):
        """使うカーフ（全幅 k）と、その状態。材料・板厚ごとのキー kerf_<…> があればそちらを探す。"""
        for k, f in self.fab.items():
            if k.startswith("kerf") and isinstance(f, dict):
                if f.get("material") and material and _norm(f["material"]) not in _norm(material):
                    continue
                if f.get("nominal") and nominal and abs(float(f["nominal"]) - float(nominal)) > 0.05:
                    continue
                return float(f.get("value", 0)), f.get("status", ""), k
        return None, "", None

    # 部品
    def _part(self, i, p):
        key = p.get("key") or re.sub(r"\W+", "_", os.path.splitext(os.path.basename(p["file"]))[0])
        mp = dict((self.meta.get("parts") or {}).get(key, {}))
        for k in ("process", "material", "t", "print", "note"):
            if k in p:
                mp[k] = p[k]
        f = p["file"] if os.path.isabs(p["file"]) else os.path.join(self.base, p["file"])
        return {"i": i, "name": p.get("name", key), "key": key, "file": f, "color": p.get("color", "#c9ccc6"),
                "opacity": p.get("opacity", 1.0), "process": mp.get("process"), "material": mp.get("material", ""),
                "t": mp.get("t"), "print": mp.get("print") or {}, "guessed": False}

    def mesh(self, part, fine=True):
        if "_mesh" not in part:
            part["_mesh"] = load_mm(part["file"], fine=fine)
        return part["_mesh"].copy()

    def classify(self):
        """process が無い部品を形から推定する（薄くて上下の断面が同じなら laser、それ以外は fdm）。"""
        for p in self.parts:
            if p["process"]:
                continue
            m = self.mesh(p)
            prof = plate_profile(m)
            thick_keys = [k for k in self.fab if k.startswith("t_")]
            near = [k for k in thick_keys if abs(float(self.P[k]) - prof["t"]) < 0.8]
            if prof["prismatic"] and prof["t"] <= 12 and min(m.extents) * 4 < max(m.extents):
                p["process"], p["guessed"] = "laser", True
                if near and not p["t"]:
                    p["t"] = near[0]
            else:
                p["process"], p["guessed"] = "fdm", True
        return self.parts

    def sheet_thickness(self, part, measured=None):
        """部品の板厚：t キーの値（実測ならその値）と状態"""
        k = part.get("t")
        if k and k in self.P:
            f = self.fab_item(k)
            return float(self.P[k]), f.get("status", ""), k, f.get("nominal")
        return measured, "モデルから", None, None

    def todo_fab(self):
        return [k for k, f in self.fab.items() if isinstance(f, dict) and str(f.get("status", "")).startswith("初期値")]


# ---------------------------------------------------------------- 形の道具
def loops_to_shape(loops):
    """閉じた輪郭の集まりを、内外を交互に（偶奇で）まとめた面にする。"""
    shape = None
    for lp in loops:
        lp = np.asarray(lp)
        if len(lp) < 4:
            continue
        p = Polygon(lp[:, :2]).buffer(0)
        if p.is_empty:
            continue
        shape = p if shape is None else shape.symmetric_difference(p)
    return shape


def section(mesh, z):
    sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if sec is None:
        return None
    return loops_to_shape(sec.discrete)


def polys(shape):
    if shape is None or shape.is_empty:
        return []
    return list(shape.geoms) if hasattr(shape, "geoms") else [shape]


def align_thin_to_z(mesh):
    """いちばん薄い向きを Z にそろえる（板が立って描かれていても平らに置く）。戻り値：(メッシュ, 回した軸の名前)"""
    ax = int(np.argmin(mesh.extents))
    if ax == 0:
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
    elif ax == 1:
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    return mesh, "XYZ"[ax]


def plate_profile(mesh):
    """板として見たときの輪郭（shapely）、厚さ、上下の断面がそろっているか（段差・座ぐりが無いか）。
    座標は板を平らに置いた向き（原点は元のまま）。"""
    m, thin = align_thin_to_z(mesh.copy())
    z0, z1 = m.bounds[0][2], m.bounds[1][2]
    t = z1 - z0
    secs = [section(m, z0 + f * t) for f in (0.2, 0.5, 0.8)]
    mid = secs[1]
    pris = False
    if mid is not None and not mid.is_empty and all(s is not None and not s.is_empty for s in secs):
        diff = max(s.symmetric_difference(mid).area for s in secs)
        pris = diff <= max(0.005 * mid.area, 0.05)
    if mid is not None:
        mid = mid.simplify(0.002)
    return {"shape": mid, "t": t, "prismatic": pris, "thin_axis": thin, "mesh": m}


def kerf_offset(shape, k):
    """カーフ補正：閉じた輪郭を k/2 ずらす（外形は外へ、穴は内へ）。k はカーフの全幅。角は尖ったまま（マイター）。"""
    if not k:
        return shape
    return shape.buffer(k / 2, join_style="mitre", mitre_limit=4.0)


def inscribed_width(poly, hi=None):
    """形の中に入るいちばん大きい円の直径（おおよそ）。ブリッジの長さや穴の幅の目安に使う。"""
    if poly.is_empty:
        return 0.0
    lo, hi = 0.0, hi or max(poly.bounds[2] - poly.bounds[0], poly.bounds[3] - poly.bounds[1])
    for _ in range(14):
        mid = (lo + hi) / 2
        if poly.buffer(-mid).is_empty:
            hi = mid
        else:
            lo = mid
    return 2 * lo


def thin_regions(shape, width, min_area=None):
    """幅 width より細い所（オープニングで消える部分）。細い壁・細いブリッジ・狭い切り抜きの検出に使う。"""
    if shape is None or shape.is_empty:
        return []
    opened = shape.buffer(-width / 2, join_style="round").buffer(width / 2, join_style="round")
    rest = shape.difference(opened.buffer(1e-3))
    min_area = min_area if min_area is not None else 0.6 * width * width
    return [g for g in polys(rest) if g.area > min_area]


def circle_info(ring):
    """輪郭が円なら (中心x, 中心y, 直径) を返す。円でなければ None。"""
    p = Polygon(ring)
    if p.area <= 0:
        return None
    circ = 4 * math.pi * p.area / (p.length ** 2)
    if circ < 0.97:
        return None
    c = p.centroid
    pts = np.asarray(ring)[:-1] if len(ring) > 3 else np.asarray(ring)
    # 頂点は円の上にあるので、中心からの平均距離で直径を出す（面積から出すと多角形の分だけ小さく出る）
    return c.x, c.y, 2 * float(np.mean(np.hypot(pts[:, 0] - c.x, pts[:, 1] - c.y)))


def sharp_inner_corners(poly, min_turn=30.0, min_seg=0.3):
    """材料側から見て内向きの尖った角（内角）の位置。円弧を細かい線で近似した所は拾わない。"""
    out = []
    p = orient(poly, 1.0)                       # 外形は反時計回り、穴は時計回り → 材料はいつも進む向きの左
    for ring in [p.exterior] + list(p.interiors):
        pts = np.asarray(ring.coords)[:-1]
        n = len(pts)
        if n < 3:
            continue
        for i in range(n):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
            v1, v2 = b - a, c - b
            l1, l2 = np.linalg.norm(v1), np.linalg.norm(v2)
            if l1 < min_seg or l2 < min_seg:
                continue
            cross = v1[0] * v2[1] - v1[1] * v2[0]
            ang = math.degrees(math.acos(max(-1, min(1, float(np.dot(v1, v2) / (l1 * l2))))))
            if cross < 0 and ang >= min_turn:          # 右に曲がる＝材料の内角
                out.append((float(b[0]), float(b[1]), ang))
    return out


def rings_in_cut_order(shape):
    """切る順：部品ごとに、内側の穴 → 外形。[(種類, 座標の並び)]"""
    out = []
    for p in polys(shape):
        for h in p.interiors:
            out.append(("hole", np.asarray(h.coords)))
        out.append(("outer", np.asarray(p.exterior.coords)))
    return out


def print_orient(mesh, part):
    """刷る向きにして、ベッド（Z=0）の上・XY の中心に置く。"""
    pr = part.get("print") or {}
    if pr.get("flip"):
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0]))
    for ax, deg in zip(([1, 0, 0], [0, 1, 0], [0, 0, 1]), pr.get("rot") or [0, 0, 0]):
        if deg:
            mesh.apply_transform(trimesh.transformations.rotation_matrix(math.radians(deg), ax))
    b = mesh.bounds
    mesh.apply_translation([-(b[0][0] + b[1][0]) / 2, -(b[0][1] + b[1][1]) / 2, -b[0][2]])
    return mesh


# ---------------------------------------------------------------- 並べる（レーザーの板を加工範囲に）
def pack(items, area_w, area_h, gap=3.0, margin=5.0):
    """items: [(名前, 形)]。棚に並べるだけの簡単な配置。入らなければ次のシートへ。
    戻り値：シートのリスト [[(名前, 置いた形, 回したか)], ...] と、範囲に入らない部品の名前"""
    W = area_w or 10000.0
    H = area_h or 10000.0
    prepared, too_big = [], []
    for name, shp in items:
        x0, y0, x1, y1 = shp.bounds
        w, h = x1 - x0, y1 - y0
        # 横幅に入らず、90°回すと入るときだけ回す
        rot = (w > W - 2 * margin) and (h <= W - 2 * margin) and (w <= H - 2 * margin)
        if rot:
            shp = affinity.rotate(shp, 90, origin=(0, 0))
            x0, y0, x1, y1 = shp.bounds
            w, h = x1 - x0, y1 - y0
        if w > W - 2 * margin + 1e-6 or h > H - 2 * margin + 1e-6:
            too_big.append(name)
        prepared.append((name, shp, rot, w, h))
    prepared.sort(key=lambda t: -t[4])
    sheets, cur = [], []
    x, y, row_h = margin, margin, 0.0
    for name, shp, rot, w, h in prepared:
        if x + w > W - margin and cur:
            x, y, row_h = margin, y + row_h + gap, 0.0
        if y + h > H - margin and cur:
            sheets.append(cur)
            cur, x, y, row_h = [], margin, margin, 0.0
        b = shp.bounds
        placed = affinity.translate(shp, x - b[0], y - b[1])
        cur.append((name, placed, rot))
        x += w + gap
        row_h = max(row_h, h)
    if cur:
        sheets.append(cur)
    return sheets, too_big


# ---------------------------------------------------------------- 書き出し
def write_svg(path, items, W, H, note=""):
    """items: [(id, 名前, 形)]。単位 mm（width/height に mm、viewBox は mm の数値）。
    赤＝切断、線幅 0.01mm、塗りなし。部品ごとに <g>、穴 → 外形の順。SVG は Y が下向きなので反転して書く。"""
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.3f}mm" height="{H:.3f}mm" viewBox="0 0 {W:.3f} {H:.3f}">',
           f"<!-- {note} 単位mm。赤=切断（内側の穴から先に切る）。 -->"]
    for pid, name, shp in items:
        out.append(f'<g id="{pid}"><title>{name}</title>')
        for kind, pts in rings_in_cut_order(shp):
            d = "M " + " L ".join(f"{x:.4f},{H - y:.4f}" for x, y in pts[:-1]) + " Z"
            out.append(f'<path d="{d}" fill="none" stroke="#ff0000" stroke-width="0.01" data-kind="{kind}"/>')
        out.append("</g>")
    out.append("</svg>")
    open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")


def write_dxf(path, items):
    """DXF（R2000、$INSUNITS=4 で mm）。層 CUT（赤）に閉じたポリライン。穴 → 外形の順。ezdxf が無ければ False。"""
    try:
        import ezdxf
    except Exception:
        return False
    doc = ezdxf.new("R2000")
    doc.header["$INSUNITS"] = 4
    doc.header["$MEASUREMENT"] = 1
    doc.layers.add("CUT", color=1)
    msp = doc.modelspace()
    for _pid, _name, shp in items:
        for _kind, pts in rings_in_cut_order(shp):
            msp.add_lwpolyline([(float(x), float(y)) for x, y in pts[:-1]], close=True, dxfattribs={"layer": "CUT"})
    doc.saveas(path)
    return True


def export_3mf(mesh, path):
    """3MF（単位 mm）。スライサーで単位を取り違えにくい"""
    mesh.export(path, file_type="3mf")


# ---------------------------------------------------------------- 図
def setup_font():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    try:
        env = json.load(open(os.path.join(CACHE, "env.json")))
        if env.get("cjk_font_path"):
            font_manager.fontManager.addfont(env["cjk_font_path"])
            plt.rcParams["font.family"] = env["cjk_font"]
    except Exception:
        pass
    return plt


def draw_shape(ax, shape, face="#bcd6e4", edge="#3b5566", lw=1.0, alpha=0.5):
    for p in polys(shape):
        xs, ys = p.exterior.xy
        ax.fill(xs, ys, color=face, alpha=alpha, lw=0)
        ax.plot(xs, ys, color=edge, lw=lw)
        for h in p.interiors:
            hx, hy = h.xy
            ax.fill(hx, hy, color="white", lw=0)
            ax.plot(hx, hy, color=edge, lw=lw * 0.8)


def render_script():
    """描画スクリプト render_model.py の場所（プロジェクトの tools/ か、プラグインの review-page/scripts/）"""
    for c in (os.path.join(HERE, "render_model.py"),
              os.path.join(HERE, "..", "..", "review-page", "scripts", "render_model.py")):
        if os.path.exists(c):
            return os.path.abspath(c)
    return None


def add_common_args(ap):
    ap.add_argument("ver", nargs="?", help="版（例 v03）。省くといちばん新しい版")
    ap.add_argument("--root", help="プロジェクトのフォルダ（params/ がある所）。既定：tools の1つ上か今のフォルダ")
    ap.add_argument("--scene", help="scene.json（人が作ったモデルを見るとき）。既定：out/<版>/scene.json")
    ap.add_argument("--params", help="寸法ファイル。既定：params/params_<版>.json（無ければいちばん新しい版）")


def open_project(args):
    root, ver, scene, params = resolve(args)
    prj = Project(scene, params, root=root, ver=ver)
    prj.classify()
    return prj


def finding(level, part, msg, basis="", at=None):
    return {"level": level, "part": part, "msg": msg, "basis": basis, "at": at}


def fmt_findings(findings):
    lines = []
    for lv in LEVELS:
        fs = [f for f in findings if f["level"] == lv]
        if not fs:
            continue
        lines += ["", f"### {lv}（{len(fs)}件）", "", "| 番号 | 部品 | 内容 | 根拠 |", "|---:|---|---|---|"]
        for f in fs:
            lines.append(f"| {f.get('no', '')} | {f['part']} | {f['msg']} | {f['basis']} |")
    return lines


if __name__ == "__main__":
    sys.exit("fabkit.py は部品です。export_fab.py・fab_check.py・cut_region.py から使います")
