"""確認ページを PC で開く（Claude Code・Codex など、どの AI からでも使うふつうの方法）。
プロジェクトの review/ を localhost の空いているポートで配信し、ブラウザで開く。
three.js や 3D モデルの読み込みは file:// では動かないので、ローカルのサーバーで配信する。

使い方
  python serve_review.py <プロジェクト>              … 配信してブラウザを開く。サーバーは別のセッションで動き続け、
                                                      URL を出したらすぐ戻る（AI のバックグラウンド実行の時間の上限で止まらない）
  python serve_review.py <プロジェクト> --no-open    … ブラウザを開かない
  python serve_review.py <プロジェクト> --stop       … 動いているサーバーを止める
  python serve_review.py <プロジェクト> --foreground … このプロセスで配信する（止めるまで戻らない）
すでに同じプロジェクトのサーバーが動いていれば（.serve.json の URL が答えれば）、新しく立てずにそのページを開く。
サーバーの出力は review/.serve.log に残る。

ページに書いたフィードバック・問いの答えは review/feedback_local.json に保存される（Artifact の db と同じ形）：
  {"feedback": {"<id>": {...}}, "answers": {"<版>~q<番号>~local": {...}}, "decisions": {"<版>~q<番号>": {...}}}
AI は「フィードバックを読んで」と頼まれたらこのファイルを読み、返信（status・resolvedIn・reply）と
決定（decisions）を同じファイルに書く。ページを開き直す（タブに戻る）と見える。
サーバーの場所は review/.serve.json に書く（--stop が使う）。
表示の言語：--lang ja|en ＞ review/board.json の "lang" ＞ 環境変数 MONOZUKURI_LANG ＞ ja。
ページの文言は board.html が board.json の "lang" で選ぶ。

English
  Opens the review page on this PC (the usual path from any AI agent, e.g. Claude Code or Codex).
  Serves <project>/review/ on a free localhost port and opens the browser. The server runs in its own
  session and the command returns once the URL is printed (--foreground keeps it in this process).
    serve_review.py <project> [--no-open] [--stop] [--foreground] [--lang ja|en]
  Feedback and answers written on the page are saved to review/feedback_local.json (same shape as the
  Artifact db). Message language: --lang > review/board.json "lang" > env MONOZUKURI_LANG > ja.
"""
import argparse
import datetime
import http.server
import json
import os
import secrets
import signal
import socketserver
import subprocess
import webbrowser
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from oscompat import alive, cmdline, dir_id, path_id, popen_detached, replace_retry, serving  # noqa: E402

STORE = "feedback_local.json"
STATE = ".serve.json"
LOG = ".serve.log"
WRITABLE = {"feedback", "answers"}       # ページから書けるのはこの2つ。decisions は AI がファイルに書く
MAX_BODY = 64 * 1024
lock = threading.Lock()

# 表示する文言（ja／en）
MSG = {
    "ja": {
        "open_manually": "ブラウザで開いてください: {url}",
        "stopped": "止めました（{url}）",
        "not_running": "動いているサーバーはありません",
        "no_index": "{rv}/index.html がありません。先に build_page.py で確認ページを作ってください",
        "running": "すでに動いています: {url}（止めるとき: {stop}）",
        "page": "確認ページ: {url}",
        "store": "フィードバックの保存先: {path}",
        "stop_hint": "止めるとき: {stop}",
        "port_help": "ポート（既定：空いているもの）",
        "fg_help": "このプロセスで配信する（止めるまで戻らない）",
        "start_failed": "サーバーを立てられませんでした（{log}）",
        "stop_failed": "止められませんでした（PID {pid}: {err}）",
        "store_bad": "{path} が読めません（{err}）。JSON の書き方と文字コード（UTF-8）を直すまで、ページからは読み書きしません",
        "no_answer": "PID {pid} は動いていますが、{url} が応答しません。止めずに review/.serve.json を残しました"
                     "（少し待ってもう一度 --stop。それでも応答しなければ、{kill}）",
        "old_no_answer": "前のサーバー（PID {pid}・{url}）は動いていますが、応答しないので新しく立てます。"
                         "前のサーバーは止めていません（{kill}）",
        "kill_posix": "kill {pid} で止める",
        "kill_nt": "タスクマネージャーで PID {pid} を終了する",
    },
    "en": {
        "open_manually": "Open this in a browser: {url}",
        "stopped": "Stopped ({url})",
        "not_running": "No server is running",
        "no_index": "{rv}/index.html not found. Build the review page with build_page.py first",
        "running": "Already running: {url} (to stop: {stop})",
        "page": "Review page: {url}",
        "store": "Feedback is saved to: {path}",
        "stop_hint": "To stop: {stop}",
        "port_help": "port (default: any free port)",
        "fg_help": "serve from this process (does not return until stopped)",
        "start_failed": "Could not start the server ({log})",
        "stop_failed": "Could not stop the server (PID {pid}: {err})",
        "store_bad": "Cannot read {path} ({err}). The page will not read or write feedback until the JSON and its "
                     "encoding (UTF-8) are fixed",
        "no_answer": "PID {pid} is running but {url} does not respond. Left it running and kept review/.serve.json "
                     "(wait a little and run --stop again; if it still does not respond, {kill})",
        "old_no_answer": "The previous server (PID {pid}, {url}) is running but does not respond, so a new one is started. "
                         "The previous one was not stopped ({kill})",
        "kill_posix": "stop it with kill {pid}",
        "kill_nt": "end PID {pid} in Task Manager",
    },
}


