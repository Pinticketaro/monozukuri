"""部品の棚と工房プロファイル：確かめた既製品の寸法と、機械・材料ごとの実測値を、プロジェクトの外に置く個人の棚。
場所は ~/.monozukuri/shelf/（環境変数 MONOZUKURI_SHELF で変えられる）。変えるたびに git でコミットする。

使い方
  python3 shelf.py init                                    棚を作る。Cura の3Dプリンターとラボのレーザー（仮）を入れる
  python3 shelf.py list [parts|machines|materials]         1行ずつ短く出す
  python3 shelf.py show <キー>                             1つを出す（寸法は表、資料は名前だけ）
  python3 shelf.py add-part <キー> --from <プロジェクト> --keys a,b,… [--refs …] [--title …] [--source URL]
                                                           プロジェクトのいちばん新しい寸法ファイルから、確かめた寸法を棚に上げる。
                                                           根拠の無い寸法・仮の寸法は上げずに名前を出す。--keys は * も使える。
                                                           --keys を省くと、上げられる寸法の候補を出して止まる
  python3 shelf.py use <部品> <プロジェクト> [--prefix pi_] 棚の寸法をプロジェクトのいちばん新しい寸法ファイルの params に足し、資料を refs/ に写す
  python3 shelf.py record <プロジェクト> [--machine …] [--material …]
                                                           寸法ファイルの fab で status が「実測」の値を、材料の measured に足す。
                                                           機械と材料は省くと寸法ファイルの meta（printer・laser・materials）から決める
  python3 shelf.py fab <機械> <材料>… [--json]             その組み合わせで使える値（実測があれば実測、無ければ無し）
"""
import argparse
import configparser
import datetime
import fnmatch
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
KINDS = ("parts", "machines", "materials")
MEASURED = ("実測", "measured")
# 仮の寸法の見分け方（status.py と同じ。label の「仮」「provisional」も見る）
TENTATIVE = re.compile(r"^\s*(仮|tentative|placeholder)|要確認|要実測|to be (confirmed|measured)", re.I)
TENTATIVE_LABEL = re.compile(r"(^|[（(、。\s・])仮([）)。、\s・]|$)|provisional", re.I)
LAB_LASER = "lab_laser"

README = """# 部品の棚（monozukuri）

確かめた既製品の寸法と、機械・材料ごとの実測値を、プロジェクトの外に置く個人の棚。
道具は monozukuri プラグインの `new-project/scripts/shelf.py`（init・list・show・add-part・use・record・fab）。
道具で変えるたびに git でコミットする（手で直したときも commit すると履歴が残る）。

| 場所 | 中身 |
|---|---|
| `parts/<キー>/part.json` | 既製品の寸法（値・単位・名前・根拠・資料）。プロジェクトの寸法ファイルの `params` と同じ形 |
| `parts/<キー>/refs/` | 図面・データシート・写真（個人の棚なので PDF も置く） |
| `parts/<キー>/model.step` | メーカーの STEP（任意） |
| `machines/<キー>.json` | 機械：種類（fdm・laser）・置き場所・造形範囲（bed：X・Y・Z mm）・ノズル・Cura の機械の名前 |
| `materials/<キー>.json` | 材料：呼びの値と、機械ごとの実測値（`measured`。同じ機械・キーは新しいものを使い、古いものも残す） |

- わからない値は `null` にして `notes` に「要確認」と書く
- 寸法は確かめたものだけを置く（仮の寸法はプロジェクトで測ってから上げる）
"""


def today():
    return datetime.date.today().isoformat()


def shelf_dir():
    return os.path.abspath(os.path.expanduser(os.environ.get("MONOZUKURI_SHELF") or "~/.monozukuri/shelf"))


def load(p, default=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2) + "\n")


def need_shelf():
    s = shelf_dir()
    if not os.path.isdir(s):
        sys.exit(f"棚がありません：{s}\n  python3 shelf.py init で作ってください")
    return s


def item_path(kind, key):
    s = shelf_dir()
    return os.path.join(s, "parts", key, "part.json") if kind == "parts" else os.path.join(s, kind, key + ".json")


def keys_of(kind):
    s = shelf_dir()
    if kind == "parts":
        return sorted(k for k in os.listdir(os.path.join(s, "parts")) if os.path.exists(item_path("parts", k))) \
            if os.path.isdir(os.path.join(s, "parts")) else []
    return sorted(os.path.splitext(f)[0] for f in os.listdir(os.path.join(s, kind)) if f.endswith(".json")) \
        if os.path.isdir(os.path.join(s, kind)) else []


def get(kind, key):
    return load(item_path(kind, key))


