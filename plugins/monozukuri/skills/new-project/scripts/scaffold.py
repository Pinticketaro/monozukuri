"""新しいものづくりプロジェクトの雛形を作る。既存のプロジェクトの道具（tools/）を新しくする。
使い方
  python3 scaffold.py --dest <作るフォルダ> --name "名前" --summary "1行の説明"
                      [--origin "外形の左下、X右・Y奥・Z上"] [--methods "上下の板：CO2レーザー／枠：3Dプリント（PLA）"]
                      [--process laser|fdm|both] [--bed 220x220] [--lang ja|en] [--git]
  python3 scaffold.py --update-tools <プロジェクトのフォルダ> [--force] [--lang ja|en]
--dest がすでにあって中身があるときは止まる（上書きしない）。
--process は作り方（laser＝レーザー、fdm＝3Dプリント、both＝両方。既定 both）。寸法ファイルの fab を、その作り方で
  使う項目だけにし、チェックリストなどの関係しない項目を外す。fdm のときは、例の形を3Dプリントの缶ケースにする。
--lang は言語（ja＝日本語、en＝英語。既定は環境変数 MONOZUKURI_LANG、無ければ ja）。文書・寸法ファイル・例の mock.py を
  その言語で作り、寸法ファイルの meta.lang に記録する。en では文書のファイル名も英語になる（docs/checklist.md など）。
--update-tools は、プラグインが持ち主の道具（geom.py・common.py・描画のスクリプトなど）だけを新しくする。
  mock.py は上書きせず、新しい雛形を tools/mock.py.new として置く。元のファイルは tools/.backup-<日時>/ に残す。
  mock.py.new と表示の言語は、いちばん新しい寸法ファイルの meta.lang（無ければ ja）。--lang を付けると表示だけその言語。
"""
import argparse
import ast
import datetime
import difflib
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

DOC_EN = """Create a new monozukuri project from the template, or update the tools (tools/) of an existing project.
Usage
  python3 scaffold.py --dest <folder> --name "Name" --summary "One-line description"
                      [--origin "Bottom-left of the outline. X right, Y back, Z up"]
                      [--methods "Top and bottom plates: CO2 laser / frame: 3D print (PLA)"]
                      [--process laser|fdm|both] [--bed 220x220] [--lang ja|en] [--git]
  python3 scaffold.py --update-tools <project folder> [--force] [--lang ja|en]
Stops if --dest already exists and has files (never overwrites).
--process is how the parts are made (laser = laser cutting, fdm = 3D printing, both = both; default both).
  Keeps only the fab values that process uses and removes checklist items that do not apply.
  With fdm, the example shape is a 3D printed can case.
--lang is the language (ja = Japanese, en = English; default: env MONOZUKURI_LANG, else ja). Docs, the params file
  and the example mock.py are written in that language, and it is stored as meta.lang in the params file.
  With en, doc file names are English too (docs/checklist.md and so on).
--update-tools replaces only the tools the plugin owns (geom.py, common.py, the render scripts, ...).
  mock.py is not overwritten; the new template is put in tools/mock.py.new. Old files stay in tools/.backup-<date-time>/.
  mock.py.new and the messages follow meta.lang of the newest params file (else ja). --lang changes only the messages.
"""

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "templates", "project")    # 言語によらないもの（道具・.gitattributes など）
LANGS = os.path.join(HERE, "..", "templates", "lang")          # 言語ごとの文書・寸法ファイル・例の mock.py（lang/<ja|en>/）
VARIANTS = os.path.join(HERE, "..", "templates", "variants")   # 作り方ごとの例（variants/<作り方>/<言語>/。params と mock.py の build() を差し替える）
PROCESSES = {"laser": {"laser"}, "fdm": {"fdm"}, "both": {"laser", "fdm"}}
LANG_CODES = ("ja", "en")
SHARED = os.path.join(HERE, "..", "..", "review-page", "scripts")
SHARED_FILES = ["render_model.py", "slices.py", "compare.py", "params_diff.py"]
# プラグインが持ち主の道具（--update-tools で上書きする）。mock.py は利用者の build() があるので入れない
OWNED = {f: os.path.join(TEMPLATE, "tools", f)
         for f in ["geom.py", "common.py", "coupons.py", "dims_sheet.py", "requirements.txt"]}
