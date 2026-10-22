"""モデル化する人に渡す寸法表 docs/寸法表_<版>.md を作る。
形の寸法、加工の値（実測か初期値か・根拠）、モックで見つかった注意点、前の版から変わった値を1枚にまとめる。
使い方: python3 tools/dims_sheet.py [v03]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common  # noqa: E402


def main():
    ver = common.version_from_argv()
    prm = common.load(ver)
    prev = common.prev_version(ver)
    old = common.load(prev) if prev else None

    def changed(k, v):
        if old is None:
            return ""
        ov = getattr(old.P, k, None)
        return "追加" if ov is None else (f"{ov} → {v}" if ov != v else "")

    lines = [f"# 寸法表 {prm.meta.get('title', '')} {ver}", "",
             "モックで決めた寸法と、加工の値です。モデル化はこの値を出発点にしてください。",
             "単位はmm、原点と向きは README の決まりに従います。", ""]
    if prm.meta.get("note"):
        lines += [f"> {prm.meta['note']}", ""]
    lines += ["## 形の寸法", "", "| 項目 | 値 | 単位 | キー | 前の版から |", "|---|---:|---|---|---|"]
    for k in prm.raw.get("params", {}):
        v = getattr(prm.P, k)
        lines.append(f"| {prm.labels[k]} | {v} | {prm.units[k]} | `{k}` | {changed(k, v)} |")

    if prm.fab:
        todo = [k for k, f in prm.fab.items() if str(f.get("status", "")).startswith("初期値")]
        lines += ["", "## 加工の値（試し片で決める値を含む）", "",
                  "Fusion ではユーザーパラメータに同じ名前（キー）で入れる。状態が「初期値」のものは、"
                  "製作の前に試し片で実測して置き換える（`tools/coupons.py`、`measurements/試し片記録.csv`）。", "",
                  "| 項目 | 値 | 単位 | キー | 状態 | 根拠 | 前の版から |", "|---|---:|---|---|---|---|---|"]
        for k, f in prm.fab.items():
            v = getattr(prm.P, k)
            lines.append(f"| {prm.labels[k]} | {v} | {prm.units[k]} | `{k}` | {f.get('status', '')} | "
                         f"{f.get('basis', '')} | {changed(k, v)} |")
        if todo:
            lines += ["", f"**まだ実測していない値：** {', '.join('`' + k + '`' for k in todo)}"]

    sp = os.path.join(common.ROOT, "out", ver, "scene.json")
    if os.path.exists(sp):
        notes = json.load(open(sp, encoding="utf-8")).get("notes") or []
        if notes:
            lines += ["", "## モックで見つかった注意点", ""] + [f"- {n}" for n in notes]
    lines += ["", "## 画像", "", f"`out/{ver}/` の外観・平面図・断面図を参照。"]
    out = os.path.join(common.ROOT, "docs", f"寸法表_{ver}.md")
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    # Fusion のユーザーパラメータに写すための一覧（名前・値・単位・コメント）
    csv = os.path.join(common.ROOT, "docs", f"fusion_params_{ver}.csv")
    with open(csv, "w", encoding="utf-8") as f:
        f.write("name,value,unit,comment\n")
        for k, v in vars(prm.P).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                st = prm.fab.get(k, {}).get("status", "")
                f.write(f"{k},{v},{prm.units[k]},\"{prm.labels[k]}{'（' + st + '）' if st else ''}\"\n")
    print(out)
    print(csv)


if __name__ == "__main__":
    main()
