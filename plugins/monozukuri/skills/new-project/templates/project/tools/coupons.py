"""試し片（クーポン）を作る。公開されている数値は機械・材料ごとに圧入とガタの差ほどずれるので、
本番の前にこれを切って・刷って、自分の機材の値を決める。結果は measurements/試し片記録.csv に書き、
寸法ファイルの fab の値を「実測」に置き換える。

出力: out/coupons/
  laser_<板厚>.svg      … レーザー用。カーフを測る四角（20mm角＋10mm角の穴）、スロット幅を
                          板厚−0.20〜+0.20mm（0.05刻み・9本）で並べたコーム、差し込む細板
                          赤＝切断（内側の穴→外形の順に切る）、青＝刻印（番号の点）。カーフ補正なしで描いてある
  fdm_fit.stl           … 3Dプリント用。ピン（φ6）と、穴 φ6＋2×クリアランス（clr_fit−0.1〜+0.1、0.05刻み）の板
  fdm_insert.stl        … ヒートインサートの下穴 4.0〜4.4mm（0.1刻み）、深さ insert_depth
  coupons.md            … 番号と値の対応、測り方、どの値をどこに書くか
番号は「点の数」で示す（1点＝1番）。文字は使わない（レーザーソフト・スライサーでの文字化けを避けるため）。

使い方: python3 tools/coupons.py [v03]
"""
import os
import sys

import manifold3d as m3
import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(__file__))
import common  # noqa: E402

SEG = 48
STEPS = [-0.20, -0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20]


# ---------------- レーザー（SVG、単位mm）
def svg_rect(x, y, w, h, color="#ff0000"):
    return f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" fill="none" stroke="{color}" stroke-width="0.01"/>'


def svg_dots(cx, y, n, color="#0000ff"):
    """n個の点（刻印）。1行5個まで、中心 cx にそろえる"""
    out = []
    for i in range(n):
        row, col = divmod(i, 5)
        cnt = min(5, n - row * 5)
        x = cx - (cnt - 1) * 0.6 + col * 1.2
        out.append(f'<circle cx="{x:.3f}" cy="{y + row * 1.3:.3f}" r="0.35" fill="{color}" stroke="none"/>')
    return "".join(out)


def comb_path(x0, y0, T, widths, depth=10.0, pitch_gap=6.0, h=24.0):
    """下の辺からスロットが切り込まれた細長い板の外形（1本の閉じたパス）"""
    pts = [(x0, y0)]
    x = x0 + pitch_gap
    for w in widths:
        pts += [(x, y0), (x, y0 + depth), (x + w, y0 + depth), (x + w, y0)]
        x += w + pitch_gap
    L = x - x0
    pts += [(x0 + L, y0), (x0 + L, y0 + h), (x0, y0 + h)]
    d = "M " + " L ".join(f"{a:.3f},{b:.3f}" for a, b in pts) + " Z"
    return f'<path d="{d}" fill="none" stroke="#ff0000" stroke-width="0.01"/>', L


def laser_svg(T, out):
    widths = [round(T + s, 3) for s in STEPS]
    parts, notes = [], []
    # 1) カーフを測る四角：外形20mm角、穴10mm角（穴を先に切る）
    parts.append(svg_rect(10, 10, 10, 10))              # 内側の穴
    parts.append(svg_rect(5, 5, 20, 20))                # 外形
    # 2) スロットのコーム（スロットの奥に番号の点）
    comb, L = comb_path(35, 5, T, widths)
    x = 35 + 6.0
    for i, w in enumerate(widths):
        parts.append(svg_dots(x + w / 2, 5 + 10 + 3, i + 1))
        x += w + 6.0
    parts.append(comb)
    # 3) 差し込む細板（同じシートから。幅10mm）
    parts.append(svg_rect(35, 36, 40, 10))
    W, H = max(35 + L + 5, 80), 52
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.2f}mm" height="{H:.2f}mm" '
           f'viewBox="0 0 {W:.3f} {H:.3f}">\n<!-- 板厚 {T}mm 用。赤=切断、青=刻印。カーフ補正なし -->\n'
           + "\n".join(parts) + "\n</svg>\n")
    open(out, "w", encoding="utf-8").write(svg)
    return widths


# ---------------- 3Dプリント（STL）
def cyl(x, y, d, z0, h):
    return m3.Manifold.cylinder(h, d / 2, d / 2, SEG).translate([x, y, z0])


def box(x0, y0, z0, w, d, h):
    return m3.Manifold.cube([w, d, h]).translate([x0, y0, z0])


def dimples(x, y, z_top, n):
    s = None
    for i in range(n):
        c = cyl(x + i * 1.8, y, 1.0, z_top - 0.6, 1.0)
        s = c if s is None else s + c
    return s


def to_mesh(mf):
    g = mf.to_mesh()
    return trimesh.Trimesh(np.asarray(g.vert_properties)[:, :3], np.asarray(g.tri_verts), process=False)


def fdm_fit(clr, out):
    pin_d, pitch, H = 6.0, 12.0, 5.0
    clrs = [round(clr + s, 3) for s in (-0.10, -0.05, 0.0, 0.05, 0.10)]
    n = len(clrs)
    plate = box(0, 0, 0, pitch * n + 4, 22, H)
    for i, c in enumerate(clrs):
        x = 2 + pitch / 2 + i * pitch
        plate = plate - cyl(x, 8, pin_d + 2 * c, -1, H + 2) - dimples(x - (i * 0.9), 18, H, i + 1)
    # ピン（土台つき）。土台の上に高さ8のピン
    pin = box(0, 26, 0, 14, 14, 2) + cyl(7, 33, pin_d, 2, 8)
    to_mesh(plate + pin).export(out)
    return clrs


