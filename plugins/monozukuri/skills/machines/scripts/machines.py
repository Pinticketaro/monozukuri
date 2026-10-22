"""機材プロファイル：自分の機材で測った値（カーフ・クリアランス・インサート穴…）を「機械×材料」ごとに残し、
次のプロジェクトでは初期値ではなく測った値から始める。

1台の機材＝1つの JSON（置き場：環境変数 MONOZUKURI_MACHINES、既定 ~/.monozukuri/machines/）。
プロジェクトに適用すると、使った機材の写しが measurements/machines/<ID>.json に入る（プロジェクト単体で再現できる）。

  {"id": "home-ender3", "name": "自宅の Ender-3 V2", "kind": "fdm",       # kind: laser / fdm
   "spec": {"bed_x": 220, "bed_y": 220, "bed_z": 250, "nozzle": 0.4},     # laser は work_x・work_y・source（"CO2 40W" など）
   "rules": {"allowed": ["MDF"], "banned": ["POM"]},                       # ラボの材料の決まり（laser）
   "values": [{"key": "clr_fit", "value": 0.15, "unit": "mm", "material": "PLA（eSUN）", "thickness": null,
               "settings": "0.2mm層 210℃", "date": "2026-10-20", "source": "fdm_fit.stl 3番", "n": [..], "note": ""}]}

使い方
  machines.py new <ID> --kind fdm --name "自宅の Ender-3 V2" --spec bed_x=220 bed_y=220 bed_z=250 nozzle=0.4
  machines.py new <ID> --kind laser --name "ラボの CO2" --spec work_x=600 work_y=400 source="CO2 40W" --allow MDF --ban POM
  machines.py list
  machines.py show <ID>
  machines.py record <ID> --key kerf --value 0.16 --material アクリル --thickness 3 --settings "出力60% 速度15" \\
                          --source "laser_3mm.svg カーフ四角" --n 0.15,0.16,0.17
  machines.py import-csv <ID> --csv <プロジェクト>/measurements/試し片記録.csv [--material アクリル] [--thickness 3]
  machines.py apply --project <フォルダ> [--laser <ID>] [--fdm <ID>] [--from v03] [--dry-run]
      → 寸法ファイルを1つ上の版にコピーし、合う値を「実測」に置き換え、meta.machines と造形範囲を入れる
  machines.py rules <ID> --allow MDF --ban POM
すべて --lib <フォルダ> で置き場を変えられる。
"""
import argparse
import csv
import datetime
import glob
import json
import os
import re
import shutil

LASER_KEYS = ("kerf", "slot_delta", "cut_")
FDM_KEYS = ("clr_", "hole_comp", "insert_")


def lib_dir(a):
    d = a.lib or os.environ.get("MONOZUKURI_MACHINES") or os.path.expanduser("~/.monozukuri/machines")
    os.makedirs(d, exist_ok=True)
    return d


def path_of(a, mid):
    return os.path.join(lib_dir(a), f"{mid}.json")


def load(a, mid):
    p = path_of(a, mid)
    if not os.path.exists(p):
        raise SystemExit(f"機材 {mid} がありません（{p}）。`machines.py list` で一覧")
    return json.load(open(p, encoding="utf-8"))


def save(a, m):
    p = path_of(a, m["id"])
    json.dump(m, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


def norm(s):
    return re.sub(r"[\s　・\-_/（）()]", "", str(s or "")).lower()


def mat_match(want, have):
    """材料が合うか：どちらかがどちらかを含めば同じとみなす（「アクリル」と「アクリル（キャスト）」）"""
    if not want or not have:
        return not want and not have
    a, b = norm(want), norm(have)
    return a in b or b in a


def kv(items):
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        try:
            out[k] = float(v) if re.fullmatch(r"-?\d+(\.\d+)?", v) else v
        except ValueError:
            out[k] = v
    return out


# ---------------------------------------------------------------- コマンド
def cmd_new(a):
    p = path_of(a, a.id)
    if os.path.exists(p) and not a.force:
        raise SystemExit(f"{a.id} は既にあります（上書きするなら --force）")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-]*", a.id):
        raise SystemExit("ID は英数字と - _ にする（ファイル名になる）")
    m = {"id": a.id, "name": a.name or a.id, "kind": a.kind, "place": a.place or "",
         "spec": kv(a.spec), "rules": {"allowed": a.allow or [], "banned": a.ban or []}, "values": [],
         "created": datetime.date.today().isoformat()}
    print(save(a, m))


