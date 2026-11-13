"""プロジェクト共通：パラメータファイルの読み込み、版番号、出力先。

パラメータファイルは params/params_vNN.json。1つの版の寸法はこのファイルだけに書く（ほかのスクリプトに数値を直接書かない）。
  params … 形の寸法（モックで決める）
  fab    … 加工パラメータ（カーフ・実板厚・クリアランス・インサート穴など）。status が「初期値」のものは
           テストピース（tools/coupons.py）で測って「実測」に置き換える
  P = load("v03").P      → P.outer_w のように値だけで使える
  load().labels          → 項目名（寸法表・差分に使う）
  load().lang            → 表示の言語（"ja" か "en"。パラメータファイルの meta.lang、無ければ環境変数 MONOZUKURI_LANG、無ければ "ja"）
版を省くと、いちばん新しい版を使う。

English: shared helpers for the project tools. Reads the params file params/params_vNN.json (the only place
where one version's dimensions are written), finds versions, and makes output folders.
  params … shape dimensions (decided with the mock)
  fab    … fabrication values (kerf, real sheet thickness, clearance, insert holes). Values with status
           "initial" are measured with coupons (tools/coupons.py) and replaced with "measured" values
  load("v03").P.outer_w  → a value;  load().labels → item names;  load().lang → "ja" or "en"
  Language: --lang ja|en on the command line > meta.lang in the params file > env MONOZUKURI_LANG > "ja".
Without a version, the latest one is used.
"""
import glob
import json
import os
import re
import sys
import sysconfig
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS = os.path.join(ROOT, "params")

MSG = {
    "ja": {"no_params": "params/ にパラメータファイルがありません",
           "assembly": "組み立て（全部品）",
           "step_bad": "{name}: STEP {se} / メッシュ {me}",
           "step_count": "{sdir}（STEP {n}個）",
           "step_check": "STEP の大きさの確認:", "step_ok": "すべて一致", "step_ng": "ずれあり → ",
           "step_skip": "STEP は省きました（CadQuery がありません。monozukuri-setup スキルで入ります）",
           "step_skip_arm": "STEP は省きました（Windows の ARM64 版 Python には CadQuery がありません。"
                            "STEP が要るなら x64 版の Python で monozukuri-setup スキルを実行します）",
           "not_utf8": "{path} が UTF-8 で保存されていません（ANSI・UTF-16 など）。UTF-8 で保存し直してください",
           "question": "問いの候補:", "qtype": "（{t}）", "note": "注意:"},
    "en": {"no_params": "No params file in params/",
           "assembly": "Assembly (all parts)",
           "step_bad": "{name}: STEP {se} / mesh {me}",
           "step_count": "{sdir} ({n} STEP files)",
           "step_check": "STEP size check:", "step_ok": "all match", "step_ng": "mismatch -> ",
           "step_skip": "Skipped STEP (CadQuery is not installed. The monozukuri-setup skill installs it)",
           "step_skip_arm": "Skipped STEP (CadQuery is not available for Python on Windows ARM64. "
                            "For STEP, run the monozukuri-setup skill with an x64 Python)",
           "not_utf8": "{path} is not saved as UTF-8 (ANSI, UTF-16 or similar). Save it again as UTF-8",
           "question": "Question candidate:", "qtype": "({t})", "note": "Note:"},
}


def resolve_lang(explicit=None, data=None):
    """表示の言語を決める：明示（--lang）> データ（meta.lang など）> 環境変数 MONOZUKURI_LANG > "ja"。"""
    for v in (explicit, data, os.environ.get("MONOZUKURI_LANG")):
        if v in ("ja", "en"):
            return v
    return "ja"


def lang_from_argv():
    """コマンドの引数に --lang ja / --lang en（--lang=en も可）があればそれ、なければ None。"""
    a = sys.argv[1:]
    for i, x in enumerate(a):
        if x == "--lang" and i + 1 < len(a):
            return a[i + 1]
        if x.startswith("--lang="):
            return x.split("=", 1)[1]
    return None


# 版の名前：v03 のような番号。同じ版から分けた案は v04a・v04b のように英小文字を付ける（ブランチ）
VER_RE = r"v\d+[a-z]*"


def ver_key(v):
    """並べる順：番号、次に案の文字（v03 < v04a < v04b < v05）"""
    m = re.fullmatch(r"v(\d+)([a-z]*)", v)
    return (int(m.group(1)), m.group(2)) if m else (0, v)


