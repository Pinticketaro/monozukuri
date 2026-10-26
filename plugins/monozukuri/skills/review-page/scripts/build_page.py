"""確認ページ（確認ボード）に版を1つ追加して、公開用のファイルをそろえる。

使い方
  python3 build_page.py --root <プロジェクト> --manifest <版の説明.json>
  python3 build_page.py --root <プロジェクト> --rebuild          （画像はそのまま、ページだけ作り直す）

版の説明（manifest）の形。パスはプロジェクトのフォルダからの相対パス
  {
    "project": "DZ60キーボード",            ← 初回だけ必須
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
    "parts": "out/v03/scene.json",               ← 書き出し（STL）で部品名を出すため。scene.json か [{"name","key"}]
                                                    scene.json の notes（モックが見つけたこと）も読む：
                                                    {"q": …, "type": "yesno"|"options", "options": […], "why": …} は問いに、
                                                    文字だけのものは「モックが見つけた注意」としてメモに足す（manifest と同じ内容は重ねない）
    "step": "out/v03/step/index.json"            ← 書き出し（STEP）用。mock.py の index.json か [{"src","name","file"}]
  }
  ページの「書き出す」では、STL は 3Dモデル（GLB）から部品ごとにその場で作り、STEP は載せたファイルを使う。
  どちらも ZIP にまとめて保存する（アーティファクトの保存は .stl / .step を直接扱えないため）。

出力（<プロジェクト>/review/）
  board.json             … 全部の版の記録（ページの元データ）
  index.html             … 公開するページ
  img/<版>/…             … 縮小した画像（webp）と3Dモデル（model.glb.txt：GLBをbase64にしたもの）
  publish_<版>.json      … 公開に使う files の一覧（この版で増えたファイルだけ）
  publish_all.json       … 全ファイルの一覧（新しい URL に初めて公開するとき）
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


def add_version(root, man):
    rv = os.path.join(root, "review")
    os.makedirs(rv, exist_ok=True)
    bpath = os.path.join(rv, "board.json")
    board = json.load(open(bpath, encoding="utf-8")) if os.path.exists(bpath) else {"project": "", "versions": []}
    if man.get("project"):
        board["project"] = man["project"]
    if not board["project"]:
        raise SystemExit("初回は manifest に project（プロジェクト名）が要ります")
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
            raise SystemExit(f"ファイルがありません: {p}")
        return q

    entry = {k: man.get(k) for k in ("version", "prev", "date", "stage", "summary", "changes", "notes")}
    # scene.json の notes：問いの候補（dict）は問いに、文字だけのものはメモに
    scene_notes = []
    if isinstance(man.get("parts"), str):
        scene_notes = json.load(open(src_path(man["parts"]), encoding="utf-8")).get("notes") or []
    questions = list(man.get("questions") or [])
    asked = {(q if isinstance(q, str) else q.get("q") or q.get("question", "")).strip() for q in questions}
    for n in scene_notes:
        if isinstance(n, dict) and (n.get("q") or "").strip() and n["q"].strip() not in asked:
            questions.append(n)
            asked.add(n["q"].strip())
    texts = [n for n in scene_notes if isinstance(n, str) and n not in (man.get("notes") or "")]
    if texts:
        entry["notes"] = ((man.get("notes") or "") + "\n\n" if man.get("notes") else "") + \
            "モックが見つけた注意：\n" + "\n".join("・" + t for t in texts)

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
            item["options"] = [{"id": "yes", "label": "はい"}, {"id": "no", "label": "いいえ"}]
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
                                "caption": im.get("caption", ""), "group": im.get("group", "図")})
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
    entry["model"] = None
    if man.get("model"):
        g = src_path(man["model"])
        if os.path.getsize(g) > MAX_GLB:
            print(f"!! GLB が {os.path.getsize(g) / 1e6:.1f}MB あるので載せません（11MBまで）。部品を減らすか粗くしてください")
        else:
            # アーティファクトは .glb をそのまま配信しないので、base64 のテキストにして載せる（ページ側で戻す）
            import base64
            os.makedirs(vdir, exist_ok=True)
            dst = os.path.join(vdir, "model.glb.txt")
            open(dst, "w").write(base64.b64encode(open(g, "rb").read()).decode("ascii"))
            new_files.append(dst)
            entry["model"] = rel(dst)

    # 書き出し用の部品一覧（GLB のノード p<番号>_<キー> と対応）。scene.json か一覧そのもの
    parts = man.get("parts")
    if isinstance(parts, str):
        parts = json.load(open(src_path(parts), encoding="utf-8")).get("parts", [])
    entry["parts"] = [{"name": p.get("name", ""), "key": p.get("key") or os.path.splitext(os.path.basename(p.get("file", "")))[0]}
                      for p in (parts or [])]

    # STEP（書き出し用）。アーティファクトは .step を配信しないので base64 のテキストにして載せる
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
                print(f"!! STEP {st['src']} が {os.path.getsize(g) / 1e6:.1f}MB あるので載せません（11MBまで）")
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
    print(f"review/index.html を作りました（{len(board['versions'])}版）。この版で増えたファイル {len(files)}個")
    print(f"公開に使う一覧: review/publish_{ver}.json（初めての公開や新しい URL のときは review/publish_all.json）")


def render(rv, board):
    html = open(TEMPLATE, encoding="utf-8").read()
    data = json.dumps(board, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("/*__BOARD__*/null", data).replace("__PROJECT__", esc(board["project"]))
    open(os.path.join(rv, "index.html"), "w", encoding="utf-8").write(html)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_publish(rv, name, files):
    json.dump({"file_path": "review/index.html", "files": files},
              open(os.path.join(rv, name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def write_all(rv, root):
    files = {}
    for d, _, fs in os.walk(os.path.join(rv, "img")):
        for f in fs:
            p = os.path.join(d, f)
            files[os.path.relpath(p, rv).replace(os.sep, "/")] = os.path.relpath(p, root).replace(os.sep, "/")
    write_publish(rv, "publish_all.json", dict(sorted(files.items())))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--manifest")
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    if a.rebuild:
        rv = os.path.join(root, "review")
        render(rv, json.load(open(os.path.join(rv, "board.json"), encoding="utf-8")))
        write_all(rv, root)
        print("review/index.html を作り直しました")
    elif a.manifest:
        add_version(root, json.load(open(a.manifest, encoding="utf-8")))
    else:
        ap.error("--manifest か --rebuild を指定してください")


if __name__ == "__main__":
    main()
