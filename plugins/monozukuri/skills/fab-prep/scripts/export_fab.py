"""加工データを書き出す（4つめの関所「本番」の手前）。モックでも、人がモデル化した STL / STEP でも使える。

  レーザーの板 → 材料・板厚ごとに SVG と DXF（単位 mm）
                 カーフ補正：閉じた輪郭を k/2 ずらす（外形は外へ、穴は内へ。k は寸法ファイルの kerf）
                 赤＝切断、部品ごとに「内側の穴 → 外形」の順。加工範囲に並べ、入らなければシートを分ける
  3Dプリント   → 部品ごとに 3MF（単位 mm）。刷る向き（meta.parts の print）にしてベッドの上に置く
  加工しない部品（既製品・中身）は書き出さない

出力：out/<版>/fab/
  laser_<材料>_<板厚>mm.svg / .dxf / .png（並べた図）、fdm_NN_<キー>.3mf、fab.md（何をどう書き出したか・
  加工ソフトで読み込んだら確かめる寸法）、index.json

使い方
  python3 tools/export_fab.py v05                 # 寸法ファイルの kerf で補正
  python3 tools/export_fab.py v05 --no-kerf       # 補正なし（LightBurn の Kerf Offset で補正するとき）
  python3 tools/export_fab.py --scene out/v06/scene.json   # 人が作ったモデル（scene.json の部品に "process" を書く）
  python3 <プラグイン>/skills/fab-prep/scripts/export_fab.py --root <プロジェクト> v05
カーフ補正はデータか加工ソフトの「どちらか一方」だけにする。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fabkit as fk  # noqa: E402


def slug(s):
    s = re.sub(r"[\\/:*?\"<>|\s（）()・]+", "", str(s or "材料未指定"))
    return s[:24] or "材料未指定"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    fk.add_common_args(ap)
    ap.add_argument("--out", help="出力先（既定 out/<版>/fab）")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--no-kerf", action="store_true", help="カーフ補正をしない（加工ソフトで補正する）")
    g.add_argument("--kerf", type=float, help="カーフの全幅 k を直接指定（寸法ファイルより優先）")
    ap.add_argument("--only", choices=["laser", "fdm"])
    ap.add_argument("--parts", help="キーをカンマ区切りで（既定：全部）")
    ap.add_argument("--gap", type=float, default=3.0, help="部品どうしのすき間 mm（既定3）")
    a = ap.parse_args()

    prj = fk.open_project(a)
    out = os.path.abspath(a.out or os.path.join(prj.root, "out", prj.ver, "fab"))
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out) if os.path.basename(out) == "fab" else []:   # 前回の書き出しが残ると取り違えるので消す（fab/ の中だけ）
        if f.startswith(("laser_", "fdm_")):
            os.remove(os.path.join(out, f))
    want = set(a.parts.split(",")) if a.parts else None
    parts = [p for p in prj.parts if (not want or p["key"] in want)]
    plt = fk.setup_font()

    md = [f"# 加工データ {prj.title}", "",
          "モックから書き出したデータは形と比率を確かめるためのもの。本番は、人がモデル化して確かめたモデルから書き出す。", ""]
    warn, index = [], []

    guessed = [p for p in parts if p["guessed"]]
    if guessed:
        md += ["**作り方を形から推定した部品**（寸法ファイルの meta.parts か scene.json に process を書くと確定する）：",
               ", ".join(f"{p['name']}→{fk.PROCESS_LABEL[p['process']]}" for p in guessed), ""]

    # ---------------- レーザー
    groups = {}
    if a.only in (None, "laser"):
        for p in [p for p in parts if p["process"] == "laser"]:
            lv, why = fk.material_safety(p["material"], prj.laser_rules())
            if lv == "NG":                       # 全面禁止・ラボで禁止の材料は書き出さない
                warn.append(f"{p['name']}：書き出していない。{why}")
                continue
            prof = fk.plate_profile(prj.mesh(p))
            if not prof["prismatic"] or prof["shape"] is None:
                warn.append(f"{p['name']}：上下で断面が違う（段差・座ぐり・彫り込み）ので、板として書き出せない。fab_check.py を参照")
                continue
            t, st, tkey, nominal = prj.sheet_thickness(p, prof["t"])
            if tkey and abs(t - prof["t"]) > 0.05:
                warn.append(f"{p['name']}：モデルの板厚 {prof['t']:.2f}mm と寸法ファイルの {tkey}={t:g}mm が違う"
                            "（モデルを実測の板厚で描き直すか、はめあいを確かめる）")
            nom = float(nominal) if nominal else round(t * 2) / 2
            groups.setdefault((p["material"] or "材料未指定", nom), []).append((p, prof, t, st, tkey))

    wx, wy, wsrc = prj.laser_spec()
    mats = {m for m, _ in groups}
    for (mat, nom), items in groups.items():
        if a.no_kerf:
            k, kst, kkey = 0.0, "補正なし（加工ソフトで補正）", None
        elif a.kerf is not None:
            k, kst, kkey = a.kerf, "コマンドで指定", None
        else:
            k, kst, kkey = prj.kerf(mat, nom)
            if k is None:
                k, kst = 0.0, "寸法ファイルに kerf が無いので補正なし"
                warn.append(f"{mat} {nom:g}mm：寸法ファイルに kerf が無いのでカーフ補正なしで書き出した")
        if kkey and len(mats) > 1 and not prj.fab_item(kkey).get("material"):
            warn.append(f"{mat} {nom:g}mm：カーフ {kkey} は材料を区別していない（材料が {len(mats)} 種類）。"
                        f"材料ごとに kerf_<材料>（\"material\" と \"nominal\" 付き）を足す")
        if str(kst).startswith("初期値"):
            warn.append(f"{mat} {nom:g}mm：カーフ {k:g}mm はまだ初期値。試し片で測ってから本番を切る")
        shapes = [(p["key"], fk.kerf_offset(prof["shape"], k)) for p, prof, *_ in items]
        sheets, too_big = fk.pack(shapes, wx, wy, gap=a.gap)
        for nm in too_big:
            warn.append(f"{nm}：加工範囲 {wx}×{wy}mm（{wsrc}）に入らない。分割するか大きい機械で")
        byname = {p["key"]: (p, prof, t, st, tkey) for p, prof, t, st, tkey in items}
        for si, sheet in enumerate(sheets):
            base = f"laser_{slug(mat)}_{nom:g}mm" + (f"_{si + 1}" if len(sheets) > 1 else "")
            used_w = max(s.bounds[2] for _, s, _ in sheet) + 5
            used_h = max(s.bounds[3] for _, s, _ in sheet) + 5
            W, H = (float(wx), float(wy)) if wx and wy else (used_w, used_h)
            svg_items = [(f"p{byname[k_][0]['i']:02d}_{k_}", byname[k_][0]["name"], s) for k_, s, _ in sheet]
            note = f"{prj.title} {mat} 板厚{nom:g}mm用。カーフ k={k:g}mm（{kst}）で補正済み" if k else \
                f"{prj.title} {mat} 板厚{nom:g}mm用。カーフ補正なし"
            fk.write_svg(os.path.join(out, base + ".svg"), svg_items, W, H, note)
            has_dxf = fk.write_dxf(os.path.join(out, base + ".dxf"), svg_items)
            if not has_dxf:
                warn.append("DXF は書き出せなかった（ezdxf が無い。setup スキルで入る）。SVG を使う")

            # 並べた図
            fig, ax = plt.subplots(figsize=(12, 12 * H / W if W > 0 else 8))
            ax.add_patch(plt.Rectangle((0, 0), W, H, fill=False, ec="#8a8d91", lw=1, ls="--"))
            big = None
            for k_, s, rot in sheet:
                p, prof, t, st, tkey = byname[k_]
                fk.draw_shape(ax, s, face="#f3c7c0", edge="#d0201a", lw=0.8, alpha=0.45)
                x0, y0, x1, y1 = s.bounds
                ax.text((x0 + x1) / 2, (y0 + y1) / 2, f"{p['name']}\n{x1 - x0:.2f}×{y1 - y0:.2f}" + ("（90°回転）" if rot else ""),
                        ha="center", va="center", fontsize=9, color="#3b2522")
                if big is None or (x1 - x0) * (y1 - y0) > big[1] * big[2]:
                    big = (p["name"], x1 - x0, y1 - y0)
            ax.set_aspect("equal")
            ax.set_xlim(-5, W + 5)
            ax.set_ylim(-5, H + 5)
            ax.set_title(f"{base}　{mat} 板厚{nom:g}mm　カーフ k={k:g}mm" + ("" if wx else "（加工範囲が未登録）"),
                         loc="left", fontsize=12)
            ax.grid(True, color="#e3e7e4", lw=0.5)
            fig.tight_layout()
            fig.savefig(os.path.join(out, base + ".png"), dpi=110)
            plt.close(fig)

            md += [f"## レーザー：{base}.svg / .dxf", "",
                   f"- 材料：{mat}、板厚 {nom:g}mm（{', '.join(sorted({f'{tk}={t:g}（{st}）' for _p, _pr, t, st, tk in byname.values() if tk})) or 'モデルの厚さ'}）",
                   f"- カーフ補正：k = {k:g}mm（{kst}{'、キー ' + kkey if kkey else ''}）。外形は外へ・穴は内へ k/2 = {k / 2:g}mm",
                   f"- 加工範囲：{f'{wx}×{wy}mm（{wsrc}）' if wx else '未登録（機材を登録すると範囲で並べる）'}",
                   f"- **読み込んだら確かめる寸法**：いちばん大きい輪郭「{big[0]}」が {big[1]:.2f} × {big[2]:.2f} mm"
                   "（1/25.4・1.067倍・1.333倍になっていたら単位か解像度の取り違え）", "",
                   "| 部品 | 補正後の外形 | 穴の数 | 回転 |", "|---|---|---:|---|"]
            for k_, s, rot in sheet:
                p = byname[k_][0]
                x0, y0, x1, y1 = s.bounds
                nh = sum(len(g.interiors) for g in fk.polys(s))
                md.append(f"| {p['name']} | {x1 - x0:.2f} × {y1 - y0:.2f} | {nh} | {'90°' if rot else ''} |")
            md.append("")
            index.append({"kind": "laser", "svg": base + ".svg", "dxf": base + ".dxf" if has_dxf else None,
                          "png": base + ".png", "material": mat, "nominal": nom, "kerf": k,
                          "parts": [k_ for k_, _, _ in sheet]})

    # ---------------- 3Dプリント
    if a.only in (None, "fdm"):
        bx, by, bz, nz, bsrc = prj.fdm_spec()
        fdm = [p for p in parts if p["process"] == "fdm"]
        if fdm:
            md += ["## 3Dプリント", "", f"造形範囲：{bx}×{by}" + (f"×{bz}" if bz else "") + f" mm（{bsrc}）", "",
                   "| ファイル | 部品 | 材料 | 大きさ（刷る向き） | 範囲 |", "|---|---|---|---|---|"]
        for p in fdm:
            m = fk.print_orient(prj.mesh(p), p)
            ex = m.extents
            fits = True
            if bx and by:
                fits = (ex[0] <= bx and ex[1] <= by) or (ex[1] <= bx and ex[0] <= by)
                if bz:
                    fits = fits and ex[2] <= bz
            fn = f"fdm_{p['i'] + 1:02d}_{p['key']}.3mf"
            fk.export_3mf(m, os.path.join(out, fn))
            if not fits:
                warn.append(f"{p['name']}：{ex[0]:.0f}×{ex[1]:.0f}×{ex[2]:.0f}mm が造形範囲（{bsrc}）に入らない。分割が要る")
            if not m.is_watertight:
                warn.append(f"{p['name']}：メッシュが閉じていない（穴あき）。スライサーで修復されるか確かめる")
            md.append(f"| {fn} | {p['name']} | {p['material'] or '—'} | {ex[0]:.1f}×{ex[1]:.1f}×{ex[2]:.1f} | "
                      f"{'入る' if fits else '**入らない**'} |")
            index.append({"kind": "fdm", "file": fn, "part": p["key"], "material": p["material"],
                          "size": [round(float(v), 2) for v in ex], "fits": bool(fits)})
        if fdm:
            hc = prj.fab_item("hole_comp")
            md += ["", "- 穴の補正は CAD かスライサーの**一方だけ**。"
                   + (f"寸法ファイルの hole_comp = {hc.get('value')}（{hc.get('status', '')}）。" if hc else "")
                   + "モックの穴は補正なしで描いてある",
                   "- 刷る向きは寸法ファイルの meta.parts の print（flip / rot）で変えられる。オーバーハングとブリッジは fab_check.py で確かめる", ""]

    skipped = [p for p in parts if p["process"] == "none"]
    if skipped:
        md += ["## 書き出していない部品（加工しない）", "", ", ".join(p["name"] for p in skipped), ""]
    todo = prj.todo_fab()
    if todo:
        md += ["## まだ初期値の加工の値", "", "本番の前に試し片で測る：" + ", ".join(f"`{k}`" for k in todo), ""]
    if warn:
        md += ["## 注意", ""] + [f"- {w}" for w in warn] + [""]
    md += ["## 加工の前に（チェックリストから）", "",
           "- レーザー：加工ソフトで読み込んだら上の寸法を測る、色と条件の対応、内側から切る、材料はラボで許可されている",
           "- 3Dプリント：本番と同じフィラメント・設定、穴の補正は一方だけ、ベッド面の縁の面取り",
           "- 送ったファイルと寸法ファイルをコミットしてタグ（例 `cut-1`）"]
    open(os.path.join(out, "fab.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump({"ver": prj.ver, "files": index, "warnings": warn}, open(os.path.join(out, "index.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(out)
    for it in index:
        print("  ", it.get("svg") or it.get("file"), "" if it["kind"] == "fdm" else f"（k={it['kerf']:g}）")
    for w in warn:
        print("注意:", w)


if __name__ == "__main__":
    main()
