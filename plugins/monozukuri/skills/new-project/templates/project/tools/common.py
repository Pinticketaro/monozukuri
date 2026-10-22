"""プロジェクト共通：寸法ファイルの読み込み、版番号、出力先。

寸法ファイルは params/params_vNN.json。1つの版の寸法はこのファイルだけに書く（ほかのスクリプトに数値を直接書かない）。
  params … 形の寸法（モックで決める）
  fab    … 加工の値（カーフ・実板厚・クリアランス・インサート穴など）。status が「初期値」のものは
           試し片（tools/coupons.py）で測って「実測」に置き換える
  P = load("v03").P      → P.outer_w のように値だけで使える
  load().labels          → 項目名（寸法表・差分に使う）
版を省くと、いちばん新しい版を使う。
"""
import glob
import json
import os
import re
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS = os.path.join(ROOT, "params")


def versions():
    vs = []
    for f in glob.glob(os.path.join(PARAMS, "params_v*.json")):
        m = re.search(r"params_(v\d+)\.json$", f)
        if m:
            vs.append(m.group(1))
    return sorted(vs, key=lambda v: int(v[1:]))


def latest():
    vs = versions()
    if not vs:
        raise SystemExit("params/ に寸法ファイルがありません")
    return vs[-1]


def version_from_argv():
    """コマンドの引数に v03 のような版があればそれ、なければ最新。"""
    for a in sys.argv[1:]:
        if re.fullmatch(r"v\d+", a):
            return a
    return latest()


def load(ver=None):
    ver = ver or latest()
    path = os.path.join(PARAMS, f"params_{ver}.json")
    d = json.load(open(path, encoding="utf-8"))
    # params（形の寸法）と fab（試し片で決める加工の値：カーフ・実板厚・クリアランスなど）を1つにまとめて使う
    items = {**d.get("params", {}), **d.get("fab", {})}
    vals = {k: (v["value"] if isinstance(v, dict) and "value" in v else v) for k, v in items.items()}
    labels = {k: (v.get("label", k) if isinstance(v, dict) else k) for k, v in items.items()}
    units = {k: (v.get("unit", "") if isinstance(v, dict) else "") for k, v in items.items()}
    fab = {k: v for k, v in d.get("fab", {}).items()}
    return SimpleNamespace(ver=ver, path=path, meta=d.get("meta", {}), P=SimpleNamespace(**vals),
                           labels=labels, units=units, fab=fab, raw=d)


def prev_version(ver):
    vs = versions()
    i = vs.index(ver) if ver in vs else len(vs)
    return vs[i - 1] if i > 0 else None


def out_dir(ver, *sub):
    d = os.path.join(ROOT, "out", ver, *sub)
    os.makedirs(d, exist_ok=True)
    return d
