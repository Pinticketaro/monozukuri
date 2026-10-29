"""モック（形と大きさの見当をつけるための粗い立体）を作る。
最終形は Fusion などで人がモデル化する（docs/引き継ぎ.md）。STEP はその出発点として使える。

出力
  out/<版>/parts/*.stl         … 部品ごとのメッシュ（描画・断面・確認ページ用）
  out/<版>/scene.json          … 部品名・色・不透明度（render_model.py・slices.py が読む）
  out/<版>/step/NN_<キー>.step … 部品ごとのソリッド（CadQuery があるとき。--no-step で省く）
  out/<版>/step/assembly_<版>.step … 全部品を名前と色付きでまとめたもの（Fusion で開くと部品ごとのコンポーネント）
  out/<版>/step/index.json     … STEP の一覧（確認ページの「書き出す」に載せるとき使う）
使い方: python3 tools/mock.py [v03] [--no-step]

▼ 雛形の例（全部3Dプリント）：350ml缶を入れる底つきの筒に、ストラップを通す耳を左右に付けたケース。
  build() の中を自分の形に書き換える。形は geom.py の道具で書く（同じ定義から STL と STEP の両方ができる）。
  部品は (表示名, 形, 色, 不透明度, 英字のキー[, オプション]) で足す。キーはファイル名と STEP の部品名に使う
  （STEP の部品名を英数字にしておくと、Fusion などで文字化けしない）。オプションは
  {"print": False}（3Dプリントしない部品：中身・既製品・レーザーの板）、{"up": "-z"}（印刷の向き）。
  3Dプリントする部品は、サポートが要りそうな下向きの面（オーバーハング overhang_deg より浅い面）が自動で注意に出る。
  notes には文字の注意のほか、決めてほしいことを問いの候補として書ける（確認ページでボタンで答えられる問いになる）：
    {"q": "抜け止めを付けますか", "type": "yesno", "why": "缶が逆さで落ちる"}
    {"q": "耳の位置", "type": "options", "options": ["上端", {"label": "中ほど", "note": "補足"}], "why": "…"}
  輪郭：RRect（角丸の長方形）・Circle（円）・Poly（多角形）。立体：slab（押し出し＋穴）・cyl（円柱）・box（直方体）・
  tube（筒）・cone（円錐台）・revolve（回転体）・lug_with_slot（ストラップを通す耳）。
  組み合わせ：+ 足す、- 引く、& 重なり、.translate(x, y, z)、.rotate_z(角度)。細部（フィレット・ネジ山など）は作らない。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common  # noqa: E402
from geom import cone, cyl, lug_with_slot, tube  # noqa: E402


# ---------- ここを自分の形に書き換える
def build(prm):
    P, col = prm.P, prm.meta.get("colors", {})
    parts, notes = [], []
    r_in = P.can_d / 2 + P.can_gap
    r_out = r_in + P.wall
    H = P.sleeve_h

    # 筒＋底（底に水抜き穴）
    body = tube(0, 0, 2 * r_out, 2 * r_in, 0, H) + cyl(0, 0, 2 * r_out, 0, P.bottom_t)
    body = body - cyl(0, 0, P.drain_d, -1, P.bottom_t + 2)
    # 耳（左右）：ストラップを上下に通す長穴つき。筒の壁に食い込ませてつなぐ
    lug_z0 = H - P.lug_top_gap - P.lug_h
    for ang in (0, 180):
        body = body + lug_with_slot(r=r_out, angle=ang, w=P.lug_w, out=P.lug_out, h=P.lug_h, z0=lug_z0,
                                    slot_w=P.strap_w + 2 * P.strap_clr, slot_t=P.strap_t + 2 * P.strap_clr,
                                    embed=min(2.0, P.wall))
    parts.append(("ケース", body, col.get("body", "#d9d4cb"), 1.0, "case"))

    # 中身（確認用）：缶の胴＋すぼまる肩
    z = P.bottom_t
    can_body_h = P.can_h - P.can_neck_h
    can = cyl(0, 0, P.can_d, z, can_body_h) + cone(0, 0, P.can_d, P.can_top_d, z + can_body_h, P.can_neck_h)
    parts.append(("缶（中身）", can, col.get("content", "#b23a3a"), 1.0, "can", {"print": False}))

    # 寸法から機械的にわかる問題
    if hasattr(P, "clr_slide") and P.can_gap < P.clr_slide:
        notes.append(f"缶とのすきま {P.can_gap:g}mm が着脱のクリアランス {P.clr_slide:g}mm より小さい（缶が入らないおそれ）")
    if P.wall < 0.8:
        notes.append(f"壁 {P.wall:g}mm がノズル径0.4の2倍＝0.8mm より薄い")
    outer_x = 2 * (r_out + P.lug_out)
    if outer_x > P.bed_x or 2 * r_out > P.bed_y or H > P.bed_z:
        notes.append(f"外形 {outer_x:.0f}×{2 * r_out:.0f}×{H:g} がプリンタの範囲 {P.bed_x:g}×{P.bed_y:g}×{P.bed_z:g} を超える")
    exposed = P.bottom_t + P.can_h - H
    notes.append(f"缶は筒の上から {exposed:.0f}mm 出る（缶の高さの {exposed / P.can_h * 100:.0f}%）")
    return parts, notes


if __name__ == "__main__":
    common.run_mock(build)
