#!/usr/bin/env bash
# monozukuri: モック・プレビュー環境のセットアップ
# 使い方: bash setup.sh [--no-cad]
#   既定で cadquery（モックの STEP 書き出し用）も入れる。数分かかる。
#   --no-cad  … cadquery を入れない（STL だけでよいとき。--with-cad は旧い書き方で、無視される）
# 何度実行しても安全（入っているものは飛ばす）。
set -u

WITH_CAD=1
for a in "$@"; do [ "$a" = "--no-cad" ] && WITH_CAD=0; done

CACHE="${MONOZUKURI_CACHE:-$HOME/.cache/monozukuri}"
THREE_VER="0.160.0"
PY="${PYTHON:-python3}"
mkdir -p "$CACHE"

say() { printf '\n== %s\n' "$*"; }

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

say "Python パッケージ"
PKGS="numpy shapely matplotlib manifold3d trimesh pillow playwright cascadio ezdxf"
MISSING=""
for p in $PKGS; do
  mod="$p"; [ "$p" = "pillow" ] && mod="PIL"
  "$PY" -c "import $mod" 2>/dev/null || MISSING="$MISSING $p"
done
if [ -n "$MISSING" ]; then
  echo "入れる:$MISSING"
  pip_install $MISSING || echo "!! 一部のパッケージを入れられませんでした（上のエラーを確認）"
else
  echo "すべて入っています"
fi
if [ "$WITH_CAD" = 1 ]; then
  "$PY" -c "import cadquery" 2>/dev/null || { echo "cadquery を入れる（数分かかります）"; pip_install cadquery || echo "!! cadquery を入れられませんでした（モックは STL だけになります）"; }
fi

say "ブラウザ（外観画像の描画用 Chromium）"
if "$PY" - <<'EOF' 2>/dev/null
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    p.chromium.launch().close()
EOF
then
  echo "Chromium は起動できます"
else
  echo "Chromium を入れる"
  "$PY" -m playwright install chromium
fi

say "three.js ${THREE_VER}"
THREE_DIR="$CACHE/three"
if [ -f "$THREE_DIR/node_modules/three/build/three.module.js" ]; then
  echo "入っています: $THREE_DIR"
elif command -v npm >/dev/null 2>&1; then
  mkdir -p "$THREE_DIR" && (cd "$THREE_DIR" && npm install --silent --no-audit --no-fund "three@${THREE_VER}") \
    && echo "入れました: $THREE_DIR"
else
  echo "!! npm がありません。Node.js を入れてからもう一度実行してください（mac: brew install node）"
fi

say "動作確認"
"$PY" "$(dirname "$0")/check_env.py"