def cmd_list(a):
    fs = sorted(glob.glob(os.path.join(lib_dir(a), "*.json")))
    if not fs:
        print(f"機材はまだありません（置き場 {lib_dir(a)}）")
        return
    for f in fs:
        m = json.load(open(f, encoding="utf-8"))
        print(f"{m['id']:<20} {m.get('kind', ''):<6} {m.get('name', '')}  値 {len(m.get('values', []))}件  {m.get('spec', {})}")


def cmd_show(a):
    m = load(a, a.id)
    print(f"# {m['name']}（{m['id']}、{m['kind']}）")
    print("仕様:", json.dumps(m.get("spec", {}), ensure_ascii=False))
    r = m.get("rules", {})
    if r.get("allowed") or r.get("banned"):
        print("ラボの決まり: 許可", r.get("allowed", []), "／禁止", r.get("banned", []))
    print("| キー | 値 | 材料 | 板厚 | 設定 | 日付 | 出どころ |")
    print("|---|---:|---|---:|---|---|---|")
    for v in sorted(m.get("values", []), key=lambda v: (v["key"], v.get("material") or "", v.get("date") or "")):
        print(f"| {v['key']} | {v['value']} | {v.get('material') or ''} | {v.get('thickness') or ''} | "
              f"{v.get('settings') or ''} | {v.get('date') or ''} | {v.get('source') or ''} |")


def add_value(m, key, value, material=None, thickness=None, settings="", source="", n=None, note="", date=None, unit="mm"):
    v = {"key": key, "value": float(value), "unit": unit, "material": material or "", "thickness": thickness,
         "settings": settings or "", "date": date or datetime.date.today().isoformat(), "source": source or "",
         "n": n or [], "note": note or ""}
    # 同じキー・材料・板厚・設定の古い値は残す（履歴）。適用ではいちばん新しい日付を使う
    m.setdefault("values", []).append(v)
    return v


def cmd_record(a):
    m = load(a, a.id)
    n = [float(x) for x in a.n.split(",")] if a.n else []
    v = add_value(m, a.key, a.value, a.material, a.thickness, a.settings, a.source, n, a.note, a.date)
    save(a, m)
    print(f"{m['id']} に記録: {v['key']} = {v['value']}（{v['material']} {v['thickness'] or ''}）")


def cmd_import_csv(a):
    """試し片記録.csv の「選んだ値」と「反映先キー」がある行を取り込む。"""
    m = load(a, a.id)
    rows = list(csv.DictReader(open(a.csv, encoding="utf-8-sig")))
    got = 0
    for r in rows:
        key = (r.get("反映先キー") or "").strip()
        val = (r.get("選んだ値") or "").strip()
        if not key or not val:
            continue
        try:
            fv = float(val)
        except ValueError:
            print(f"  飛ばした（数でない）: {key}={val}")
            continue
        n = []
        for c in ("n1", "n2", "n3"):
            try:
                n.append(float(r.get(c)))
            except (TypeError, ValueError):
                pass
        add_value(m, key, fv, a.material or "", a.thickness, r.get("機械・材料・設定", ""), r.get("試し片", ""), n,
                  r.get("メモ", ""), (r.get("日付") or "").strip() or None)
        got += 1
        print(f"  {key} = {fv}")
    save(a, m)
    print(f"{got}件を {m['id']} に取り込みました")


def cmd_rules(a):
    m = load(a, a.id)
    r = m.setdefault("rules", {"allowed": [], "banned": []})
    for x in a.allow or []:
        if x not in r["allowed"]:
            r["allowed"].append(x)
    for x in a.ban or []:
        if x not in r["banned"]:
            r["banned"].append(x)
    save(a, m)
    print("許可:", r["allowed"], "／禁止:", r["banned"])


# ---------------------------------------------------------------- 適用
def versions(project):
    vs = []
    for f in glob.glob(os.path.join(project, "params", "params_v*.json")):
        mm = re.search(r"params_v(\d+)\.json$", f)
        if mm:
            vs.append(int(mm.group(1)))
    return sorted(vs)