def need(kind, key):
    d = get(kind, key)
    if d is None:
        name = {"parts": "部品", "machines": "機械", "materials": "材料"}[kind]
        sys.exit(f"棚に{name}「{key}」がありません。ある{name}：{', '.join(keys_of(kind)) or '（無し）'}")
    return d


def commit(msg):
    """棚の変更を git でコミットする（git が無い・設定が無いときは1行知らせて続ける）"""
    s = shelf_dir()
    if not os.path.isdir(os.path.join(s, ".git")):
        return
    try:
        subprocess.run(["git", "-C", s, "add", "-A"], check=True, capture_output=True)
        if subprocess.run(["git", "-C", s, "diff", "--cached", "--quiet"]).returncode == 0:
            return
        subprocess.run(["git", "-C", s, "commit", "-q", "-m", msg], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        print("!! 棚をコミットできませんでした（git の user.name / user.email を設定してから git commit）")


# ---- プロジェクトの寸法ファイル ----

def latest_params(proj, ver=None):
    """いちばん新しい寸法ファイル（params/params_vNN.json。枝分かれの案 v04a なども数える）の (版, パス)"""
    vs = []
    for f in glob.glob(os.path.join(proj, "params", "params_v*.json")):
        m = re.search(r"params_(v(\d+)([a-z]*))\.json$", f)
        if m and (ver is None or m.group(1) == ver):
            vs.append((int(m.group(2)), m.group(3), m.group(1), f))
    if not vs:
        sys.exit(f"寸法ファイルがありません：{os.path.join(proj, 'params', 'params_' + (ver or 'vNN') + '.json')}")
    _, _, v, f = max(vs)
    return v, f


def write_params(path, d):
    """寸法ファイルを元の書き方のまま書く（雛形の1項目1行の形なら同じ形、そうでなければ indent=2）"""
    text = open(path, encoding="utf-8").read()
    if re.search(r'^\s+"[^"]+":\s*\{"value"', text, re.M):
        sys.path.insert(0, HERE)
        from scaffold import dump_params
        dump_params(d, path)
    else:
        out = json.dumps(d, ensure_ascii=False, indent=2)
        open(path, "w", encoding="utf-8").write(out + ("\n" if text.endswith("\n") else ""))


def refs_index(proj):
    """プロジェクトの資料の一覧（refs/資料.md か refs/index.md）。無ければ refs/資料.md"""
    for f in ("資料.md", "index.md"):
        p = os.path.join(proj, "refs", f)
        if os.path.exists(p):
            return p
    return os.path.join(proj, "refs", "資料.md")


def index_rows(path):
    """資料の一覧の表の行 → {ファイル名: [何か, 出典, 取った日, 使った寸法]}"""
    rows = {}
    if not os.path.exists(path):
        return rows
    for ln in open(path, encoding="utf-8").read().splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")] if ln.strip().startswith("|") else []
        if len(cells) >= 2 and cells[0] and not set(cells[0]) <= set("-: "):
            rows[cells[0].strip("`")] = (cells[1:] + [""] * 4)[:4]
    return rows


def is_local(ref):
    return bool(ref) and not re.match(r"^[a-z]+:", ref, re.I)


# ---- Cura の機械 ----

def cura_dirs():
    """Cura の設定のフォルダ（いちばん新しい版）と、Cura の定義のフォルダ（resources）"""
    conf = None
    for base in (os.environ.get("MONOZUKURI_CURA_DIR"), "~/Library/Application Support/cura", "~/.local/share/cura",
                 os.path.join(os.environ.get("APPDATA", ""), "cura") if os.environ.get("APPDATA") else None):
        if not base:
            continue
        base = os.path.expanduser(base)
        if os.path.isdir(os.path.join(base, "machine_instances")):
            conf = base
            break
        vs = [d for d in glob.glob(os.path.join(base, "*")) if os.path.isdir(os.path.join(d, "machine_instances"))]
        vs.sort(key=lambda d: tuple(int(x) if x.isdigit() else 0 for x in os.path.basename(d).split(".")))
        if vs:
            conf = vs[-1]
            break
    res = None
    for r in [os.environ.get("MONOZUKURI_CURA_RESOURCES")] + sorted(glob.glob("/Applications/*Cura*.app/Contents/Resources/share/cura/resources")):
        if r and os.path.isdir(os.path.join(r, "definitions")):
            res = r
            break
    return conf, res


def read_cfg(path):
    c = configparser.ConfigParser(interpolation=None)
    try:
        c.read(path, encoding="utf-8")
    except configparser.Error:
        return None
    return c


def cfg_file(conf, sub, cid):
    """Cura の入れ物の id → ファイル（名前は URL のように符号化される：空白は +、# は %23）"""
    p = os.path.join(conf, sub, urllib.parse.quote_plus(cid) + ".inst.cfg")
    return p if os.path.exists(p) else None


def def_value(dirs, def_id, key, depth=0):
    """Cura の定義（*.def.json）を継承をたどって、設定の既定の値を探す"""
    if depth > 20:
        return None
    d = None
    for base in dirs:
        for sub in ("definitions", "extruders"):
            p = os.path.join(base, sub, def_id + ".def.json")
            if os.path.exists(p):
                d = load(p)
                break
        if d:
            break
    if not d:
        return None
    o = (d.get("overrides") or {}).get(key) or {}
    for f in ("default_value", "value"):
        v = o.get(f)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return v
        if isinstance(v, str) and re.fullmatch(r"\s*-?\d+(\.\d+)?\s*", v):
            return float(v)
    if d.get("inherits"):
        return def_value(dirs, d["inherits"], key, depth + 1)

    def walk(node):
        for k, v in (node or {}).items():
            if k == key and isinstance(v, dict):
                return v.get("default_value")
            if isinstance(v, dict):
                r = walk(v.get("children"))
                if r is not None:
                    return r
        return None
    return walk(d.get("settings"))


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return int(f) if f == int(f) else f


def machine_key(name, manufacturer):
    """Cura の機械の名前 → 棚のキー（例：Creality Ender-3 S1 Pro → ender3_s1_pro）"""
    words = name.split()
    if len(words) > 1 and manufacturer and manufacturer.lower().startswith(words[0].lower()):
        words = words[1:]
    k = re.sub(r"[^a-z0-9]+", "_", " ".join(words).lower().replace("-", "")).strip("_")
    return k or "printer"


def cura_machines():
    """Cura の機械（machine_instances）を棚の機械の形にして返す。Cura が無ければ []"""
    conf, res = cura_dirs()
    if not conf:
        return [], None
    dirs = [conf] + ([res] if res else [])
    ver = os.path.basename(conf)
    out = []
    extruders = []
    for p in glob.glob(os.path.join(conf, "extruders", "*.cfg")):
        c = read_cfg(p)
        if c and c.has_section("metadata"):
            extruders.append(c)
    for p in sorted(glob.glob(os.path.join(conf, "machine_instances", "*.global.cfg"))):
        c = read_cfg(p)
        if not c or not c.has_section("containers"):
            continue
        name = c.get("general", "name", fallback=None) or c.get("general", "id", fallback="")
        conts = [c.get("containers", k) for k in sorted(c.options("containers"), key=int)]
        definition = conts[-1] if conts else None
        # 造形範囲：機械ごとの変更（definition_changes）＞ 定義の継承
        changes = {}
        for cid in conts:
            f = cfg_file(conf, "definition_changes", cid)
            if f:
                cc = read_cfg(f)
                if cc and cc.has_section("values"):
                    changes.update(dict(cc.items("values")))
        bed = [num(changes.get(k)) if num(changes.get(k)) is not None else num(def_value(dirs, definition, k))
               for k in ("machine_width", "machine_depth", "machine_height")]
        manu = None
        for base in dirs:
            dj = load(os.path.join(base, "definitions", f"{definition}.def.json"))
            if dj:
                manu = (dj.get("metadata") or {}).get("manufacturer")
                if not manu and dj.get("inherits"):
                    up = load(os.path.join(base, "definitions", f"{dj['inherits']}.def.json")) or {}
                    manu = (up.get("metadata") or {}).get("manufacturer")
                break
        # ノズル：この機械の押し出し機の variant（例 creality_ender3s1pro_0.4）＞ 押し出し機の定義
        nozzle, filament, cura_mat = None, None, None
        for e in extruders:
            if e.get("metadata", "machine", fallback=None) != name or e.get("metadata", "position", fallback="0") != "0":
                continue
            # 押し出し機の積み重ね：user・quality_changes・intent・quality・material・variant・definition_changes・definition
            econts = [e.get("containers", k) for k in sorted(e.options("containers"), key=int)] if e.has_section("containers") else []
            if len(econts) == 8:
                cura_mat = None if econts[4].startswith("empty") else econts[4]
                vf = next(iter(glob.glob(os.path.join(res, "variants", "**", econts[5] + ".inst.cfg"), recursive=True)), None) \
                    if res and not econts[5].startswith("empty") else None
                vc = read_cfg(vf) if vf else None
                if vc and vc.has_option("values", "machine_nozzle_size"):
                    nozzle = num(vc.get("values", "machine_nozzle_size"))
            edef = econts[-1] if econts else None
            if nozzle is None and edef:
                nozzle = num(def_value(dirs, edef, "machine_nozzle_size"))
            if edef:
                filament = num(def_value(dirs, edef, "material_diameter"))
        notes = [f"Cura {ver} の機械「{name}」から取り込んだ（{today()}）。造形範囲は Cura の machine_width・machine_depth・machine_height"]
        if None in bed:
            notes.append("造形範囲の一部が Cura から読めなかった（要確認）")
        if nozzle is None:
            notes.append("ノズルの径が Cura から読めなかった（要確認）")
        notes.append("置き場所（where）は推定。違えば直す")
        if cura_mat:
            notes.append(f"Cura で選んでいる材料：{cura_mat}")
        key = machine_key(name, manu)
        while key in {m["key"] for m in out}:
            key += "_2"
        out.append({"key": key, "title": name, "kind": "fdm", "where": "自宅",
                    "bed": bed, "nozzle": nozzle, "filament_d": filament,
                    "cura": {"machine": name, "definition": definition, "version": ver}, "notes": notes})
    return out, conf


# ---- コマンド ----

def cmd_init(a):
    s = shelf_dir()
    new = not os.path.isdir(s)
    for k in KINDS:
        os.makedirs(os.path.join(s, k), exist_ok=True)
    if not os.path.exists(os.path.join(s, "README.md")):
        open(os.path.join(s, "README.md"), "w", encoding="utf-8").write(README)
    print(f"棚：{s}{'（新しく作った）' if new else '（すでにある）'}")
    added = []
    machines, conf = cura_machines()
    if not conf:
        print("  Cura の設定が見つかりません（3Dプリンターは取り込まない。machines/<キー>.json を手で足せる）")
    for m in machines:
        key = m.pop("key")
        p = item_path("machines", key)
        bed = "×".join("?" if v is None else str(v) for v in m["bed"])
        if os.path.exists(p):
            print(f"  機械 {key}：すでにある（そのまま）")
            continue
        save(p, m)
        added.append(key)
        print(f"  機械 {key}：{m['title']}（Cura）造形範囲 {bed} mm・ノズル {m['nozzle']}")
    p = item_path("machines", LAB_LASER)
    if not os.path.exists(p):
        save(p, {"title": "ラボのレーザー", "kind": "laser", "where": "ラボ", "model": None, "bed": None, "materials": None,
                 "notes": ["仮の項目。機種（model）・加工範囲（bed：[X, Y] mm）・加工できる材料と厚み（materials）は要確認",
                           "materials の形：[{\"material\": \"MDF\", \"max_t\": 6}]（ラボのカットしてよい材料のリストに合わせる）"]})
        added.append(LAB_LASER)
        print(f"  機械 {LAB_LASER}：ラボのレーザー（仮。機種・加工範囲・材料は要確認）")
    if not os.path.isdir(os.path.join(s, ".git")):
        try:
            subprocess.run(["git", "-C", s, "init", "-q", "-b", "main"], check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError):
            print("!! git init できませんでした（履歴は残りません）")
    commit("棚を作った" if new else f"棚：機械を足した（{', '.join(added)}）" if added else "棚：init")


def short(kind, key, d):
    if kind == "parts":
        n_ref = len(d.get("refs") or [])
        return f"寸法 {len(d.get('dims') or {})}・資料 {n_ref}"
    if kind == "machines":
        bed = d.get("bed")
        bed = "範囲 要確認" if not bed or None in bed else "×".join(str(v) for v in bed)
        return f"{d.get('kind', '?')}・{bed}・{d.get('where') or '置き場所 要確認'}"
    ms = d.get("measured") or []
    by = sorted({m.get("machine", "?") for m in ms})
    return f"{d.get('kind', '?')}・実測 {len(ms)}" + (f"（{', '.join(by)}）" if by else "")


def cmd_list(a):
    s = need_shelf()
    kinds = [a.kind] if a.kind else KINDS
    title = {"parts": "部品（parts）", "machines": "機械（machines）", "materials": "材料（materials）"}
    print(f"棚：{s}")
    for k in kinds:
        keys = keys_of(k)
        print(f"{title[k]}：{len(keys)}")
        w = max([len(x) for x in keys] + [4])
        for key in keys:
            d = get(k, key) or {}
            print(f"  {key:<{w}}  {d.get('title', '')}  {short(k, key, d)}")


def latest_measured(ms):
    """同じ機械・キーの実測が複数あれば、日付の新しいもの（同じ日なら後に足したもの）"""
    best = {}
    for i, m in enumerate(ms):
        k = (m.get("machine"), m.get("key"))
        if k not in best or (m.get("date") or "", i) >= (best[k][1].get("date") or "", best[k][0]):
            best[k] = (i, m)
    return {k: v[1] for k, v in best.items()}


def cmd_show(a):
    need_shelf()
    key = a.key
    hits = []
    if "/" in key:
        kind, key = key.split("/", 1)
        hits = [kind] if kind in KINDS and get(kind, key) is not None else []
    else:
        hits = [k for k in KINDS if get(k, key) is not None]
    if not hits:
        sys.exit(f"棚に「{a.key}」がありません（shelf.py list で一覧）")
    kind = hits[0]
    d = get(kind, key)
    print(f"{kind}/{key}：{d.get('title', '')}")
    if kind == "parts":
        for f in ("source", "checked"):
            if d.get(f):
                print(f"  {f}: {d[f]}")
        print("  | キー | 値 | 単位 | 名前 | 根拠 |")
        for k, it in (d.get("dims") or {}).items():
            print(f"  | {k} | {it.get('value')} | {it.get('unit', '')} | {it.get('label', '')} | {it.get('basis', '')} |")
        refs = [os.path.basename(r.get("file", "")) for r in d.get("refs") or []]
        if os.path.exists(os.path.join(os.path.dirname(item_path("parts", key)), "model.step")):
            refs.append("model.step")
        if refs:
            print("  資料：" + "、".join(refs))
    elif kind == "machines":
        for f in ("kind", "where", "model", "bed", "nozzle", "filament_d", "materials"):
            if f in d:
                print(f"  {f}: {json.dumps(d[f], ensure_ascii=False)}")
        if d.get("cura"):
            print(f"  cura: {d['cura'].get('machine')}（定義 {d['cura'].get('definition')}）")
    else:
        print(f"  kind: {d.get('kind')}  nominal: {json.dumps(d.get('nominal') or {}, ensure_ascii=False)}")
        ms = d.get("measured") or []
        use = {id(m) for m in latest_measured(ms).values()}
        if ms:
            print("  | 機械 | キー | 値 | 日付 | どこから | 使う |")
        for m in ms:
            print(f"  | {m.get('machine')} | {m.get('key')} | {m.get('value')} {m.get('unit', '')} | {m.get('date', '')} | "
                  f"{m.get('from', '')} | {'○' if id(m) in use else '（古い）'} |")
    for n in d.get("notes") or []:
        print(f"  - {n}")


def cmd_add_part(a):
    need_shelf()
    if not re.fullmatch(r"[a-z0-9_][a-z0-9_\-]*", a.key):
        sys.exit(f"部品のキーは英小文字・数字・_ で（例 raspberry_pi4）：{a.key}")
    proj = os.path.abspath(a.from_)
    ver, pf = latest_params(proj)
    params = (load(pf) or {}).get("params") or {}
    ok_keys, skip_tent, skip_nob = [], [], []
    for k, it in params.items():
        if not isinstance(it, dict) or "value" not in it:
            continue
        if not it.get("basis"):
            skip_nob.append(k)
        elif TENTATIVE.search(str(it["basis"])) or TENTATIVE_LABEL.search(str(it.get("label", ""))):
            skip_tent.append(k)
        else:
            ok_keys.append(k)
    if not a.keys:
        print(f"{os.path.basename(proj)} {ver} の寸法のうち、根拠があり仮でないもの（棚に上げられる候補）：")
        print("  " + ",".join(k for k in ok_keys if params[k].get("ref")) + "  ← 資料（ref）つき")
        print("  " + ",".join(k for k in ok_keys if not params[k].get("ref")) + "  ← 資料なし（設計で決めた値も入る。既製品の寸法だけを選ぶ）")
        sys.exit("--keys で上げる寸法を指定してください（* も使える）")
    pats = [p.strip() for p in a.keys.split(",") if p.strip()]
    chosen, missing = [], []
    for p in pats:
        hit = [k for k in params if fnmatch.fnmatchcase(k, p)]
        if not hit:
            missing.append(p)
        chosen += [k for k in hit if k not in chosen]
    up = [k for k in chosen if k in ok_keys]
    tent = [k for k in chosen if k in skip_tent]
    nob = [k for k in chosen if k in skip_nob]
    if not up:
        sys.exit("上げられる寸法がありません" + (f"（仮：{', '.join(tent)}）" if tent else "") + (f"（根拠なし：{', '.join(nob)}）" if nob else ""))

    pdir = os.path.dirname(item_path("parts", a.key))
    part = get("parts", a.key) or {"title": a.key, "source": None, "checked": None, "dims": {}, "refs": [], "notes": []}
    rows = index_rows(refs_index(proj))
    # 資料：選んだ寸法の ref が指すファイル ＋ --refs
    files = []
    for k in up:
        r = params[k].get("ref")
        if is_local(r):
            files.append(r)
    for r in a.refs or []:
        files.append(os.path.relpath(os.path.abspath(r), proj) if os.path.isabs(r) or os.path.exists(r) else r)
    copied = []
    for r in dict.fromkeys(files):
        src = os.path.join(proj, r)
        if not os.path.exists(src):
            src = os.path.join(proj, "refs", r)
        if not os.path.isfile(src):
            print(f"  資料が見つかりません（飛ばした）：{r}")
            continue
        name = os.path.basename(src)
        os.makedirs(os.path.join(pdir, "refs"), exist_ok=True)
        shutil.copy2(src, os.path.join(pdir, "refs", name))
        what, source, taken, _ = rows.get(name, ["", "", "", ""])
        entry = {"file": "refs/" + name, "what": what, "source": source, "taken": taken}
        part["refs"] = [x for x in part.get("refs") or [] if x.get("file") != entry["file"]] + [entry]
        copied.append(name)
    changed = []
    for k in up:
        it = params[k]
        ref = it.get("ref")
        if is_local(ref):
            ref = "refs/" + os.path.basename(ref)
        new = {"value": it["value"], "unit": it.get("unit", ""), "label": it.get("label", k), "basis": it["basis"]}
        if ref:
            new["ref"] = ref
        old = (part.get("dims") or {}).get(k)
        if old and old.get("value") != new["value"]:
            changed.append(f"{k} {old.get('value')}→{new['value']}")
        part.setdefault("dims", {})[k] = new
    if a.title:
        part["title"] = a.title
    urls = [m for r in part.get("refs") or [] for m in re.findall(r"https?://[^\s）)|]+", r.get("source", ""))]
    part["source"] = a.source or part.get("source") or (urls[0] if urls else None)
    takens = sorted(r.get("taken") for r in part.get("refs") or [] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.get("taken") or ""))
    part["checked"] = takens[-1] if takens else today()
    part.setdefault("notes", []).append(f"{os.path.basename(proj)} の {ver} から寸法 {len(up)} を上げた（{today()}）")
    save(item_path("parts", a.key), part)
    print(f"部品 {a.key}（{part['title']}）に寸法 {len(up)} を上げた：{', '.join(up)}")
    if changed:
        print(f"  値が変わった寸法：{', '.join(changed)}")
    if copied:
        print(f"  資料：{', '.join(copied)}")
    if tent:
        print(f"  上げなかった（仮）：{', '.join(tent)}")
    if nob:
        print(f"  上げなかった（根拠なし）：{', '.join(nob)}")
    if missing:
        print(f"  寸法ファイルに無いキー：{', '.join(missing)}")
    commit(f"部品 {a.key}：{os.path.basename(proj)} {ver} から寸法 {len(up)}" + (f"・資料 {len(copied)}" if copied else ""))


