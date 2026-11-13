"""形の定義を1回書けば、STL（メッシュ）と STEP（ソリッド）の両方を出せる小さなツール。

  - STL  … manifold3d で作る。速く、いつでも使える（レンダリング・断面・確認ページ用）
  - STEP … CadQuery（OpenCascade）で作る。面・円弧・円柱を持つソリッドなので、Fusion などで開いて
           押し出し・フィレット・穴などの編集ができる。モデル化の出発点に使う
           （CadQuery が入っていないときは STEP を飛ばす。monozukuri-setup スキルで入る。Windows の ARM64 版 Python には無い）

使い方（tools/mock.py の build() の中で）
    from geom import RRect, Circle, Poly, slab, prism, cyl, box, tube, cone, revolve, lug_with_slot, tab
    outer = RRect(180, 110, r=8)                      # 角丸の長方形（中心 0,0）
    plate = slab(outer, z0=0, t=3, holes=[Circle(3.4, cx=85, cy=50)])
    frame = slab(outer, 3, 16, holes=[RRect(162, 92, r=2)])
    left  = frame & box(-100, -60, 0, 100, 120, 40)    # & は交差（共通部分）、+ は結合、- は切り取り
    part  = plate.translate(0, 0, 10).rotate_z(30)     # 移動、Z軸まわりに30°回転

    # X軸・Y軸まわりの回転（軸の + の側から見て反時計回りが正）
    side  = slab(Poly([(0, 0), (60, 0), (0, 40)]), 0, 80).rotate_x(90)   # 側面の形を XY に描いて押し出し、X軸まわりに90°回転して立てる（Y→Z、Z→−Y）
    lean  = box(0, 0, 0, 3, 40, 80).rotate_y(-10, cx=0, cz=0)           # Y軸（中心 x=0, z=0）まわりに −10° 回転して、上を −X 側へ傾ける（rotate_y(90) は Z→X、X→−Z）

    # 横向きの押し出し（断面を描いた座標のまま、X・Y・Z のどれかの向きに押し出す）
    rib   = prism([(0, 0), (40, 0), (0, 30)], "x", 0, 5)   # 断面 (y, z) を x=0〜5 に押し出す。"y" なら断面 (x, z) を Y の向きに、"z" なら slab と同じ

    # レーザーの板のタブとスロット（大きさは呼び寸法のまま。カーフは入れない）
    bottom = box(0, 0, 0, 100, 60, 3)                       # 底板（3mm）
    front  = box(0, 3, 3, 100, 3, 40)                       # 底板に立てる前板
    front, bottom = tab(front, bottom, 20, 3, 0, 10, 3, 3)  # 前板の下にタブ 10×3×3 を結合し、底板に同じ大きさのスロットを抜く

    # 回転体・筒の部品
    cup   = tube(0, 0, 72, 68, 0, 90) + cyl(0, 0, 72, 0, 2)          # 筒（外径72・内径68・高さ90）＋底
    neck  = cone(0, 0, 66, 54, 110, 12)                               # 円錐台（下φ66 → 上φ54）
    knob  = revolve([(0, 0), (10, 0), (10, 4), (6, 8), (0, 8)], z0=90)  # (半径, 高さ) の点列を Z 軸まわりに回転
    ear   = lug_with_slot(r=36, angle=0, w=28, out=11, h=14, z0=72, slot_w=21, slot_t=3)  # ストラップホール付きのラグ

輪郭は「角丸の長方形」「円」「多角形」の3種類。STEP では角丸は本物の円弧、円は本物の円、
円柱・円錐・回転体は本物の曲面になる（点の並びで近似しないので、Fusion で寸法を測ったり
フィレットを掛け直したりしやすい）。単位は mm。Z が上。

English: a small toolkit. Write a shape once, and get both STL (mesh) and STEP (solid) from it.
  - STL  … made with manifold3d. Fast and always available (for renders, sections and the review page)
  - STEP … made with CadQuery (OpenCascade). A solid with real faces, arcs and cylinders, so you can open it in
           Fusion and edit it with extrude, fillet, hole and so on. Use it as the starting point for the CAD model
           (without CadQuery, STEP is skipped. The monozukuri-setup skill installs it; not available for Python on Windows ARM64)
How to use: inside build() in tools/mock.py, as in the example above.
Outlines (2D): RRect(w, d, r, cx, cy) rounded rectangle, Circle(d, cx, cy), Poly([(x, y), ...]) polygon.
Solids: slab(outline, z0, t, holes) extrude with holes, cyl(cx, cy, d, z0, h) cylinder, box(x0, y0, z0, w, d, h),
  tube(cx, cy, d_out, d_in, z0, h) hollow cylinder, cone(cx, cy, d0, d1, z0, h) truncated cone,
  revolve([(radius, height), ...], z0) solid of revolution around Z,
  lug_with_slot(r, angle, w, out, h, z0, slot_w, slot_t) strap lug on a tube,
  prism(points, axis, start, length, holes) extrude an outline along X, Y or Z. The points keep their coordinates
    (nothing is mirrored): axis "x" takes (y, z) points and fills x = start..start+length, "y" takes (x, z) points
    and fills y = start..start+length, "z" takes (x, y) points like slab.
    e.g. rib = prism([(0, 0), (40, 0), (0, 30)], "x", 0, 5)
Laser plates: tab(plate, receiver, x, y, z, dx, dy, dz) adds box(x, y, z, dx, dy, dz) to plate as a tab and cuts the
  same box from receiver as a slot; returns (plate, receiver). Nominal size: kerf is not applied.
    e.g. front, bottom = tab(front, bottom, 20, 3, 0, 10, 3, 3)
Combine: a + b union, a - b cut, a & b intersection; .translate(x, y, z), .rotate_z(deg, cx, cy),
  .rotate_x(deg, cy, cz), .rotate_y(deg, cx, cz) (counterclockwise seen from the + end of the axis is positive).
    e.g. side = slab(Poly([(0, 0), (60, 0), (0, 40)]), 0, 80).rotate_x(90) stands up a side profile drawn on XY
    (rotate_x(90): Y becomes Z, Z becomes -Y); box(0, 0, 0, 3, 40, 80).rotate_y(-10) leans the top toward -X
    (rotate_y(90): Z becomes X, X becomes -Z).
Export: export_stl, export_step, export_assembly (one STEP with named, colored parts), check_step (re-reads the STEP
  and checks its size against the mesh, a units check), to_trimesh, has_cad.
In STEP, rounded corners are real arcs, circles are real circles, and cylinders, cones and revolved shapes are real
curved surfaces (not point approximations), so dimensions and fillets are easy to work with in Fusion. Units: mm. Z is up.
"""
import math