def project_materials(d, kind):
    """寸法ファイルの meta.parts から、その作り方で使う (材料, 呼び板厚) の組"""
    out = set()
    fab = d.get("fab", {})
    for _k, p in (d.get("meta", {}).get("parts") or {}).items():
        if p.get("process") != kind:
            continue
        nom = None
        if kind == "laser" and p.get("t") in fab:
            f = fab[p["t"]]
            nom = f.get("nominal") or round(float(f.get("value", 0)) * 2) / 2
        out.add((p.get("material") or "", float(nom) if nom else None))
    return out


def key_kind(key):
    if key.startswith(LASER_KEYS):
        return "laser"
    if key.startswith(FDM_KEYS):
        return "fdm"
    return None


def pick(m, key, material, thickness):
    cands = []
    for v in m.get("values", []):
        if v["key"] != key:
            continue
        if material is not None and not mat_match(material, v.get("material")):
            continue
        if thickness and v.get("thickness") and abs(float(v["thickness"]) - float(thickness)) > 0.05:
            continue
        cands.append(v)
    return sorted(cands, key=lambda v: v.get("date") or "")[-1] if cands else None


def cmd_apply(a):
    project = os.path.abspath(a.project)
    vs = versions(project)
    if not vs:
        raise SystemExit(f"{project}/params に寸法ファイルがありません")
    src_v = int(a.src[1:]) if a.src else vs[-1]
    new_v = vs[-1] + 1
    src = os.path.join(project, "params", f"params_v{src_v:02d}.json")
    d = json.load(open(src, encoding="utf-8"))
    meta = d.setdefault("meta", {})
    fab = d.setdefault("fab", {})
    used = {}
    for kind in ("laser", "fdm"):
        mid = getattr(a, kind)
        if mid:
            used[kind] = load(a, mid)
            if used[kind].get("kind") != kind:
                raise SystemExit(f"{mid} は {used[kind].get('kind')} の機材です（--{kind} には {kind} の機材を）")
    if not used:
        raise SystemExit("--laser か --fdm で機材を指定してください")

    applied, missing, changes = [], [], []
    for key, f in fab.items():
        if not isinstance(f, dict):
            continue
        kind = key_kind(key)
        if kind not in used:
            continue
        m = used[kind]
        if f.get("material") or f.get("nominal"):
            combos = {(f.get("material") or "", f.get("nominal"))}
        else:
            combos = project_materials(d, kind) or {("", None)}
        if a.material:
            combos = {(a.material, a.thickness if kind == "laser" else None)}
        if len(combos) > 1:
            missing.append(f"{key}：材料が複数（{', '.join(f'{c[0]} {c[1] or ""}'.strip() for c in combos)}）。"
                           f"{key}_<材料> に分けるか --material で指定")
            continue
        mat, nom = next(iter(combos))
        v = pick(m, key, mat or None, nom)
        if not v:
            if not str(f.get("status", "")).startswith("初期値"):
                continue            # 規格・指針・計算の値は、測った値が無ければそのまま
            missing.append(f"{key}：{m['name']} で {mat or '材料未指定'}{f' {nom:g}mm' if nom else ''} の値がまだ無い")
            continue
        old = (f.get("value"), f.get("status"))
        f["value"] = v["value"]
        f["status"] = "実測"
        f["basis"] = (f"機材 {m['name']}（{m['id']}）{v.get('date', '')}：{v.get('source', '')}"
                      f"{'、' + v['material'] if v.get('material') else ''}{'、' + v['settings'] if v.get('settings') else ''}"
                      f"{'、n=' + '/'.join(str(x) for x in v['n']) if v.get('n') else ''}")
        applied.append(f"{key}: {old[0]}（{old[1]}）→ {v['value']}（実測）")
        changes.append(key)

    machines = meta.setdefault("machines", {})
    for kind, m in used.items():
        machines[kind] = m["id"]
    if "fdm" in used:
        s = used["fdm"].get("spec", {})
        prm = d.get("params", {})
        for k in ("bed_x", "bed_y"):
            if k in s and k in prm and prm[k].get("value") != s[k]:
                applied.append(f"{k}: {prm[k]['value']} → {s[k]}（機材の造形範囲）")
                prm[k]["value"] = s[k]
                changes.append(k)
    meta["version"] = f"v{new_v:02d}"

    print(f"v{src_v:02d} → v{new_v:02d}（機材 {', '.join(m['name'] for m in used.values())}）")
    for x in applied:
        print("  反映:", x)
    for x in missing:
        print("  未反映:", x)
    if a.dry_run:
        print("（--dry-run なので書き込んでいません）")
        return
    dst = os.path.join(project, "params", f"params_v{new_v:02d}.json")
    write_params(d, dst)
    snap = os.path.join(project, "measurements", "machines")
    os.makedirs(snap, exist_ok=True)
    for m in used.values():
        shutil.copy(path_of(a, m["id"]), os.path.join(snap, f"{m['id']}.json"))
    print(dst)


