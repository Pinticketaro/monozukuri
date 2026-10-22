"""2つの版の寸法ファイル（params_vNN.json）を比べて、変わった値の一覧を出す。
使い方: python3 params_diff.py params_v02.json params_v03.json [--json out.json]

寸法ファイルの形（monozukuri の雛形）
  {"meta": {...}, "params": {"outer_w": {"value": 160, "unit": "mm", "label": "外形の幅"}, ...}}
値だけの形 {"outer_w": 160, ...} や、入れ子の JSON でも比べられる（キーを a.b.c とつなげる）。
"""
import argparse
import json


def flatten(d, prefix=""):
    out = {}
    if isinstance(d, dict) and ("params" in d or "fab" in d) and not prefix:
        d = {**d.get("params", {}), **d.get("fab", {})}     # monozukuri の寸法ファイル（形の寸法＋加工の値）
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and "value" in v:
            out[key] = {"value": v["value"], "unit": v.get("unit", ""), "label": v.get("label", k)}
        elif isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = {"value": v, "unit": "", "label": key}
    return out


def diff(a, b):
    A, B = flatten(a), flatten(b)
    rows = []
    for k in sorted(set(A) | set(B), key=lambda x: (list(B).index(x) if x in B else 10 ** 6, x)):
        va, vb = A.get(k), B.get(k)
        if va and vb and va["value"] == vb["value"]:
            continue
        src = vb or va
        row = {"key": k, "label": src["label"], "unit": src["unit"],
               "before": va["value"] if va else None, "after": vb["value"] if vb else None}
        if va is None:
            row["kind"] = "added"
        elif vb is None:
            row["kind"] = "removed"
        else:
            row["kind"] = "changed"
            if isinstance(va["value"], (int, float)) and isinstance(vb["value"], (int, float)) \
                    and not isinstance(va["value"], bool):
                row["delta"] = round(vb["value"] - va["value"], 6)
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--json")
    a = ap.parse_args()
    rows = diff(json.load(open(a.before, encoding="utf-8")), json.load(open(a.after, encoding="utf-8")))
    if a.json:
        json.dump(rows, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not rows:
        print("変わった値はありません")
    for r in rows:
        d = f"（{r['delta']:+g}{r['unit']}）" if "delta" in r else ""
        print(f"- {r['label']}: {r['before']} → {r['after']}{r['unit'] if r['after'] is not None else ''}{d}")


if __name__ == "__main__":
    main()