try:
    # CadQuery は trimesh より先に読む。trimesh が STEP 用に読む cascadio も OpenCASCADE を持っていて、
    # それが先に入ると macOS では CadQuery が落ちる（Segmentation fault）
    import cadquery  # noqa: F401
except Exception:
    pass
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

    __xor__ = __and__          # manifold3d と同じ書き方（^ ＝ 交差）も使える

    def translate(self, x=0.0, y=0.0, z=0.0):
        return Solid("move", self, (float(x), float(y), float(z)))

    def rotate_z(self, deg, cx=0.0, cy=0.0):
        """Z軸（中心 cx, cy）まわりに deg 度回転する（反時計回りが正）"""
        return Solid("rotz", self, (float(deg), float(cx), float(cy)))

    def rotate_x(self, deg, cy=0.0, cz=0.0):
        """X軸（中心 cy, cz）まわりに deg 度回転する（X の正の向きから見て反時計回りが正）。
        側面の形を XY に描いて押し出し、rotate_x(90) で立てる、という使い方ができる（Y→Z、Z→−Y）"""
        return Solid("rot", self, ((1.0, 0.0, 0.0), float(deg), (0.0, float(cy), float(cz))))

    def rotate_y(self, deg, cx=0.0, cz=0.0):
        """Y軸（中心 cx, cz）まわりに deg 度回転する（Y の正の向きから見て反時計回りが正。Z→X、X→−Z）"""
        return Solid("rot", self, ((0.0, 1.0, 0.0), float(deg), (float(cx), 0.0, float(cz))))

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
            elif self.op == "revolve":
                pts, z0, cx, cy = a
                cs = m3.CrossSection([pts], m3.FillRule.EvenOdd)
                self._mf = m3.Manifold.revolve(cs, SEG).translate([cx, cy, z0])
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
            elif self.op == "rotz":
                deg, cx, cy = a[1]
                self._mf = a[0].mf().translate([-cx, -cy, 0]).rotate([0, 0, deg]).translate([cx, cy, 0])
            elif self.op == "rot":
                ax, deg, c = a[1]
                self._mf = (a[0].mf().translate([-c[0], -c[1], -c[2]])
                            .rotate([ax[0] * deg, ax[1] * deg, ax[2] * deg]).translate(list(c)))
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
            elif self.op == "revolve":
                pts, z0, cx, cy = a
                # XZ のワークプレーンでは、点の (x, y) が (半径, 高さ) になる。その面の縦軸（＝Z軸）まわりに回転する
                s = cq.Workplane("XZ").polyline(pts).close().revolve(360, (0, 0, 0), (0, 1, 0))
                self._cq = s.translate((cx, cy, z0))
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
            elif self.op == "rotz":
                deg, cx, cy = a[1]
                self._cq = a[0].cq().rotate((cx, cy, 0), (cx, cy, 1), deg)
            elif self.op == "rot":
                ax, deg, c = a[1]
                self._cq = a[0].cq().rotate(c, (c[0] + ax[0], c[1] + ax[1], c[2] + ax[2]), deg)
        return self._cq


