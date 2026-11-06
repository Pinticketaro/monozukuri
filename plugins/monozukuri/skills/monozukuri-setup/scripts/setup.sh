#!/usr/bin/env bash
# monozukuri: モック・プレビュー環境のセットアップ（macOS・Linux 用の入口）
# 中身は setup.py（どの OS でも python で動く）。前からの bash scripts/setup.sh でも動くように残している。
# 使い方: bash setup.sh [--no-cad] [--lang ja|en] [--venv <フォルダ> | --no-venv] [--python <Python>]
#   引数と環境変数（MONOZUKURI_VENV・MONOZUKURI_CACHE・MONOZUKURI_LANG・PYTHON・BASE_PYTHON）は setup.py と同じ。
#   setup.py を動かす Python は BASE_PYTHON、無ければ python3（3.9 でも動き、3.10 以上が無ければ案内を出す）。
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "${BASE_PYTHON:-python3}" "$DIR/setup.py" "$@"
