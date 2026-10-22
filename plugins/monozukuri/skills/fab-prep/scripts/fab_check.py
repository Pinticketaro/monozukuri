"""製作前チェック：モックや人が作ったモデルを、技術要件（new-project スキルの references/fab-requirements.md・
fab-safety.md）と機材の値に照らして、問題になりそうな所に番号を付けて返す。

  NG   … このままでは切れない・刷れない・危ない（禁止材料、範囲外、板の形でない、焼け落ちる細さ）
  注意 … 失敗しやすい（穴が縁に近い、薄い壁、45°を超えるオーバーハング、5mmを超えるブリッジ、板厚の食い違い）
  確認 … 人が判断する（ラボ次第の材料、まだ初期値の値、ボルト穴の等級、内角、作り方の推定）

見る所
  共通    単位（全体の大きさ）、作り方が推定の部品、まだ初期値の加工の値、機材の登録
  レーザー 材料の安全、板の形（上下の断面が同じか）、板厚、加工範囲、穴と縁の距離（アクリル）、
          ボルト穴の等級（JIS B 1001）、線どうしの間隔（0.5mm）と細部（1mm）、狭い切り抜き、内角（アクリル）
  3Dプリント 造形範囲、閉じたメッシュか、壁の薄さ（ノズル径の2倍）、オーバーハング（45°）、
          天井・ブリッジ（5mm）、材料の耐熱
刷る向きは寸法ファイルの meta.parts の print（flip / rot）。向きを変えるとオーバーハングの結果が変わる。

出力：out/<版>/check/check.md（表）、check_laser.png・check_fdm.png（番号の付いた図）、check.json、
      --render で check_3d.png（3Dプリント部品のオーバーハング・薄い壁を色付けした外観）
使い方
  python3 tools/fab_check.py v05 [--render]
  python3 tools/fab_check.py --scene out/v06/scene.json          # 人が作ったモデル
"""
import argparse
import json
import math
import os
import subprocess
import sys

import numpy as np
import trimesh
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fabkit as fk  # noqa: E402

LV_COLOR = {"NG": "#d0201a", "注意": "#e08a00", "確認": "#2f6fb5"}