OWNED.update({f: os.path.join(SHARED, f) for f in SHARED_FILES})
KNOWN = os.path.join(HERE, "tool_versions.json")       # これまでの版の道具の中身（sha256）と定義の名前。版を出すときに足す
VERSION_FILE = ".monozukuri-version"

# 表示の言葉（日本語・英語）
MSG = {
    "ja": {
        "no_template": "雛形がありません：{path}",
        "dest_nonempty": "{dest} には既にファイルがあります。空のフォルダか新しい名前を指定してください",
        "methods_tbd": "（未定）",
        "origin": "外形の中心が X=0・Y=0、底面が Z=0。X右・Y奥・Z上",
        "commit": "雛形：{name}（monozukuri）",
        "commit_fail": "!! コミットできませんでした（git の user.name / user.email を設定してから再実行）",
        "no_tools": "{tools} がありません。プロジェクトのフォルダを指定してください",
        "estimated": "{v}（推定）",
        "unknown": "不明",
        "start": "道具を新しくします：{old} → {new}（{tools}）",
        "added": "追加",
        "upd_known": "更新（{v} の中身）",
        "upd_mine": "更新（手を加えた所{names} は新しい版にあります）",
        "names": "：{names}",
        "lost": "新しい版に無い定義：{names}",
        "differs": "雛形のどの版とも中身が違います",
        "blocked": "\n!! プロジェクトで手を加えたファイルがあるので、何も上書きせずに止めました",
        "item": "   {f}：{why}",
        "blocked_hint": "   手を加えた所を残したいときは、新しい版に写してから再実行してください。"
                        "上書きしてよいときは --force を付けます（元のファイルは tools/.backup-<日時>/ に残ります）",
        "forced": "上書き（--force。手を加えた所は控えにだけ残ります）",
        "done": "  {f}：{how}",
        "up_to_date": "  道具はすでに新しい版です",
        "backup": "  元のファイル：tools/.backup-{stamp}/",
        "mock_new": "\nmock.py はそのままです（build() があるため）。新しい雛形を tools/mock.py.new に置きました",
        "mock_same": "  build() の外は同じです。差し替えは要りません",
        "mock_diff": "  build() の外の違い（{n}行。新しい枠組みを使うときは、mock.py.new の build() を今の build() に置き換えて使う）：",
        "run_mock": "   ※ 新しい mock.py は main() を持たず、最後で common.run_mock(build) を呼びます。今の mock.py の"
                    " def main() から下を消し、if __name__ == \"__main__\": common.run_mock(build) にすると、"
                    "サポートが要る面の確認などの新しい機能が使えます",
        "more": "   …ほか {n}行",
        "build_cut": "def build(prm):  # （省略：プロジェクトの形）",
        "gi_comment": "# 道具を新しくしたときの控え（scaffold.py --update-tools）",
        "recorded": "\n記録しました：tools/{vf} = {v}",
        "known_recorded": "{path} に {v} を記録しました",
        "need_args": "--dest と --name（新しく作る）か、--update-tools（道具を新しくする）を指定してください",
        "h_process": "作り方：laser（レーザー）、fdm（3Dプリント）、both（両方。既定）",
        "h_bed": "プリンタの造形範囲 例 220x220",
        "h_lang": "言語：ja（日本語）、en（英語）。既定は環境変数 MONOZUKURI_LANG、無ければ ja。"
                  "--update-tools ではプロジェクトの meta.lang に従い、--lang は表示だけを変える",
        "h_git": "git init と最初のコミットまで行う",
        "m_update": "プロジェクト",
        "h_update": "既存のプロジェクトの tools/ を新しくする",
        "h_force": "--update-tools で、手を加えたファイルも上書きする",
    },
    "en": {
        "no_template": "Template not found: {path}",
        "dest_nonempty": "{dest} already has files. Give an empty folder or a new name",
        "methods_tbd": "(not decided yet)",
        "origin": "Outline centered at X=0, Y=0; bottom at Z=0. X right, Y back, Z up",
        "commit": "Scaffold: {name} (monozukuri)",
        "commit_fail": "!! Could not commit (set git user.name / user.email, then run again)",
        "no_tools": "{tools} not found. Give the project folder",
        "estimated": "{v} (estimated)",
        "unknown": "unknown",
        "start": "Updating tools: {old} -> {new} ({tools})",
        "added": "added",
        "upd_known": "updated (was the {v} version)",
        "upd_mine": "updated (your changes{names} are in the new version)",
        "names": ": {names}",
        "lost": "definitions missing from the new version: {names}",
        "differs": "matches no released version of the template",
        "blocked": "\n!! Some tool files were changed in this project, so nothing was overwritten",
        "item": "   {f}: {why}",
        "blocked_hint": "   To keep your changes, copy them into the new version and run again. "
                        "To overwrite, add --force (the old files stay in tools/.backup-<date-time>/)",
        "forced": "overwritten (--force; your changes are kept only in the backup)",
        "done": "  {f}: {how}",
        "up_to_date": "  Tools are already up to date",
        "backup": "  Old files: tools/.backup-{stamp}/",
        "mock_new": "\nmock.py was left as is (it has your build()). The new template is in tools/mock.py.new",
        "mock_same": "  Nothing differs outside build(). No need to switch",
        "mock_diff": "  Differences outside build() ({n} lines. To use the new framework, take mock.py.new and"
                     " replace its build() with your current build()):",
        "run_mock": "   Note: the new mock.py has no main(); it calls common.run_mock(build) at the end. Delete"
                    " everything from def main() down in your mock.py and end it with"
                    " if __name__ == \"__main__\": common.run_mock(build) to get the new features,"
                    " such as the check for faces that need support",
        "more": "   ...and {n} more lines",
        "build_cut": "def build(prm):  # (omitted: the project's shape)",
        "gi_comment": "# Backups made when updating tools (scaffold.py --update-tools)",
        "recorded": "\nRecorded: tools/{vf} = {v}",
        "known_recorded": "Recorded {v} in {path}",
        "need_args": "Give --dest and --name (create a new project), or --update-tools (update the tools)",
        "h_process": "Process: laser (laser cutting), fdm (3D printing), both (default)",
        "h_bed": "Printer bed size, e.g. 220x220",
        "h_lang": "Language: ja (Japanese), en (English). Default: env MONOZUKURI_LANG, else ja. "
                  "With --update-tools the project's meta.lang is used; --lang changes only the messages",
        "h_git": "Run git init and make the first commit",
        "m_update": "PROJECT",
        "h_update": "Update tools/ of an existing project",
        "h_force": "With --update-tools, also overwrite tool files changed in the project",
    },
}


