"""プロジェクトのいまの状態を30行ほどで出す。新しい会話の始めに、これだけ読めば続きから始められるように。

使い方
  python status.py <プロジェクト>

出すもの
  バージョン履歴（どの版から作ったか・続けなかった案）、最新の版の要点、確認ページの場所、
  未対応のフィードバック（PC のページ。アーティファクトとして公開したページは references/publish-artifact.md の手順で読む）、
  最新の版の問いと答え・決定、答えはあるが決まっていない前の版の問い
  （答え・決定は PC のページの分。review/artifact.json があるときは、公開したページの答え・決定は読めないことを1回だけ書き添える）、
  仮の寸法・根拠の無い寸法・テストピースで測る値（初期値）、LOG.md の最新の版の節の「次に試す」、決定事項の数と最後の行。
読むファイル（どれも無くてよい）: params/params_v*.json、review/board.json、review/feedback_local.json、
  review/artifact.json、review/.serve.json、LOG.md、docs/決定事項.md（英語のプロジェクトは docs/decisions.md）
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from oscompat import serving  # noqa: E402

VER_RE = r"v\d+[a-z]*"
# 仮の寸法の見分け方。label と basis の両方に当てる。new-project の shelf.py の PROVISIONAL と同じ文にしておく（直すときは両方）
PROVISIONAL = re.compile(r"^\s*仮|(?<=[\s（(、。・,;:])仮(?=[）)。、,;:\s・]|$)|provisional|tentative|placeholder|要確認|要実測|to be (confirmed|measured)", re.I)
INITIAL = ("初期値", "initial")


def ver_key(v):
    m = re.fullmatch(r"v(\d+)([a-z]*)", v or "")
    return (int(m.group(1)), m.group(2)) if m else (0, v or "")


BAD = []   # あるのに読めなかった JSON ファイル（パス, 理由）。main で知らせる


def load(p, default=None):
    """JSON を読む。無いときは default。あるのに読めない（JSON の書き方・UTF-16 など）ときも default にして BAD に足す。
    utf-8-sig: PowerShell 5.1・メモ帳が付ける BOM も読む"""
    try:
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as e:            # ValueError: JSON の誤り・UTF-8 でないバイト
        if all(p != q for q, _ in BAD):
            BAD.append((p, e))
        return default


def read_text(p):
    with open(p, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def params_versions(root):
    vs = []
    for p in glob.glob(os.path.join(glob.escape(root), "params", "params_v*.json")):
        m = re.fullmatch(r"params_(" + VER_RE + r")\.json", os.path.basename(p))
        if m:
            vs.append(m.group(1))
    return sorted(vs, key=ver_key)


def parent_of(root, ver, order):
    """パラメータファイルの meta.parent、無ければ番号が1つ前の版（同じ番号の案どうしはつながない）"""
    meta = (load(os.path.join(root, "params", f"params_{ver}.json"), {}) or {}).get("meta", {})
    if meta.get("parent"):
        return meta["parent"]
    n = ver_key(ver)[0]
    older = [v for v in order if ver_key(v)[0] < n]
    return older[-1] if older else None


def short(s, n=80):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n - 1] + "…"


def flow(order, prev, latest):
    """v01 → v02 → v03a（v02 から・続けず）・v03b（v02 から）→ v04（v03b から）"""
    children = {p for p in prev.values() if p}
    out = []
    for i, v in enumerate(order):
        p = prev.get(v)
        tags = []
        if p and (i == 0 or order[i - 1] != p):
            tags.append(f"{p} から")
        if v != latest and v not in children and i < len(order) - 1:
            tags.append("続けず")
        s = v + (f"（{'・'.join(tags)}）" if tags else "")
        if i == 0:
            out.append(s)
        else:
            sep = "・" if ver_key(v)[0] == ver_key(order[i - 1])[0] else " → "
            out.append(sep + s)
    return "".join(out)


def q_label(q):
    if isinstance(q, str):
        return "文字", q
    t = q.get("type") or ("options" if q.get("options") else "text")
    # board.json の案から選ぶ問いは "choice"（build_page.py が manifest の options から作る）
    return {"yesno": "はい/いいえ", "options": "選ぶ", "choice": "選ぶ"}.get(t, "文字"), q.get("q", "")


def main():
    for _s in (sys.stdout, sys.stderr):        # Windows のパイプは ANSI コードページになるので UTF-8 にそろえる
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    root = os.path.abspath(os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "."))   # PowerShell は ~ をそのまま渡す
    rv = os.path.join(root, "review")
    board = load(os.path.join(rv, "board.json"), {}) or {}
    sp = os.path.join(rv, "feedback_local.json")
    store = load(sp, {})
    # 読めても形が違う（[] や "feedback" が {} でない）ときも、読めないファイルとして知らせる（serve_review.py の load_store と同じ）
    if not isinstance(store, dict):
        BAD.append((sp, "not a JSON object"))
        store = {}
    for k in ("feedback", "answers", "decisions"):
        if not isinstance(store.get(k, {}), dict):
            BAD.append((sp, f'"{k}" is not a JSON object'))
            store[k] = {}
    bvers = {v["version"]: v for v in board.get("versions", [])}
    pvers = params_versions(root)
    order = sorted(set(bvers) | set(pvers), key=ver_key)
    if not order:
        raise SystemExit(f"版が見つかりません: {root}（params/params_vNN.json か review/board.json）")
    prev = {v: (bvers[v].get("prev") if v in bvers and "prev" in bvers[v] else parent_of(root, v, order)) for v in order}
    built = sorted(bvers, key=ver_key)
    latest = built[-1] if built else order[-1]
    lp = pvers[-1] if pvers else None
    params = (load(os.path.join(root, "params", f"params_{lp}.json"), {}) or {}) if lp else {}
    meta = params.get("meta", {})
    lang = meta.get("lang", board.get("lang", "ja"))
    L = []

    title = board.get("project") or meta.get("title") or os.path.basename(root)
    L.append(f"{title}（{lang}・{meta.get('process', '?')}） {root}")
    L.append("版: " + flow(order, prev, latest))
    if latest in bvers:
        b = bvers[latest]
        L.append(f"最新の版: {latest}（{b.get('stage', '')}・{b.get('date', '')}）{short(b.get('summary'), 100)}")
    extra = [v for v in pvers if v not in bvers]
    if extra:
        L.append("パラメータファイルだけあって、まだページに載せていない版: " + "・".join(extra))

    # 確認ページ
    art_p = os.path.join(rv, "artifact.json")
    has_art = os.path.exists(art_p)               # アーティファクトとしても公開してある（答え・決定の一部はそちらにある）
    art = load(art_p, {})                         # 「or {}」を付けない：[] ・ "" ・ null も下で読めないファイルとして知らせる
    srv = load(os.path.join(rv, ".serve.json"), {})
    for p, x in ((art_p, art), (os.path.join(rv, ".serve.json"), srv)):
        if not isinstance(x, dict):                # 読めても形が違う（[] など）
            BAD.append((p, "not a JSON object"))
    art, srv = (x if isinstance(x, dict) else {} for x in (art, srv))
    page = []
    if art.get("url"):
        page.append(f"公開 {art['url']}（アーティファクト。フィードバックは references/publish-artifact.md の手順で読む）")
    if srv.get("url"):
        up = serving(srv, rv)                     # True・False・None（PID は動いているが応答しない）
        page.append(f"PC {srv['url']}（" + ("動いている" if up else "止まっている。serve_review.py で動かす" if up is False else
                    f"PID {srv.get('pid')} は動いているが応答しない。serve_review.py で新しく立てられる") + "）")
    if page:
        L.append("確認ページ: " + "／".join(page))

    # 未対応のフィードバック（PC のページ）
    fb = store.get("feedback", {})
    opened = sorted(((k, f) for k, f in fb.items() if (f.get("status") or "open") == "open"),
                    key=lambda kf: kf[1].get("createdAt", ""))
    if fb or os.path.exists(os.path.join(rv, "feedback_local.json")):
        L.append(f"未対応のフィードバック（PC）: {len(opened)}件")
        for k, f in opened[:10]:
            L.append(f"  [{k}] {f.get('version', '')} {f.get('target', '')} {f.get('kind', '')}: {short(f.get('text'), 100)}")
        if len(opened) > 10:
            L.append(f"  ほか {len(opened) - 10}件（review/feedback_local.json）")

    # 問い：最新の版の全部と、答えはあるのに決まっていない前の版の問い
    answers, decisions = store.get("answers", {}), store.get("decisions", {})
    # 公開したページの答え・決定は feedback_local.json に無い。「答え: なし」「決定: まだ」が公開したページでもそうだと読まれないよう、最初の見出しに1回だけ書く
    art_note = ["公開したページの答え・決定はこのスクリプトでは読めない。references/publish-artifact.md の手順で読む"] if has_art else []

    def head(title, sub=""):
        parts = ([sub] if sub else []) + ([f"ここから下の答え・決定は PC のページの分。{art_note.pop()}"] if art_note else [])
        return title + (f"（{'。'.join(parts)}）" if parts else "") + ":"

    def q_line(v, i, q):
        kind, text = q_label(q)
        cnt = {}
        for k, a in answers.items():
            if k.startswith(f"{v}~q{i}~"):
                cnt[a.get("label") or a.get("choice")] = cnt.get(a.get("label") or a.get("choice"), 0) + 1
        d = decisions.get(f"{v}~q{i}")
        s = f"  {v}~q{i} {kind}: {short(text, 70)}"
        if kind != "文字":
            s += "  答え: " + ("、".join(f"{lab} {n}" for lab, n in cnt.items()) if cnt else "なし")
            s += f"  決定: {d.get('choice') if isinstance(d, dict) else d}" if d else "  決定: まだ"
        return s, bool(cnt), bool(d), kind

    lines = [q_line(latest, i, q) for i, q in enumerate(bvers.get(latest, {}).get("questions", []))]
    if lines:
        L.append(head(f"{latest} の問い"))
        L += [s for s, *_ in lines]
    pend, undecided = [], []
    for v in built[:-1]:
        for i, q in enumerate(bvers[v].get("questions", [])):
            s, has_a, has_d, kind = q_line(v, i, q)
            if has_a and not has_d and kind != "文字":
                pend.append(s)
            if not has_d and kind != "文字":
                undecided.append(f"{v}~q{i}")
    if pend:
        L.append(head("答えはあるが決定していない問い", "前の版"))
        L += pend[:6] + ([f"  ほか {len(pend) - 6}件"] if len(pend) > 6 else [])
    elif has_art and undecided:                   # 見出しを出さなかったときも、答え・決定が公開したページにだけあるかもしれない
        ids = "、".join(undecided[:8]) + (f" ほか{len(undecided) - 8}" if len(undecided) > 8 else "")
        L.append(f"PC のページで決定が無い問い（はい/いいえ・選ぶ。前の版）: {len(undecided)}件（{ids}）"
                 + (f"。{art_note.pop()}" if art_note else ""))

    # パラメータファイル：仮・根拠なし・テストピースで測る値
    if params:
        tent, nob, init = [], [], []
        for sec in ("params", "fab"):
            for k, it in (params.get(sec) or {}).items():
                if not isinstance(it, dict):
                    continue
                basis = it.get("basis", "")
                if not basis:
                    nob.append(k)
                if PROVISIONAL.search(str(it.get("label", ""))) or PROVISIONAL.search(str(basis)):   # 根拠なしとは別に調べる
                    tent.append(f"{k} {it.get('value')}{it.get('unit', '')}")
                if sec == "fab" and it.get("status") in INITIAL:
                    init.append(k)
        L.append(f"パラメータファイル {lp}: 仮 {len(tent)}・根拠なし {len(nob)}・テストピースで測る値 {len(init)}")
        cap = lambda xs: "、".join(xs[:12]) + (f" ほか{len(xs) - 12}" if len(xs) > 12 else "")
        if tent:
            L.append("  仮: " + cap(tent))
        if nob:
            L.append("  根拠なし: " + cap(nob))
        if init:
            L.append("  テストピースで測る値（初期値）: " + cap(init))

    # LOG.md の最後の版の節と、決定事項
    log = os.path.join(root, "LOG.md")
    if os.path.exists(log):
        secs = [s for s in re.split(r"(?m)^(?=## )", read_text(log)) if s.startswith("## ")]
        # 最新の版（ページに載せた最後の版）の名前が見出しにある節。無ければ最後の節
        named = [s for s in secs if re.search(rf"(?<![0-9A-Za-z]){re.escape(latest)}(?![0-9A-Za-z])", s.splitlines()[0])]
        last = (named or secs or [""])[-1].strip().splitlines()
        if last:
            L.append(f"LOG の最後: {last[0].lstrip('# ').strip()}")
            L += ["  " + short(x, 140) for x in last[1:] if re.match(r"-\s*(次|Next)", x.strip())]
    for name in ("決定事項.md", "decisions.md"):
        p = os.path.join(root, "docs", name)
        if os.path.exists(p):
            rows = [r for r in read_text(p).splitlines()
                    if r.startswith("|") and not re.match(r"\|\s*-", r)][1:]
            if rows:
                cells = [c.strip() for c in rows[-1].strip("|").split("|")]
                L.append(f"決定事項（docs/{name}）: {len(rows)}件。最後: {short(' ／ '.join(c for c in cells[1:3] if c), 80)}")
            break

    nxt = f"v{ver_key(latest)[0] + 1:02d}"
    L.append(f"次の版を作るとき: params/params_{nxt}.json（meta.parent: \"{latest}\"）→ make_version.py <プロジェクト> {nxt}")
    L += [f"!! 読めないファイル（JSON の書き方か文字コード（UTF-8）を直す）: {os.path.relpath(p, root) if p.startswith(root) else p}（{e}）"
          for p, e in BAD]
    print("\n".join(L))


if __name__ == "__main__":
    main()