def versions():
    vs = []
    for f in glob.glob(os.path.join(glob.escape(PARAMS), "params_v*.json")):     # フォルダ名に [ ] があっても探せるように
        m = re.search(r"params_(" + VER_RE + r")\.json$", f)
        if m:
            vs.append(m.group(1))
    return sorted(vs, key=ver_key)


def latest():
    vs = versions()
    if not vs:
        raise SystemExit(MSG[resolve_lang(lang_from_argv())]["no_params"])
    return vs[-1]


def version_from_argv():
    """コマンドの引数に v03 のような版があればそれ、なければ最新。"""
    # 古いプロジェクトの mock.py（run_mock を呼ばず自分の main() を持つ）も最初にここを呼ぶので、ここでもそろえる
    for _s in (sys.stdout, sys.stderr):        # Windows のパイプは ANSI コードページになるので UTF-8 にそろえる
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    for a in sys.argv[1:]:
        if re.fullmatch(VER_RE, a):
            return a
    return latest()


def read_json(path, lang=None):
    """JSON を読む。utf-8-sig なので BOM 付きの UTF-8（Windows の PowerShell 5.1・メモ帳が付ける）も読める。
    UTF-8 でないファイル（ANSI・UTF-16 で保存したもの）は、トレースバックでなく1行の案内で止める"""
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except UnicodeDecodeError:
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        raise SystemExit(MSG[resolve_lang(lang or lang_from_argv())]["not_utf8"].format(path=rel))


def load(ver=None, lang=None):
    """lang を渡すとそれを優先する（--lang の値など）。無ければパラメータファイルの meta.lang → 環境変数 → "ja"。"""
    ver = ver or latest()
    path = os.path.join(PARAMS, f"params_{ver}.json")
    d = read_json(path, lang)
    # params（形の寸法）と fab（テストピースで決める加工パラメータ：カーフ・実板厚・クリアランスなど）を1つにまとめて使う
    items = {**d.get("params", {}), **d.get("fab", {})}
    vals = {k: (v["value"] if isinstance(v, dict) and "value" in v else v) for k, v in items.items()}
    labels = {k: (v.get("label", k) if isinstance(v, dict) else k) for k, v in items.items()}
    units = {k: (v.get("unit", "") if isinstance(v, dict) else "") for k, v in items.items()}
    fab = {k: v for k, v in d.get("fab", {}).items()}
    meta = d.get("meta", {})
    return SimpleNamespace(ver=ver, path=path, meta=meta, lang=resolve_lang(lang, meta.get("lang")),
                           P=SimpleNamespace(**vals), labels=labels, units=units, fab=fab, raw=d)


def prev_version(ver):
    """前の版（親）。パラメータファイルの meta.parent があればそれ。無ければ1つ前の番号の版
    （その番号に案が複数あるとき＝ブランチの後は、いちばん後の案。続ける案は meta.parent に書く）"""
    path = os.path.join(PARAMS, f"params_{ver}.json")
    if os.path.exists(path):
        parent = read_json(path).get("meta", {}).get("parent")
        if parent:
            return parent
    n = ver_key(ver)[0]
    older = [v for v in versions() if ver_key(v)[0] < n]
    return older[-1] if older else None


def siblings(ver):
    """同じ番号の別の案（v04a に対する v04b など）"""
    n = ver_key(ver)[0]
    return [v for v in versions() if ver_key(v)[0] == n and v != ver]


def out_dir(ver, *sub):
    d = os.path.join(ROOT, "out", ver, *sub)
    os.makedirs(d, exist_ok=True)
    return d


# ---------------------------------------------------------------- モックを作る（tools/mock.py から呼ぶ）
UP_DIRS = {"z": (0, 0, 1), "-z": (0, 0, -1), "x": (1, 0, 0), "-x": (-1, 0, 0), "y": (0, 1, 0), "-y": (0, -1, 0)}
BRIDGE_MAX = 5.0           # サポートなしで印刷できるブリッジの長さの目安（fab に bridge_max が無いとき）
OVERHANG_MIN = 1.0         # これより短いオーバーハング（支えから水平に測る）は、サポートなしで印刷できることが多い。
                           # 経験則で出典なし（0.4mm ノズルの線2〜3本分。OrcaSlicer の「Ignore small overhangs」も大きさは公開していない）。
                           # 寝かせた細いピンや、ベッドに接する小さな角R の下側など。テストプリントで確かめる


