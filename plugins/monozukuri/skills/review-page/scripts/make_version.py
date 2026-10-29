"""1つの版を1回のコマンドで作る：モック → 外観・平面図・断面 → 寸法の差 → 確認ページ。
出すのは短い要約だけ。各段の全部の出力は out/<版>/make.log に残す。

使い方
  python3 make_version.py <プロジェクト> vNN                  … 全部（manifest が無ければ画像まで）
  python3 make_version.py <プロジェクト> vNN --page-only      … 画像は作り直さず、manifest を埋めてページだけ
  python3 make_version.py <プロジェクト> vNN --no-page        … 画像まで
  python3 make_version.py <プロジェクト> vNN --tool tools/model.py   … mock.py の代わりに使う道具（none で飛ばす。人が作ったモデルは
                                                                     out/vNN/scene.json を先に書いて --tool none）
  ほか: --views iso,top,side（render_model.py へ）、--at x=値（slices.py の断面の位置）

manifest（out/vNN/manifest.json）は文だけ書けばよい：stage・summary・changes・questions（notes・compare は任意）。
空いている欄はこのスクリプトが埋めて書き戻す：
  version・prev（寸法ファイルの meta.parent、無ければ前の番号の版）・date・
  images（外観・平面図・断面。manifest に書いた画像は外観の後に入る。並びを自分で決めるときは
          out/vNN/preview.png なども含めて全部書く）・
  compare（前の版の外観と重ねる）・params_diff・model・parts・step・
  notes（寸法ファイルの fab に「初期値」があれば「本番の前にテストピースで測る値：…」）・project（初回だけ）
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from status import load, params_versions, parent_of, ver_key  # noqa: E402

CAP = {
    "ja": {"preview": "外観", "plan": "平面図", "section": "断面", "fig": "図", "stage": "モック",
           "measure": "本番の前にテストピースで測る値："},
    "en": {"preview": "Exterior", "plan": "Plan", "section": "Section", "fig": "Figures", "stage": "Mock",
           "measure": "Measure with coupons before the final build: "},
}


class Run:
    def __init__(self, root, ver):
        self.root, self.ver = root, ver
        self.log = []

    def step(self, name, cmd):
        """1段を動かして出力を返す。失敗したら最後の25行を出して止める"""
        r = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True)
        out = (r.stdout + r.stderr).strip()
        self.log.append(f"$ {' '.join(cmd)}\n{out}\n")
        if r.returncode:
            self.save()
            tail = "\n".join(out.splitlines()[-25:])
            raise SystemExit(f"!! {name} で止まりました（終了コード {r.returncode}）\n{tail}\n全部の出力: out/{self.ver}/make.log")
        return [ln for ln in out.splitlines() if ln.strip() and not self.is_path(ln)]

    def is_path(self, ln):
        head = ln.strip().split("（")[0].split(" ")[0]
        return head.startswith((self.root, "out/", "/")) and ("/" in head)

    def save(self):
        d = os.path.join(self.root, "out", self.ver)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "make.log"), "w", encoding="utf-8").write("\n".join(self.log))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("version")
    ap.add_argument("--tool", default="tools/mock.py")
    ap.add_argument("--views")
    ap.add_argument("--at")
    ap.add_argument("--page-only", action="store_true")
    ap.add_argument("--no-page", action="store_true")
    a = ap.parse_args()
    root, ver = os.path.abspath(a.project), a.version
    py, R = sys.executable, Run(root, ver)
    o = lambda f: f"out/{ver}/{f}"
    exists = lambda rel: os.path.exists(os.path.join(root, rel))

    params = load(os.path.join(root, "params", f"params_{ver}.json"), {}) or {}
    meta = params.get("meta", {})
    lang = meta.get("lang") if meta.get("lang") in CAP else "ja"
    C = CAP[lang]
    board = load(os.path.join(root, "review", "board.json"), {}) or {}
    order = sorted(set(params_versions(root)) | {v["version"] for v in board.get("versions", [])} | {ver}, key=ver_key)
    mpath = os.path.join(root, "out", ver, "manifest.json")
    man = load(mpath, {}) or {}
    prev = man.get("prev") or parent_of(root, ver, order)
    say = [f"{ver}（{prev} から）" if prev else ver]

    # 1. 形と画像
    if not a.page_only:
        if a.tool != "none":
            if not exists(a.tool):
                raise SystemExit(f"!! {a.tool} がありません（人が作ったモデルなら out/{ver}/scene.json を書いて --tool none）")
            say += ["  " + ln for ln in R.step(a.tool, [py, a.tool, ver])]
        if not exists(o("scene.json")):
            raise SystemExit(f"!! {o('scene.json')} がありません")
        cmd = [py, os.path.join(HERE, "render_model.py"), "--scene", o("scene.json"), "--out", o("preview.png"), "--glb", o("model.glb")]
        say += ["  " + ln for ln in R.step("render_model.py", cmd + (["--views", a.views] if a.views else []))]
        cmd = [py, os.path.join(HERE, "slices.py"), "--scene", o("scene.json"), "--plan", o("plan.png"), "--section", o("section.png")]
        say += ["  " + ln for ln in R.step("slices.py", cmd + (["--at", a.at] if a.at else []))]
    if prev and exists(f"params/params_{prev}.json") and exists(f"params/params_{ver}.json"):
        diff = R.step("params_diff.py", [py, os.path.join(HERE, "params_diff.py"), f"params/params_{prev}.json",
                                         f"params/params_{ver}.json", "--json", o("params_diff.json")])
        say.append(f"  寸法の差（{prev} → {ver}）: {len(diff)}件")
        say += ["    " + ln.lstrip("- ") for ln in diff[:12]] + ([f"    ほか {len(diff) - 12}件"] if len(diff) > 12 else [])

    # 2. manifest の空いている欄を埋めて、ページを作る
    if a.no_page or not man:
        R.save()
        if not man:
            say.append(f"  manifest（{o('manifest.json')}）が無いのでページは作っていません。文（stage・summary・changes・questions）を書いて --page-only")
        say.append(f"  見る画像: {o('preview.png')}（ほか plan.png・section.png）")
        print("\n".join(say))
        return
    filled = []

    def fill(k, v):
        if k not in man and v not in (None, [], ""):
            man[k] = v
            filled.append(k)

    fill("project", None if board.get("project") else meta.get("title"))
    fill("version", ver)
    fill("prev", prev)
    fill("date", datetime.date.today().isoformat())
    fill("stage", C["stage"])
    defaults = [{"src": o("preview.png"), "caption": C["preview"], "group": C["preview"]},
                {"src": o("plan.png"), "caption": C["plan"], "group": C["fig"]},
                {"src": o("section.png"), "caption": C["section"], "group": C["fig"]}]
    defaults = [d for d in defaults if exists(d["src"])]
    given = man.get("images", [])
    if not any(g.get("src") in {d["src"] for d in defaults} for g in given):
        man["images"] = defaults[:1] + given + defaults[1:]
        filled.append("images")
    if prev and exists(f"out/{prev}/preview.png") and exists(o("preview.png")):
        fill("compare", [{"before": f"out/{prev}/preview.png", "after": o("preview.png"), "caption": C["preview"]}])
    fill("params_diff", o("params_diff.json") if exists(o("params_diff.json")) else None)
    fill("model", o("model.glb") if exists(o("model.glb")) else None)
    fill("parts", o("scene.json") if exists(o("scene.json")) else None)
    fill("step", next((s for s in (o("step/index.json"), o("model/index.json")) if exists(s)), None))
    init = [k for k, it in (params.get("fab") or {}).items() if isinstance(it, dict) and it.get("status") in ("初期値", "initial")]
    fill("notes", C["measure"] + ("、" if lang == "ja" else ", ").join(init) if init else None)
    json.dump(man, open(mpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if filled:
        say.append("  manifest に埋めた欄: " + "・".join(filled))
    say += ["  " + ln for ln in R.step("build_page.py", [py, os.path.join(HERE, "build_page.py"), "--root", root,
                                                          "--manifest", os.path.relpath(mpath, root)])]
    R.save()

    # 3. ページの届け先
    art = load(os.path.join(root, "review", "artifact.json"), {}) or {}
    srv = load(os.path.join(root, "review", ".serve.json"), {}) or {}
    if art.get("url"):
        say.append(f"  公開: Artifact に review/publish_{ver}.json の files で（{art['url']}、capabilities は3つとも）")
    if srv.get("url"):
        try:
            os.kill(int(srv.get("pid")), 0)
            say.append(f"  PC のページ {srv['url']} は自動で更新されます")
        except (OSError, TypeError, ValueError):
            say.append("  PC のページのサーバーは止まっています（serve_review.py で動かす）")
    say.append(f"  見る画像: {o('preview.png')}（ほか plan.png・section.png）。全部の出力: {o('make.log')}")
    print("\n".join(say))


if __name__ == "__main__":
    main()
