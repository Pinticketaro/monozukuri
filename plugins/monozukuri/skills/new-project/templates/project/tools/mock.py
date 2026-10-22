"""モック（形と大きさの見当をつけるための粗い立体）を作る。
製造用のデータではない。最終形は Fusion などで人がモデル化する（docs/引き継ぎ.md）。

出力: out/<版>/parts/*.stl と out/<版>/scene.json（render_model.py・slices.py が読む）
使い方: python3 tools/mock.py [v03]

▼ 雛形の例：アクリル板2枚でPLAの枠を挟み、中に物を入れる箱。
  build() の中を自分の形に書き換える。部品は「名前・形・色・不透明度」で parts に足していけばよい。
  形は manifold3d で作る（押し出し・ブール演算・移動）。細部（フィレット・ネジ山など）は作らない。
"""
import json
import os
import sys

import manifold3d as m3
import numpy as np
import trimesh
from shapely.geometry import box as sbox

sys.path.insert(0, os.path.dirname(__file__))
import common  # noqa: E402

SEG = 48


# ---------- 形を作る小さな道具
def rrect(w, d, r, cx=0.0, cy=0.0):
    """角丸の長方形（中心 cx, cy）の輪郭点"""
    r = max(0.0, min(r, w / 2 - 0.01, d / 2 - 0.01))
    poly = sbox(cx - w / 2 + r, cy - d / 2 + r, cx + w / 2 - r, cy + d / 2 - r).buffer(r, quad_segs=8) if r else \
        sbox(cx - w / 2, cy - d / 2, cx + w / 2, cy + d / 2)
    return list(poly.exterior.coords)[:-1]


def slab(outline, z0, t, holes=()):
    """輪郭を z0 から厚さ t だけ押し出す。holes は輪郭点のリスト（くり抜き）"""
    cs = m3.CrossSection([outline], m3.FillRule.EvenOdd)
    for h in holes:
        cs = cs - m3.CrossSection([h], m3.FillRule.EvenOdd)
    return m3.Manifold.extrude(cs, t).translate([0, 0, z0])


def circle(cx, cy, d, n=SEG):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return [(cx + d / 2 * np.cos(t), cy + d / 2 * np.sin(t)) for t in a]


def cyl(cx, cy, d, z0, h):
    return m3.Manifold.cylinder(h, d / 2, d / 2, SEG).translate([cx, cy, z0])


def to_mesh(mf):
    g = mf.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(g.vert_properties)[:, :3], faces=np.asarray(g.tri_verts), process=False)


# ---------- ここを自分の形に書き換える
def build(prm):
    P, col = prm.P, prm.meta.get("colors", {})
    parts, notes = [], []
    W, D = P.outer_w, P.outer_d
    holes_xy = [(sx * (W / 2 - P.hole_inset), sy * (D / 2 - P.hole_inset)) for sx in (-1, 1) for sy in (-1, 1)]
    hole_pts = [circle(x, y, P.screw_clear) for x, y in holes_xy]
    outer = rrect(W, D, P.corner_r)

    z = 0.0
    parts.append(("底板", slab(outer, z, P.t_bottom, hole_pts), col.get("plate", "#bcd6e4"), 0.75))
    z += P.t_bottom

    inner = rrect(W - 2 * P.wall, D - 2 * P.wall, max(0.5, P.corner_r - P.wall))
    frame = slab(outer, z, P.frame_h, [inner] + hole_pts)
    # 造形範囲に入らなければ左右に分ける（見た目の確認用。継ぎ目の形はモデル化で決める）
    if W > P.bed_x or D > P.bed_y:
        half = m3.Manifold.cube([W, D * 2, P.frame_h * 4], True).translate([W / 2, 0, z])
        parts.append(("枠（左）", frame - half, col.get("frame", "#d9d4cb"), 1.0))
        parts.append(("枠（右）", frame ^ half, col.get("frame", "#d9d4cb"), 1.0))
        notes.append(f"枠 {W:g}×{D:g} がプリンタの範囲 {P.bed_x:g}×{P.bed_y:g} を超えるので左右2分割で表示")
    else:
        parts.append(("枠", frame, col.get("frame", "#d9d4cb"), 1.0))

    parts.append(("中身", slab(rrect(P.content_w, P.content_d, 2), z + 1.0, P.content_h), col.get("content", "#2b2f2d"), 1.0))
    if P.content_w > W - 2 * P.wall or P.content_d > D - 2 * P.wall:
        notes.append("中身が枠の内側より大きい")
    if 1.0 + P.content_h > P.frame_h:
        notes.append("中身が枠より高い（上板に当たる）")
    if P.hole_inset < 1.5 * P.screw_clear:
        notes.append(f"ネジ穴が外周に近い（{P.hole_inset:g}mm）。アクリルは穴径の1.5倍＝{1.5 * P.screw_clear:.1f}mm以上（ACRYLITE）")
    if P.wall < P.boss_d:
        notes.append(f"壁の厚さ {P.wall:g}mm がインサートのボス外径 {P.boss_d:g}mm より薄い")
    z += P.frame_h

    window = rrect(P.window_w, P.window_d, 4)
    parts.append(("上板", slab(outer, z, P.t_top, [window] + hole_pts), col.get("plate", "#bcd6e4"), 0.6))
    z += P.t_top

    screws = None
    for x, y in holes_xy:
        s = cyl(x, y, 5.5, z, 2.0)
        screws = s if screws is None else screws + s
    parts.append(("ネジ頭", screws, col.get("screw", "#8a8d91"), 1.0))
    return parts, notes


def main():
    ver = common.version_from_argv()
    prm = common.load(ver)
    parts, notes = build(prm)
    pdir = common.out_dir(ver, "parts")
    scene = {"title": f"{prm.meta.get('title', '')} {ver}", "up": "z", "views": ["iso", "back", "side"], "parts": []}
    for i, (name, mf, color, opacity) in enumerate(parts):
        fn = f"{i + 1:02d}.stl"
        to_mesh(mf).export(os.path.join(pdir, fn))
        scene["parts"].append({"file": f"parts/{fn}", "name": name, "color": color, "opacity": opacity,
                               "roughness": 0.3 if opacity < 1 else 0.8})
    scene["notes"] = notes
    sp = os.path.join(common.out_dir(ver), "scene.json")
    json.dump(scene, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(sp)
    for n in notes:
        print("注意:", n)


if __name__ == "__main__":
    main()