def slab(outer, z0, t, holes=()):
    """輪郭 outer を z0 から厚さ t だけ押し出し、holes（輪郭のリスト）を抜く。
    t が負なら z0+t〜z0 に押し出す（メッシュと STEP で同じ形になるよう、ここで向きをそろえる）"""
    z0, t = float(z0), float(t)
    if t < 0:
        z0, t = z0 + t, -t
    return Solid("extrude", outer, z0, t, list(holes))


def prism(pts, axis, start, length, holes=()):
    """輪郭を X・Y・Z のどれかの向きに押し出す（横向きの角柱・リブ・レーザーの側板など）。
      axis="x" … pts は (y, z) の点。x = start〜start+length に押し出す
      axis="y" … pts は (x, z) の点。y = start〜start+length に押し出す
      axis="z" … pts は (x, y) の点。z = start〜start+length に押し出す（slab と同じ）
    pts は点の並び（閉じなくてよい）か輪郭（RRect・Circle・Poly）。holes は抜く輪郭か点の並びのリスト（pts と同じ座標で書く）。
    点は書いた座標のまま置かれる（ミラーにならない）。length が負なら start+length〜start に押し出す"""
    outer = pts if isinstance(pts, Outline) else Poly(pts)
    holes = [h if isinstance(h, Outline) else Poly(h) for h in holes]
    start, length, ax = float(start), float(length), str(axis).lower()
    if length < 0:
        start, length = start + length, -length
    if ax == "z":
        return slab(outer, start, length, holes)
    if ax == "x":
        # 断面 (u, v) を w = start〜start+length に押し出し、(u, v, w) → rotate_x(90) → (u, −w, v) → rotate_z(90) → (w, u, v)
        return slab(outer, start, length, holes).rotate_x(90).rotate_z(90)
    if ax == "y":
        # (u, v, w) → rotate_x(90) → (u, −w, v)。w を −(start+length)〜−start に置くと y = start〜start+length
        return slab(outer, -(start + length), length, holes).rotate_x(90)
    raise ValueError(f'prism の axis は "x"・"y"・"z" のどれか（axis must be "x", "y" or "z"）: {axis!r}')


def cyl(cx, cy, d, z0, h):
    """円柱：中心 (cx, cy)、直径 d、z0 から高さ h"""
    return Solid("cyl", float(cx), float(cy), float(d), float(z0), float(h))


