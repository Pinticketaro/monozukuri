"""立体モデルを切って、平面図（上から見た各部品の輪郭の重ね合わせ）と断面図を描く。
部品ごとに色を分けるので、穴ずれ・はみ出し・すき間がひと目でわかる。

使い方
  python3 slices.py --scene scene.json --plan plan.png
  python3 slices.py --scene scene.json --section section.png --at y=50      （Y=50mm の面で切る）
  python3 slices.py --scene scene.json --section section.png --at x=80 --zoom 0,40
    --zoom=a,b … 断面の横方向を a〜b mm だけ拡大して描く（負の値があるので = でつなぐ）
座標はモデルのまま（単位mm、up=z を前提。up=y のモデルは scene.json に "up": "y"）。
"""
import argparse
import json
import os

import matplotlib
import numpy as np
import trimesh

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402


def setup_font():
    try:
        env = json.load(open(os.path.expanduser("~/.cache/monozukuri/env.json")))
        if env.get("cjk_font_path"):
            font_manager.fontManager.addfont(env["cjk_font_path"])
            plt.rcParams["font.family"] = env["cjk_font"]
    except Exception:
        pass


def load(scene_path):
    sc = json.load(open(scene_path, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(scene_path))
    parts = []
    for p in sc["parts"]:
        f = p["file"] if os.path.isabs(p["file"]) else os.path.join(base, p["file"])
        m = trimesh.load(f, force="mesh")
        if getattr(m, "units", None) and m.units not in ("millimeters", "mm"):
            m.convert_units("millimeters")      # STEP（メートル）を mm にそろえる
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


def draw_shape(ax, shape, color, lw, fill_alpha):
    if shape is None or shape.is_empty:
        return
    edge = darker(color)
    for poly in getattr(shape, "geoms", [shape]):
        xs, ys = poly.exterior.xy
        ax.fill(xs, ys, color=color, alpha=fill_alpha, lw=0)
        ax.plot(xs, ys, color=edge, lw=lw)
        for h in poly.interiors:
            hx, hy = h.xy
            ax.plot(hx, hy, color=edge, lw=lw * 0.8)


def plan(sc, parts, out):
    fig, ax = plt.subplots(figsize=(14, 8))
    handles = []
    for name, color, m in parts:
        z0, z1 = m.bounds[0][2], m.bounds[1][2]
        sec = m.section(plane_origin=[0, 0, (z0 + z1) / 2], plane_normal=[0, 0, 1])
        if sec is None:
            continue
        draw_shape(ax, loops_to_shape(sec.discrete), color, 1.3, 0.18)
        handles.append(plt.Line2D([], [], color=darker(color, 0.8), lw=3, label=f"{name}（高さ{z0:.1f}〜{z1:.1f}）"))
    ax.set_aspect("equal")
    ax.set_axisbelow(True)
    ax.grid(True, color="#dde3de", lw=0.6)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=10, frameon=False)
    ax.set_title(f"{sc.get('title', '')} 平面図（各部品の高さの中央で切った輪郭）", fontsize=13, loc="left")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    print(out)


def section(sc, parts, out, at, zoom):
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
        a, b = map(float, zoom.split(","))
        ax.set_xlim(a, b)
    ax.set_xlabel(("Y" if axis == "x" else "X") + " (mm)")
    ax.set_ylabel("Z (mm)")
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=10, frameon=False)
    ax.set_title(f"{sc.get('title', '')} 断面 {axis.upper()}={val:g}mm", fontsize=13, loc="left")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    print(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--plan")
    ap.add_argument("--section")
    ap.add_argument("--at", default=None, help="x=値 または y=値（既定：Yの中央）")
    ap.add_argument("--zoom")
    a = ap.parse_args()
    setup_font()
    sc, parts = load(a.scene)
    if a.plan:
        plan(sc, parts, a.plan)
    if a.section:
        at = a.at
        if not at:
            lo = min(m.bounds[0][1] for _, _, m in parts)
            hi = max(m.bounds[1][1] for _, _, m in parts)
            at = f"y={(lo + hi) / 2:.2f}"
        section(sc, parts, a.section, at, a.zoom)


if __name__ == "__main__":
    main()