def write_params(d, path):
    """寸法ファイルを、項目ごとに1行の読みやすい形で書く（雛形と同じ書き方）"""
    one = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731
    L = ["{"]
    secs = [k for k in d.keys()]
    for si, sec in enumerate(secs):
        v = d[sec]
        end = "," if si < len(secs) - 1 else ""
        if not isinstance(v, dict) or not v:
            L.append(f"  {one(sec)}: {one(v)}{end}")
            continue
        L.append(f"  {one(sec)}: {{")
        items = list(v.items())
        w = max(len(one(k)) for k, _ in items)
        for i, (k, x) in enumerate(items):
            e2 = "," if i < len(items) - 1 else ""
            if sec == "meta" and isinstance(x, dict) and x and all(isinstance(y, dict) for y in x.values()):
                L.append(f"    {one(k)}: {{")
                sub = list(x.items())
                w2 = max(len(one(a)) for a, _ in sub)
                for j, (a, b) in enumerate(sub):
                    L.append(f"      {(one(a) + ':').ljust(w2 + 1)} {one(b)}" + ("," if j < len(sub) - 1 else ""))
                L.append("    }" + e2)
            elif sec == "meta":
                L.append(f"    {one(k)}: {one(x)}{e2}")
            else:
                L.append(f"    {(one(k) + ':').ljust(w + 1)} {one(x)}{e2}")
        L.append("  }" + end)
    L.append("}")
    s = "\n".join(L) + "\n"
    json.loads(s)
    open(path, "w", encoding="utf-8").write(s)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lib", help="機材の置き場（既定 $MONOZUKURI_MACHINES か ~/.monozukuri/machines）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new")
    s.add_argument("id")
    s.add_argument("--kind", required=True, choices=["laser", "fdm"])
    s.add_argument("--name")
    s.add_argument("--place")
    s.add_argument("--spec", nargs="*", help="key=value（fdm: bed_x bed_y bed_z nozzle／laser: work_x work_y source）")
    s.add_argument("--allow", nargs="*")
    s.add_argument("--ban", nargs="*")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("list")
    s.set_defaults(fn=cmd_list)
    s = sub.add_parser("show")
    s.add_argument("id")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("record")
    s.add_argument("id")
    s.add_argument("--key", required=True)
    s.add_argument("--value", required=True, type=float)
    s.add_argument("--material")
    s.add_argument("--thickness", type=float, help="レーザー：呼び板厚 mm")
    s.add_argument("--settings", default="")
    s.add_argument("--source", default="")
    s.add_argument("--n", help="測った値をカンマ区切りで")
    s.add_argument("--note", default="")
    s.add_argument("--date")
    s.set_defaults(fn=cmd_record)

    s = sub.add_parser("import-csv")
    s.add_argument("id")
    s.add_argument("--csv", required=True)
    s.add_argument("--material")
    s.add_argument("--thickness", type=float)
    s.set_defaults(fn=cmd_import_csv)

    s = sub.add_parser("rules")
    s.add_argument("id")
    s.add_argument("--allow", nargs="*")
    s.add_argument("--ban", nargs="*")
    s.set_defaults(fn=cmd_rules)

    s = sub.add_parser("apply")
    s.add_argument("--project", required=True)
    s.add_argument("--laser")
    s.add_argument("--fdm")
    s.add_argument("--from", dest="src", help="元にする版（既定：いちばん新しい版）")
    s.add_argument("--material", help="材料を指定（寸法ファイルから決まらないとき）")
    s.add_argument("--thickness", type=float)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_apply)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