def cmd_use(a):
    need_shelf()
    part = need("parts", a.part)
    proj = os.path.abspath(a.project)
    ver, pf = latest_params(proj)
    d = load(pf)
    if d is None:
        sys.exit(f"寸法ファイルが読めません：{pf}")
    dims = part.get("dims") or {}
    if not dims:
        sys.exit(f"部品 {a.part} に寸法がありません")
    pre = a.prefix or ""
    have = set((d.get("params") or {})) | set((d.get("fab") or {}))
    clash = [pre + k for k in dims if pre + k in have]
    if clash:
        sys.exit(f"寸法ファイル {os.path.basename(pf)} に同じキーがあるので、何も変えずに止めました：{', '.join(clash)}\n"
                 f"  --prefix で前に付ける文字を変えてください（例 --prefix {a.part.split('_')[0]}_）")
    # 資料：棚の refs/ をプロジェクトの refs/ に写す。同じ名前で中身が違うファイルがあれば止める
    pdir = os.path.dirname(item_path("parts", a.part))
    plan = []
    for r in part.get("refs") or []:
        src = os.path.join(pdir, r.get("file", ""))
        if not os.path.isfile(src):
            continue
        dst = os.path.join(proj, "refs", os.path.basename(src))
        if os.path.exists(dst) and open(dst, "rb").read() != open(src, "rb").read():
            sys.exit(f"プロジェクトの refs/ に同じ名前で中身が違うファイルがあるので、何も変えずに止めました：{os.path.basename(src)}")
        plan.append((r, src, dst))
    for _, src, dst in plan:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
    params = d.setdefault("params", {})
    for k, it in dims.items():
        new = {"value": it.get("value"), "unit": it.get("unit", ""), "label": it.get("label", k),
               "basis": f"部品の棚：{a.part}（{it.get('basis', '')}）"}
        if it.get("ref"):
            new["ref"] = it["ref"]           # 棚の refs/<名前> はプロジェクトの refs/<名前> と同じ
        params[pre + k] = new
    write_params(pf, d)
    # 資料の一覧に行を足す（同じファイルの行があれば足さない）
    idx = refs_index(proj)
    added_rows = []
    if plan:
        text = open(idx, encoding="utf-8").read() if os.path.exists(idx) else \
            "# 資料\n\n| ファイル | 何か | 出典（URL・ページ） | 取った日 | 使った寸法（キー） |\n|---|---|---|---|---|\n"
        rows = index_rows(idx)
        lines = text.split("\n")
        for r, src, _ in plan:
            name = os.path.basename(src)
            if name in rows:
                continue
            used = [pre + k for k, it in dims.items() if it.get("ref") == r.get("file")]
            what = (r.get("what") or part.get("title") or a.part) + f"（部品の棚：{a.part}）"
            row = f"| `{name}` | {what} | {r.get('source') or part.get('source') or ''} | {r.get('taken') or part.get('checked') or ''} | {'・'.join(used) or '―'} |"
            empty = next((i for i, ln in enumerate(lines) if re.fullmatch(r"\|(\s*\|){4,}\s*", ln.strip())), None)
            last = max((i for i, ln in enumerate(lines) if ln.strip().startswith("|")), default=None)
            if empty is not None:
                lines[empty] = row
            elif last is not None:
                lines.insert(last + 1, row)
            else:
                lines += ["", "| ファイル | 何か | 出典（URL・ページ） | 取った日 | 使った寸法（キー） |", "|---|---|---|---|---|", row]
            added_rows.append(name)
        os.makedirs(os.path.dirname(idx), exist_ok=True)
        open(idx, "w", encoding="utf-8").write("\n".join(lines))
    print(f"{os.path.basename(pf)} の params に、部品の棚 {a.part}（{part.get('title', '')}）の寸法 {len(dims)} を足した："
          f"{', '.join(pre + k for k in dims)}")
    if plan:
        print(f"  資料：{', '.join('refs/' + os.path.basename(s) for _, s, _ in plan)}"
              + (f"（{os.path.relpath(idx, proj)} に {len(added_rows)} 行）" if added_rows else ""))
    print(f"  mock.py では P.{pre}{next(iter(dims))} のように読む")
    if os.path.exists(os.path.join(proj, "out", ver, "scene.json")):
        print(f"  ※ {ver} はもう作ってある版です。画像は古い寸法のまま（mock.py で作り直すか、次の版で使う）")