def resolve_lang(explicit=None, data=None):
    for v in (explicit, data, os.environ.get("MONOZUKURI_LANG")):
        if v in ("ja", "en"):
            return v
    return "ja"


def board_lang(rv):
    """review/board.json の lang（無ければ None）"""
    try:
        with open(os.path.join(rv, "board.json"), encoding="utf-8-sig") as f:
            return json.load(f).get("lang")
    except (OSError, ValueError, AttributeError):
        return None


def load_store(path):
    """feedback_local.json を読む。無ければ空。あるのに読めない（JSON の書き方・UTF-16 など）ときは ValueError。
    空として扱うと次の保存で上書きして、それまでのフィードバックが消えるので、そうはしない。
    utf-8-sig: PowerShell 5.1・メモ帳が付ける BOM も読む"""
    try:
        with open(path, encoding="utf-8-sig") as f:
            d = json.load(f)
    except FileNotFoundError:
        d = {}
    if not isinstance(d, dict):
        raise ValueError("not a JSON object")
    for k in ("feedback", "answers", "decisions"):
        if not isinstance(d.setdefault(k, {}), dict):
            raise ValueError(f'"{k}" is not a JSON object')
    return d


def save_store(path, d):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    replace_retry(tmp, path)


def read_state(rv):
    """review/.serve.json（無い・読めないときは {}）"""
    try:
        with open(os.path.join(rv, STATE), encoding="utf-8-sig") as f:
            st = json.load(f)
    except (OSError, ValueError):
        return {}
    return st if isinstance(st, dict) else {}


def remove_state(rv, token=None):
    """review/.serve.json を消す。token を渡したら、そのサーバーの .serve.json のときだけ"""
    if token is not None and read_state(rv).get("token") != token:
        return
    try:
        os.remove(os.path.join(rv, STATE))
    except OSError:                                # 無い・ほかのプロセスが開いている（Windows）。次に立てるとき書き直す
        pass


# 配信するファイルの種類（Content-Type）を決めておく。Windows ではレジストリの設定が Python の既定より優先され、
# .js が text/plain・.csv が Excel の種類になる PC がある
TYPES = {
    ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".mjs": "text/javascript",
    ".json": "application/json", ".wasm": "application/wasm",
    ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".stl": "model/stl",
    ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".pdf": "application/pdf", ".md": "text/markdown", ".txt": "text/plain", ".csv": "text/csv",
}
# ページからは見せないファイル（小文字でそろえて比べる。Windows・macOS のファイルシステムは大文字小文字を区別しない）
HIDDEN = {x.lower() for x in (STORE, STATE, LOG, STORE + ".tmp")}


def open_browser(url, lang="ja"):
    # Windows・macOS・Linux で共通に既定のブラウザを開く
    try:
        opened = webbrowser.open(url)
    except Exception:
        opened = False
    if not opened:
        print(MSG[lang]["open_manually"].format(url=url))


