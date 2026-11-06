"""OS（Windows・macOS・Linux）の違いをまとめる。serve_review.py・status.py・make_version.py が使う。
プロジェクトの tools/ には写さない（写すスクリプトは、これを import しない）。

  alive(pid)               … そのプロセスが動いているか
  dir_id(path)・path_id(path) … フォルダーを見分ける短い文字列（GET /stamp の dir・dirp）
  serving(st, rv)          … review/.serve.json の中身 st のサーバーが、いま rv を配信して答えるか（PID と GET /stamp）。
                             True・False・None（PID は動いているが応答しない）
  replace_retry(src, dst)  … os.replace。Windows でほかのプロセスが dst を開いていれば、少し待ってやり直す
  detach_kwargs()          … 呼んだ側が終わっても止まらない子プロセスを立てる Popen の引数
  popen_detached(cmd, …)   … detach_kwargs() で立てる。Windows でジョブから外せなければ、外さずに立てる
  cmdline(args)            … 人や AI がそのまま打てるコマンドの1行（空白のあるパスは引用符で囲む）
"""
import hashlib
import http.client
import json
import os
import re
import shlex
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


def alive(pid):
    """pid のプロセスが動いていて、このユーザーの権限でアクセスできるか"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:                                   # os.kill(0, …) はプロセスグループ全体を指すので使わない
        return False
    if os.name == "nt":
        # Windows の os.kill(pid, 0) は CTRL_C_EVENT を送ってしまう。OpenProcess と終了コードで確かめる
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        h = k32.OpenProcess(0x1000, False, pid)      # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = wintypes.DWORD()
            return bool(k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259   # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _short_hash(key):
    return hashlib.sha256(key.encode("utf-8", "surrogatepass")).hexdigest()[:16]


def dir_id(path):
    """フォルダーを見分ける短い文字列（パスそのものは出さない）。プロジェクトをフォルダーごとコピーすると、
    コピーの review/.serve.json は元のプロジェクトのサーバーを指したままになるので、それと取り違えないため。
    パスの書き方（大文字小文字・/tmp と /private/tmp など）によらないように、デバイスと inode で決める"""
    try:
        s = os.stat(path)
    except OSError:
        return None
    return _short_hash(f"{s.st_dev}:{s.st_ino}") if s.st_ino else path_id(path)


def path_id(path):
    """パスで決めた dir_id。Windows の st_dev・st_ino は Python 3.12 から値の決め方が変わった（64 ビットのボリュームの
    シリアル番号・128 ビットのファイル ID）ので、サーバーと別の版の Python で確かめると dir_id が合わない。そのときのため"""
    return _short_hash(os.path.normcase(os.path.realpath(path)))


def serving(st, rv=None, timeout=3.0):
    """review/.serve.json の中身 st のサーバーが、いま答えるか。
      True  … 答えた（st に token があれば同じ token。rv を渡したら、rv を配信している）
      False … 動いていない：PID が動いていない、そのポートで待ち受けているサーバーが無い、別のサーバー・別のプロジェクトのサーバーが答えた
      None  … PID は動いているが応答しない（タイムアウトなど。PC の負荷が高い・プロセスが一時停止している・
               ループバックの接続がブロックされている）。サーバーが動いているかもしれないので、.serve.json は消さない
    PID が動いているかだけでは決めない（Windows は PID をすぐ使い回すので、別のプロセスのことがある）。
    st の url に GET /stamp を送り、token と /stamp の dir・dirp（コピーしたプロジェクト対策）を比べる。
    token の無い .serve.json（0.7.0 までのサーバー）は、/stamp が答えれば動いているとみなす。
    timeout: Windows は待ち受けの無いポートへの接続が失敗するまで約2秒かかるので、それより長くする"""
    if not isinstance(st, dict) or not st.get("url") or not alive(st.get("pid")):
        return False
    u = urllib.parse.urlsplit(str(st["url"]))
    if u.scheme != "http" or u.hostname not in ("127.0.0.1", "localhost", "::1"):
        return False                               # この PC のサーバーにだけ送る
    # プロキシの設定は使わない（Windows のプロキシの設定は 127.0.0.1 を除外しないことがある）
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://{u.netloc}/stamp", timeout=timeout) as r:
            got = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError:                 # 答えたが /stamp が無い：別のサーバー
        return False
    except urllib.error.URLError as e:             # 接続できない
        return False if isinstance(e.reason, ConnectionRefusedError) else None
    except ConnectionRefusedError:
        return False
    except OSError:                                # タイムアウト・接続が切れた
        return None
    except (ValueError, http.client.HTTPException):   # JSON・HTTP でないものが返った：別のサーバー
        return False
    if not isinstance(got, dict):
        return False
    if not (got.get("token") == st["token"] if st.get("token") else "board" in got):
        return False
    if rv is None or "dir" not in got:
        return True
    return got["dir"] == dir_id(rv) or got.get("dirp") == path_id(rv)


def replace_retry(src, dst, tries=20, wait=0.05):
    """os.replace(src, dst)。Windows では dst をほかのプロセス（エディター・ウイルス対策・同期のソフト・
    ファイルを読んでいる status.py など）が開いていると PermissionError になるので、少し待ってやり直す（合わせて約1秒）"""
    for i in range(tries):
        try:
            return os.replace(src, dst)
        except PermissionError:
            if os.name != "nt" or i == tries - 1:
                raise
            time.sleep(wait)


def detach_kwargs(breakaway=True):
    """呼んだ側（AI のシェル・コンソール）が終わっても止まらない子プロセスを立てる Popen の引数。
    POSIX: 新しいセッション（setsid）。
    Windows: start_new_session は無視されるので、新しいプロセスグループ（Ctrl+C が届かない）と
    ウィンドウの無いコンソール（呼んだ側のコンソールを閉じても止まらない）にする。breakaway なら
    呼んだ側のジョブからも外す（ジョブを閉じると中のプロセスを全部止める AI ツールがある）"""
    if os.name != "nt":
        return {"start_new_session": True}
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200) | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    if breakaway:
        flags |= getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0x01000000)
    return {"creationflags": flags}


def popen_detached(cmd, **kw):
    """detach_kwargs() で子プロセスを立てる"""
    try:
        return subprocess.Popen(cmd, **kw, **detach_kwargs())
    except OSError:
        if os.name != "nt":
            raise
        # ジョブから外すのを許さないジョブの中では CreateProcess が ERROR_ACCESS_DENIED になる。外さずに立てる
        return subprocess.Popen(cmd, **kw, **detach_kwargs(breakaway=False))


def cmdline(args):
    """コマンドの1行。空白や記号のある引数だけ引用符で囲む。
    POSIX: sh・bash・zsh でそのまま動く形。
    Windows: PowerShell（Codex）と Git Bash（Claude Code）でそのまま動く形。\\ は / にする（Git Bash は
    引用符の外の \\ を消す。python.exe も Windows の API も / を受け付ける）。囲むのは "…"。ただし、どちらのシェルも
    "…" の中で展開する $・` のある引数と、\\ を残す UNC パス（\\\\server\\share）は '…'。
    PowerShell では、引用符で始まる行（python.exe のパスに空白がある）の先頭に & が要る"""
    args = [str(x) for x in args]
    if os.name == "nt":
        out = []
        for x in args:
            if not x.startswith("\\\\"):              # Git Bash は //server を /server にするので、UNC はそのまま
                x = x.replace("\\", "/")
            if not x or re.search(r"[^\w%+=:./-]", x):  # , は PowerShell では配列、@ は先頭なら展開になる
                x = f"'{x}'" if re.search(r"[$`\\]", x) and "'" not in x else f'"{x}"'
            out.append(x)
        return " ".join(out)
    return " ".join(shlex.quote(x) if re.search(r"[^\w@%+=:,./-]", x) else x for x in args)