def fdm_insert(depth, out):
    holes = [4.0, 4.1, 4.2, 4.3, 4.4]
    pitch, H = 12.0, depth + 2.0
    blk = box(0, 0, 0, pitch * len(holes) + 4, 20, H)
    for i, d in enumerate(holes):
        x = 2 + pitch / 2 + i * pitch
        blk = blk - cyl(x, 8, d, H - depth, depth + 1) - dimples(x - (i * 0.9), 16.5, H, i + 1)
    to_mesh(blk).export(out)
    return holes


def main():
    ver = common.version_from_argv()
    prm = common.load(ver)
    P = prm.P
    out = os.path.join(common.ROOT, "out", "coupons")
    os.makedirs(out, exist_ok=True)
    lines = [f"# 試し片 {prm.meta.get('title', '')}（{ver} の値から作成）", "",
             "番号は点の数（1点＝1番）。結果は `measurements/試し片記録.csv` に書き、寸法ファイルの `fab` を更新して状態を「実測」にする。", ""]

    thick = sorted({v for k, v in vars(P).items() if k.startswith("t_") and isinstance(v, (int, float))})
    for T in thick:
        fn = f"laser_{T:g}mm.svg"
        widths = laser_svg(T, os.path.join(out, fn))
        lines += [f"## レーザー：{fn}（板厚 {T:g}mm 用）", "",
                  "1. **板厚を測る**：シートの4隅と中央をノギスで測り、平均を `t_` の値にする（呼び寸法と違うことが多い）",
                  "2. **カーフ**：20mm角の外形を測る。カーフ k（切断溝の全幅）＝ 20 − 測った値。X方向とY方向を別に記録する",
                  "   - 確かめ：10mm角の穴は 10 ＋ k、抜けた中身は 10 − k になる",
                  "3. **スロットのコーム**：細板を各スロットに差し、指で押して入り・抜けない番号を選ぶ",
                  "", "| 番号 | 描いたスロット幅 | 板厚との差 |", "|---:|---:|---:|"]
        lines += [f"| {i + 1} | {w:.2f} | {s:+.2f} |" for i, (w, s) in enumerate(zip(widths, STEPS))]
        lines += ["", "- コームは**カーフ補正なし**で描いてある。本番も補正なしで描くなら、選んだ「板厚との差」をそのまま使う。"
                  "補正ありで描くなら、カーフ k を `kerf` に入れて k/2 ずつずらす（外形は外へ、穴は内へ）。どちらか一方に決める",
                  "- アクリルは圧入しない（締め付けで内角から割れる）。すきまばめ＋ネジか接着にする", ""]

    if not hasattr(P, "clr_fit"):                      # 3Dプリントを使わないプロジェクト（fab に clr_fit が無い）
        lines += partial_lines()
        return finish(out, lines)
    clrs = fdm_fit(P.clr_fit, os.path.join(out, "fdm_fit.stl"))
    lines += ["## 3Dプリント：fdm_fit.stl", "",
              "平置きで、本番と同じフィラメント・同じ設定で刷る。スライサーの穴補正は本番と同じにする。", "",
              "| 番号 | 穴径（φ6＋2×クリアランス） | クリアランス（片側） |", "|---:|---:|---:|"]
    lines += [f"| {i + 1} | {6 + 2 * c:.2f} | {c:.2f} |" for i, c in enumerate(clrs)]
    lines += ["", "- 力を入れずに入って回る番号 → `clr_slide`、軽く押して入りガタがない番号 → `clr_fit`",
              "- このクリアランスにはプリンタの穴の縮みが含まれる。ピンと穴のはめ合いは `clr_*` だけで描き、`hole_comp` は重ねない", ""]

    if hasattr(P, "insert_depth"):
        holes = fdm_insert(P.insert_depth, os.path.join(out, "fdm_insert.stl"))
        lines += ["## 3Dプリント：fdm_insert.stl", "",
                  f"M3インサート用の下穴 {holes[0]}〜{holes[-1]}mm、深さ {P.insert_depth:g}mm。外周4本・インフィル25%以上で刷る（UW–Madison）。", "",
                  "- こては印刷温度＋10〜20℃から始め、約90%まで沈めてから平らな物で面一に押さえ、15〜30秒冷ます（CNC Kitchen・UW）",
                  "- まっすぐ入り、周りが盛り上がらず、ネジを締めても回らない番号 → `insert_hole`",
                  "", "| 番号 | 下穴径 |", "|---:|---:|"] + [f"| {i + 1} | {d:.1f} |" for i, d in enumerate(holes)]
    lines += partial_lines()
    finish(out, lines)


def partial_lines():
    return ["", "## 部分試作（本番の前に）", "",
            "いちばん合わせが難しい所（差し込み・ネジ・中身の角など）だけを切り出して切る・刷る。実物を合わせて確かめる。"
            "USB-C の切り欠きがあるなら、いちばん太いケーブルで試す（切り欠きはケーブル側の太さで決まる）。"]


def finish(out, lines):
    open(os.path.join(out, "coupons.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(out)
    for f in sorted(os.listdir(out)):
        print(" ", f)


if __name__ == "__main__":
    main()
