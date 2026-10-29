"""確認ページ（確認ボード）に版を1つ追加して、公開用のファイルをそろえる。

使い方
  python3 build_page.py --root <プロジェクト> --manifest <版の説明.json>
  python3 build_page.py --root <プロジェクト> --rebuild          （画像はそのまま、ページだけ作り直す）
  どちらも --lang ja|en でページの言語を指定できる（下の「言語」）

版の説明（manifest）の形。パスはプロジェクトのフォルダからの相対パス
  {
    "project": "DZ60キーボード",            ← 初回だけ必須
    "lang": "ja",                           ← 任意。ページの言語（ja／en）
    "version": "v03", "prev": "v02", "date": "2026-10-22",
    "stage": "モック",                      ← モック／モデル（Fusion）／試作品 など
    "summary": "この版で見てほしいことを1〜2文で",
    "changes": ["変えたこと", ...],
    "questions": [                          ← 決めてほしいこと。3つの書き方（why＝なぜ聞くか、は任意）
      "自由に書いてほしいこと",                                   … 文字だけ：フィードバック欄に書いてもらう
      {"q": "USBの穴を左に寄せてよい？", "type": "yesno", "why": "ケーブルが机に当たる"},   … はい／いいえ をボタンで選ぶ
      {"q": "分割線はどれ？", "options": ["A案：中央で直線",       … 案の中から1つをボタンで選ぶ
          {"label": "B案：キーの間でジグザグ", "note": "補足", "img": "out/v03/split_b.png"}]}
    ],                                        ← 選んだ答えは db の answers に1人1件で入る（選び直せる）
                                                モックの notes にある問いの候補（下）も、ここに足される
    "images": [{"src": "out/v03/preview.png", "caption": "外観", "group": "外観"}, ...],   ← 1枚目が大きく出る
    "compare": [{"before": "out/v02/preview.png", "after": "out/v03/preview.png", "caption": "外観"},
                {"src": "out/v03/compare_side.png", "caption": "横から"}],
    "params_diff": "out/v03/params_diff.json",   ← params_diff.py --json の出力（または一覧そのもの）
    "model": "out/v03/model.glb",                ← render_model.py --glb の出力（任意、11MBまで。base64 のテキストにして載せる）
    "notes": "任意のメモ",
    "parts": "out/v03/scene.json",               ← エクスポート（STL）で部品名を出すため。scene.json か [{"name","key"}]
                                                    scene.json の notes（モックが見つけたこと）も読む：
                                                    {"q": …, "type": "yesno"|"options", "options": […], "why": …} は問いに、
                                                    文字だけのものは「モックが見つけた注意」としてメモに足す（manifest と同じ内容は重ねない）
    "step": "out/v03/step/index.json"            ← エクスポート（STEP）用。mock.py の index.json か [{"src","name","file"}]
  }
  ページの「エクスポート」では、STL は 3Dモデル（GLB）から部品ごとにその場で作り、STEP は載せたファイルを使う。
  どちらも ZIP にまとめて保存する（アーティファクトの保存は .stl / .step を直接扱えないため）。

言語（ページの文言・はい／いいえ・「モックが見つけた注意」・このスクリプトの表示）
  --lang ＞ manifest の "lang" ＞ scene.json（manifest の parts）の "lang" ＞ board.json の "lang"
  ＞ 環境変数 MONOZUKURI_LANG ＞ ja。決まった言語は board.json の "lang" に残る（--rebuild はそれを使う）。
  ページに切り替えボタンは無い。変えるときは --lang を付けて作り直す。

出力（<プロジェクト>/review/）
  board.json             … 全部の版の記録（ページの元データ）
  index.html             … 公開するページ
  img/<版>/…             … 縮小した画像（webp）と3Dモデル（model.glb.txt：GLBをbase64にしたもの）
  publish_<版>.json      … 公開に使う files の一覧（この版で増えたファイルだけ）
  publish_all.json       … 全ファイルの一覧（新しい URL に初めて公開するとき）

English
  Adds one version to the review page (review board) and prepares the files to publish.
  Usage: build_page.py --root <project> --manifest <manifest.json> [--lang ja|en]
         build_page.py --root <project> --rebuild [--lang ja|en]   (re-render the page only)
  Manifest fields (paths are relative to the project folder):
    project      project name (required the first time)
    lang         optional page language, "ja" or "en"
    version, prev, date, stage ("mock", "model (Fusion)", "prototype", ...)
    summary      1-2 sentences on what to look at in this version
    changes      list of what changed
    questions    things to decide. A plain string is answered in the feedback panel;
                 {"q": ..., "type": "yesno", "why": ...} gets Yes/No buttons;
                 {"q": ..., "options": ["A ...", {"label": ..., "note": ..., "img": ...}]} gets one choice
                 per person. Answers go to the db "answers" collection (one per person, can be changed).
                 Question candidates in scene.json notes (below) are added too.
    images       [{"src", "caption", "group"}]; the first one is shown large
    compare      [{"before", "after", "caption"}] (slider) or [{"src", "caption"}]
    params_diff  output of params_diff.py --json (path or the list itself)
    model        output of render_model.py --glb (optional, up to 11MB, embedded as base64 text)
    notes        optional notes
    parts        scene.json path or [{"name", "key"}], for part names in the STL export.
                 scene.json notes are read too: dict entries become questions, plain strings are added
                 to the notes under "Found by the mock:" (text already in the manifest notes is skipped).
    step         mock.py step/index.json path or [{"src", "name", "file"}], for the STEP export
  Language: --lang > manifest "lang" > scene.json "lang" > board.json "lang" > env MONOZUKURI_LANG > ja.
  The result is stored in board.json "lang". The page has no language toggle; rebuild with --lang to change it.
  Output in <project>/review/: board.json, index.html, img/<version>/..., publish_<version>.json, publish_all.json
"""
import argparse
import json
import os
import shutil

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "board.html")
MAX_W = 2000
MAX_GLB = 11 * 1024 * 1024

