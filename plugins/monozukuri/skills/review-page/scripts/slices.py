"""立体モデルを切って、平面図（上から見た各部品の輪郭の重ね合わせ）と断面図を描く。
部品ごとに色を分けるので、穴ずれ・はみ出し・すき間がひと目でわかる。
平面図は、断面（濃い線）の下に、真上から見た外形（薄い面）を重ねる。切る高さに無い耳や出っ張りも外形で見える。

使い方
  python3 slices.py --scene scene.json --plan plan.png                 （各部品の高さの中央で切る）
  python3 slices.py --scene scene.json --plan plan.png --plan-z 45,80  （高さ 45mm と 80mm で切る）
  python3 slices.py --scene scene.json --section section.png --at y=50      （Y=50mm の面で切る）
  python3 slices.py --scene scene.json --section section.png --at x=80 --zoom 0,40
    --zoom=a,b … 断面の横方向を a〜b mm だけ拡大して描く（負の値があるので = でつなぐ）
    --zoom=a,b,c,d … 横方向 a〜b mm、高さ c〜d mm を拡大して描く（溝や段差など小さな所を見るとき）
座標はモデルのまま（単位mm、up=z を前提。up=y のモデルは scene.json に "up": "y"）。
言葉（見出し・凡例）は --lang ja|en、無ければ scene.json の "lang"、環境変数 MONOZUKURI_LANG、どれも無ければ ja。
"""
import argparse
import json
import os
import sys

import matplotlib
import numpy as np
import trimesh

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


def resolve_lang(explicit=None, data=None):
    """言葉を決める：引数の --lang ＞ データ（scene.json の "lang"）＞ 環境変数 MONOZUKURI_LANG ＞ ja"""
    for v in (explicit, data, os.environ.get("MONOZUKURI_LANG")):
        if v in ("ja", "en"):
            return v
    return "ja"


def help_lang(argv):
    """--help の言葉。引数を読む前なので、--lang と --scene の scene.json だけ先に見る"""
    got = {}
    for i, s in enumerate(argv):
        for k in ("--lang", "--scene"):
            if s == k and i + 1 < len(argv):
                got[k] = argv[i + 1]
            elif s.startswith(k + "="):
                got[k] = s[len(k) + 1:]
    data = None
    try:
        data = json.load(open(got["--scene"], encoding="utf-8")).get("lang")
    except Exception:
        pass
    return resolve_lang(got.get("--lang"), data)


def setup_font():
    try:
        env = json.load(open(os.path.expanduser("~/.cache/monozukuri/env.json"), encoding="utf-8"))
        if env.get("cjk_font_path"):
            font_manager.fontManager.addfont(env["cjk_font_path"])
            plt.rcParams["font.family"] = env["cjk_font"]
    except Exception:
        pass


def load_mm(path):
    """メッシュとして読み、mm にそろえる。STEP は cascadio 経由でメートルになるので換算する
    （組み立て STEP はシーンとして読まれるので、シーンの単位で換算してから1つにまとめる）。"""
    obj = trimesh.load(path)
    units = getattr(obj, "units", None)
    if units and units not in ("millimeters", "mm"):
        obj = obj.convert_units("millimeters")
    if isinstance(obj, trimesh.Scene):
        obj = obj.to_mesh() if hasattr(obj, "to_mesh") else obj.dump(concatenate=True)
    return obj


