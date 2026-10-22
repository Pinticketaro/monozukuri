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
    "questions": ["決めてほしいこと", ...],
    "images": [{"src": "out/v03/preview.png", "caption": "外観", "group": "外観"}, ...],   ← 1枚目が大きく出る
    "compare": [{"before": "out/v02/preview.png", "after": "out/v03/preview.png", "caption": "外観"},
                {"src": "out/v03/compare_side.png", "caption": "横から"}],
    "params_diff": "out/v03/params_diff.json",   ← params_diff.py --json の出力（または一覧そのもの）
    "model": "out/v03/model.glb",                ← render_model.py --glb の出力（任意、11MBまで。base64 のテキストにして載せる）
    "notes": "任意のメモ"
  }

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

    entry = {k: man.get(k) for k in ("version", "prev", "date", "stage", "summary", "changes", "questions", "notes")}
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