# 表示する文言（ja／en）。ページの文言は board.html の I18N にある
MSG = {
    "ja": {
        "title": "{project} 確認ボード",
        "yes": "はい", "no": "いいえ",
        "found": "モックが見つけた注意：", "bullet": "・",
        "group": "図",
        "need_project": "初回は manifest に project（プロジェクト名）が要ります",
        "no_file": "ファイルがありません: {p}",
        "glb_big": "!! GLB が {mb:.1f}MB あるので載せません（11MBまで）。部品を減らすか粗くしてください",
        "step_big": "!! STEP {src} が {mb:.1f}MB あるので載せません（11MBまで）",
        "built": "review/index.html を作りました（{n}版）。この版で増えたファイル {k}個",
        "publish": "公開に使う一覧: review/publish_{ver}.json（初めての公開や新しい URL のときは review/publish_all.json）",
        "rebuilt": "review/index.html を作り直しました",
        "usage": "--manifest か --rebuild を指定してください",
        "open_local": "!! PC のページに未対応のフィードバックが {n}件あります（review/feedback_local.json）。この版に反映したか確かめてください：",
        "open_artifact": "公開中のページのフィードバックは ArtifactData で読んで確かめてください（review/artifact.json）",
    },
    "en": {
        "title": "{project} review board",
        "yes": "Yes", "no": "No",
        "found": "Found by the mock:", "bullet": "- ",
        "group": "Figures",
        "need_project": "The first manifest needs \"project\" (the project name)",
        "no_file": "File not found: {p}",
        "glb_big": "!! The GLB is {mb:.1f}MB, so it is not included (limit 11MB). Use fewer parts or a coarser mesh",
        "step_big": "!! STEP {src} is {mb:.1f}MB, so it is not included (limit 11MB)",
        "built": "Built review/index.html ({n} versions). New files in this version: {k}",
        "publish": "Files to publish: review/publish_{ver}.json (for a first publish or a new URL: review/publish_all.json)",
        "rebuilt": "Rebuilt review/index.html",
        "usage": "Specify --manifest or --rebuild",
        "open_local": "!! The local page has {n} open feedback item(s) (review/feedback_local.json). Check that this version addresses them:",
        "open_artifact": "Read the published page's feedback with ArtifactData too (review/artifact.json)",
    },
}


def resolve_lang(explicit=None, data=None):
    for v in (explicit, data, os.environ.get("MONOZUKURI_LANG")):
        if v in ("ja", "en"):
            return v
    return "ja"