def make_handler(rv, token, m):
    store_path = os.path.join(rv, STORE)
    rv_id, rv_pid = dir_id(rv), path_id(rv)

    class H(http.server.SimpleHTTPRequestHandler):
        extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **TYPES}

        def __init__(self, *a, **k):
            super().__init__(*a, directory=rv, **k)

        def log_message(self, *a):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")     # 作り直したページ・AI の返信がすぐ見えるように
            super().end_headers()

        def guess_type(self, path):
            # 文字のファイル（資料の .md・.txt・.csv など）は UTF-8 と伝える。伝えないとブラウザが別の文字コードで読み、文字化けする
            t = super().guess_type(path)
            return t + "; charset=utf-8" if t.startswith("text/") and "charset" not in t else t

        def send_json(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def hidden(self):
            # 名前はデコードしてそろえて比べる（%2e・末尾の「.」・Windows の「::$DATA」でも同じファイルになる）
            n = os.path.basename(self.translate_path(self.path)).split(":")[0].rstrip(". ")
            return n.lower() in HIDDEN

        def store_error(self, e):
            print(m["store_bad"].format(path=store_path, err=e), file=sys.stderr, flush=True)
            return self.send_json(500, {"error": "store_unreadable", "detail": str(e)})

        def do_GET(self):
            if self.path.split("?")[0] == "/feedback":
                with lock:
                    try:
                        d = load_store(store_path)
                    except (OSError, ValueError) as e:
                        return self.store_error(e)
                    return self.send_json(200, d)
            if self.path.split("?")[0] == "/stamp":
                # ページが数秒ごとに見るスタンプ。ページ（新しい版）とフィードバックのファイルが変わったかだけを返す。
                # token と dir・dirp は、このプロジェクトのこのサーバーかどうかを serve_review.py・status.py が確かめるため
                mt = lambda f: os.stat(os.path.join(rv, f)).st_mtime_ns if os.path.exists(os.path.join(rv, f)) else 0
                return self.send_json(200, {"board": mt("index.html"), "store": mt(STORE), "token": token,
                                            "dir": rv_id, "dirp": rv_pid})
            if self.hidden():
                return self.send_json(404, {"error": "not_found"})
            return super().do_GET()

        def do_HEAD(self):
            if self.hidden():
                self.send_response(404)
                self.send_header("Content-Length", "0")
                return self.end_headers()
            return super().do_HEAD()

        def do_POST(self):
            if self.path.split("?")[0] != "/feedback":
                return self.send_json(404, {"error": "not_found"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = 0
            if n <= 0 or n > MAX_BODY:
                return self.send_json(413, {"error": "too_large"})
            try:
                req = json.loads(self.rfile.read(n))
            except ValueError:                       # JSON の誤り・UTF-8 でないバイト
                return self.send_json(400, {"error": "bad_json"})
            if not isinstance(req, dict):
                return self.send_json(400, {"error": "bad_json"})
            col = req.get("collection")
            if col not in WRITABLE:
                return self.send_json(403, {"error": "not_writable"})
            with lock:
                try:
                    d = load_store(store_path)
                except (OSError, ValueError) as e:
                    return self.store_error(e)       # 読めないファイルは上書きしない
                if req.get("delete"):
                    d[col].pop(str(req.get("id")), None)
                else:
                    doc = req.get("doc")
                    if not isinstance(doc, dict):
                        return self.send_json(400, {"error": "bad_doc"})
                    did = str(req.get("id") or datetime.datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3))
                    d[col][did] = doc
                try:
                    save_store(store_path, d)
                except OSError as e:
                    print(f"{store_path}: {e}", file=sys.stderr, flush=True)
                    return self.send_json(500, {"error": "store_not_saved", "detail": str(e)})
                return self.send_json(200, d)

    return H


class Server(socketserver.ThreadingTCPServer):
    # Windows の SO_REUSEADDR は、ほかのサーバーが使っているポートにも重ねて bind できてしまうので POSIX だけ
    allow_reuse_address = os.name != "nt"


def main():
    for _s in (sys.stdout, sys.stderr):        # Windows のパイプは ANSI コードページになるので UTF-8 にそろえる
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--port", type=int, default=0, help=MSG[resolve_lang()]["port_help"])
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--lang", choices=["ja", "en"])
    ap.add_argument("--foreground", action="store_true", help=MSG[resolve_lang()]["fg_help"])
    ap.add_argument("--token", help=argparse.SUPPRESS)   # 立てたサーバーを見分ける token（serve_review.py が子に渡す）
    a = ap.parse_args()
    project = os.path.abspath(os.path.expanduser(a.project))   # PowerShell は ~ をそのまま渡す
    rv = os.path.join(project, "review")
    lang = resolve_lang(a.lang, board_lang(rv))
    m = MSG[lang]
    st = read_state(rv)
    stop = cmdline([sys.executable, os.path.abspath(__file__), project, "--stop"])
    up = serving(st, rv)                           # True・False・None（PID は動いているが応答しない）
    kill = lambda: m["kill_nt" if os.name == "nt" else "kill_posix"].format(pid=st.get("pid"))

    if a.stop:
        # 止めるのは、.serve.json の URL がこのプロジェクトのサーバーとして答えるときだけ
        # （PID が使い回されたほかのプロセス・コピー元のプロジェクトのサーバーは止めない）
        if up is None:
            # 動いているかもしれないサーバーの .serve.json は消さない（消すと、それを指すものが無くなる）
            sys.exit(m["no_answer"].format(pid=st.get("pid"), url=st.get("url"), kill=kill()))
        if up:
            pid = int(st["pid"])
            try:
                os.kill(pid, signal.SIGTERM)       # Windows では TerminateProcess（サーバーの finally は動かない）
            except OSError as e:
                sys.exit(m["stop_failed"].format(pid=pid, err=e))
            for _ in range(30):                    # 止まるまで3秒まで待つ（Windows はそれまでポートとログのファイルを放さない）
                if not alive(pid):
                    break
                time.sleep(0.1)
            print(m["stopped"].format(url=st.get("url")))
        else:
            print(m["not_running"])
        remove_state(rv)
        return
    if not os.path.isfile(os.path.join(rv, "index.html")):
        sys.exit(m["no_index"].format(rv=rv))
    if up:
        print(m["running"].format(url=st["url"], stop=stop))
        if not a.no_open:
            open_browser(st["url"], lang)
        return
    if up is None:
        print(m["old_no_answer"].format(pid=st.get("pid"), url=st.get("url"), kill=kill()), flush=True)

    if not a.foreground:
        # 別のセッションでサーバーを立て、URL が書かれたら戻る。呼んだ側（AI のバックグラウンド実行など）が
        # 時間の上限で止められても、サーバーは止まらない。止めるのは --stop
        remove_state(rv)                           # 止まったサーバーの .serve.json は消す
        token = secrets.token_hex(8)
        log = os.path.join(rv, LOG)
        cmd = [sys.executable, os.path.abspath(__file__), project, "--foreground", "--port", str(a.port), "--token", token]
        cmd += ["--no-open"] if a.no_open else []
        cmd += ["--lang", a.lang] if a.lang else []
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        with open(log, "wb") as lf:
            # cwd: 呼んだ側のフォルダーを使い続けない（Windows では使っているフォルダーを消せない・名前を変えられない）
            p = popen_detached(cmd, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT, cwd=rv, env=env)
        # 子が .serve.json に同じ token を書いたら立った。PID では比べない（Windows の venv の python.exe は
        # 本当の python.exe を別のプロセスとして立てるので、p.pid とサーバーの PID が違う）
        st = {}
        for _ in range(150):                       # 15秒まで待つ
            time.sleep(0.1)
            st = read_state(rv)
            if st.get("token") == token or p.poll() is not None:
                break
        if st.get("token") != token:
            sys.exit(m["start_failed"].format(log=log))
        print(m["page"].format(url=st["url"]))
        print(m["store"].format(path=os.path.join(rv, STORE)))
        print(m["stop_hint"].format(stop=stop))
        return

    token = a.token or secrets.token_hex(8)
    httpd = Server(("127.0.0.1", a.port), make_handler(rv, token, m))
    url = f"http://127.0.0.1:{httpd.server_address[1]}/index.html"
    print(m["page"].format(url=url), flush=True)
    print(m["store"].format(path=os.path.join(rv, STORE)), flush=True)
    print(m["stop_hint"].format(stop=stop), flush=True)
    # 書いたら立ったとみなされるので、最後に書く（ポートはもう受け付けていて、serve_forever までの接続は待たせる）
    with open(os.path.join(rv, STATE), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"pid": os.getpid(), "url": url, "token": token}, f)
    if not a.no_open:
        open_browser(url, lang)

    def bye(*_):
        threading.Thread(target=httpd.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, bye)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        remove_state(rv, token)


if __name__ == "__main__":
    main()
