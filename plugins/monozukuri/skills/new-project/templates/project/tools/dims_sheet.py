"""モデル化する人に渡す寸法表 docs/寸法表_<版>.md を作る。
形の寸法、加工の値（実測か初期値か・根拠）、モックで見つかった注意点、前の版から変わった値を1枚にまとめる。
使い方: python3 tools/dims_sheet.py [v03] [--lang ja|en]

English: writes the dimension sheet for the person who builds the CAD model: docs/dims_<version>.md
(Japanese projects: docs/寸法表_<version>.md), plus docs/fusion_params_<version>.csv for Fusion user parameters.
One page with the shape dimensions, the fabrication values (measured or initial, and the basis), notes found in
the mock, and the values changed from the previous version. Language: meta.lang in the params file (or --lang ja|en).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common  # noqa: E402

TXT = {
    "ja": {
        "file": "寸法表_{ver}.md",
        "added": "追加",
        "title": "# 寸法表 {title} {ver}",
        "intro": ["モックで決めた寸法と、加工の値です。モデル化はこの値を出発点にしてください。",
                  "単位はmm、原点と向きは README の決まりに従います。"],
        "shape_h": "## 形の寸法",
        "shape_cols": ["| 項目 | 値 | 単位 | キー | 前の版から |", "|---|---:|---|---|---|"],
        "fab_h": "## 加工の値（試し片で決める値を含む）",
        "fab_intro": "Fusion ではユーザーパラメータに同じ名前（キー）で入れる。状態が「初期値」のものは、"
                     "製作の前に試し片で実測して置き換える（`tools/coupons.py`、`measurements/試し片記録.csv`）。",
        "fab_cols": ["| 項目 | 値 | 単位 | キー | 状態 | 根拠 | 前の版から |", "|---|---:|---|---|---|---|---|"],
        "todo": "**まだ実測していない値：** ",
        "notes_h": "## モックで見つかった注意点",
        "img_h": "## 画像",
        "img": "`out/{ver}/` の外観・平面図・断面図を参照。",
        "csv_status": "（{st}）",
    },
    "en": {
        "file": "dims_{ver}.md",
        "added": "added",
        "title": "# Dimension sheet {title} {ver}",
        "intro": ["These are the dimensions decided with the mock, and the fabrication values. "
                  "Use them as the starting point for the CAD model.",
                  "Units are mm. The origin and axes follow the rules in README."],
        "shape_h": "## Shape dimensions",
        "shape_cols": ["| Item | Value | Unit | Key | Change from previous version |", "|---|---:|---|---|---|"],
        "fab_h": "## Fabrication values (including values set with coupons)",
        "fab_intro": "In Fusion, enter them as user parameters with the same names (keys). Values with the status \"initial\" "
                     "must be measured with coupons and replaced before fabrication "
                     "(`tools/coupons.py`, `measurements/coupon_log.csv`).",
        "fab_cols": ["| Item | Value | Unit | Key | Status | Basis | Change from previous version |",
                     "|---|---:|---|---|---|---|---|"],
        "todo": "**Not measured yet:** ",
        "notes_h": "## Notes found in the mock",
        "img_h": "## Images",
        "img": "See the exterior views, plan views and sections in `out/{ver}/`.",
        "csv_status": " ({st})",
    },
}


def not_measured(status):
    """まだ試し片で測っていない値か（状態が「初期値」、英語の寸法ファイルでは "initial"）"""
    s = str(status)
    return s.startswith("初期値") or s.lower().startswith("initial")


def main():
    ver = common.version_from_argv()
    prm = common.load(ver, lang=common.lang_from_argv())
    t = TXT[prm.lang]
    prev = common.prev_version(ver)
    old = common.load(prev) if prev else None

    def changed(k, v):
        if old is None:
            return ""
        ov = getattr(old.P, k, None)
        return t["added"] if ov is None else (f"{ov} → {v}" if ov != v else "")

    lines = [t["title"].format(title=prm.meta.get('title', ''), ver=ver), ""] + t["intro"] + [""]
    if prm.meta.get("note"):
        lines += [f"> {prm.meta['note']}", ""]
    lines += [t["shape_h"], ""] + t["shape_cols"]
    for k in prm.raw.get("params", {}):
        v = getattr(prm.P, k)
        lines.append(f"| {prm.labels[k]} | {v} | {prm.units[k]} | `{k}` | {changed(k, v)} |")

    if prm.fab:
        todo = [k for k, f in prm.fab.items() if not_measured(f.get("status", ""))]
        lines += ["", t["fab_h"], "", t["fab_intro"], ""] + t["fab_cols"]
        for k, f in prm.fab.items():
            v = getattr(prm.P, k)
            lines.append(f"| {prm.labels[k]} | {v} | {prm.units[k]} | `{k}` | {f.get('status', '')} | "
                         f"{f.get('basis', '')} | {changed(k, v)} |")
        if todo:
            lines += ["", f"{t['todo']}{', '.join('`' + k + '`' for k in todo)}"]

    sp = os.path.join(common.ROOT, "out", ver, "scene.json")
    if os.path.exists(sp):
        notes = json.load(open(sp, encoding="utf-8")).get("notes") or []
        if notes:
            lines += ["", t["notes_h"], ""] + [f"- {n}" for n in notes]
    lines += ["", t["img_h"], "", t["img"].format(ver=ver)]
    out = os.path.join(common.ROOT, "docs", t["file"].format(ver=ver))
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    # Fusion のユーザーパラメータに写すための一覧（名前・値・単位・コメント）。ファイル名はどの言語でも同じ
    csv = os.path.join(common.ROOT, "docs", f"fusion_params_{ver}.csv")
    with open(csv, "w", encoding="utf-8") as f:
        f.write("name,value,unit,comment\n")
        for k, v in vars(prm.P).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                st = prm.fab.get(k, {}).get("status", "")
                f.write(f"{k},{v},{prm.units[k]},\"{prm.labels[k]}{t['csv_status'].format(st=st) if st else ''}\"\n")
    print(out)
    print(csv)


if __name__ == "__main__":
    main()