class Checker:
    def __init__(self, prj):
        self.prj = prj
        self.f = []
        self.marks = {}          # 部品キー → [(x, y, 番号, レベル)]
        self.shapes = {}         # 図に描く形
        self.extra = {}          # 3Dプリント：薄い所・オーバーハングの面

    def add(self, level, part, msg, basis="", at=None):
        pname = part["name"] if isinstance(part, dict) else part
        for f in self.f:                      # 同じ部品の同じ指摘は1行にまとめ、印だけ増やす
            if f["level"] == level and f["part"] == pname and f["msg"] == msg:
                f["n"] += 1
                if at is not None and isinstance(part, dict):
                    self.marks.setdefault(part["key"], []).append((at[0], at[1], f["no"], level))
                return f["no"]
        no = len(self.f) + 1
        self.f.append({"no": no, "level": level, "part": pname, "msg": msg, "basis": basis, "at": at, "n": 1})
        if at is not None and isinstance(part, dict):
            self.marks.setdefault(part["key"], []).append((at[0], at[1], no, level))
        return no

    # ---------------- 共通
    def common(self):
        prj = self.prj
        allm = [prj.mesh(p) for p in prj.parts]
        if allm:
            b = np.array([m.bounds for m in allm])
            ext = b[:, 1, :].max(axis=0) - b[:, 0, :].min(axis=0)
            if max(ext) < 5 or max(ext) > 2000:
                self.add("NG", "全体", f"全体の大きさ {ext[0]:.1f}×{ext[1]:.1f}×{ext[2]:.1f}mm が不自然。"
                         "単位の取り違え（25.4倍・1000倍）を疑う", "単位の関所：既知の寸法を1つ測る")
        for p in prj.parts:
            if p["guessed"]:
                self.add("確認", p, f"作り方を形から「{fk.PROCESS_LABEL[p['process']]}」と推定した。"
                         "寸法ファイルの meta.parts（人のモデルなら scene.json）に process を書くと確定する")
        todo = prj.todo_fab()
        if todo:
            self.add("確認", "全体", "まだ初期値の加工の値：" + ", ".join(todo) + "。本番の前に試し片で測る",
                     "公開値は初期値（出典どうしのずれが圧入とガタの差ほどある）")
        kinds = {p["process"] for p in prj.parts}
        for kind in ("laser", "fdm"):
            if kind not in kinds:
                continue
            m = prj.machines.get(kind)
            if m and m.get("_missing"):
                self.add("注意", "全体", f"機材 {m['id']} のプロファイルが見つからない（measurements/machines/ にも、機材の置き場にも無い）")
            elif not m:
                self.add("確認", "全体", f"{fk.PROCESS_LABEL[kind]}の機材が未登録。"
                         + ("造形範囲は寸法ファイル、ノズル径は0.4mmと仮定" if kind == "fdm" else "加工範囲とラボの材料の決まりは見ていない"),
                         "machines スキルで登録すると、測った値と範囲で見る")

    # ---------------- レーザー
    def laser(self, p):
        prj = self.prj
        lv, msg = fk.material_safety(p["material"], prj.laser_rules())
        if lv:
            self.add(lv, p, msg, "references/fab-safety.md")
        prof = fk.plate_profile(prj.mesh(p))
        shape = prof["shape"]
        if shape is None or shape.is_empty:
            self.add("NG", p, "板の輪郭が取れない（形が閉じていない）")
            return
        self.shapes[p["key"]] = shape
        if prof["thin_axis"] != "Z":
            self.add("確認", p, f"板が立っている（いちばん薄い向きが {prof['thin_axis']}）。平らに置いて見ている")
        if not prof["prismatic"]:
            self.add("NG", p, "上下で断面が違う（段差・座ぐり・彫り込み）。レーザーで切るなら板の形にするか、彫刻を別の層に分ける")
        t, st, tkey, _nom = prj.sheet_thickness(p, prof["t"])
        if tkey and abs(t - prof["t"]) > 0.05:
            self.add("注意", p, f"モデルの板厚 {prof['t']:.2f}mm と寸法ファイルの {tkey}={t:g}mm（{st}）が違う。"
                     "溝・スペーサーの高さは実測の板厚で決める", "板厚は呼び寸法からずれる（3mmで±0.7mm）")
        acrylic = fk.is_acrylic(p["material"])
        wx, wy, wsrc = prj.laser_spec()
        x0, y0, x1, y1 = shape.bounds
        w, h = x1 - x0, y1 - y0
        if wx and wy and not ((w <= wx and h <= wy) or (h <= wx and w <= wy)):
            self.add("NG", p, f"{w:.0f}×{h:.0f}mm が加工範囲 {wx}×{wy}mm（{wsrc}）に入らない")

        for poly in fk.polys(shape):
            ext = Polygon(poly.exterior)
            for ring in poly.interiors:
                ci = fk.circle_info(ring.coords)
                if not ci:
                    continue
                cx, cy, d = ci
                edge = ext.exterior.distance(Point(cx, cy))
                if acrylic and edge < fk.RULE["edge_ratio"][0] * d - 0.05:
                    self.add("注意", p, f"φ{d:.1f} の穴が縁に近い（中心から縁まで {edge:.1f}mm、{1.5 * d:.1f}mm 以上がよい）",
                             fk.RULE["edge_ratio"][1], (cx, cy))
                for mname, (lo, mid, hi) in fk.JIS.items():
                    if lo - 0.3 <= d < lo - 0.01:
                        self.add("確認", p, f"φ{d:.2f} の穴：{mname} のボルト穴なら小さい（2級 {mid}）。タップ下穴なら問題ない",
                                 fk.RULE["jis"][1], (cx, cy))
                    elif hi + 0.01 < d <= hi + 0.4 and not any(l2 - 0.3 <= d <= h2 for n2, (l2, _m, h2) in fk.JIS.items() if n2 != mname):
                        self.add("確認", p, f"φ{d:.2f} の穴：{mname} のボルト穴なら大きい（3級 {hi}）",
                                 fk.RULE["jis"][1], (cx, cy))
            for g in fk.thin_regions(poly, fk.RULE["line_gap"][0]):
                c = g.representative_point()
                self.add("NG", p, f"幅 {fk.RULE['line_gap'][0]}mm 未満の細い所（焼け落ちる）", fk.RULE["line_gap"][1], (c.x, c.y))
            thin05 = unary_union(fk.thin_regions(poly, fk.RULE["line_gap"][0]) or [Polygon()])
            for g in fk.thin_regions(poly, fk.RULE["detail"][0]):
                if g.difference(thin05.buffer(0.2)).area < 0.3:
                    continue
                c = g.representative_point()
                self.add("注意", p, f"幅 {fk.RULE['detail'][0]}mm 未満の細い所（細部は1mm以上）", fk.RULE["detail"][1], (c.x, c.y))
            for ring in poly.interiors:
                hole = Polygon(ring)
                if fk.circle_info(ring.coords):
                    if 2 * math.sqrt(hole.area / math.pi) < t - 0.05:
                        c = hole.centroid
                        self.add("確認", p, f"穴の径が板厚 {t:g}mm より小さい（きれいに抜けないことがある）", fk.RULE["cutout"][1], (c.x, c.y))
                    continue
                for g in fk.thin_regions(hole, t, min_area=0.4 * t * t):
                    c = g.representative_point()
                    self.add("確認", p, f"切り抜きの幅が板厚 {t:g}mm より狭い所", fk.RULE["cutout"][1], (c.x, c.y))
                    break
            if acrylic:
                corners = fk.sharp_inner_corners(poly)
                if corners:
                    no = self.add("確認", p, f"内角が尖っている所が {len(corners)} か所（はめ込みや力のかかる所なら R0.5 以上に）",
                                  fk.RULE["inner_r"][1], corners[0][:2])
                    for cx, cy, _a in corners[1:]:
                        self.marks.setdefault(p["key"], []).append((cx, cy, no, "確認", "dot"))

    # ---------------- 3Dプリント
    def fdm(self, p):
        prj = self.prj
        m = fk.print_orient(prj.mesh(p), p)
        bx, by, bz, nz, bsrc = prj.fdm_spec()
        ex = m.extents
        if bx and by:
            fits = (ex[0] <= bx and ex[1] <= by) or (ex[1] <= bx and ex[0] <= by)
            if bz:
                fits = fits and ex[2] <= bz
            if not fits:
                self.add("NG", p, f"{ex[0]:.0f}×{ex[1]:.0f}×{ex[2]:.0f}mm が造形範囲 {bx}×{by}" + (f"×{bz}" if bz else "")
                         + f"mm（{bsrc}）に入らない。分割と継ぎ目を部分試作で確かめる")
        if not m.is_watertight:
            self.add("注意", p, "メッシュが閉じていない（穴あき・面の向きの乱れ）。スライサーで修復されるか確かめる")
        mat = p["material"] or ""
        if fk._hit(mat, ["pla"]):
            self.add("確認", p, "PLA は約57℃で変形し始める。車内・窓際・熱を持つ機器の近くなら ASA など", "PLA の HDT 57℃【実測】")
        elif fk._hit(mat, ["abs", "asa"]):
            self.add("確認", p, "ABS / ASA は筐体（エンクロージャー）と換気が要る", "references/fab-safety.md")

        # 壁の薄さ：高さごとに切って、ノズル径の2倍より細い所を探す
        wmin = fk.RULE["wall"][0] * nz
        H = ex[2]
        n = int(min(60, max(10, H / 0.5)))
        thin = []
        foot = []
        for z in np.linspace(min(0.3, H / 4), H - min(0.3, H / 4), n):
            sec = fk.section(m, z)
            if sec is None or sec.is_empty:
                continue
            foot.append(sec)
            for g in fk.thin_regions(sec, wmin, min_area=wmin * wmin):
                thin.append((g, float(z)))
        footprint = unary_union(foot) if foot else None
        clusters = []
        for g, z in thin:
            for c in clusters:
                if c["shape"].buffer(0.6).intersects(g):
                    c["shape"] = c["shape"].union(g)
                    c["z"] = (min(c["z"][0], z), max(c["z"][1], z))
                    c["w"] = min(c["w"], fk.inscribed_width(g, hi=wmin))
                    break
            else:
                clusters.append({"shape": g, "z": (z, z), "w": fk.inscribed_width(g, hi=wmin)})
        thin_meshes = []
        for c in clusters[:12]:
            pt = c["shape"].representative_point()
            self.add("注意", p, f"壁が {wmin:g}mm（ノズル {nz:g}×2）より薄い所：約 {max(c['w'], 0.05):.1f}mm、高さ {c['z'][0]:.1f}〜{c['z'][1]:.1f}mm",
                     fk.RULE["wall"][1], (pt.x, pt.y))
            for g in fk.polys(c["shape"]):
                try:
                    thin_meshes.append(trimesh.creation.extrude_polygon(g, max(0.4, c["z"][1] - c["z"][0] + 0.4))
                                       .apply_translation([0, 0, c["z"][0] - 0.2]))
                except Exception:
                    pass
        if len(clusters) > 12:
            self.add("注意", p, f"ほかにも薄い所が {len(clusters) - 12} か所")

        # オーバーハングと天井（ブリッジ）
        nzs = m.face_normals[:, 2]
        zmin_face = m.vertices[m.faces][:, :, 2].min(axis=1)
        lim = -math.sin(math.radians(fk.RULE["overhang"][0]))
        down = np.where((nzs < lim - 1e-3) & (zmin_face > 0.25))[0]
        flat = set(np.where(nzs < -0.985)[0].tolist())
        groups = trimesh.graph.connected_components(m.face_adjacency, nodes=down, min_len=1) if len(down) else []
        over_faces, bridge_faces, fps = [], [], []
        for grp in groups:
            grp = np.asarray(grp)
            area = float(m.area_faces[grp].sum())
            if area < 2.0:
                continue
            tri = m.vertices[m.faces[grp]]
            fp = unary_union([Polygon(t[:, :2]).buffer(0.01) for t in tri if Polygon(t[:, :2]).area > 1e-6])
            if fp.is_empty:
                continue
            c = fp.representative_point()
            z = float(tri[:, :, 2].mean())
            is_flat = np.mean([i in flat for i in grp]) > 0.8
            fps.append((fp, "#7b3fb5" if is_flat else "#e08a00"))
            if is_flat:
                w = fk.inscribed_width(fp)
                if w > fk.RULE["bridge"][0]:
                    self.add("注意", p, f"下向きの水平な面（天井・ブリッジ）の幅 約{w:.0f}mm、高さ {z:.1f}mm。"
                             "サポートを付けるか、刷る向きを変える", fk.RULE["bridge"][1], (c.x, c.y))
                    bridge_faces += grp.tolist()
            else:
                ang = math.degrees(math.asin(min(1.0, -float(nzs[grp].min()))))
                d = fk.inscribed_width(fp)
                hint = "（水平の穴なら上側をティアドロップ形に）" if d < 8 and area < 60 else ""
                self.add("注意", p, f"45°を超えるオーバーハング：約{area:.0f}mm²、最大 {ang:.0f}°、高さ {z:.1f}mm{hint}",
                         fk.RULE["overhang"][1], (c.x, c.y))
                over_faces += grp.tolist()
        self.shapes[p["key"]] = footprint
        self.extra[p["key"]] = {"mesh": m, "over": over_faces, "bridge": bridge_faces, "thin": thin_meshes,
                                "thin2d": [c["shape"] for c in clusters], "fps": fps}

    def run(self):
        self.common()
        for p in self.prj.parts:
            if p["process"] == "laser":
                self.laser(p)
            elif p["process"] == "fdm":
                self.fdm(p)
        for f in self.f:
            if f["n"] > 1:
                f["msg"] += f"（{f['n']}か所）"
        return self.f