def resolve_lang(explicit=None, data=None):
    """言語を決める：引数の指定 > データ（寸法ファイルの meta.lang など）> 環境変数 MONOZUKURI_LANG > ja"""
    for v in (explicit, data, os.environ.get("MONOZUKURI_LANG")):
        if v in LANG_CODES:
            return v
    return "ja"


def plugin_version():
    p = os.path.join(HERE, "..", "..", "..", ".claude-plugin", "plugin.json")
    return json.load(open(p, encoding="utf-8"))["version"]


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def known_versions():
    """古い版から順に並べる"""
    d = json.load(open(KNOWN, encoding="utf-8")) if os.path.exists(KNOWN) else {}
    return dict(sorted(d.items(), key=lambda kv: tuple(int(x) for x in kv[0].split("."))))


def top_defs(path):
    """ファイルの一番外側で定義している関数・クラスの名前"""
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (SyntaxError, UnicodeDecodeError):
        return None
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def without_build(path, lang="ja"):
    """mock.py から冒頭の説明と build() を除いた行（枠組みだけを比べるため）"""
    src = open(path, encoding="utf-8").read().splitlines()
    try:
        tree = ast.parse("\n".join(src))
    except SyntaxError:
        return src
    cut = []
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(getattr(tree.body[0], "value", None), ast.Constant):
        cut.append((tree.body[0].lineno - 1, tree.body[0].end_lineno, []))
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == "build":
            start = (n.decorator_list[0].lineno if n.decorator_list else n.lineno) - 1
            cut.append((start, n.end_lineno, [MSG[lang]["build_cut"]]))
    for a, b, put in sorted(cut, reverse=True):
        src[a:b] = put
    return src


def project_meta(proj):
    """いちばん新しい寸法ファイル（params/params_vNN.json）の meta。読めなければ {}"""
    vs = []
    for f in glob.glob(os.path.join(proj, "params", "params_v*.json")):
        m = re.search(r"params_v(\d+)\.json$", f)
        if m:
            vs.append((int(m.group(1)), f))
    if not vs:
        return {}
    try:
        meta = json.load(open(max(vs)[1], encoding="utf-8")).get("meta", {})
    except (OSError, ValueError, AttributeError):
        return {}
    return meta if isinstance(meta, dict) else {}


