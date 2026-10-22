"""新しいものづくりプロジェクトの雛形を作る。
使い方
  python3 scaffold.py --dest <作るフォルダ> --name "名前" --summary "1行の説明"
                      [--origin "外形の左下、X右・Y奥・Z上"] [--methods "上下の板：CO2レーザー／枠：3Dプリント（PLA）"]
                      [--bed 220x220] [--git]
--dest がすでにあって中身があるときは止まる（上書きしない）。
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "templates", "project")
SHARED = os.path.join(HERE, "..", "..", "review-page", "scripts")
SHARED_FILES = ["render_model.py", "slices.py", "compare.py", "params_diff.py"]
FAB = os.path.join(HERE, "..", "..", "fab-prep", "scripts")
FAB_FILES = ["fabkit.py", "fab_check.py", "export_fab.py", "cut_region.py"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--summary", default="")
    ap.add_argument("--origin", default="外形の中心が X=0・Y=0、底面が Z=0。X右・Y奥・Z上")
    ap.add_argument("--methods", default="")
    ap.add_argument("--bed", default=None, help="プリンタの造形範囲 例 220x220")
    ap.add_argument("--git", action="store_true", help="git init と最初のコミットまで行う")
    a = ap.parse_args()

    dest = os.path.abspath(a.dest)
    if os.path.isdir(dest) and os.listdir(dest):
        sys.exit(f"{dest} には既にファイルがあります。空のフォルダか新しい名前を指定してください")
    shutil.copytree(TEMPLATE, dest, dirs_exist_ok=True)
    for f in SHARED_FILES:
        shutil.copy(os.path.join(SHARED, f), os.path.join(dest, "tools", f))
    for f in FAB_FILES:
        shutil.copy(os.path.join(FAB, f), os.path.join(dest, "tools", f))

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


if __name__ == "__main__":
    main()