def load(scene_path):
    sc = json.load(open(scene_path, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(scene_path))
    parts = []
    for p in sc["parts"]:
        f = p["file"] if os.path.isabs(p["file"]) else os.path.join(base, p["file"])
        m = load_mm(f)                          # STEP（メートル）も mm にそろえる
        if sc.get("up", "z") == "y":
            m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
        parts.append((p.get("name", os.path.basename(f)), p.get("color", "#888888"), m))
    return sc, parts


def loops_to_shape(loops):
    """閉じた輪郭の集まりを、内外を交互に（偶奇で）まとめた面にする。"""
    from shapely.geometry import Polygon
    shape = None
    for lp in loops:
        if len(lp) < 4:
            continue
        p = Polygon(lp[:, :2]).buffer(0)
        shape = p if shape is None else shape.symmetric_difference(p)
    return shape


def darker(color, k=0.55):
    from matplotlib.colors import to_rgb
    return tuple(c * k for c in to_rgb(color))


def draw_shape(ax, shape, color, lw, fill_alpha, ls="-", zorder=2):
    if shape is None or shape.is_empty:
        return
    edge = darker(color)
    for poly in getattr(shape, "geoms", [shape]):
        xs, ys = poly.exterior.xy
        ax.fill(xs, ys, color=color, alpha=fill_alpha, lw=0, zorder=zorder)
        ax.plot(xs, ys, color=edge, lw=lw, ls=ls, zorder=zorder)
        for h in poly.interiors:
            hx, hy = h.xy
            ax.plot(hx, hy, color=edge, lw=lw * 0.8, ls=ls, zorder=zorder)


def silhouette(m):
    """真上から見た外形：上向きの面を XY に落として和を取る（閉じた立体なら、これで全部の面を落としたのと同じ）"""
    from shapely import union_all
    from shapely.geometry import Polygon
    tri = m.triangles[m.face_normals[:, 2] > 1e-6][:, :, :2]
    polys = [Polygon(t) for t in tri]
    polys = [p for p in polys if p.area > 1e-6]
    return union_all(polys).buffer(0) if polys else None


def draw_silhouette(ax, shape, color):
    if shape is None or shape.is_empty:
        return
    for poly in getattr(shape, "geoms", [shape]):
        if poly.geom_type != "Polygon":
            continue
        xs, ys = poly.exterior.xy
        ax.fill(xs, ys, color=color, alpha=0.35, lw=0, zorder=1)
        ax.plot(xs, ys, color=darker(color, 0.75), lw=0.9, alpha=0.8, zorder=1)
        for h in poly.interiors:
            hx, hy = h.xy
            ax.fill(hx, hy, color="white", alpha=0.5, lw=0, zorder=1)


SEC_STYLES = ["-", "--", ":", "-."]


def plan(sc, parts, out, zs=None, lang="ja"):
    """zs：切る高さのリスト（mm）。None なら各部品の高さの中央"""
    ja = lang == "ja"
    fig, ax = plt.subplots(figsize=(14, 8))
    handles = []
    for name, color, m in parts:
        draw_silhouette(ax, silhouette(m), color)
    for name, color, m in parts:
        z0, z1 = m.bounds[0][2], m.bounds[1][2]
        cuts = [(z0 + z1) / 2] if zs is None else [z for z in zs if z0 < z < z1]
        for z in cuts:
            sec = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
            if sec is None:
                continue
            ls = "-" if zs is None else SEC_STYLES[zs.index(z) % len(SEC_STYLES)]
            draw_shape(ax, loops_to_shape(sec.discrete), color, 1.5, 0.18, ls=ls, zorder=3)
        if ja:
            where = f"、断面{(z0 + z1) / 2:.1f}" if zs is None else ("、断面なし" if not cuts else "")
            label = f"{name}（高さ{z0:.1f}〜{z1:.1f}{where}）"
        else:
            where = f", cut at {(z0 + z1) / 2:.1f}" if zs is None else (", not cut" if not cuts else "")
            label = f"{name} (height {z0:.1f}–{z1:.1f}{where})"
        handles.append(plt.Line2D([], [], color=darker(color, 0.8), lw=3, label=label))
    if zs is not None:
        handles += [plt.Line2D([], [], color="#444", lw=1.6, ls=SEC_STYLES[i % len(SEC_STYLES)],
                               label=f"高さ{z:g}mmの断面" if ja else f"Section at height {z:g} mm")
                    for i, z in enumerate(zs)]
    handles.append(Patch(color="#999", alpha=0.3, label="薄い面＝真上から見た外形" if ja else "Light fill = outline seen from above"))
    ax.set_aspect("equal")
    ax.set_axisbelow(True)
    ax.grid(True, color="#dde3de", lw=0.6)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=10, frameon=False)
    if ja:
        what = "各部品の高さの中央" if zs is None else "高さ " + "・".join(f"{z:g}" for z in zs) + "mm"
        title = f"{sc.get('title', '')} 平面図（濃い線＝{what}の断面、薄い面＝真上から見た外形）"
    else:
        what = "mid-height of each part" if zs is None else "height " + ", ".join(f"{z:g}" for z in zs) + " mm"
        title = f"{sc.get('title', '')} Plan (dark lines = section at {what}, light fill = outline seen from above)"
    ax.set_title(title, fontsize=13, loc="left")
    fig.tight_layout()
    fig.savefig(out, dpi=120, bbox_inches="tight", pad_inches=0.2)
    print(out)


