#!/usr/bin/env bash
# monozukuri: モック・プレビュー環境のセットアップ
# 使い方: bash setup.sh [--no-cad] [--lang ja|en]
#   既定で cadquery（モックの STEP 書き出し用）も入れる。数分かかる。
#   --no-cad  … cadquery を入れない（STL だけでよいとき。--with-cad は旧い書き方で、無視される）
#   --lang    … 表示の言葉（ja / en）。無ければ環境変数 MONOZUKURI_LANG、どれも無ければ ja
# 何度実行しても安全（入っているものは飛ばす）。
# Python の置き場所
#   macOS：プロジェクトの外の仮想環境 ~/.monozukuri/venv に入れる（MONOZUKURI_VENV で変更可）
#   Linux（クラウドの作業環境など）：今までどおり python3 に直接入れる（MONOZUKURI_VENV を指定すれば仮想環境）
#   PYTHON を指定すると、その Python に直接入れる（conda など。PYTHON=python）
set -u

WITH_CAD=1
LANG_ARG=""
prev=""
for a in "$@"; do
  case "$a" in
    --no-cad) WITH_CAD=0 ;;
    --lang=*) LANG_ARG="${a#--lang=}" ;;
  esac
  [ "$prev" = "--lang" ] && LANG_ARG="$a"
  prev="$a"
done

# 言葉: --lang > MONOZUKURI_LANG > ja（LANG はロケールの変数なので使わない）
MZ_LANG="ja"
for v in "$LANG_ARG" "${MONOZUKURI_LANG:-}"; do
  case "$v" in ja|en) MZ_LANG="$v"; break ;; esac
done

CACHE="${MONOZUKURI_CACHE:-$HOME/.cache/monozukuri}"
THREE_VER="0.160.0"
mkdir -p "$CACHE"

# 見出しと文: 日本語・英語を並べて渡し、MZ_LANG で選ぶ
say() { if [ "$MZ_LANG" = "en" ]; then printf '\n== %s\n' "$2"; else printf '\n== %s\n' "$1"; fi; }
msg() { if [ "$MZ_LANG" = "en" ]; then printf '%s\n' "$2"; else printf '%s\n' "$1"; fi; }

VENV="${MONOZUKURI_VENV:-}"
if [ -z "${PYTHON:-}" ] && [ -z "$VENV" ] && [ "$(uname -s)" = "Darwin" ]; then
  VENV="$HOME/.monozukuri/venv"
fi
if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif [ -n "$VENV" ]; then
  say "Python の仮想環境（${VENV}）" "Python virtual environment (${VENV})"
  if [ -x "$VENV/bin/python" ]; then
    msg "あります" "Already exists"
  else
    BASE="${BASE_PYTHON:-python3}"
    if ! "$BASE" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] else 1)' 2>/dev/null; then
      msg "!! Python 3.10 以上が要ります（mac: brew install python@3.12）。BASE_PYTHON で使う Python を指定できます" \
          "!! Python 3.10 or newer is required (mac: brew install python@3.12). Set BASE_PYTHON to choose the Python to use"
      exit 1
    fi
    mkdir -p "$(dirname "$VENV")" && "$BASE" -m venv "$VENV" && "$VENV/bin/python" -m pip install -q --upgrade pip \
      && BASE_VER="$("$BASE" --version 2>&1)" \
      && msg "作りました（元の Python: ${BASE_VER}）" "Created (base Python: ${BASE_VER})"
  fi
  PY="$VENV/bin/python"
else
  PY="python3"
fi

pip_install() {
  # 外部管理された環境（Debian/Ubuntu の system python）では --break-system-packages が要る
  if ! "$PY" -m pip install -q "$@" 2>/tmp/mz_pip_err.txt; then
    if grep -q "externally-managed" /tmp/mz_pip_err.txt; then
      "$PY" -m pip install -q --break-system-packages "$@"
    else
      cat /tmp/mz_pip_err.txt >&2
      return 1
    fi
  fi
}

say "Python パッケージ" "Python packages"
PKGS="numpy shapely matplotlib manifold3d trimesh networkx pillow playwright cascadio"
MISSING=""
for p in $PKGS; do
  mod="$p"; [ "$p" = "pillow" ] && mod="PIL"
  "$PY" -c "import $mod" 2>/dev/null || MISSING="$MISSING $p"
done
if [ -n "$MISSING" ]; then
  msg "入れる:${MISSING}" "Installing:${MISSING}"
  pip_install $MISSING || msg "!! 一部のパッケージを入れられませんでした（上のエラーを確認）" "!! Some packages could not be installed (see the error above)"
else
  msg "すべて入っています" "All installed"
fi
if [ "$WITH_CAD" = 1 ]; then
  "$PY" -c "import cadquery" 2>/dev/null || {
    msg "cadquery を入れる（数分かかります）" "Installing cadquery (takes a few minutes)"
    pip_install cadquery || msg "!! cadquery を入れられませんでした（モックは STL だけになります）" "!! Could not install cadquery (mocks will be STL only)"
  }
fi

say "ブラウザ（外観画像の描画用 Chromium）" "Browser (Chromium for rendering the view images)"
if "$PY" - <<'EOF' 2>/dev/null
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    p.chromium.launch().close()
EOF
then
  msg "Chromium は起動できます" "Chromium starts OK"
else
  msg "Chromium を入れる" "Installing Chromium"
  "$PY" -m playwright install chromium
fi

say "three.js ${THREE_VER}" "three.js ${THREE_VER}"
THREE_DIR="$CACHE/three"
if [ -f "$THREE_DIR/node_modules/three/build/three.module.js" ]; then
  msg "入っています: ${THREE_DIR}" "Already installed: ${THREE_DIR}"
elif command -v npm >/dev/null 2>&1; then
  mkdir -p "$THREE_DIR" && (cd "$THREE_DIR" && npm install --silent --no-audit --no-fund "three@${THREE_VER}") \
    && msg "入れました: ${THREE_DIR}" "Installed: ${THREE_DIR}"
else
  msg "!! npm がありません。Node.js を入れてからもう一度実行してください（mac: brew install node）" \
      "!! npm not found. Install Node.js, then run this again (mac: brew install node)"
fi

say "動作確認" "Checking the setup"
MONOZUKURI_LANG="$MZ_LANG" "$PY" "$(dirname "$0")/check_env.py"