def material_kind(key):
    """材料の種類：棚にあればその kind、無ければキーの名前から推す（pla・petg… はフィラメント、mdf・acrylic・3mm… は板）"""
    d = get("materials", key)
    if d and d.get("kind"):
        return d["kind"]
    k = key.lower()
    if re.search(r"(^|_)(pla|petg|pet|abs|asa|tpu|tpe|pa|pa\d+|nylon|pc|hips|pva|filament)(_|\d|$)", k):
        return "filament"
    if re.search(r"\d(\.\d+)?mm|mdf|acryl|ply|veneer|wood|board|sheet|felt|leather|paper|cardboard|アクリル|ベニヤ|合板", k):
        return "sheet"
    return None


def project_kinds(proc):
    """fab の process（["laser"]・["fdm"]・両方）→ 機械の種類"""
    return [p for p in ("laser", "fdm") if p in (proc or ["laser", "fdm"])]


def cmd_record(a):
    need_shelf()
    proj = os.path.abspath(a.project)
    ver, pf = latest_params(proj, a.version)
    d = load(pf) or {}
    meta = d.get("meta") or {}
    name = os.path.basename(proj.rstrip(os.sep))
    if a.machine:
        need("machines", a.machine)
    mats_meta = [m for m in (meta.get("materials") or []) if isinstance(m, str)]
    measured = {k: it for k, it in (d.get("fab") or {}).items() if isinstance(it, dict) and it.get("status") in MEASURED}
    if not measured:
        print(f"{os.path.basename(pf)} の fab に「実測」の値がありません（テストピースで測ったら status を「実測」にする）")
        return
    done, skipped, known = {}, [], []
    for k, it in measured.items():
        kinds = project_kinds(it.get("process"))
        # 機械：--machine ＞ 寸法ファイルの meta（laser の値は meta.laser、fdm の値は meta.printer）
        if a.machine:
            mk = (get("machines", a.machine) or {}).get("kind")
            if mk not in kinds:
                skipped.append(f"{k}（{'・'.join(kinds)} の値。{a.machine} は {mk}）")
                continue
            machine, kind = a.machine, mk
        else:
            cand = [(meta.get("laser" if kd == "laser" else "printer"), kd) for kd in kinds]
            cand = [c for c in cand if c[0]]
            if len(cand) != 1:
                skipped.append(f"{k}（機械がわからない。--machine で指定）")
                continue
            machine, kind = cand[0]
            if get("machines", machine) is None:
                skipped.append(f"{k}（棚に機械 {machine} が無い）")
                continue
        want = "sheet" if kind == "laser" else "filament"
        if a.material:
            material = a.material
        else:
            ms = [m for m in mats_meta if material_kind(m) in (want, None)]
            if len(ms) != 1:
                skipped.append(f"{k}（材料がわからない。--material で指定）")
                continue
            material = ms[0]
        mat = get("materials", material)
        if mat is not None and mat.get("kind", want) != want:
            skipped.append(f"{k}（{kind} の値。材料 {material} は {mat.get('kind')}）")
            continue
        if mat is None:
            mat = {"title": material, "kind": want, "nominal": {}, "measured": [],
                   "notes": [f"shelf.py record が作った（{today()}）。title・nominal は直してよい"]}
            print(f"  新しい材料：materials/{material}.json（{want}。名前 title は直してよい）")
        dm = re.search(r"\d{4}-\d{2}-\d{2}", str(it.get("basis", "")))
        entry = {"machine": machine, "key": k, "value": it.get("value"), "unit": it.get("unit", ""),
                 "date": dm.group(0) if dm else today(), "from": f"{name} {ver}", "note": it.get("basis", "")}
        same = [m for m in mat.get("measured") or [] if all(m.get(f) == entry[f] for f in ("machine", "key", "value", "from"))]
        if same:
            known.append(k)
            continue
        mat.setdefault("measured", []).append(entry)
        save(item_path("materials", material), mat)
        done.setdefault((machine, material), []).append(f"{k} {entry['value']}{entry['unit']}")
    for (machine, material), ks in done.items():
        print(f"材料 {material} に実測を足した（{machine}・{name} {ver}）：{', '.join(ks)}")
    if known:
        print(f"  もう棚にある（同じ値・同じ版）：{', '.join(known)}")
    if skipped:
        print(f"  足さなかった：{'、'.join(skipped)}")
    if done:
        commit(f"実測：{name} {ver} から " + "・".join(f"{mat}（{mc}）" for mc, mat in done))