def mock_template(lang, process):
    """プロジェクトの言語・作り方に合う mock.py の雛形。作り方ごとの例があればそれ、無ければ言語の例（箱）"""
    for p in (os.path.join(VARIANTS, process, lang, "tools", "mock.py"),
              os.path.join(LANGS, lang, "tools", "mock.py"),
              os.path.join(LANGS, "ja", "tools", "mock.py")):
        if os.path.exists(p):
            return p
    return None


def update_tools(proj, force, lang_flag=None):
    proj = os.path.abspath(proj)
    tools = os.path.join(proj, "tools")
    # プロジェクトの言語と作り方：いちばん新しい寸法ファイルの meta.lang（無ければ ja）と meta.process（無ければ both）
    meta = project_meta(proj)
    proj_lang = meta.get("lang") if meta.get("lang") in LANG_CODES else "ja"
    process = meta.get("process") if meta.get("process") in PROCESSES else "both"
    lang = resolve_lang(lang_flag, proj_lang)            # 表示は --lang があればそれ、無ければプロジェクトの言語
    T = MSG[lang]
    if not os.path.isdir(tools):
        sys.exit(T["no_tools"].format(tools=tools))
    new_ver = plugin_version()
    known = known_versions()
    vf = os.path.join(tools, VERSION_FILE)
    old_ver = open(vf, encoding="utf-8").read().strip() if os.path.exists(vf) else None
    if not old_ver:
        # 記録が無ければ、中身がいちばん多く合う版を推定する
        score = {v: sum(1 for f, e in d.items() if os.path.exists(os.path.join(tools, f)) and sha(os.path.join(tools, f)) in e["sha256"])
                 for v, d in known.items()}
        best = max(score, key=score.get) if score else None
        old_ver = T["estimated"].format(v=best) if best and score[best] else T["unknown"]
    print(T["start"].format(old=old_ver, new=new_ver, tools=tools))

    plan, blocked, notes = [], [], []
    for f, src in OWNED.items():
        dst = os.path.join(tools, f)
        if not os.path.exists(dst):
            plan.append((f, T["added"]))
            continue
        h = sha(dst)
        if h == sha(src):
            continue                                     # すでに新しい
        hits = [v for v, d in known.items() if h in d.get(f, {}).get("sha256", [])]
        if hits:
            plan.append((f, T["upd_known"].format(v=hits[-1])))
            continue
        # プロジェクトで手を加えたファイル。足した定義が新しい版にすべてあれば上書きしてよい
        mine, theirs = top_defs(dst), top_defs(src)
        if f.endswith(".py") and mine is not None and theirs is not None and mine <= theirs:
            olds = [d[f]["defs"] for v, d in known.items() if f in d and v != new_ver]   # 今の版より前の版と比べる
            added = sorted(mine - set(olds[-1])) if olds else []
            plan.append((f, T["upd_mine"].format(names=T["names"].format(names=", ".join(added)) if added else "")))
            continue
        lost = sorted(mine - theirs) if mine is not None and theirs is not None else []
        blocked.append((f, T["lost"].format(names=", ".join(lost)) if lost else T["differs"]))

    if blocked and not force:
        print(T["blocked"])
        for f, why in blocked:
            print(T["item"].format(f=f, why=why))
        print(T["blocked_hint"])
        sys.exit(1)
    plan += [(f, T["forced"]) for f, _ in blocked]

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(tools, f".backup-{stamp}")
    for f, how in plan:
        dst = os.path.join(tools, f)
        if os.path.exists(dst):
            os.makedirs(backup, exist_ok=True)
            shutil.copy2(dst, os.path.join(backup, f))
        shutil.copy(OWNED[f], dst)
        print(T["done"].format(f=f, how=how))
    if not plan:
        print(T["up_to_date"])
    elif os.path.isdir(backup):
        print(T["backup"].format(stamp=stamp))

    # mock.py は上書きしない。プロジェクトの言語・作り方の新しい雛形を mock.py.new として置き、build() の外の違いを見せる
    new_mock = mock_template(proj_lang, process)
    mine = os.path.join(tools, "mock.py")
    if new_mock and (not os.path.exists(mine) or sha(mine) != sha(new_mock)):
        shutil.copy(new_mock, os.path.join(tools, "mock.py.new"))
        print(T["mock_new"])
        if os.path.exists(mine):
            diff = list(difflib.unified_diff(without_build(mine, lang), without_build(new_mock, lang),
                                             "mock.py", "mock.py.new", n=0, lineterm=""))
            body = [d for d in diff if d[:1] in "+-" and not d.startswith(("+++", "---"))]
            if not body:
                print(T["mock_same"])
            else:
                print(T["mock_diff"].format(n=len(body)))
                mine_src = open(mine, encoding="utf-8").read()
                if "run_mock(build)" not in mine_src and "def main(" in mine_src:
                    print(T["run_mock"])
                for d in body[:20]:
                    print("   " + d)
                if len(body) > 20:
                    print(T["more"].format(n=len(body) - 20))

    open(vf, "w", encoding="utf-8").write(new_ver + "\n")
    gi = os.path.join(proj, ".gitignore")
    line = "tools/.backup-*/"
    if os.path.exists(gi) and line not in open(gi, encoding="utf-8").read().split("\n"):
        with open(gi, "a", encoding="utf-8") as fp:
            fp.write(f"\n{MSG[proj_lang]['gi_comment']}\n{line}\n")
    print(T["recorded"].format(vf=VERSION_FILE, v=new_ver))


