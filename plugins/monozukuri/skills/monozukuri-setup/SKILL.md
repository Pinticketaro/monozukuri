---
name: monozukuri-setup
description: >
  This skill should be used when the user asks to "モックの環境を整えて", "monozukuri のセットアップ",
  "レンダリングできるようにして", "Mac でレンダリングできるようにして", "set up the mock environment",
  "set up monozukuri", "make rendering work on my Mac", or when a monozukuri script fails because a library,
  Chromium, three.js or a Japanese font is missing. Installs and checks everything the monozukuri mock and
  review-page scripts need (shapely, manifold3d, trimesh, networkx, cascadio, cadquery for STEP output,
  playwright + Chromium, three.js, CJK font) and runs a test render. On macOS it installs into ~/.monozukuri/venv.
license: MIT
compatibility: macOS と Linux（Windows は WSL）。Python 3.10 以上と Node.js が要る。Claude Code・Claude アプリ・Codex などで動く
metadata:
  version: "0.7.1"
---

# 環境セットアップ

モック作成・レンダリング・確認ページづくりに必要なものを1回でそろえ、テストレンダリングまで確かめる。

日本語の文（会話の返事・表示）は、monozukuri-new-project スキルの `references/ai-words-ja.md`（AI ワード辞書）に従う。

## 聞き方
決めてほしいこと（どこで動かすか、cadquery を入れるか）は、選択式の問いの画面があればそれで聞く（Claude の AskUserQuestion など）。無ければ、番号付きの選択肢を文字で添えて聞く。1回に4問まで、1問に2〜4択、おすすめの案を先頭に「（おすすめ）」付きで置く。画面には「その他」が自動で付くので選択肢に入れない（文字で聞くときは最後に「その他」を付ける）。

## 言語（日本語・英語）
- ユーザーが書いた言語で答える。問いと選択肢も、その言語で書く（英語なら「（おすすめ）」は「(Recommended)」）。
- ユーザーが英語で書いているときは、`MONOZUKURI_LANG=en` を付けて実行する（`MONOZUKURI_LANG=en bash scripts/setup.sh`、`MONOZUKURI_LANG=en python3 scripts/check_env.py`）。表と表示が英語になる。付けなければ今までどおり日本語。
- monozukuri-setup はプロジェクトを持たないので、言語は環境変数で決める。プロジェクトの言語はパラメータファイル（params/params_vNN.json）の `meta.lang`（`ja`／`en`、無ければ `ja`）。決め方・切り替え方は monozukuri-new-project スキルの `references/language.md`。
- 英語で使うときも日本語フォントは入れる（部品名や前の版の文字に日本語が残ることがある）。

## 手順

1. **どこで動かすかを決める**
   - AI がユーザーの PC（Mac・Linux）で動いているなら（Claude Code・Codex など）、PC に入れる。プロジェクトを PC のフォルダに置くなら、レンダリングも PC でするのがいちばん手間が少ない（クラウドとの同期が要らない）。
   - クラウドの作業環境で動いているなら（Claude アプリなど）、そこに入れる。セッションが新しくなるたびに入れ直しが要る。
   - 置き場所：macOS では Python のパッケージをプロジェクトの外の仮想環境 `~/.monozukuri/venv` に入れる（`MONOZUKURI_VENV` で変更可）。Linux（クラウド）では今までどおり `python3` に入れる。特定の Python に入れたいときは `PYTHON` で指定する（conda なら `PYTHON=python`）。

2. **セットアップを実行する**（このスキルの基準ディレクトリからの相対パス）
   ```bash
   bash scripts/setup.sh           # 通常（cadquery も入れる。モックを STEP でもエクスポートできる）
   bash scripts/setup.sh --no-cad  # STL だけでよいとき（cadquery は数百MBあり、入れるのに数分かかる）
   ```
   - コマンドのタイムアウトは長め（10分）にする（Claude Code では timeout 600000）。cadquery・cascadio・Chromium・three.js のダウンロードに時間がかかる。
   - 何度実行しても安全。入っているものは飛ばす。

3. **結果の表を読む**
   - 最後に `check_env.py` が表を出す。`NG` が残ったら下の「つまずいたとき」で直し、`python3 scripts/check_env.py` だけを再実行する。
   - `任意` は無くても動く（cascadio は STEP を読むとき、cadquery はモックを STEP でエクスポートするときだけ必要。無ければモックは STL だけになる）。
   - テストレンダリングの PNG のパスが出るので、画像を見る機能で開いて一度だけ確かめる（Claude は Read）：等角の図に影、右側面の図に段差と面取りの明暗が見えること。見られない環境では、ユーザーに開いてもらい、影と明暗が見えるかを聞く。
   - 表の最後に「python3 の代わりに次の Python で実行してください」（英語ではその訳）と出たら（mac の仮想環境など）、以後の monozukuri のコマンドの `python3` はその Python に読み替える（例：`~/.monozukuri/venv/bin/python tools/mock.py`）。

4. **ユーザーへの報告は1〜2文**：準備できたこと、入らなかったものがあればその影響（例：「STEP は読めないので STL でエクスポートしてください」）。

## つまずいたとき

| 症状 | 対処 |
|---|---|
| `externally-managed-environment` | setup.sh が自動で `--break-system-packages` を付けて再試行する。それでも失敗したら仮想環境を使う（`MONOZUKURI_VENV=~/.monozukuri/venv bash scripts/setup.sh`） |
| mac で仮想環境が作れない（Python 3.10 以上が無い） | `brew install python@3.12` のあと `BASE_PYTHON=python3.12 bash scripts/setup.sh` |
| mac で STEP をエクスポートすると落ちる（Segmentation fault / Abort trap） | cascadio と CadQuery の読み込み順の問題。テンプレートの `geom.py` は CadQuery を先に読むので、古いプロジェクトは monozukuri-new-project の `scaffold.py --update-tools` でツールを新しくする |
| Chromium が起動しない | `python3 -m playwright install chromium`。クラウドの作業環境では入っているはずなので、`PLAYWRIGHT_BROWSERS_PATH` を確認 |
| three.js が入らない（npm がない） | mac は `brew install node`。入れられない環境では、作業環境（クラウド）側でレンダリングする |
| 日本語フォントが見つからない | mac はヒラギノ、Linux は `fonts-noto-cjk` を入れる。入れられない場合、図の日本語が□になるだけでレンダリング自体はできる |
| cadquery が入らない | Python のバージョンに合う版が無いことがある（3.10〜3.12 が確実）。入らなくても STL のモックと確認ページは使える。STEP が要るときは conda（`conda install -c conda-forge cadquery`）を試す |
| AI のサンドボックスでダウンロードや `~/` への書き込みが止められる（Codex の既定の設定など） | setup.sh はネットワークと、`~/.monozukuri/`・`~/.cache/monozukuri/` への書き込みが要る。ユーザーの許可を得て、サンドボックスの外で実行する（またはユーザーに `bash scripts/setup.sh` を実行してもらう） |
| テストレンダリングがタイムアウト | WebGL がソフトウェアレンダリング（SwiftShader）で遅い環境。もう一度だけ実行し、それでもだめなら幅を小さく（`--width 1200`） |

## 置き場所
- three.js と環境の記録は `~/.cache/monozukuri/`（`MONOZUKURI_CACHE` で変更可）。
- 環境の記録 `env.json` に日本語フォントの場所と、使う Python が入る。比較画像・断面図はそのフォントを使う。
- macOS の Python のパッケージは `~/.monozukuri/venv`（プロジェクトの外。`MONOZUKURI_VENV` で変更可）。