def _nearest(ref):
    """点の集まり ref（n, 2）から、いちばん近い点を探す関数を返す：f(点の並び) → (距離, ref の番号)。
    scipy があれば KD 木、無ければ総当たり（メモリを使いすぎないよう分けて計算する）"""
    import numpy as np
    ref = np.asarray(ref, float)
    try:
        from scipy.spatial import cKDTree
        tree = cKDTree(ref)
        return lambda pts: tree.query(np.asarray(pts, float))
    except ImportError:
        pass

    c0 = ref.mean(axis=0) if len(ref) else np.zeros(2)                  # 原点の近くへ寄せて、桁落ちを防ぐ
    r0 = ref - c0
    rr = (r0 * r0).sum(axis=1)

    def query(pts):
        pts = np.asarray(pts, float) - c0
        dist, idx = np.empty(len(pts)), np.empty(len(pts), dtype=int)
        step = max(1, 4_000_000 // max(1, len(ref)))
        for s in range(0, len(pts), step):
            q = pts[s:s + step]
            d2 = rr[None, :] - 2 * (q @ r0.T)                            # |q − r|² − |q|²（行ごとの最小は同じ）
            i = d2.argmin(axis=1)
            idx[s:s + step] = i
            dist[s:s + step] = np.sqrt(np.maximum(d2[np.arange(len(q)), i] + (q * q).sum(axis=1), 0))
        return dist, idx
    return query


def _sample_tris(T2, budget=6000):
    """平面に投影した三角形（k, 3, 2）の中に、間隔 h 以下で点を置く：いちばん長い辺に平行な列を h 以下の間隔で引き、
    列の上に h 以下の間隔で並べる（細長い三角形でも点が増えすぎない）。点の数が budget の数倍に収まるよう h を決める。
    戻り値は (点（n, 2）, h)"""
    import numpy as np
    L = np.stack([np.hypot(*(T2[:, (i + 1) % 3] - T2[:, i]).T) for i in range(3)], axis=1)
    i0 = L.argmax(axis=1)                                            # いちばん長い辺 i0→i0+1、残りの頂点 i0+2
    rows = np.arange(len(T2))
    p0, p1, p2 = T2[rows, i0], T2[rows, (i0 + 1) % 3], T2[rows, (i0 + 2) % 3]
    base = L[rows, i0]
    cr = np.abs((p1 - p0)[:, 0] * (p2 - p0)[:, 1] - (p1 - p0)[:, 1] * (p2 - p0)[:, 0])
    alt = cr / np.maximum(base, 1e-12)                               # いちばん長い辺から残りの頂点までの距離
    h = max(0.1, (0.5 * float(cr.sum()) / budget) ** 0.5)
    for _ in range(12):
        n1 = np.maximum(1, np.ceil(base / h)).astype(int)
        n2 = np.maximum(1, np.ceil(alt / h)).astype(int)
        if int(((n1 + 1) * (n2 + 1)).sum()) <= 4 * budget:
            break
        h *= 1.5
    pts = []
    key = n1.astype(np.int64) * 1_000_000 + n2
    for kv in np.unique(key):
        s_ = key == kv
        s, t = np.meshgrid(np.linspace(0, 1, kv // 1_000_000 + 1), np.linspace(0, 1, kv % 1_000_000 + 1), indexing="ij")
        s, t = s.ravel()[None, :, None], t.ravel()[None, :, None]
        q = p0[s_][:, None, :] + s * (p1 - p0)[s_][:, None, :]
        pts.append(((1 - t) * q + t * p2[s_][:, None, :]).reshape(-1, 2))
    return np.concatenate(pts), h


def _densify(a, b, step):
    """線分（a[i]〜b[i]）の上に、間隔 step 以下で点を置く。戻り値は (点, 点の載る線分の番号)"""
    import numpy as np
    cnt = np.maximum(1, np.ceil(np.hypot(*(b - a).T) / step).astype(int)) + 1
    seg = np.repeat(np.arange(len(a)), cnt)
    t = (np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)) / np.repeat(cnt - 1, cnt)
    return a[seg] + (b - a)[seg] * t[:, None], seg


def _closest_on_segs(p, a, b):
    """点 p から線分（a[i]〜b[i]）までの距離と、線分の上のいちばん近い点"""
    import numpy as np
    ab = b - a
    t = np.clip(((p - a) * ab).sum(axis=1) / np.maximum((ab * ab).sum(axis=1), 1e-24), 0, 1)
    q = a + ab * t[:, None]
    return np.hypot(*(q - p).T), q


def _bridge_span(a2, b2, anc, ref, allow=1.0):
    """平面に投影したまとまりの縁（線分 a2[i]〜b2[i]。anc[i] が True なら支えのある縁）から、ブリッジの長さを求める。
    向きを変えながら、まとまりにその向きの平行な線（ブリッジの線）を引く。線の両端が支えのある縁なら、その線は支えられている。
    両端が支えられていない線の部分が、支えられた線か支え（点 ref）から allow mm 以内の細い所だけなら、その向きでブリッジにできる
    （穴の脇のように片側だけ支えられた所が広く残る向きは、ブリッジにできない）。
    できる向きのうち、いちばん長い線がいちばん短い向きを選び、その長さを返す。どの向きでもできなければ None。
    向きの候補は、支えのある縁に直角な向き・支えの無い縁に平行な向き（縁の長い順に12）と、7.5° おきの24"""
    import numpy as np
    d = b2 - a2
    L = np.hypot(d[:, 0], d[:, 1])
    ang = np.mod(np.arctan2(d[:, 1], d[:, 0]) + np.where(anc, np.pi / 2, 0.0), np.pi)
    bins = np.minimum((ang / np.pi * 360).astype(int), 359)                 # 0.5° ごと
    wsum = np.bincount(bins, weights=L, minlength=360)
    dirs = []
    for bn in np.argsort(-wsum, kind="stable")[:12]:
        if wsum[bn] > 0:
            m_ = np.nonzero(bins == bn)[0]
            dirs.append(float(ang[m_[np.argmax(L[m_])]]))                   # その中でいちばん長い縁の向き
    dirs += [k * np.pi / 24 for k in range(24)]
    best, seen = None, set()
    for th in dirs:
        if round(th, 6) in seen:
            continue
        seen.add(round(th, 6))
        c, s = np.cos(th), np.sin(th)
        u0, v0 = a2 @ (c, s), a2 @ (-s, c)                                  # u：線に沿う向き、v：線に直角な向き
        u1, v1 = b2 @ (c, s), b2 @ (-s, c)
        lo, hi = np.minimum(v0, v1), np.maximum(v0, v1)
        vmin, ext = float(lo.min()), float(hi.max() - lo.min())
        if ext < 1e-9:
            continue
        S = int(min(200, max(16, np.ceil(ext / 0.2))))                      # 線の数
        dv = ext / S
        k0 = np.clip(np.ceil((lo - vmin) / dv - 0.5), 0, S).astype(int)    # 縁 i と交わる線：k0 ≤ k < k1
        k1 = np.clip(np.ceil((hi - vmin) / dv - 0.5), 0, S).astype(int)
        cnt = np.maximum(k1 - k0, 0)
        if not cnt.sum():
            continue
        seg = np.repeat(np.arange(len(a2)), cnt)
        kk = np.repeat(k0, cnt) + np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        vk = vmin + (kk + 0.5) * dv
        uu = u0[seg] + (vk - v0[seg]) / (v1[seg] - v0[seg]) * (u1[seg] - u0[seg])
        o = np.lexsort((uu, kk))
        kk, uu, seg = kk[o], uu[o], seg[o]
        keep = (np.bincount(kk, minlength=S) % 2 == 0)[kk]                  # 交わりが奇数の線（数値の誤差）は使わない
        kk, uu, seg = kk[keep], uu[keep], seg[keep]
        if not len(kk):
            continue
        ua, ub, vv = uu[0::2], uu[1::2], vmin + (kk[0::2] + 0.5) * dv      # まとまりの中を通る区間（交わりの2つずつ）
        ln = ub - ua
        ok = anc[seg[0::2]] & anc[seg[1::2]]
        if not ok.any():
            continue
        span = float(ln[ok].max())
        if best is not None and span >= best - 1e-6:
            continue
        bad = ~ok & (ln > 1e-6)
        if bad.any():
            step = max(allow / 2, dv)
            pb = _densify(np.column_stack([ua[bad], vv[bad]]), np.column_stack([ub[bad], vv[bad]]), step)[0]
            po = _densify(np.column_stack([ua[ok], vv[ok]]), np.column_stack([ub[ok], vv[ok]]), step)[0]
            R = np.concatenate([po, np.column_stack([ref @ (c, s), ref @ (-s, c)])])
            if _nearest(R)(pb)[0].max() > allow + dv:
                continue
        best = span
    return best


def overhangs(mesh, deg=45.0, up="z", min_area=1.0, tol=0.5):
    """3Dプリントでサポートが要りそうな面（オーバーハング）と、ブリッジを探す。
    印刷の向き up（モデルのどの向きをベッドから上へ向けるか）で立てたとき、水平からの角度が deg より浅いオーバーハング面
    （tol° の余裕を見る。ちょうど deg の斜面、たとえば 45° の面取りは入れない）。ベッドから1レイヤー（0.2mm）以内にある面
    （部品のいちばん下の面など）は除く。
    つながった面ごとにまとめ、まとまりの縁のうち、隣の面がその縁より下へ続く所（先に印刷される所）と、ベッドから1レイヤー
    （0.2mm）以内の辺を「支え」とする。ベッドから1レイヤー以内の辺は、まとまりの中の辺（寝かせた丸棒がベッドに接する線など）も
    支えとして長さを測る（ブリッジの線の両端に使うのは縁の支えだけ）。
    支えからいちばん遠い点の向かい合う両側に支えがあり、まとまりを両端が支えられた平行な線で渡せればブリッジ
    （length＝いちばん長い線の長さ。_bridge_span）。そうでなければオーバーハング（length＝支えからいちばん遠い点までの長さ。
    支えが無いまとまりは、いちばん低い所の辺から測る。辺が無ければいちばん低い頂点から）。長さは印刷の向きで水平に測る。
    支えが無く、ベッドから1レイヤーより上にあるまとまりは floating（下につながる所が無く、空中から印刷が始まる）。
    [{"kind": "bridge" か "overhang", "length": mm, "area": mm², "angle": 水平からの角度, "floating": True か False,
      "z": 高さ, "x": X, "y": Y}, ...]
    を面積の大きい順に返す（位置はモデルの座標。0.001mm に丸める）。"""
    import numpy as np
    import trimesh
    R = trimesh.geometry.align_vectors(UP_DIRS.get(up, UP_DIRS["z"]), (0, 0, 1))
    m = mesh.copy()
    m.apply_transform(R)
    zmin = m.bounds[0][2]
    # trimesh の配列（TrackedArray）から一部を取り出すと、その配列は「変わった」扱いになり、次にキャッシュの値（m.triangles など）を
    # 読むときにメッシュ全体のハッシュを計算し直す。まとまりが多いと遅くなるので、普通の numpy 配列にしてから使う
    n, MF, MV, MT = (np.asarray(x) for x in (m.face_normals, m.faces, m.vertices, m.triangles))
    layer = 0.2                                                      # 1レイヤー：ベッドからこの高さまでの面は除き、辺はベッドが支える
    on_bed = np.all(MT[:, :, 2] < zmin + layer, axis=1)
    down = -n[:, 2] > np.cos(np.radians(max(deg - tol, 0.0)))   # オーバーハング面：水平から (deg − tol)° より浅い
    sel = np.nonzero(down & ~on_bed)[0]
    if not len(sel):
        return []
    insel = np.zeros(len(MF), dtype=bool)
    insel[sel] = True
    fa = np.asarray(m.face_adjacency)
    groups = trimesh.graph.connected_components(fa[insel[fa[:, 0]] & insel[fa[:, 1]]], nodes=sel, min_len=1)

    # まとまりの縁で、隣の面がまとまりの外にある辺。隣の面が縁から下へ続いていれば「支え」
    one = insel[fa[:, 0]] != insel[fa[:, 1]]
    f_out = np.where(insel[fa[one, 0]], fa[one, 1], fa[one, 0])
    ev = np.asarray(m.face_adjacency_edges)[one]
    a, b = MV[ev[:, 0]], MV[ev[:, 1]]
    t = (b - a) / np.maximum(np.linalg.norm(b - a, axis=1), 1e-12)[:, None]
    w = np.asarray(m.triangles_center)[f_out] - a
    d = w - (w * t).sum(axis=1)[:, None] * t                        # 隣の面の中で、縁から離れる向き
    below = d[:, 2] / np.maximum(np.linalg.norm(d, axis=1), 1e-12) < -0.1
    nv = len(MV)
    ekey = np.sort(ev, axis=1).astype(np.int64)
    ekey = ekey[:, 0] * nv + ekey[:, 1]
    eo = np.argsort(ekey, kind="stable")
    ekey, below = ekey[eo], below[eo]
    AF, TC = np.asarray(mesh.area_faces), np.asarray(mesh.triangles_center)

    out = []
    for g in groups:
        g = np.asarray(g, dtype=int)
        area = float(AF[g].sum())
        if area < min_area:
            continue
        c = (TC[g] * AF[g, None]).sum(axis=0) / area
        ang = float(np.degrees(np.arccos(np.clip(-n[g, 2].min(), -1, 1))))   # いちばん浅い所

        # まとまりの縁（まとまりの面の辺のうち、1つの面にしか出てこない辺）と、それぞれが支えか
        T = MT[g]
        fe = np.sort(MF[g][:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1).astype(np.int64)   # 面 i の辺は 3i〜3i+2 行
        fk = fe[:, 0] * nv + fe[:, 1]
        uk, inv, cnt = np.unique(fk, return_inverse=True, return_counts=True)
        bk = uk[cnt == 1]
        pos = np.minimum(np.searchsorted(ekey, bk), max(len(ekey) - 1, 0))
        anc = (ekey[pos] == bk) & below[pos] if len(ekey) else np.zeros(len(bk), dtype=bool)
        va, vb = MV[bk // nv], MV[bk % nv]
        anc |= (va[:, 2] < zmin + layer) & (vb[:, 2] < zmin + layer)
        a2, b2 = va[:, :2], vb[:, :2]

        # 長さを測る元の線分：支えの縁と、まとまりの中でベッドから1レイヤー以内の辺（寝かせた丸棒がベッドに接する線など）
        ik = uk[cnt > 1]
        ik = ik[(MV[ik // nv, 2] < zmin + layer) & (MV[ik % nv, 2] < zmin + layer)]
        sa = np.concatenate([a2[anc], MV[ik // nv, :2]])
        sb = np.concatenate([b2[anc], MV[ik % nv, :2]])
        floating = False
        if not len(sa):
            # 支えが無い：いちばん低い所の辺（下を向いた稜線や、平らな面の縁。平らな面の中の対角線は使わない）から測る。
            # ベッドから1レイヤーより上なら、空中から印刷が始まる（下につながる所が無い）
            floating = bool(T[:, :, 2].min() >= zmin + layer)
            zlo = float(T[:, :, 2].min()) + 0.05
            low = (MV[fe, 2] < zlo).all(axis=1)
            flat = np.repeat((T[:, :, 2] < zlo).all(axis=1), 3)
            lk = np.unique(fk[low & (~flat | (cnt[inv] == 1))])
            sa, sb = MV[lk // nv, :2], MV[lk % nv, :2]

        P, h = _sample_tris(T[:, :, :2])
        if len(sa):
            # 線分に置く点の間隔は h と別に決める（三角形が多いまとまりでは h が大きくなり、縁に点が数個しか載らない）。
            # 0.25mm 以下なら、いちばん遠い点を選ぶときのずれは 0.13mm 以下。縁がとても長いときは点を 20000 くらいまでにする
            sl = float(np.hypot(*(sb - sa).T).sum())
            A = _densify(sa, sb, max(min(h, 0.5) / 2, sl / 20000))[0]
        else:                                                        # 低い所の辺も無い（円錐の先を下に向けた所など）：いちばん低い頂点から
            V = MV[np.unique(MF[g])]
            A = V[V[:, 2] < V[:, 2].min() + 0.05][:, :2]
        dist = _nearest(A)(P)[0]
        p = P[int(np.argmax(dist))]                                  # 支えからいちばん遠い点
        kind, length = "overhang", float(dist.max())
        if len(sa):
            length = float(_closest_on_segs(p, sa, sb)[0].min())     # 線分までの正確な距離
        if anc.sum() >= 2 and length > 1e-6:
            # p から見た支えの向きが 150° 以上に広がる（向かい合う両側に支えがある）ときだけ、ブリッジにできるかを調べる
            th = np.sort(np.arctan2(A[:, 1] - p[1], A[:, 0] - p[0]))
            gap = np.diff(np.concatenate([th, th[:1] + 2 * np.pi])).max()
            if 2 * np.pi - gap >= np.radians(150):
                span = _bridge_span(a2, b2, anc, A)
                if span is not None:
                    kind, length = "bridge", span
        # 位置は丸めてから並べる・表示する（面の順や scipy の有無で末尾の桁が変わっても、順と表示の整数が変わらないように）
        out.append({"kind": kind, "length": length, "area": area, "angle": ang, "floating": floating,
                    "x": round(float(c[0]), 3), "y": round(float(c[1]), 3), "z": round(float(c[2]), 3)})
    return sorted(out, key=lambda r: (-round(r["area"], 1), r["z"], r["x"], r["y"]))


def overhang_notes(name, mesh, deg, up="z", lang="ja", bridge_max=None, min_len=None):
    """overhangs() の結果を注意の文にする。サポートが要りそうなもの（min_len 以上のオーバーハング、空中から印刷が始まるまとまり、
    bridge_max より長いブリッジ）で1行、サポートなしで印刷できそうなブリッジで1行。支えがあって min_len より短いもの
    （オーバーハングとブリッジ）は出さない（支えのすぐ脇なので、サポートなしで印刷できることが多い）。
    bridge_max を省くと 5mm（run_mock は fab の bridge_max を渡す）、min_len を省くと 1mm"""
    bm = BRIDGE_MAX if bridge_max is None else float(bridge_max)
    om = OVERHANG_MIN if min_len is None else float(min_len)
    regs = overhangs(mesh, deg, up)

    def needs(r):                                                    # 表示する長さで比べる
        if r["kind"] == "bridge":
            return round(r["length"], 1) > bm
        return r.get("floating", False) or round(r["length"], 1) >= om

    need = [r for r in regs if needs(r)]
    ok = [r for r in regs if r["kind"] == "bridge" and not needs(r) and round(r["length"], 1) >= om]

    def mm(v):
        return f"{round(v, 1):g}"

    def more(items, sep, n_more):
        return sep.join(items[:3]) + (n_more.format(n=len(items) - 3) if len(items) > 3 else "")

    notes = []
    if lang == "en":
        ori = f" (print orientation {up})" if up != "z" else ""
        if need:
            flat = min(r["angle"] for r in need)
            where = more([f"height {round(r['z'])}mm (near X{round(r['x']):+d}, Y{round(r['y']):+d}) "
                          + (f"bridge {mm(r['length'])}mm (longer than {bm:g}mm)" if r["kind"] == "bridge"
                             else "printing starts in mid-air (not connected to anything below)" if r.get("floating")
                             else f"unsupported length {mm(r['length'])}mm")
                          + f", about {r['area']:.0f}mm²" for r in need], "; ", "; {n} more")
            notes.append(f"{name}: downward faces{ori} likely need support: {where} "
                         f"({flat:.0f}° from horizontal; shallower than the {deg:g}° overhang limit)")
        if ok:
            where = more([f"{mm(r['length'])}mm (height {round(r['z'])}mm, "
                          f"near X{round(r['x']):+d}, Y{round(r['y']):+d})" for r in ok], ", ", ", {n} more")
            notes.append(f"{name}: {'bridges' if len(ok) > 1 else 'bridge'}{ori} {where}. Both ends are supported; "
                         f"bridges up to about {bm:g}mm usually print without support")
        return notes
    ori = f"（印刷の向き {up}）" if up != "z" else ""
    if need:
        flat = min(r["angle"] for r in need)
        where = more([f"高さ{round(r['z'])}mm（X{round(r['x']):+d}・Y{round(r['y']):+d}付近）"
                      + (f"ブリッジ {mm(r['length'])}mm（目安 {bm:g}mm より長い）" if r["kind"] == "bridge"
                         else "空中から印刷が始まる（下につながる所が無い）" if r.get("floating")
                         else f"支えのない長さ {mm(r['length'])}mm")
                      + f"・約{r['area']:.0f}mm²" for r in need], "、", " ほか{n}か所")
        notes.append(f"{name}のオーバーハング面{ori}にサポートが要りそう：{where}"
                     f"（水平から{flat:.0f}°。オーバーハング{deg:g}°より浅い）")
    if ok:
        where = more([f"{mm(r['length'])}mm（高さ{round(r['z'])}mm・X{round(r['x']):+d}・Y{round(r['y']):+d}付近）"
                      for r in ok], "、", " ほか{n}か所")
        notes.append(f"{name}のブリッジ{ori}：{where}。両端が支えられている。"
                     f"目安 {bm:g}mm 以下ならサポートなしで印刷できることが多い")
    return notes


def run_mock(build):
    """mock.py の build() を受け取り、部品ごとの STL と STEP をエクスポートし、scene.json を書く。
    build(prm) は (部品のリスト, 注意のリスト) を返す。部品は (表示名, 形, 色, 不透明度, 英字のキー) か、
    6つめにオプションの dict を付けたもの：{"print": False}（3Dプリントしない部品：中身・既製品・レーザーの板など。
    オーバーハングを調べない）、{"up": "-z"}（印刷の向き。z・-z・x・-x・y・-y。既定は z＝モデルの上がそのまま上）。
    印刷の向きはパラメータファイルの meta に "print_up": {"キー": "-z"} と書いてもよい（こちらが優先）。
    パラメータファイルの meta.process が laser でなければ、3Dプリントする部品のサポートが要りそうな面とブリッジを調べて注意に足す
    （しきい値は fab の overhang_deg、無ければ 45°。ブリッジの長さの目安は fab の bridge_max、無ければ 5mm。
    目安より長いブリッジはサポートが要りそうな方に入る。支えから 1mm 未満の短いオーバーハング・ブリッジは出さない。
    空中から印刷が始まる所は、長さによらずサポートが要りそうな方に入る）。
    表示の言語は prm.lang（パラメータファイルの meta.lang。--lang ja|en で上書きできる）。scene.json の "lang" にも書く。"""
    for _s in (sys.stdout, sys.stderr):        # Windows のパイプは ANSI コードページになるので UTF-8 にそろえる
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    import geom
    ver = version_from_argv()
    want_step = "--no-step" not in sys.argv
    prm = load(ver, lang=lang_from_argv())
    msg = MSG[prm.lang]
    parts, notes = build(prm)
    parts = [tuple(p) + ({},) if len(p) == 5 else tuple(p) for p in parts]

    pdir = out_dir(ver, "parts")
    scene = {"title": f"{prm.meta.get('title', '')} {ver}", "lang": prm.lang, "up": "z", "views": ["iso", "back", "side"],
             "parts": []}
    for i, (name, solid, color, opacity, key, _opt) in enumerate(parts):
        fn = f"{i + 1:02d}_{key}.stl"
        geom.export_stl(solid, os.path.join(pdir, fn))
        scene["parts"].append({"file": f"parts/{fn}", "name": name, "key": key, "color": color, "opacity": opacity,
                               "roughness": 0.3 if opacity < 1 else 0.8})

    # 3Dプリントのオーバーハング（サポートが要りそうな面）とブリッジ
    if prm.meta.get("process") != "laser":
        deg = float(getattr(prm.P, "overhang_deg", 45))
        bm = float(getattr(prm.P, "bridge_max", BRIDGE_MAX))
        ups = prm.meta.get("print_up", {})
        for name, solid, _c, _o, key, opt in parts:
            if opt.get("print", True):
                notes += overhang_notes(name, geom.to_trimesh(solid), deg, ups.get(key, opt.get("up", "z")),
                                        lang=prm.lang, bridge_max=bm)

    scene["notes"] = notes
    sp = os.path.join(out_dir(ver), "scene.json")
    with open(sp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(scene, f, ensure_ascii=False, indent=1)
    print(sp)

    if want_step and geom.has_cad():
        sdir = out_dir(ver, "step")
        index = []
        asm = os.path.join(sdir, f"assembly_{ver}.step")
        geom.export_assembly([(k, s, c, o) for _n, s, c, o, k, _opt in parts], asm)
        # src は確認ページが読むので、どの OS でも "/" で書く
        index.append({"src": os.path.relpath(asm, ROOT).replace(os.sep, "/"), "name": msg["assembly"],
                      "file": f"assembly_{ver}.step"})
        bad = []
        for i, (name, solid, _c, _o, key, _opt) in enumerate(parts):
            fp = os.path.join(sdir, f"{i + 1:02d}_{key}.step")
            geom.export_step(solid, fp)
            ok, se, me = geom.check_step(solid, fp)
            if not ok:
                bad.append(msg["step_bad"].format(name=name, se=se, me=me))
            index.append({"src": os.path.relpath(fp, ROOT).replace(os.sep, "/"), "name": name,
                          "file": os.path.basename(fp)})
        with open(os.path.join(sdir, "index.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(index, f, ensure_ascii=False, indent=1)
        print(msg["step_count"].format(sdir=sdir, n=len(index)))
        print(msg["step_check"], msg["step_ok"] if not bad else msg["step_ng"] + " / ".join(bad))
    elif want_step:
        # Windows の ARM64 版 Python には CadQuery のパッケージが無い。見るのは実行中の Python のビルド
        # （platform.machine() は CPU を返すので、ARM64 の PC の x64 版 Python でも "ARM64" になる）
        arm = os.name == "nt" and sysconfig.get_platform() == "win-arm64"
        print(msg["step_skip_arm" if arm else "step_skip"])

    for n in notes:
        if isinstance(n, dict):
            print(msg["question"], n.get("q", ""), msg["qtype"].format(t=n.get("type", "")))
        else:
            print(msg["note"], n)