def dump_params(d, path):
    """寸法ファイルを、params・fab は1項目1行で書き出す（雛形と同じ読みやすい形）"""
    out, secs = ["{"], list(d.items())
    for si, (sec, val) in enumerate(secs):
        comma = "," if si < len(secs) - 1 else ""
        if sec in ("params", "fab") and isinstance(val, dict) and val:
            out.append(f'  "{sec}": {{')
            w = max(len(json.dumps(k, ensure_ascii=False)) for k in val) + 1
            for i, (k, v) in enumerate(val.items()):
                key = json.dumps(k, ensure_ascii=False) + ":"
                out.append(f"    {key:<{w}} {json.dumps(v, ensure_ascii=False)}{',' if i < len(val) - 1 else ''}")
            out.append("  }" + comma)
        else:
            body = json.dumps(val, ensure_ascii=False, indent=2).replace("\n", "\n  ")
            out.append(f'  "{sec}": {body}{comma}')
    open(path, "w", encoding="utf-8").write("\n".join(out + ["}"]) + "\n")


def keep_process_blocks(text, keep):
    """<!-- laser --> 〜 <!-- /laser -->（fdm も同じ）の区間を、作り方に入っていなければ外す。印の行は消す"""
    out, skip = [], []
    for ln in text.split("\n"):
        m = re.fullmatch(r"\s*<!-- (/?)(laser|fdm) -->\s*", ln)
        if m:
            if m.group(1):
                skip.pop()
            else:
                skip.append(m.group(2) not in keep)
            continue
        if not any(skip):
            out.append(ln)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