def section(sc, parts, out, at, zoom, lang="ja"):
    axis, val = at.split("=")
    val = float(val)
    normal = {"x": [1, 0, 0], "y": [0, 1, 0]}[axis]
    origin = [val if axis == "x" else 0, val if axis == "y" else 0, 0]
    horiz = 1 if axis == "x" else 0          # 断面図の横軸：xで切ったらY、yで切ったらX
    fig, ax = plt.subplots(figsize=(14, 5))
    handles = []
    for name, color, m in parts:
        sec = m.section(plane_origin=origin, plane_normal=normal)
        if sec is None:
            continue
        loops = [np.column_stack([ent[:, horiz], ent[:, 2]]) for ent in sec.discrete]
        draw_shape(ax, loops_to_shape(loops), color, 1.1, 0.55)
        handles.append(plt.Line2D([], [], color=color, lw=6, alpha=0.6, label=name))
    ax.set_aspect("equal")
    ax.set_axisbelow(True)
    ax.grid(True, color="#dde3de", lw=0.6)
    if zoom:
        z = [float(v) for v in zoom.split(",")]
        ax.set_xlim(z[0], z[1])
        if len(z) >= 4:
            ax.set_ylim(z[2], z[3])
    ax.set_xlabel(("Y" if axis == "x" else "X") + " (mm)")
    ax.set_ylabel("Z (mm)")
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=10, frameon=False)
    ax.set_title(f"{sc.get('title', '')} 断面 {axis.upper()}={val:g}mm" if lang == "ja"
                 else f"{sc.get('title', '')} Section {axis.upper()}={val:g} mm", fontsize=13, loc="left")
    fig.tight_layout()
    fig.savefig(out, dpi=120, bbox_inches="tight", pad_inches=0.2)
    print(out)


def main():
    ja = help_lang(sys.argv[1:]) == "ja"
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--plan")
    ap.add_argument("--plan-z", help="平面図で切る高さ（mm、カンマ区切り）。例: 45,80。省くと各部品の高さの中央" if ja
                    else "heights to cut the plan at (mm, comma-separated), e.g. 45,80. Default: mid-height of each part")
    ap.add_argument("--section")
    ap.add_argument("--at", default=None, help="x=値 または y=値（既定：Yの中央）" if ja else "x=value or y=value (default: middle of Y)")
    ap.add_argument("--zoom")
    ap.add_argument("--lang", choices=["ja", "en"], help="見出し・凡例の言葉（既定：scene.json の lang ＞ 環境変数 MONOZUKURI_LANG ＞ ja）" if ja
                    else "language of titles and legends (default: scene.json lang > MONOZUKURI_LANG > ja)")
    a = ap.parse_args()
    setup_font()
    sc, parts = load(a.scene)
    lang = resolve_lang(a.lang, sc.get("lang"))
    if a.plan:
        plan(sc, parts, a.plan, [float(z) for z in a.plan_z.split(",")] if a.plan_z else None, lang)
    if a.section:
        at = a.at
        if not at:
            lo = min(m.bounds[0][1] for _, _, m in parts)
            hi = max(m.bounds[1][1] for _, _, m in parts)
            at = f"y={(lo + hi) / 2:.2f}"
        section(sc, parts, a.section, at, a.zoom, lang)


if __name__ == "__main__":
    main()
