"""モック（形と大きさの見当をつけるための粗い立体）を作る。
最終形は Fusion などで人がモデル化する（docs/引き継ぎ.md）。STEP はその出発点として使える。

出力
  out/<版>/parts/*.stl         … 部品ごとのメッシュ（レンダリング・断面・確認ページ用）
  out/<版>/scene.json          … 部品名・色・不透明度（render_model.py・slices.py が読む）
  out/<版>/step/NN_<キー>.step … 部品ごとのソリッド（CadQuery があるとき。--no-step で省く）
  out/<版>/step/assembly_<版>.step … 全部品を名前と色付きでまとめたもの（Fusion で開くと部品ごとのコンポーネント）
  out/<版>/step/index.json     … STEP の一覧（確認ページの「エクスポート」に載せるとき使う）
使い方: python tools/mock.py [v03] [--no-step]

▼ テンプレートの例（全部レーザーカット）：アクリル 3mm の板5枚（底板・前・後ろ・左右の側板）をタブとスロットで組む、ふたの無い小物入れ。
  向き：正面が −Y、幅が X、高さが Z。外形の中心が X=0・Y=0、底板の下面が Z=0。
  板どうしは、タブ（板の縁から出した突起）を相手の板のスロット（穴）に通して組む。前後の板は側板より end_margin だけ外へ出し、
  側板のタブを受けるスロットの外に縁を残す。モックのタブとスロットは呼び寸法（カーフ・slot_fit の補正なし。
  補正はレーザーカット用のデータを作るときに入れる）。板厚は fab の t_bottom を全部の板に使う（同じシートからカットする。
  厚さの違う板があれば、fab に t_<名前> を足す）。
  build() の中を自分の形に書き換える。形は geom.py の関数で書く（同じ定義から STL と STEP の両方ができる）。
  部品は (表示名, 形, 色, 不透明度, 英字のキー[, オプション]) で足す。キーはファイル名と STEP の部品名に使う
  （STEP の部品名を英数字にしておくと、Fusion などで文字化けしない）。オプションは
  {"print": False}（3Dプリントしない部品：中身・既製品・レーザーの板）、{"up": "-z"}（印刷の向き）。
  notes には文字の注意のほか、決めてほしいことを問いの候補として書ける（確認ページでボタンで答えられる問いになる）：
    {"q": "仕切りを付けますか", "type": "yesno", "why": "小物を分けて入れられる"}
    {"q": "前の板の高さ", "type": "options", "options": ["後ろと同じ", {"label": "低くする", "note": "補足"}], "why": "…"}
  輪郭：RRect（角丸の長方形）・Circle（円）・Poly（多角形）。立体：slab（押し出し＋穴）・prism（X・Y・Z の向きに押し出し）・
  cyl（円柱）・box（直方体）。レーザーの板：tab（板にタブを結合し、受ける板に同じ大きさのスロットを抜く）。
  組み合わせ：+ 結合、- 切り取り、& 交差、.translate(x, y, z)、.rotate_z(角度)・.rotate_x(角度)・.rotate_y(角度)
  （斜めに立てる板は、立てた板を rotate_x・rotate_y で傾ける）。細部（スロットの内角のR・刻印など）は作らない。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common  # noqa: E402
from geom import RRect, prism, slab, tab  # noqa: E402


# ---------- ここを自分の形に書き換える
def build(prm):
    P, col = prm.P, prm.meta.get("colors", {})
    parts, notes = [], []

    def spots(a, b, w):
        """a〜b の縁に並べるタブの中心。短い縁（タブの幅の6倍未満）は真ん中に1つ、長い縁は2つ"""
        n = 2 if b - a >= 6 * w else 1
        return [a + (b - a) * (i + 0.5) / n for i in range(n)]

    t = P.t_bottom                                   # 板厚（全部の板を同じシートからカットする）
    W, D, H, m, e, tw = P.outer_w, P.outer_d, P.wall_h, P.margin, P.end_margin, P.tab_w
    x0, x1, y0, y1 = -W / 2 + m, W / 2 - m, -D / 2 + m, D / 2 - m   # 前後の板の左右の端、前の板の前面・後ろの板の背面
    xs = (x0 + e, x1 - e - t)                        # 左右の側板の左の面の X
    zb = t                                           # 壁の下端（底板の上面）

    bottom = slab(RRect(W, D, P.corner_r), 0, t)
    # 前後の板は断面 (x, z) を Y の向きに、側板は断面 (y, z) を X の向きに押し出す（板の形を変えるときは点を書き換える）
    fb = [(x0, zb), (x1, zb), (x1, zb + H), (x0, zb + H)]
    front, back = prism(fb, "y", y0, t), prism(fb, "y", y1 - t, t)
    sd = [(y0 + t, zb), (y1 - t, zb), (y1 - t, zb + H), (y0 + t, zb + H)]
    sides = [prism(sd, "x", x, t) for x in xs]

    # 底板へのタブ（各板の下の縁から）
    for xc in spots(x0, x1, tw):
        front, bottom = tab(front, bottom, xc - tw / 2, y0, 0, tw, t, t)
        back, bottom = tab(back, bottom, xc - tw / 2, y1 - t, 0, tw, t, t)
    for k, x in enumerate(xs):
        for yc in spots(y0 + t, y1 - t, tw):
            sides[k], bottom = tab(sides[k], bottom, x, yc - tw / 2, 0, t, tw, t)
    # 側板から前後の板へのタブ（側板の前と後ろの縁から）
    for k, x in enumerate(xs):
        for zc in spots(zb, zb + H, tw):
            sides[k], front = tab(sides[k], front, x, y0, zc - tw / 2, t, t, tw)
            sides[k], back = tab(sides[k], back, x, y1 - t, zc - tw / 2, t, t, tw)

    pc, sc = col.get("plate", "#bcd6e4"), col.get("side", "#9fc3d6")
    for name, s, c, key in [("底板", bottom, pc, "bottom"), ("前の板", front, pc, "front"), ("後ろの板", back, pc, "back"),
                            ("左の側板", sides[0], sc, "side_left"), ("右の側板", sides[1], sc, "side_right")]:
        parts.append((name, s, c, 0.85, key, {"print": False}))

    # 寸法から機械的にわかる問題
    if m < t:
        notes.append(f"底板のスロットの縁距離 {m:g}mm が板厚 {t:g}mm より小さい（アクリルは割れやすい）")
    if e < t:
        notes.append(f"前後の板のスロットの縁距離 {e:g}mm が板厚 {t:g}mm より小さい（アクリルは割れやすい）")
    if tw < 3 * t:
        notes.append(f"タブの幅 {tw:g}mm が板厚の3倍＝{3 * t:g}mm より細い（折れやすい）")
    if tw > H:
        notes.append(f"タブの幅 {tw:g}mm が壁の高さ {H:g}mm より大きい（側板のタブが前後の板に収まらない）")
    else:
        ev = min(min(zc - tw / 2 - zb, zb + H - (zc + tw / 2)) for zc in spots(zb, zb + H, tw))
        if ev < t:
            notes.append(f"前後の板のスロット（側板のタブ）の上下の縁距離 {ev:g}mm が板厚 {t:g}mm より小さい（アクリルは割れやすい）")
    plates = {"底板": (W, D), "前の板・後ろの板": (x1 - x0, H + t), "側板": (y1 - y0, H + t)}   # タブを含めた外接する長方形
    lx, ly = P.laser_x, P.laser_y
    big = [f"{n}（{a:g}×{b:g}mm）" for n, (a, b) in plates.items()
           if max(a, b) > max(lx, ly) or min(a, b) > min(lx, ly)]
    if big:
        notes.append(f"レーザー加工機の加工範囲 {lx:g}×{ly:g}mm に入らない板：" + "、".join(big))
    notes.append(f"外形 幅{W:g}×奥行き{D:g}×高さ{H + t:g}mm、内寸 幅{xs[1] - xs[0] - t:g}×奥行き{y1 - y0 - 2 * t:g}×深さ{H:g}mm。"
                 f"板は5枚（アクリル {t:g}mm）")
    fit = getattr(P, "slot_fit", 0.0)
    notes.append(f"スロットの幅は 板厚＋slot_fit＝{t + fit:.2f}mm（レーザーカットのデータで使う。モックは板厚のまま。"
                 f"slot_fit はスロットのコームで決める）")
    notes.append({"q": "前の板の高さ", "type": "options",
                  "options": ["後ろの板と同じ（今の形）", {"label": "低くする", "note": "側板の上は前から後ろへ斜めにする"}],
                  "why": "前が低いと中が見え、物を取り出しやすい。同じ高さなら板の形が単純になる"})
    notes.append({"q": "仕切りを付けますか", "type": "yesno",
                  "why": "小物を分けて入れられる。板が1枚増え、前後の板にスロットが増える"})
    return parts, notes


if __name__ == "__main__":
    common.run_mock(build)
