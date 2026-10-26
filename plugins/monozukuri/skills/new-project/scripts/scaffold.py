"""新しいものづくりプロジェクトの雛形を作る。既存のプロジェクトの道具（tools/）を新しくする。
使い方
  python3 scaffold.py --dest <作るフォルダ> --name "名前" --summary "1行の説明"
                      [--origin "外形の左下、X右・Y奥・Z上"] [--methods "上下の板：CO2レーザー／枠：3Dプリント（PLA）"]
                      [--bed 220x220] [--git]
  python3 scaffold.py --update-tools <プロジェクトのフォルダ> [--force]
--dest がすでにあって中身があるときは止まる（上書きしない）。
--update-tools は、プラグインが持ち主の道具（geom.py・common.py・描画のスクリプトなど）だけを新しくする。
  mock.py は上書きせず、新しい雛形を tools/mock.py.new として置く。元のファイルは tools/.backup-<日時>/ に残す。
"""
import argparse
import ast
import datetime
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "templates", "project")
SHARED = os.path.join(HERE, "..", "..", "review-page", "scripts")
SHARED_FILES = ["render_model.py", "slices.py", "compare.py", "params_diff.py"]
# プラグインが持ち主の道具（--update-tools で上書きする）。mock.py は利用者の build() があるので入れない
OWNED = {f: os.path.join(TEMPLATE, "tools", f)
         for f in ["geom.py", "common.py", "coupons.py", "dims_sheet.py", "requirements.txt"]}
OWNED.update({f: os.path.join(SHARED, f) for f in SHARED_FILES})
KNOWN = os.path.join(HERE, "tool_versions.json")       # これまでの版の道具の中身（sha256）と定義の名前。版を出すときに足す
VERSION_FILE = ".monozukuri-version"


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


def without_build(path):
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
            cut.append((start, n.end_lineno, ["def build(prm):  # （省略：プロジェクトの形）"]))
    for a, b, put in sorted(cut, reverse=True):
        src[a:b] = put
    return src


def update_tools(proj, force):
    proj = os.path.abspath(proj)
    tools = os.path.join(proj, "tools")
    if not os.path.isdir(tools):
        sys.exit(f"{tools} がありません。プロジェクトのフォルダを指定してください")
    new_ver = plugin_version()
    known = known_versions()
    vf = os.path.join(tools, VERSION_FILE)
    old_ver = open(vf, encoding="utf-8").read().strip() if os.path.exists(vf) else None
    if not old_ver:
        # 記録が無ければ、中身がいちばん多く合う版を推定する
        score = {v: sum(1 for f, e in d.items() if os.path.exists(os.path.join(tools, f)) and sha(os.path.join(tools, f)) in e["sha256"])
                 for v, d in known.items()}
        best = max(score, key=score.get) if score else None
        old_ver = f"{best}（推定）" if best and score[best] else "不明"
    print(f"道具を新しくします：{old_ver} → {new_ver}（{tools}）")

    plan, blocked, notes = [], [], []
    for f, src in OWNED.items():
        dst = os.path.join(tools, f)
        if not os.path.exists(dst):
            plan.append((f, "追加"))
            continue
        h = sha(dst)
        if h == sha(src):
            continue                                     # すでに新しい
        hits = [v for v, d in known.items() if h in d.get(f, {}).get("sha256", [])]
        if hits:
            plan.append((f, f"更新（{hits[-1]} の中身）"))
            continue
        # プロジェクトで手を加えたファイル。足した定義が新しい版にすべてあれば上書きしてよい
        mine, theirs = top_defs(dst), top_defs(src)
        if f.endswith(".py") and mine is not None and theirs is not None and mine <= theirs:
            olds = [d[f]["defs"] for d in known.values() if f in d]
            added = sorted(mine - set(olds[-1])) if olds else []
            plan.append((f, "更新（手を加えた所" + (f"：{', '.join(added)}" if added else "") + " は新しい版にあります）"))
            continue
        lost = sorted(mine - theirs) if mine is not None and theirs is not None else []
        blocked.append((f, "新しい版に無い定義：" + ", ".join(lost) if lost else "雛形のどの版とも中身が違います"))

    if blocked and not force:
        print("\n!! プロジェクトで手を加えたファイルがあるので、何も上書きせずに止めました")
        for f, why in blocked:
            print(f"   {f}：{why}")
        print("   手を加えた所を残したいときは、新しい版に写してから再実行してください。"
              "上書きしてよいときは --force を付けます（元のファイルは tools/.backup-<日時>/ に残ります）")
        sys.exit(1)
    plan += [(f, "上書き（--force。手を加えた所は控えにだけ残ります）") for f, _ in blocked]

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(tools, f".backup-{stamp}")
    for f, how in plan:
        dst = os.path.join(tools, f)
        if os.path.exists(dst):
            os.makedirs(backup, exist_ok=True)
            shutil.copy2(dst, os.path.join(backup, f))
        shutil.copy(OWNED[f], dst)
        print(f"  {f}：{how}")
    if not plan:
        print("  道具はすでに新しい版です")
    elif os.path.isdir(backup):
        print(f"  元のファイル：tools/.backup-{stamp}/")

    # mock.py は上書きしない。新しい雛形を mock.py.new として置き、build() の外の違いを見せる
    new_mock = os.path.join(TEMPLATE, "tools", "mock.py")
    mine = os.path.join(tools, "mock.py")
    if not os.path.exists(mine) or sha(mine) != sha(new_mock):
        shutil.copy(new_mock, os.path.join(tools, "mock.py.new"))
        print("\nmock.py はそのままです（build() があるため）。新しい雛形を tools/mock.py.new に置きました")
        if os.path.exists(mine):
            diff = list(difflib.unified_diff(without_build(mine), without_build(new_mock), "mock.py", "mock.py.new",
                                             n=0, lineterm=""))
            body = [d for d in diff if d[:1] in "+-" and not d.startswith(("+++", "---"))]
            if not body:
                print("  build() の外は同じです。差し替えは要りません")
            else:
                print(f"  build() の外の違い（{len(body)}行。新しい枠組みを使うときは、mock.py.new の build() を今の build() に置き換えて使う）：")
                for d in body[:40]:
                    print("   " + d)
                if len(body) > 40:
                    print(f"   …ほか {len(body) - 40}行")

    open(vf, "w", encoding="utf-8").write(new_ver + "\n")
    gi = os.path.join(proj, ".gitignore")
    line = "tools/.backup-*/"
    if os.path.exists(gi) and line not in open(gi, encoding="utf-8").read().split("\n"):
        with open(gi, "a", encoding="utf-8") as fp:
            fp.write(f"\n# 道具を新しくしたときの控え（scaffold.py --update-tools）\n{line}\n")
    print(f"\n記録しました：tools/{VERSION_FILE} = {new_ver}")


