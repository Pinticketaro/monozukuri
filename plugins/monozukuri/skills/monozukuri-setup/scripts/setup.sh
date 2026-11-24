#!/usr/bin/env bash
# monozukuri: モック・プレビュー環境のセットアップ（macOS・Linux 用の入口）
# 中身は setup.py（どの OS でも python で動く）。前からの bash scripts/setup.sh でも動くように残している。
# 使い方: bash setup.sh [--no-cad] [--lang ja|en] [--venv <フォルダ> | --no-venv] [--python <Python>] [--rebuild-venv] [--no-uv]
#   引数と環境変数（MONOZUKURI_VENV・MONOZUKURI_CACHE・MONOZUKURI_LANG・PYTHON・BASE_PYTHON）は setup.py と同じ。
#   setup.py を動かす Python は BASE_PYTHON、無ければ python3（mac の 3.9 でも動く。STEP まで使える版（3.11〜3.13）で
#   なければ、uv で monozukuri 用の Python 3.12 を用意して仮想環境を作る）。
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "${BASE_PYTHON:-python3}" "$DIR/setup.py" "$@"
