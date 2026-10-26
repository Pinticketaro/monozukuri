"""形の定義を1回書けば、STL（メッシュ）と STEP（ソリッド）の両方を出せる小さな道具。

  - STL  … manifold3d で作る。速く、いつでも使える（描画・断面・確認ページ用）
  - STEP … CadQuery（OpenCascade）で作る。面・円弧・円柱を持つソリッドなので、Fusion などで開いて
           押し出し・フィレット・穴などの編集ができる。モデル化の出発点に使う
           （CadQuery が入っていないときは STEP を飛ばす。setup スキルの `setup.sh --with-cad` で入る）

使い方（tools/mock.py の build() の中で）
    from geom import RRect, Circle, Poly, slab, cyl, box
    outer = RRect(180, 110, r=8)                      # 角丸の長方形（中心 0,0）
    plate = slab(outer, z0=0, t=3, holes=[Circle(3.4, cx=85, cy=50)])
    frame = slab(outer, 3, 16, holes=[RRect(162, 92, r=2)])
    left  = frame & box(-100, -60, 0, 100, 120, 40)    # & は重なり（共通部分）、+ は足す、- は引く
    part  = plate.translate(0, 0, 10)

輪郭は「角丸の長方形」「円」「多角形」の3種類。STEP では角丸は本物の円弧、円は本物の円になる
（点の並びで近似しないので、Fusion で寸法を測ったりフィレットを掛け直したりしやすい）。
単位は mm。Z が上。
"""
import math

import manifold3d as m3
import numpy as np
import trimesh

SEG = 64
EPS = 0.01


def has_cad():
    try:
        import cadquery  # noqa: F401
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- 輪郭
class Outline:
    def points(self):
        raise NotImplementedError

    def cq_extrude(self, z0, t):
        raise NotImplementedError