def create(a):
    dest = os.path.abspath(a.dest)
    if os.path.isdir(dest) and os.listdir(dest):
        sys.exit(f"{dest} には既にファイルがあります。空のフォルダか新しい名前を指定してください")
    shutil.copytree(TEMPLATE, dest, dirs_exist_ok=True)
    for f in SHARED_FILES:
        shutil.copy(os.path.join(SHARED, f), os.path.join(dest, "tools", f))
    open(os.path.join(dest, "tools", VERSION_FILE), "w", encoding="utf-8").write(plugin_version() + "\n")

    rep = {"{{NAME}}": a.name, "{{SUMMARY}}": a.summary or a.name, "{{ORIGIN}}": a.origin,
           "{{METHODS}}": a.methods or "（未定）", "{{DATE}}": datetime.date.today().isoformat()}
    for d, _, fs in os.walk(dest):
        for f in fs:
            if f.endswith((".md", ".json")):
                p = os.path.join(d, f)
                s = open(p, encoding="utf-8").read()
                for k, v in rep.items():
                    s = s.replace(k, v)
                open(p, "w", encoding="utf-8").write(s)
    if a.bed:
        bx, by = (float(x) for x in a.bed.lower().split("x"))
        pp = os.path.join(dest, "params", "params_v01.json")
        d = json.load(open(pp, encoding="utf-8"))
        d["params"]["bed_x"]["value"], d["params"]["bed_y"]["value"] = bx, by
        json.dump(d, open(pp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    if a.git:
        def git(*args):
            subprocess.run(["git", "-C", dest, *args], check=True, capture_output=True)
        if not os.path.isdir(os.path.join(dest, ".git")):
            git("init", "-q", "-b", "main")
        git("add", "-A")
        try:
            git("commit", "-q", "-m", f"雛形：{a.name}（monozukuri）")
        except subprocess.CalledProcessError:
            print("!! コミットできませんでした（git の user.name / user.email を設定してから再実行）")
    print(dest)


def record_tool_versions():
    """版を出すときに実行する：今の道具の中身を tool_versions.json に足す（--update-tools が古い版を見分けるため）"""
    known = known_versions()
    v = plugin_version()
    for f, src in list(OWNED.items()) + [("mock.py", os.path.join(TEMPLATE, "tools", "mock.py"))]:
        e = known.setdefault(v, {}).setdefault(f, {"sha256": [], "defs": []})
        if sha(src) not in e["sha256"]:
            e["sha256"].append(sha(src))
        if f.endswith(".py"):
            e["defs"] = sorted(set(e["defs"]) | (top_defs(src) or set()))
    json.dump(known, open(KNOWN, "w", encoding="utf-8"), indent=1)
    print(f"{KNOWN} に {v} を記録しました")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest")
    ap.add_argument("--name")
    ap.add_argument("--summary", default="")
    ap.add_argument("--origin", default="外形の中心が X=0・Y=0、底面が Z=0。X右・Y奥・Z上")
    ap.add_argument("--methods", default="")
    ap.add_argument("--bed", default=None, help="プリンタの造形範囲 例 220x220")
    ap.add_argument("--git", action="store_true", help="git init と最初のコミットまで行う")
    ap.add_argument("--update-tools", metavar="プロジェクト", help="既存のプロジェクトの tools/ を新しくする")
    ap.add_argument("--force", action="store_true", help="--update-tools で、手を加えたファイルも上書きする")
    ap.add_argument("--record-tool-versions", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.record_tool_versions:
        record_tool_versions()
    elif a.update_tools:
        update_tools(a.update_tools, a.force)
    elif a.dest and a.name:
        create(a)
    else:
        ap.error("--dest と --name（新しく作る）か、--update-tools（道具を新しくする）を指定してください")


if __name__ == "__main__":
    main()
