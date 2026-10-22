"""前の版と今の版の画像を並べた比較画像を作る（左：前、中：今、右：変わった所を赤で強調）。
使い方: python3 compare.py before.png after.png --out compare.png [--labels "v02" "v03"] [--no-diff]
大きさが違う画像は、同じ高さにそろえてから比べる（差分は形がそろっているときだけ意味がある）。
"""
import argparse
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FONT_CANDIDATES = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                   "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                   "/System/Library/Fonts/Hiragino Sans GB.ttc",
                   "C:/Windows/Fonts/YuGothM.ttc"]


def font(size):
    try:
        import json
        env = json.load(open(os.path.expanduser("~/.cache/monozukuri/env.json")))
        if env.get("cjk_font_path"):
            return ImageFont.truetype(env["cjk_font_path"], size)
    except Exception:
        pass
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def fit(im, h):
    return im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)


def diff_image(a, b):
    """b を薄くして、a と違う所を赤く塗る。"""
    if a.size != b.size:
        a = a.resize(b.size, Image.LANCZOS)
    d = ImageChops.difference(a.convert("RGB"), b.convert("RGB")).convert("L")
    mask = d.point(lambda v: 255 if v > 28 else 0).filter(ImageFilter.MaxFilter(5))
    base = Image.blend(b.convert("RGB"), Image.new("RGB", b.size, "white"), 0.6)
    red = Image.new("RGB", b.size, (214, 48, 39))
    base.paste(red, mask=mask)
    import numpy as np
    changed = float((np.asarray(mask) > 0).mean())
    return base, changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--out", required=True)
    ap.add_argument("--labels", nargs=2, default=["前の版", "この版"])
    ap.add_argument("--height", type=int, default=520)
    ap.add_argument("--no-diff", action="store_true")
    a = ap.parse_args()

    A, B = Image.open(a.before).convert("RGB"), Image.open(a.after).convert("RGB")
    h = a.height
    tiles = [(fit(A, h), a.labels[0]), (fit(B, h), a.labels[1])]
    note = ""
    if not a.no_diff:
        d, changed = diff_image(A, B)
        tiles.append((fit(d, h), "変わった所（赤）"))
        note = f"画素の変化 {changed * 100:.1f}%"
    pad, top = 16, 46
    W = sum(t.width for t, _ in tiles) + pad * (len(tiles) + 1)
    out = Image.new("RGB", (W, h + top + pad), (244, 245, 242))
    dr = ImageDraw.Draw(out)
    f = font(24)
    x = pad
    for im, lab in tiles:
        out.paste(im, (x, top))
        dr.text((x + 4, 10), lab, fill=(40, 48, 44), font=f)
        x += im.width + pad
    if note:
        dr.text((W - pad - dr.textlength(note, font=font(18)), 14), note, fill=(110, 120, 114), font=font(18))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    out.save(a.out)
    print(a.out, note)


if __name__ == "__main__":
    main()
