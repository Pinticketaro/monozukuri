"""モック（形と大きさの見当をつけるための粗い立体）を作る。
最終形は Fusion などで人がモデル化する（docs/引き継ぎ.md）。STEP はその出発点として使える。

出力
  out/<版>/parts/*.stl         … 部品ごとのメッシュ（描画・断面・確認ページ用）
  out/<版>/scene.json          … 部品名・色・不透明度（render_model.py・slices.py が読む）
  out/<版>/step/NN_<キー>.step … 部品ごとのソリッド（CadQuery があるとき。--no-step で省く）
  out/<版>/step/assembly_<版>.step … 全部品を名前と色付きでまとめたもの（Fusion で開くと部品ごとのコンポーネント）
  out/<版>/step/index.json     … STEP の一覧（確認ページの「書き出す」に載せるとき使う）
使い方: python3 tools/mock.py [v03] [--no-step]

▼ 雛形の例：アクリル板2枚でPLAの枠を挟み、中に物を入れる箱。
  build() の中を自分の形に書き換える。形は geom.py の道具で書く（同じ定義から STL と STEP の両方ができる）。
  部品は (表示名, 形, 色, 不透明度, 英字のキー[, オプション]) で足す。キーはファイル名と STEP の部品名に使う
  （STEP の部品名を英数字にしておくと、Fusion などで文字化けしない）。オプションは
  {"print": False}（3Dプリントしない部品：中身・既製品・レーザーの板）、{"up": "-z"}（印刷の向き）。
  3Dプリントする部品は、サポートが要りそうな下向きの面（張り出し overhang_deg より浅い面）が自動で注意に出る。
  輪郭：RRect（角丸の長方形）・Circle（円）・Poly（多角形）。立体：slab（押し出し＋穴）・cyl（円柱）・box（直方体）。
  組み合わせ：+ 足す、- 引く、& 重なり、.translate(x, y, z)。細部（フィレット・ネジ山など）は作らない。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common  # noqa: E402
from geom import Circle, RRect, box, cyl, slab  # noqa: E402


# ---------- ここを自分の形に書き換える
def build(prm):
    P, col = prm.P, prm.meta.get("colors", {})
    parts, notes = [], []
    W, D = P.outer_w, P.outer_d
    holes_xy = [(sx * (W / 2 - P.hole_inset), sy * (D / 2 - P.hole_inset)) for sx in (-1, 1) for sy in (-1, 1)]
    holes = [Circle(P.screw_clear, x, y) for x, y in holes_xy]
    outer = RRect(W, D, P.corner_r)

    z = 0.0
    parts.append(("底板", slab(outer, z, P.t_bottom, holes), col.get("plate", "#bcd6e4"), 0.75, "bottom_plate", {"print": False}))
    z += P.t_bottom

    inner = RRect(W - 2 * P.wall, D - 2 * P.wall, max(0.5, P.corner_r - P.wall))
    frame = slab(outer, z, P.frame_h, [inner] + holes)
    # 造形範囲に入らなければ左右に分ける（見た目の確認用。継ぎ目の形はモデル化で決める）
    if W > P.bed_x or D > P.bed_y:
        right = box(0, -D, z - 1, W, 2 * D, P.frame_h + 2)
        parts.append(("枠（左）", frame - right, col.get("frame", "#d9d4cb"), 1.0, "frame_left"))
        parts.append(("枠（右）", frame & right, col.get("frame", "#d9d4cb"), 1.0, "frame_right"))
        notes.append(f"枠 {W:g}×{D:g} がプリンタの範囲 {P.bed_x:g}×{P.bed_y:g} を超えるので左右2分割で表示")
    else:
        parts.append(("枠", frame, col.get("frame", "#d9d4cb"), 1.0, "frame"))

    parts.append(("中身", slab(RRect(P.content_w, P.content_d, 2), z + 1.0, P.content_h), col.get("content", "#2b2f2d"), 1.0, "content",
                  {"print": False}))
    if P.content_w > W - 2 * P.wall or P.content_d > D - 2 * P.wall:
        notes.append("中身が枠の内側より大きい")
    if 1.0 + P.content_h > P.frame_h:
        notes.append("中身が枠より高い（上板に当たる）")
    if P.hole_inset < 1.5 * P.screw_clear:
        notes.append(f"ネジ穴が外周に近い（{P.hole_inset:g}mm）。アクリルは穴径の1.5倍＝{1.5 * P.screw_clear:.1f}mm以上（ACRYLITE）")
    if hasattr(P, "boss_d") and P.wall < P.boss_d:
        notes.append(f"壁の厚さ {P.wall:g}mm がインサートのボス外径 {P.boss_d:g}mm より薄い")
    z += P.frame_h

    parts.append(("上板", slab(outer, z, P.t_top, [RRect(P.window_w, P.window_d, 4)] + holes),
                  col.get("plate", "#bcd6e4"), 0.6, "top_plate", {"print": False}))
    z += P.t_top

    heads = None
    for x, y in holes_xy:
        c = cyl(x, y, 5.5, z, 2.0)
        heads = c if heads is None else heads + c
    parts.append(("ネジ頭", heads, col.get("screw", "#8a8d91"), 1.0, "screw_heads", {"print": False}))
    return parts, notes


if __name__ == "__main__":
    common.run_mock(build)