# ---------------------------------------------------------------- 図
def draw(chk, kind, path, plt):
    parts = [p for p in chk.prj.parts if p["process"] == kind and chk.shapes.get(p["key"]) is not None]
    if not parts:
        return False
    n = len(parts)
    cols = min(3, n)
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(6.2 * cols, 5.2 * rows), squeeze=False)
    for ax in axes.flat:
        ax.axis("off")
    for ax, p in zip(axes.flat, parts):
        ax.axis("on")
        shp = chk.shapes[p["key"]]
        fk.draw_shape(ax, shp, face="#bcd6e4" if kind == "laser" else "#d9d4cb", edge="#3b5566", lw=0.9, alpha=0.55)
        if kind == "fdm":
            ex = chk.extra.get(p["key"], {})
            for fp, col in ex.get("fps", []):
                fk.draw_shape(ax, fp, face=col, edge=col, lw=0.6, alpha=0.35)
            for g in ex.get("thin2d", []):
                fk.draw_shape(ax, g, face="#d0201a", edge="#d0201a", lw=0.8, alpha=0.7)
        marks = chk.marks.get(p["key"], [])
        seen = set()
        for mk in marks:                      # 印は輪だけ（下の穴や角が見えるように）、番号は右上に
            x, y, no, lv = mk[:4]
            if len(mk) > 4:                    # 同じ指摘の2つめ以降（内角など）は小さな点だけ
                ax.plot([x], [y], "o", ms=4, color=LV_COLOR[lv])
                continue
            ax.plot([x], [y], "o", ms=14, mfc="none", mec=LV_COLOR[lv], mew=2)
            if (no, round(x, 1), round(y, 1)) not in seen:
                ax.annotate(str(no), (x, y), xytext=(7, 7), textcoords="offset points", fontsize=9,
                            color=LV_COLOR[lv], fontweight="bold",
                            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
                seen.add((no, round(x, 1), round(y, 1)))
        nums = sorted({mk[2] for mk in marks})
        title = f"{p['name']}（{p['material'] or '材料未指定'}）"
        if kind == "fdm":
            title += "　刷る向きで上から"
        ax.set_title(title, loc="left", fontsize=11)
        ax.set_aspect("equal")
        ax.grid(True, color="#e3e7e4", lw=0.5)
        if not nums and not any(f["part"] == p["name"] and f["level"] != "確認" for f in chk.f):
            ax.text(0.02, 0.02, "問題なし", transform=ax.transAxes, color="#2e7d4f", fontsize=10)
    handles = [plt.Line2D([], [], marker="o", ls="", mfc="white", mec=c, mew=2, ms=10, label=l) for l, c in LV_COLOR.items()]
    fig.legend(handles=handles, loc="upper right", ncol=3, frameon=False, fontsize=10)
    fig.suptitle(f"{chk.prj.title} 製作前チェック（{fk.PROCESS_LABEL[kind]}）　番号は check.md の表", x=0.01, ha="left", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return True


def render3d(chk, out):
    """3Dプリント部品を刷る向きで並べ、オーバーハング（橙）・天井（紫）・薄い壁（赤）を重ねた外観"""
    rs = fk.render_script()
    if not rs or not chk.extra:
        return None
    d = os.path.join(out, "_3d")
    os.makedirs(d, exist_ok=True)
    specs, x = [], 0.0
    bad = {k: ex for k, ex in chk.extra.items() if ex["over"] or ex["bridge"] or ex["thin"]}
    if not bad:
        return None
    for key, ex in bad.items():                  # 問題のある部品だけを、刷る向きで横に並べる
        m = ex["mesh"]
        off = [x - m.bounds[0][0], 0, 0]
        x += m.extents[0] + 15
        base = m.copy().apply_translation(off)
        f = os.path.join(d, f"{key}.stl")
        base.export(f)
        specs.append(f"{f}:#d9d4cb:0.4")
        for name, faces, col in (("over", ex["over"], "#e08a00"), ("bridge", ex["bridge"], "#7b3fb5")):
            if faces:
                sub = m.submesh([faces], append=True).apply_translation(off)
                sub.apply_translation([0, 0, -0.05])
                f2 = os.path.join(d, f"{key}_{name}.stl")
                sub.export(f2)
                specs.append(f"{f2}:{col}")
        if ex["thin"]:
            tm = trimesh.util.concatenate(ex["thin"]).apply_translation(off)
            f3 = os.path.join(d, f"{key}_thin.stl")
            tm.export(f3)
            specs.append(f"{f3}:#d0201a")
    png = os.path.join(out, "check_3d.png")
    r = subprocess.run([sys.executable, rs, *specs, "--out", png, "--views", "iso,back,top",
                        "--title", f"{chk.prj.title} 刷る向き（橙＝45°超のオーバーハング、紫＝天井、赤＝薄い壁）"],
                       capture_output=True, text=True)
    import shutil
    shutil.rmtree(d, ignore_errors=True)          # 描画用の一時ファイル
    return png if r.returncode == 0 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    fk.add_common_args(ap)
    ap.add_argument("--out", help="出力先（既定 out/<版>/check）")
    ap.add_argument("--render", action="store_true", help="3Dプリント部品の問題箇所を色付けした外観も作る（数十秒）")
    a = ap.parse_args()
    prj = fk.open_project(a)
    out = os.path.abspath(a.out or os.path.join(prj.root, "out", prj.ver, "check"))
    os.makedirs(out, exist_ok=True)
    chk = Checker(prj)
    fs = chk.run()
    plt = fk.setup_font()
    imgs = []
    for kind in ("laser", "fdm"):
        pth = os.path.join(out, f"check_{kind}.png")
        if draw(chk, kind, pth, plt):
            imgs.append(pth)
    if a.render:
        r = render3d(chk, out)
        if r:
            imgs.append(r)

    cnt = {lv: sum(1 for f in fs if f["level"] == lv) for lv in fk.LEVELS}
    md = [f"# 製作前チェック {prj.title}", "",
          f"NG {cnt['NG']}件・注意 {cnt['注意']}件・確認 {cnt['確認']}件。番号は図（{', '.join(os.path.basename(i) for i in imgs) or '図なし'}）の印と同じ。", "",
          "| 部品 | 作り方 | 材料 | 板厚・向き |", "|---|---|---|---|"]
    for p in prj.parts:
        how = fk.PROCESS_LABEL.get(p["process"], "?") + ("（推定）" if p["guessed"] else "")
        extra = ""
        if p["process"] == "laser" and p.get("t"):
            extra = f"`{p['t']}`"
        elif p["process"] == "fdm" and p["print"]:
            extra = json.dumps(p["print"], ensure_ascii=False)
        md.append(f"| {p['name']} | {how} | {p['material'] or '—'} | {extra} |")
    bx, by, bz, nz, bsrc = prj.fdm_spec()
    wx, wy, wsrc = prj.laser_spec()
    md += ["", f"機材：3Dプリント {bx}×{by}" + (f"×{bz}" if bz else "") + f"mm・ノズル {nz:g}mm（{bsrc}）／"
           f"レーザー {f'{wx}×{wy}mm（{wsrc}）' if wx else '加工範囲は未登録'}"]
    md += fk.fmt_findings(fs)
    if not fs:
        md += ["", "見つかった問題はありません。"]
    md += ["", "形から機械的に見つけられるものだけを見ている。はめあい・取り合いは部分試作で、材料の可否は所属ラボのリストで確かめる。"]
    open(os.path.join(out, "check.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump({"ver": prj.ver, "count": cnt, "findings": fs, "images": [os.path.basename(i) for i in imgs]},
              open(os.path.join(out, "check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(out)
    print(f"NG {cnt['NG']}・注意 {cnt['注意']}・確認 {cnt['確認']}")
    for f in fs:
        if f["level"] != "確認":
            print(f"  {f['no']:>2} {f['level']} {f['part']}: {f['msg']}")
    for i in imgs:
        print(" ", i)


if __name__ == "__main__":
    main()