def create(a, lang):
    T = MSG[lang]
    dest = os.path.abspath(a.dest)
    if os.path.isdir(dest) and os.listdir(dest):
        sys.exit(T["dest_nonempty"].format(dest=dest))
    lang_dir = os.path.join(LANGS, lang)
    lang_params = os.path.join(lang_dir, "params", "params_v01.json")
    if not os.path.exists(lang_params):
        sys.exit(T["no_template"].format(path=os.path.normpath(lang_params)))
    keep = PROCESSES[a.process]
    junk = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
    shutil.copytree(TEMPLATE, dest, dirs_exist_ok=True, ignore=junk)
    shutil.copytree(lang_dir, dest, dirs_exist_ok=True, ignore=junk)       # 言語ごとの文書・寸法ファイル・例の mock.py を重ねる
    for f in SHARED_FILES:
        shutil.copy(os.path.join(SHARED, f), os.path.join(dest, "tools", f))
    open(os.path.join(dest, "tools", VERSION_FILE), "w", encoding="utf-8").write(plugin_version() + "\n")

    # 寸法ファイル：例の形（fdm は3Dプリントの例）＋作り方で使う fab だけ。fab はその言語の雛形の寸法ファイルから取る
    pp = os.path.join(dest, "params", "params_v01.json")
    base = json.load(open(lang_params, encoding="utf-8"))
    var = os.path.join(VARIANTS, a.process, lang)
    if os.path.isdir(var):
        shutil.copytree(var, dest, dirs_exist_ok=True, ignore=junk)
    d = json.load(open(pp, encoding="utf-8"))
    d["meta"]["process"] = a.process
    d["meta"]["lang"] = lang
    d["fab"] = {k: v for k, v in base["fab"].items() if set(v.get("process", ["laser", "fdm"])) & keep}
    if a.bed:
        bx, by = (float(x) for x in a.bed.lower().split("x"))
        d["params"]["bed_x"]["value"], d["params"]["bed_y"]["value"] = bx, by
    dump_params(d, pp)

    rep = {"{{NAME}}": a.name, "{{SUMMARY}}": a.summary or a.name,
           "{{ORIGIN}}": a.origin if a.origin is not None else T["origin"],
           "{{METHODS}}": a.methods or T["methods_tbd"], "{{DATE}}": datetime.date.today().isoformat()}
    for dd, _, fs in os.walk(dest):
        for f in fs:
            if f.endswith((".md", ".json")):
                p = os.path.join(dd, f)
                s = open(p, encoding="utf-8").read()
                for k, v in rep.items():
                    s = s.replace(k, v)
                if f.endswith(".md"):
                    s = keep_process_blocks(s, keep)
                open(p, "w", encoding="utf-8").write(s)

    if a.git:
        def git(*args):
            subprocess.run(["git", "-C", dest, *args], check=True, capture_output=True)
        if not os.path.isdir(os.path.join(dest, ".git")):
            git("init", "-q", "-b", "main")
        git("add", "-A")
        try:
            git("commit", "-q", "-m", T["commit"].format(name=a.name))
        except subprocess.CalledProcessError:
            print(T["commit_fail"])
    print(dest)


def record_tool_versions(lang="ja"):
    """版を出すときに実行する：今の道具の中身を tool_versions.json に足す（--update-tools が古い版を見分けるため）。
    mock.py は日本語の箱の例（lang/ja/tools/mock.py）だけを記録する"""
    known = known_versions()
    v = plugin_version()
    for f, src in list(OWNED.items()) + [("mock.py", os.path.join(LANGS, "ja", "tools", "mock.py"))]:
        e = known.setdefault(v, {}).setdefault(f, {"sha256": [], "defs": []})
        if sha(src) not in e["sha256"]:
            e["sha256"].append(sha(src))
        if f.endswith(".py"):
            e["defs"] = sorted(set(e["defs"]) | (top_defs(src) or set()))
    json.dump(known, open(KNOWN, "w", encoding="utf-8"), indent=1)
    print(MSG[lang]["known_recorded"].format(path=KNOWN, v=v))


def main():
    # ヘルプの言語を先に決める（--lang があればそれ、無ければ MONOZUKURI_LANG、無ければ ja）
    argv, hl = sys.argv[1:], None
    for i, x in enumerate(argv):
        if x == "--lang" and i + 1 < len(argv):
            hl = argv[i + 1]
        elif x.startswith("--lang="):
            hl = x.split("=", 1)[1]
    hl = resolve_lang(hl)
    H = MSG[hl]
    ap = argparse.ArgumentParser(description=__doc__ if hl == "ja" else DOC_EN,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest")
    ap.add_argument("--name")
    ap.add_argument("--summary", default="")
    ap.add_argument("--origin", default=None)       # 省くと言語ごとの既定（MSG の origin）
    ap.add_argument("--methods", default="")
    ap.add_argument("--process", default="both", choices=sorted(PROCESSES), help=H["h_process"])
    ap.add_argument("--bed", default=None, help=H["h_bed"])
    ap.add_argument("--lang", default=None, choices=list(LANG_CODES), help=H["h_lang"])
    ap.add_argument("--git", action="store_true", help=H["h_git"])
    ap.add_argument("--update-tools", metavar=H["m_update"], help=H["h_update"])
    ap.add_argument("--force", action="store_true", help=H["h_force"])
    ap.add_argument("--record-tool-versions", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    lang = resolve_lang(a.lang)
    if a.record_tool_versions:
        record_tool_versions(lang)
    elif a.update_tools:
        update_tools(a.update_tools, a.force, a.lang)
    elif a.dest and a.name:
        create(a, lang)
    else:
        ap.error(MSG[lang]["need_args"])


if __name__ == "__main__":
    main()
