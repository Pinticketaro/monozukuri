---
name: setup
description: >
  This skill should be used when the user asks to "モックの環境を整えて", "プレビューの環境を作って",
  "monozukuri のセットアップ", "描画できるようにして", or when a monozukuri script fails because a library,
  Chromium, three.js or a Japanese font is missing. Installs and checks everything the monozukuri mock and
  review-page scripts need (shapely, manifold3d, trimesh, cascadio, cadquery for STEP output, playwright +
  Chromium, three.js, CJK font) and runs a test render.
metadata:
  version: "0.3.0"
---

# 環境セットアップ

モック作成・描画・確認ページづくりに必要なものを1回でそろえ、テスト描画まで確かめる。

## 聞き方
決めてほしいこと（どこで動かすか、cadquery を入れるか）は、番号で選ぶ問いの画面（AskUserQuestion）が使えるときはそれで聞く。1回に4問まで、1問に2〜4択、おすすめの案を先頭に「（おすすめ）」付きで置く。「その他」は自動で付くので選択肢に入れない。画面が使えない環境では文字で聞く。

## 手順

1. **どこで動かすかを決める**
   - Claude Code などユーザーの PC（Mac）で動いているなら、PC に入れる。プロジェクトを PC のフォルダに置くなら、描画も PC でするのがいちばん手間が少ない（クラウドとの同期が要らない）。
   - Claude アプリのクラウドの作業環境なら、そこに入れる。セッションが新しくなるたびに入れ直しが要る。
   - 置き場所：macOS では Python のパッケージをプロジェクトの外の仮想環境 `~/.monozukuri/venv` に入れる（`MONOZUKURI_VENV` で変更可）。Linux（クラウド）では今までどおり `python3` に入れる。特定の Python に入れたいときは `PYTHON` で指定する（conda なら `PYTHON=python`）。

2. **セットアップを実行する**（このスキルの基準ディレクトリからの相対パス）
   ```bash
   bash scripts/setup.sh           # 通常（cadquery も入れる。モックを STEP でも書き出せる）
   bash scripts/setup.sh --no-cad  # STL だけでよいとき（cadquery は数百MBあり、入れるのに数分かかる）
   ```
   - タイムアウトは長め（10分）にする。cadquery・cascadio・Chromium・three.js のダウンロードに時間がかかる。
   - 何度実行しても安全。入っているものは飛ばす。

3. **結果の表を読む**
   - 最後に `check_env.py` が表を出す。`NG` が残ったら下の「つまずいたとき」で直し、`python3 scripts/check_env.py` だけを再実行する。
   - `任意` は無くても動く（cascadio は STEP を読むとき、cadquery はモックを STEP で書き出すときだけ必要。無ければモックは STL だけになる）。
   - テスト描画の PNG のパスが出るので、Read で開いて箱が影付きで描けているか一度だけ確かめる。
   - 表の最後に「python3 の代わりに次の Python で実行してください」と出たら（mac の仮想環境など）、以後の monozukuri のコマンドの `python3` はその Python に読み替える（例：`~/.monozukuri/venv/bin/python tools/mock.py`）。

4. **ユーザーへの報告は1〜2文**：準備できたこと、入らなかったものがあればその影響（例：「STEP は読めないので STL で書き出してください」）。

## つまずいたとき

| 症状 | 対処 |
|---|---|
| `externally-managed-environment` | setup.sh が自動で `--break-system-packages` を付けて再試行する。それでも失敗したら仮想環境を使う（`MONOZUKURI_VENV=~/.monozukuri/venv bash scripts/setup.sh`） |
| mac で仮想環境が作れない（Python 3.10 以上が無い） | `brew install python@3.12` のあと `BASE_PYTHON=python3.12 bash scripts/setup.sh` |
| mac で STEP を書き出すと落ちる（Segmentation fault / Abort trap） | cascadio と CadQuery の読み込み順の問題。雛形の `geom.py` は CadQuery を先に読むので、古いプロジェクトは new-project の `scaffold.py --update-tools` で道具を新しくする |
| Chromium が起動しない | `python3 -m playwright install chromium`。クラウドの作業環境では入っているはずなので、`PLAYWRIGHT_BROWSERS_PATH` を確認 |
| three.js が入らない（npm がない） | mac は `brew install node`。入れられない環境では、作業環境（クラウド）側で描画する |
| 日本語フォントが見つからない | mac はヒラギノ、Linux は `fonts-noto-cjk` を入れる。入れられない場合、図の日本語が□になるだけで描画自体はできる |
| cadquery が入らない | Python のバージョンに合う版が無いことがある（3.10〜3.12 が確実）。入らなくても STL のモックと確認ページは使える。STEP が要るときは conda（`conda install -c conda-forge cadquery`）を試す |
| テスト描画がタイムアウト | WebGL がソフトウェア描画（SwiftShader）で遅い環境。もう一度だけ実行し、それでもだめなら幅を小さく（`--width 1200`） |

## 置き場所
- three.js と環境の記録は `~/.cache/monozukuri/`（`MONOZUKURI_CACHE` で変更可）。
- 環境の記録 `env.json` に日本語フォントの場所と、使う Python が入る。比較画像・断面図はそのフォントを使う。
- macOS の Python のパッケージは `~/.monozukuri/venv`（プロジェクトの外。`MONOZUKURI_VENV` で変更可）。