def cone(cx, cy, d0, d1, z0, h):
    """円錐台：中心 (cx, cy)、下の直径 d0・上の直径 d1、z0 から高さ h（缶の肩・すぼまる形）"""
    return Solid("cone", float(cx), float(cy), float(d0), float(d1), float(z0), float(h))


def box(x0, y0, z0, w, d, h):
    """直方体：角 (x0, y0, z0) から w×d×h"""
    return Solid("box", float(x0), float(y0), float(z0), float(w), float(d), float(h))


def tube(cx, cy, d_out, d_in, z0, h):
    """筒（中空の円柱）：中心 (cx, cy)、外径 d_out・内径 d_in、z0 から高さ h。底を付けるときは cyl を結合する"""
    return cyl(cx, cy, d_out, z0, h) - cyl(cx, cy, d_in, z0 - EPS, h + 2 * EPS)


def revolve(profile_pts, z0=0.0, cx=0.0, cy=0.0):
    """回転体：(半径, 高さ) の点列（閉じなくてよい。半径は 0 以上）を Z 軸まわりに1周回転する。
    缶の肩・ノブ・ボトルのような形に使う。z0 だけ持ち上げ、中心を (cx, cy) に置く"""
    pts = [(max(0.0, float(r)), float(z)) for r, z in profile_pts]
    return Solid("revolve", pts, float(z0), float(cx), float(cy))


def lug_with_slot(r, angle, w, out, h, z0, slot_w, slot_t, slot_at=None, embed=2.0, cx=0.0, cy=0.0):
    """ストラップホール付きのラグ：筒の外面（半径 r）から外へ出る板状の突起に、上下に貫通する長穴（ストラップホール）を開ける。
      angle   … ラグの向き（度。0＝+X、90＝+Y）
      w, out, h … ラグの幅（周方向）、筒の外面から出る量、高さ（Z）。z0 はラグの下端
      slot_w, slot_t … 長穴の長さ（周方向＝ストラップの幅＋すきま）と幅（半径方向＝ストラップの厚み＋すきま）
      slot_at … 長穴の中心の、筒の外面からの距離（既定は out の真ん中）
      embed   … 筒とつながるよう、外面より内側へ埋め込む量（筒の壁の厚さ以下にする）
    中心 (cx, cy) の筒に付ける。筒の内側へはみ出さないよう、embed は壁の厚さ以下にする"""
    at = out / 2 if slot_at is None else slot_at
    blk = box(r - embed, -w / 2, z0, out + embed, w, h)
    hole = box(r + at - slot_t / 2, -slot_w / 2, z0 - 1, slot_t, slot_w, h + 2)
    lug = blk - hole
    if angle:
        lug = lug.rotate_z(angle)
    return lug.translate(cx, cy, 0) if (cx or cy) else lug


def tab(plate, receiver, x, y, z, dx, dy, dz):
    """タブとスロット（レーザーの板を組む）：plate に直方体 box(x, y, z, dx, dy, dz) をタブとして結合し、
    受ける板 receiver から同じ直方体をスロットとして抜く。戻り値は (タブ付きの板, スロット付きの板)。
    大きさは呼び寸法のまま（カーフ・slot_fit は入れない）。
    例：front, bottom = tab(front, bottom, 20, 3, 0, 10, 3, 3)"""
    b = box(x, y, z, dx, dy, dz)
    return plate + b, receiver - b


# ---------------------------------------------------------------- エクスポート
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
    """エクスポートした STEP を読み直して、メッシュと大きさ（mm）がそろっているか確かめる（単位チェック）。
    戻り値：(合っているか, STEPの大きさ, メッシュの大きさ)"""
    import cadquery as cq
    bb = cq.importers.importStep(path).val().BoundingBox()
    step_ext = (bb.xlen, bb.ylen, bb.zlen)
    mesh_ext = tuple(float(v) for v in to_trimesh(solid).extents)
    ok = all(abs(a - b) <= tol + 0.01 * max(a, b) for a, b in zip(step_ext, mesh_ext))
    return ok, step_ext, mesh_ext