def fab_values(machine, materials):
    """機械と材料の組み合わせで使える値：{材料: {キー: 実測の記録}}。実測が無いキーは入らない"""
    out = {}
    for m in materials:
        d = get("materials", m)
        if d is None:
            continue
        out[m] = {k: e for (mc, k), e in latest_measured(d.get("measured") or []).items() if mc == machine}
    return out


def cmd_fab(a):
    need_shelf()
    need("machines", a.machine)
    vals = fab_values(a.machine, a.materials)
    if a.json:
        print(json.dumps(vals, ensure_ascii=False, indent=1))
        return
    for m in a.materials:
        if m not in vals:
            print(f"{m}：棚に無い材料")
            continue
        if not vals[m]:
            print(f"{m}：{a.machine} での実測なし（初期値を使う）")
            continue
        print(f"{m}（{a.machine}）")
        for k, e in vals[m].items():
            print(f"  {k} = {e.get('value')} {e.get('unit', '')}（実測：{e.get('from', '')}・{e.get('date', '')}）")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("init", help="棚を作る（Cura の3Dプリンターとラボのレーザーを入れる）")
    p = sp.add_parser("list", help="1行ずつ短く出す")
    p.add_argument("kind", nargs="?", choices=KINDS)
    p = sp.add_parser("show", help="1つを出す")
    p.add_argument("key", help="キー（parts/<キー> のように種類を付けてもよい）")
    p = sp.add_parser("add-part", help="プロジェクトの寸法ファイルから、確かめた寸法を棚に上げる")
    p.add_argument("key")
    p.add_argument("--from", dest="from_", required=True, metavar="プロジェクト")
    p.add_argument("--keys", help="上げる寸法のキー（, 区切り。* も使える）")
    p.add_argument("--refs", nargs="*", help="一緒に置く資料（プロジェクトからの相対パス）。省くと寸法の ref が指すファイル")
    p.add_argument("--title")
    p.add_argument("--source", help="出典の URL（省くと資料の一覧の出典から）")
    p = sp.add_parser("use", help="棚の寸法をプロジェクトに入れる")
    p.add_argument("part")
    p.add_argument("project")
    p.add_argument("--prefix", default="", help="キーの前に付ける文字（例 pi_）")
    p = sp.add_parser("record", help="寸法ファイルの「実測」の値を材料に残す")
    p.add_argument("project")
    p.add_argument("--machine")
    p.add_argument("--material")
    p.add_argument("--version", help="寸法ファイルの版（省くといちばん新しい版）")
    p = sp.add_parser("fab", help="機械と材料の組み合わせで使える値")
    p.add_argument("machine")
    p.add_argument("materials", nargs="+")
    p.add_argument("--json", action="store_true")
    a = ap.parse_args()
    {"init": cmd_init, "list": cmd_list, "show": cmd_show, "add-part": cmd_add_part, "use": cmd_use,
     "record": cmd_record, "fab": cmd_fab}[a.cmd](a)


if __name__ == "__main__":
    main()