class RRect(Outline):
    """角丸の長方形。w×d、角の半径 r、中心 (cx, cy)"""

    def __init__(self, w, d, r=0.0, cx=0.0, cy=0.0):
        self.w, self.d, self.cx, self.cy = float(w), float(d), float(cx), float(cy)
        self.r = max(0.0, min(float(r), self.w / 2 - 0.01, self.d / 2 - 0.01))

    def points(self):
        w, d, r, cx, cy = self.w, self.d, self.r, self.cx, self.cy
        if r <= 0:
            return [(cx - w / 2, cy - d / 2), (cx + w / 2, cy - d / 2), (cx + w / 2, cy + d / 2), (cx - w / 2, cy + d / 2)]
        pts, n = [], max(4, SEG // 4)
        for (sx, sy, a0) in [(1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)]:
            ox, oy = cx + sx * (w / 2 - r), cy + sy * (d / 2 - r)
            for i in range(n + 1):
                a = math.radians(a0 + 90 * i / n)
                pts.append((ox + r * math.cos(a), oy + r * math.sin(a)))
        return pts

    def cq_extrude(self, z0, t):
        import cadquery as cq
        s = cq.Workplane("XY").workplane(offset=z0).center(self.cx, self.cy).rect(self.w, self.d).extrude(t)
        return s.edges("|Z").fillet(self.r) if self.r > 0 else s


class Circle(Outline):
    """円。直径 d、中心 (cx, cy)"""

    def __init__(self, d, cx=0.0, cy=0.0):
        self.d, self.cx, self.cy = float(d), float(cx), float(cy)

    def points(self):
        return [(self.cx + self.d / 2 * math.cos(a), self.cy + self.d / 2 * math.sin(a))
                for a in np.linspace(0, 2 * math.pi, SEG, endpoint=False)]

    def cq_extrude(self, z0, t):
        import cadquery as cq
        return cq.Workplane("XY").workplane(offset=z0).center(self.cx, self.cy).circle(self.d / 2).extrude(t)


class Poly(Outline):
    """多角形。点の並び [(x, y), ...]（閉じなくてよい）"""

    def __init__(self, pts):
        self.pts = [(float(x), float(y)) for x, y in pts]

    def points(self):
        return self.pts

    def cq_extrude(self, z0, t):
        import cadquery as cq
        return cq.Workplane("XY").workplane(offset=z0).polyline(self.pts).close().extrude(t)


# ---------------------------------------------------------------- 立体
class Solid:
    """形の作り方（木構造）を覚えておき、必要になったら STL 用・STEP 用それぞれに作る。"""

    def __init__(self, op, *args):
        self.op, self.args = op, args
        self._mf = None
        self._cq = None

    # 組み合わせ
    def __add__(self, o):
        return Solid("union", self, o)

    def __sub__(self, o):
        return Solid("cut", self, o)

    def __and__(self, o):
        return Solid("inter", self, o)

    __xor__ = __and__          # manifold3d と同じ書き方（^ ＝ 重なり）も使える

    def translate(self, x=0.0, y=0.0, z=0.0):
        return Solid("move", self, (float(x), float(y), float(z)))

    # メッシュ（manifold3d）
    def mf(self):
        if self._mf is None:
            a = self.args
            if self.op == "extrude":
                outer, z0, t, holes = a
                cs = m3.CrossSection([outer.points()], m3.FillRule.EvenOdd)
                for h in holes:
                    cs = cs - m3.CrossSection([h.points()], m3.FillRule.EvenOdd)
                self._mf = m3.Manifold.extrude(cs, t).translate([0, 0, z0])
            elif self.op == "cyl":
                cx, cy, d, z0, h = a
                self._mf = m3.Manifold.cylinder(h, d / 2, d / 2, SEG).translate([cx, cy, z0])
            elif self.op == "cone":
                cx, cy, d0, d1, z0, h = a
                self._mf = m3.Manifold.cylinder(h, d0 / 2, d1 / 2, SEG).translate([cx, cy, z0])
            elif self.op == "box":
                x0, y0, z0, w, d, h = a
                self._mf = m3.Manifold.cube([w, d, h]).translate([x0, y0, z0])
            elif self.op == "union":
                self._mf = a[0].mf() + a[1].mf()
            elif self.op == "cut":
                self._mf = a[0].mf() - a[1].mf()
            elif self.op == "inter":
                self._mf = a[0].mf() ^ a[1].mf()
            elif self.op == "move":
                self._mf = a[0].mf().translate(list(a[1]))
        return self._mf

    # ソリッド（CadQuery）
    def cq(self):
        if self._cq is None:
            import cadquery as cq
            a = self.args
            if self.op == "extrude":
                outer, z0, t, holes = a
                s = outer.cq_extrude(z0, t)
                for h in holes:                       # 穴は少し長く抜いて、薄い膜が残らないようにする
                    s = s.cut(h.cq_extrude(z0 - EPS, t + 2 * EPS))
                self._cq = s
            elif self.op == "cyl":
                cx, cy, d, z0, h = a
                self._cq = cq.Workplane("XY").workplane(offset=z0).center(cx, cy).circle(d / 2).extrude(h)
            elif self.op == "cone":
                cx, cy, d0, d1, z0, h = a
                self._cq = cq.Workplane("XY").add(cq.Solid.makeCone(d0 / 2, d1 / 2, h, cq.Vector(cx, cy, z0)))
            elif self.op == "box":
                x0, y0, z0, w, d, h = a
                self._cq = cq.Workplane("XY").box(w, d, h, centered=False).translate((x0, y0, z0))
            elif self.op == "union":
                self._cq = a[0].cq().union(a[1].cq())
            elif self.op == "cut":
                self._cq = a[0].cq().cut(a[1].cq())
            elif self.op == "inter":
                self._cq = a[0].cq().intersect(a[1].cq())
            elif self.op == "move":
                self._cq = a[0].cq().translate(a[1])
        return self._cq


def slab(outer, z0, t, holes=()):
    """輪郭 outer を z0 から厚さ t だけ押し出し、holes（輪郭のリスト）を抜く"""
    return Solid("extrude", outer, float(z0), float(t), list(holes))


def cyl(cx, cy, d, z0, h):
    """円柱：中心 (cx, cy)、直径 d、z0 から高さ h"""
    return Solid("cyl", float(cx), float(cy), float(d), float(z0), float(h))


def cone(cx, cy, d0, d1, z0, h):
    """円錐台：中心 (cx, cy)、下の直径 d0・上の直径 d1、z0 から高さ h（缶の肩・すぼまる形）"""
    return Solid("cone", float(cx), float(cy), float(d0), float(d1), float(z0), float(h))


def box(x0, y0, z0, w, d, h):
    """直方体：角 (x0, y0, z0) から w×d×h"""
    return Solid("box", float(x0), float(y0), float(z0), float(w), float(d), float(h))


# ---------------------------------------------------------------- 書き出し
def to_trimesh(solid):
    g = solid.mf().to_mesh()
    return trimesh.Trimesh(np.asarray(g.vert_properties)[:, :3], np.asarray(g.tri_verts), process=False)


def export_stl(solid, path):
    to_trimesh(solid).export(path)


def export_step(solid, path):
    import cadquery as cq
    cq.exporters.export(solid.cq(), path, exportType="STEP")


def export_assembly(parts, path):
    """parts: [(名前, Solid, "#rrggbb", 不透明度), ...] を、名前と色の付いた1つの STEP にまとめる。
    Fusion で開くと部品ごとのコンポーネントになる。"""
    import cadquery as cq
    import os
    assy = cq.Assembly(name=os.path.splitext(os.path.basename(path))[0])
    for name, solid, color, opacity in parts:
        h = color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        assy.add(solid.cq(), name=name, color=cq.Color(r, g, b, float(opacity)))
    if hasattr(assy, "export"):
        assy.export(path)
    else:
        assy.save(path, exportType="STEP")


def check_step(solid, path, tol=0.05):
    """書き出した STEP を読み直して、メッシュと大きさ（mm）がそろっているか確かめる（単位の関所）。
    戻り値：(合っているか, STEPの大きさ, メッシュの大きさ)"""
    import cadquery as cq
    bb = cq.importers.importStep(path).val().BoundingBox()
    step_ext = (bb.xlen, bb.ylen, bb.zlen)
    mesh_ext = tuple(float(v) for v in to_trimesh(solid).extents)
    ok = all(abs(a - b) <= tol + 0.01 * max(a, b) for a, b in zip(step_ext, mesh_ext))
    return ok, step_ext, mesh_ext