def first_lang(*vs):
    """データに入っている言語のうち、最初の有効なもの（無ければ None）"""
    return next((v for v in vs if v in ("ja", "en")), None)


def vkey(v):
    digits = "".join(ch for ch in v if ch.isdigit())
    return (int(digits) if digits else 0, v)


def put_image(src, dst_dir, name):
    os.makedirs(dst_dir, exist_ok=True)
    im = Image.open(src)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    if im.width > MAX_W:
        im = im.resize((MAX_W, round(im.height * MAX_W / im.width)), Image.LANCZOS)
    out = os.path.join(dst_dir, name + ".webp")
    im.save(out, "WEBP", quality=86, method=5)
    return out


def add_version(root, man, cli_lang=None):
    rv = os.path.join(root, "review")
    os.makedirs(rv, exist_ok=True)
    bpath = os.path.join(rv, "board.json")
    board = json.load(open(bpath, encoding="utf-8")) if os.path.exists(bpath) else {"project": "", "versions": []}
    # 言語：--lang ＞ manifest ＞ scene.json ＞ board.json ＞ 環境変数 ＞ ja（scene.json を読むまでは scene.json 抜きで決めておく）
    lang = resolve_lang(cli_lang, first_lang(man.get("lang"), board.get("lang")))
    if man.get("project"):
        board["project"] = man["project"]
    if not board["project"]:
        raise SystemExit(MSG[lang]["need_project"])
    ver = man["version"]
    vdir = os.path.join(rv, "img", ver)
    if os.path.isdir(vdir):
        shutil.rmtree(vdir)          # 同じ版を作り直すときは置き換える
    new_files = []

    def rel(p):
        return os.path.relpath(p, rv).replace(os.sep, "/")

    def src_path(p):
        q = p if os.path.isabs(p) else os.path.join(root, p)
        if not os.path.exists(q):
            raise SystemExit(MSG[lang]["no_file"].format(p=p))
        return q

    entry = {k: man.get(k) for k in ("version", "prev", "date", "stage", "summary", "changes", "notes")}
    # scene.json（manifest の parts に渡したもの）：言語・notes・部品一覧を読む
    scene = json.load(open(src_path(man["parts"]), encoding="utf-8")) if isinstance(man.get("parts"), str) else {}
    lang = resolve_lang(cli_lang, first_lang(man.get("lang"), scene.get("lang"), board.get("lang")))
    board["lang"] = lang
    t = MSG[lang]
    # scene.json の notes：問いの候補（dict）は問いに、文字だけのものはメモに
    scene_notes = scene.get("notes") or []
    questions = list(man.get("questions") or [])
    asked = {(q if isinstance(q, str) else q.get("q") or q.get("question", "")).strip() for q in questions}
    for n in scene_notes:
        if isinstance(n, dict) and (n.get("q") or "").strip() and n["q"].strip() not in asked:
            questions.append(n)
            asked.add(n["q"].strip())
    texts = [n for n in scene_notes if isinstance(n, str) and n not in (man.get("notes") or "")]
    if texts:
        entry["notes"] = ((man.get("notes") or "") + "\n\n" if man.get("notes") else "") + \
            t["found"] + "\n" + "\n".join(t["bullet"] + s for s in texts)

    entry["questions"] = []
    for i, q in enumerate(questions):
        if isinstance(q, str):
            entry["questions"].append({"q": q, "type": "text"})
            continue
        item = {"q": q.get("q") or q.get("question", ""), "type": "text"}
        if q.get("why"):
            item["why"] = q["why"]
        if q.get("type") == "yesno":
            item["type"] = "yesno"
            item["options"] = [{"id": "yes", "label": t["yes"]}, {"id": "no", "label": t["no"]}]
        elif q.get("options"):
            item["type"] = "choice"
            item["options"] = []
            for j, o in enumerate(q["options"]):
                o = {"label": o} if isinstance(o, str) else dict(o)
                opt = {"id": o.get("id") or chr(ord("a") + j), "label": o.get("label", ""), "note": o.get("note", "")}
                if o.get("img"):
                    out = put_image(src_path(o["img"]), vdir, f"q{i + 1:02d}{opt['id']}")
                    new_files.append(out)
                    opt["img"] = rel(out)
                item["options"].append(opt)
        entry["questions"].append(item)
    entry["images"] = []
    for i, im in enumerate(man.get("images", [])):
        out = put_image(src_path(im["src"]), vdir, f"img{i + 1:02d}")
        new_files.append(out)
        entry["images"].append({"src": "img/" + ver + "/" + os.path.basename(out),
                                "caption": im.get("caption", ""), "group": im.get("group", t["group"])})
    entry["compare"] = []
    for i, c in enumerate(man.get("compare", [])):
        if "before" in c:
            b = put_image(src_path(c["before"]), vdir, f"cmp{i + 1:02d}a")
            a = put_image(src_path(c["after"]), vdir, f"cmp{i + 1:02d}b")
            new_files += [b, a]
            entry["compare"].append({"before": rel(b), "after": rel(a), "caption": c.get("caption", "")})
        else:
            s = put_image(src_path(c["src"]), vdir, f"cmp{i + 1:02d}")
            new_files.append(s)
            entry["compare"].append({"src": rel(s), "caption": c.get("caption", "")})
    pd = man.get("params_diff")
    if isinstance(pd, str):
        pd = json.load(open(src_path(pd), encoding="utf-8"))
    entry["params_diff"] = pd or []

    # 寸法と根拠：パラメータファイルの全項目（値・根拠 basis・資料 ref・状態）。manifest の "dims" か params/params_<版>.json
    dq = man.get("dims") or os.path.join("params", f"params_{ver}.json")
    dq = dq if os.path.isabs(dq) else os.path.join(root, dq)
    entry["dims"] = []
    if os.path.exists(dq):
        pj = json.load(open(dq, encoding="utf-8"))
        for sec in ("params", "fab"):
            for k, it in (pj.get(sec) or {}).items():
                if isinstance(it, dict) and "value" in it:
                    entry["dims"].append({"key": k, "label": it.get("label", k), "value": it["value"], "unit": it.get("unit", ""),
                                          "basis": it.get("basis", ""), "ref": it.get("ref", ""), "status": it.get("status", ""),
                                          "fab": sec == "fab"})

    # 資料（プロジェクトの refs/）：図面・データシート・写真など。review/refs/ に写してページから開けるようにする。
    # manifest の "refs": [{"src": "refs/xx.png", "caption": "説明"}] で説明を付けられる
    entry["refs"] = []
    rdir = os.path.join(root, "refs")
    if os.path.isdir(rdir):
        caps = {r["src"]: r.get("caption", "") for r in (man.get("refs") or []) if isinstance(r, dict) and r.get("src")}
        os.makedirs(os.path.join(rv, "refs"), exist_ok=True)
        for f in sorted(os.listdir(rdir)):
            src = os.path.join(rdir, f)
            if f.startswith(".") or not os.path.isfile(src):
                continue
            dst = os.path.join(rv, "refs", f)
            if not os.path.exists(dst) or open(dst, "rb").read() != open(src, "rb").read():
                shutil.copy2(src, dst)
                new_files.append(dst)
            entry["refs"].append({"src": "refs/" + f, "name": f, "caption": caps.get("refs/" + f, ""),
                                  "img": f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"))})
    entry["model"] = None
    if man.get("model"):
        g = src_path(man["model"])
        if os.path.getsize(g) > MAX_GLB:
            print(t["glb_big"].format(mb=os.path.getsize(g) / 1e6))
        else:
            # アーティファクトは .glb をそのまま配信しないので、base64 のテキストにして載せる（ページ側で戻す）
            import base64
            os.makedirs(vdir, exist_ok=True)
            dst = os.path.join(vdir, "model.glb.txt")
            open(dst, "w").write(base64.b64encode(open(g, "rb").read()).decode("ascii"))
            new_files.append(dst)
            entry["model"] = rel(dst)

    # エクスポート用の部品一覧（GLB のノード p<番号>_<キー> と対応）。scene.json か一覧そのもの
    parts = man.get("parts")
    if isinstance(parts, str):
        parts = scene.get("parts", [])
    entry["parts"] = [{"name": p.get("name", ""), "key": p.get("key") or os.path.splitext(os.path.basename(p.get("file", "")))[0]}
                      for p in (parts or [])]

    # STEP（エクスポート用）。アーティファクトは .step を配信しないので base64 のテキストにして載せる
    steps = man.get("step")
    if isinstance(steps, str):
        steps = json.load(open(src_path(steps), encoding="utf-8"))
    entry["step"] = []
    if steps:
        import base64
        sdir = os.path.join(vdir, "step")
        os.makedirs(sdir, exist_ok=True)
        for i, st in enumerate(steps):
            g = src_path(st["src"])
            if os.path.getsize(g) > MAX_GLB:
                print(t["step_big"].format(src=st["src"], mb=os.path.getsize(g) / 1e6))
                continue
            fname = st.get("file") or os.path.basename(g)
            dst = os.path.join(sdir, f"{i + 1:02d}.step.txt")
            open(dst, "w").write(base64.b64encode(open(g, "rb").read()).decode("ascii"))
            new_files.append(dst)
            entry["step"].append({"src": rel(dst), "name": st.get("name", fname), "file": fname})

    board["versions"] = [v for v in board["versions"] if v["version"] != ver] + [entry]
    board["versions"].sort(key=lambda v: vkey(v["version"]))
    json.dump(board, open(bpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    render(rv, board)
    files = {rel(f): os.path.relpath(f, root).replace(os.sep, "/") for f in new_files}
    write_publish(rv, f"publish_{ver}.json", files)
    write_all(rv, root)
    print(t["built"].format(n=len(board["versions"]), k=len(files)))
    print(t["publish"].format(ver=ver))
    warn_open_feedback(rv, t)


def warn_open_feedback(rv, t):
    """版を足すたびに、まだ対応していないフィードバックを知らせる（書かれた後に版を作って見落とさないように）"""
    lp = os.path.join(rv, "feedback_local.json")
    if os.path.exists(lp):
        try:
            fb = json.load(open(lp, encoding="utf-8")).get("feedback", {})
        except (json.JSONDecodeError, OSError):
            fb = {}
        opened = [f for f in fb.values() if (f.get("status") or "open") == "open"]
        if opened:
            print(t["open_local"].format(n=len(opened)))
            for f in sorted(opened, key=lambda f: f.get("createdAt", "")):
                print(f"   - {f.get('version', '')} {f.get('kind', '')}: {str(f.get('text', ''))[:60]}")
    if os.path.exists(os.path.join(rv, "artifact.json")):
        print(t["open_artifact"])


def render(rv, board):
    html = open(TEMPLATE, encoding="utf-8").read()
    lang = resolve_lang(None, board.get("lang"))
    board = dict(board, lang=lang)       # ページは BOARD.lang で文言を選ぶ
    data = json.dumps(board, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("__TITLE__", esc(MSG[lang]["title"].format(project=board["project"])))
    html = html.replace("/*__BOARD__*/null", data).replace("__PROJECT__", esc(board["project"]))
    open(os.path.join(rv, "index.html"), "w", encoding="utf-8").write(html)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_publish(rv, name, files):
    json.dump({"file_path": "review/index.html", "files": files},
              open(os.path.join(rv, name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def write_all(rv, root):
    files = {}
    for d, _, fs in [w for sub in ("img", "refs") for w in os.walk(os.path.join(rv, sub))]:
        for f in fs:
            p = os.path.join(d, f)
            files[os.path.relpath(p, rv).replace(os.sep, "/")] = os.path.relpath(p, root).replace(os.sep, "/")
    write_publish(rv, "publish_all.json", dict(sorted(files.items())))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--manifest")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--lang", choices=["ja", "en"])
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    if a.rebuild:
        rv = os.path.join(root, "review")
        bpath = os.path.join(rv, "board.json")
        board = json.load(open(bpath, encoding="utf-8"))
        lang = resolve_lang(a.lang, board.get("lang"))
        if board.get("lang") != lang:      # 決まった言語を board.json に残す（serve_review.py も読む）
            board["lang"] = lang
            json.dump(board, open(bpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        render(rv, board)
        write_all(rv, root)
        print(MSG[lang]["rebuilt"])
    elif a.manifest:
        add_version(root, json.load(open(a.manifest, encoding="utf-8")), a.lang)
    else:
        ap.error(MSG[resolve_lang(a.lang)]["usage"])


if __name__ == "__main__":
    main()
