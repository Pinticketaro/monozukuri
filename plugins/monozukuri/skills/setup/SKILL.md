---
name: setup
description: >
  This skill should be used when the user asks to "モックの環境を整えて", "プレビューの環境を作って",
  "monozukuri のセットアップ", "描画できるようにして", or when a monozukuri script fails because a library,
  Chromium, three.js or a Japanese font is missing. Installs and checks everything the monozukuri mock and
  review-page scripts need (shapely, manifold3d, trimesh, cascadio, playwright + Chromium, three.js, CJK font)
  and runs a test render.
metadata:
  version: "0.2.0"
---

# 環境セットアップ

モック作成・描画・確認ページづくりに必要なものを1回でそろえ、テスト描画まで確かめる。

## 手順

1. **どこで動かすかを決める**
   - 既定はこのセッションの作業環境（クラウド）。セッションが新しくなるたびに入れ直しが要る。
   - ユーザーのPCがつながっていて、PC上でも描画したいと言われた場合だけ、PC側のシェルで同じ手順を行う。PC側では `PYTHON` に使う Python を指定できる（conda なら `PYTHON=python`）。

2. **セットアップを実行する**（このスキルの基準ディレクトリからの相対パス）
   ```bash
   bash scripts/setup.sh            # 通常
   bash scripts/setup.sh --with-cad # STEP を書き出す必要があるときだけ（cadquery は重い）
   ```
   - タイムアウトは長め（10分）にする。cascadio・Chromium・three.js のダウンロードに時間がかかる。
   - 何度実行しても安全。入っているものは飛ばす。

3. **結果の表を読む**
   - 最後に `check_env.py` が表を出す。`NG` が残ったら下の「つまずいたとき」で直し、`python3 scripts/check_env.py` だけを再実行する。
   - `任意` は無くても動く（cascadio は STEP を読むとき、cadquery は STEP を書き出すときだけ必要）。
   - テスト描画の PNG のパスが出るので、Read で開いて箱が影付きで描けているか一度だけ確かめる。

4. **ユーザーへの報告は1〜2文**：準備できたこと、入らなかったものがあればその影響（例：「STEP は読めないので STL で書き出してください」）。

## つまずいたとき

| 症状 | 対処 |
|---|---|
| `externally-managed-environment` | setup.sh が自動で `--break-system-packages` を付けて再試行する。それでも失敗したら仮想環境（`python3 -m venv ~/.venv/monozukuri`）を作り `PYTHON` に指定 |
| Chromium が起動しない | `python3 -m playwright install chromium`。クラウドの作業環境では入っているはずなので、`PLAYWRIGHT_BROWSERS_PATH` を確認 |
| three.js が入らない（npm がない） | mac は `brew install node`。入れられない環境では、作業環境（クラウド）側で描画する |
| 日本語フォントが見つからない | mac はヒラギノ、Linux は `fonts-noto-cjk` を入れる。入れられない場合、図の日本語が□になるだけで描画自体はできる |
| テスト描画がタイムアウト | WebGL がソフトウェア描画（SwiftShader）で遅い環境。もう一度だけ実行し、それでもだめなら幅を小さく（`--width 1200`） |

## 置き場所
- three.js と環境の記録は `~/.cache/monozukuri/`（`MONOZUKURI_CACHE` で変更可）。
- 環境の記録 `env.json` に日本語フォントの場所が入り、比較画像・断面図がそれを使う。
