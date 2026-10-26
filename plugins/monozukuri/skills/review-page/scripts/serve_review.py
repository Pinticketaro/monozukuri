"""確認ページを PC で開く（Artifact を公開できない環境、たとえば Claude Code 用）。
プロジェクトの review/ を localhost の空いているポートで配り、ブラウザで開く。
three.js や 3D モデルの読み込みは file:// では動かないので、ローカルのサーバーで配る。

使い方
  python3 serve_review.py <プロジェクト>             … 配ってブラウザを開く（止めるまで動き続ける。裏で動かす）
  python3 serve_review.py <プロジェクト> --no-open   … ブラウザを開かない
  python3 serve_review.py <プロジェクト> --stop      … 動いているサーバーを止める
すでに同じプロジェクトのサーバーが動いていれば、新しく立てずにそのページを開く。

ページに書いたフィードバック・問いの答えは review/feedback_local.json に保存される（Artifact の db と同じ形）：
  {"feedback": {"<id>": {...}}, "answers": {"<版>~q<番号>~local": {...}}, "decisions": {"<版>~q<番号>": {...}}}
Claude は「フィードバックを読んで」と頼まれたらこのファイルを読み、返信（status・resolvedIn・reply）と
決定（decisions）を同じファイルに書く。ページを開き直す（タブに戻る）と見える。
サーバーの場所は review/.serve.json に書く（--stop が使う）。
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
import sys
import threading

STORE = "feedback_local.json"
STATE = ".serve.json"
WRITABLE = {"feedback", "answers"}       # ページから書けるのはこの2つ。decisions は Claude がファイルに書く
MAX_BODY = 64 * 1024
lock = threading.Lock()


def load_store(path):
    try:
        d = json.load(open(path, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        d = {}
    for k in ("feedback", "answers", "decisions"):
        d.setdefault(k, {})
    return d


def save_store(path, d):
    tmp = path + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def open_browser(url):
    cmd = {"darwin": ["open", url]}.get(sys.platform, ["xdg-open", url])
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print(f"ブラウザで開いてください: {url}")


def make_handler(rv):
    store_path = os.path.join(rv, STORE)

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=rv, **k)

        def log_message(self, *a):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")     # 作り直したページ・Claude の返信がすぐ見えるように
            super().end_headers()

        def send_json(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.split("?")[0] == "/feedback":
                with lock:
                    return self.send_json(200, load_store(store_path))
            if os.path.basename(self.path.split("?")[0]) in (STORE, STATE):
                return self.send_json(404, {"error": "not_found"})
            return super().do_GET()

        def do_POST(self):
            if self.path.split("?")[0] != "/feedback":
                return self.send_json(404, {"error": "not_found"})
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                return self.send_json(413, {"error": "too_large"})
            try:
                req = json.loads(self.rfile.read(n))
            except json.JSONDecodeError:
                return self.send_json(400, {"error": "bad_json"})
            col = req.get("collection")
            if col not in WRITABLE:
                return self.send_json(403, {"error": "not_writable"})
            with lock:
                d = load_store(store_path)
                if req.get("delete"):
                    d[col].pop(str(req.get("id")), None)
                else:
                    doc = req.get("doc")
                    if not isinstance(doc, dict):
                        return self.send_json(400, {"error": "bad_doc"})
                    did = str(req.get("id") or datetime.datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3))
                    d[col][did] = doc
                save_store(store_path, d)
                return self.send_json(200, d)

    return H


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--port", type=int, default=0, help="ポート（既定：空いているもの）")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--stop", action="store_true")
    a = ap.parse_args()
    rv = os.path.join(os.path.abspath(a.project), "review")
    state = os.path.join(rv, STATE)
    st = json.load(open(state)) if os.path.exists(state) else {}

    if a.stop:
        if st.get("pid") and alive(st["pid"]):
            os.kill(st["pid"], signal.SIGTERM)
            print(f"止めました（{st.get('url')}）")
        else:
            print("動いているサーバーはありません")
        if os.path.exists(state):
            os.remove(state)
        return
    if not os.path.isfile(os.path.join(rv, "index.html")):
        sys.exit(f"{rv}/index.html がありません。先に build_page.py で確認ページを作ってください")
    if st.get("pid") and alive(st["pid"]):
        print(f"すでに動いています: {st['url']}（止めるとき: python3 {sys.argv[0]} {a.project} --stop）")
        if not a.no_open:
            open_browser(st["url"])
        return

    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", a.port), make_handler(rv))
    url = f"http://127.0.0.1:{httpd.server_address[1]}/index.html"
    json.dump({"pid": os.getpid(), "url": url}, open(state, "w"))
    print(f"確認ページ: {url}", flush=True)
    print(f"フィードバックの保存先: {os.path.join(rv, STORE)}", flush=True)
    print(f"止めるとき: python3 {sys.argv[0]} {a.project} --stop", flush=True)
    if not a.no_open:
        open_browser(url)

    def bye(*_):
        threading.Thread(target=httpd.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, bye)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        try:
            if json.load(open(state)).get("pid") == os.getpid():
                os.remove(state)
        except (FileNotFoundError, json.JSONDecodeError):
            pass


if __name__ == "__main__":
    main()
