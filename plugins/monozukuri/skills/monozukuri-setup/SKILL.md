---
name: monozukuri-setup
description: >
  This skill should be used when the user asks to "モックの環境を整えて", "monozukuri のセットアップ",
  "レンダリングできるようにして", "Mac でレンダリングできるようにして", "Windows でレンダリングできるようにして",
  "set up the mock environment", "set up monozukuri", "make rendering work on my Mac",
  "make rendering work on Windows", or when a monozukuri script fails because a library,
  Chromium, three.js or a Japanese font is missing. Installs and checks everything the monozukuri mock and
  review-page scripts need (shapely, manifold3d, trimesh, networkx, cascadio, cadquery for STEP output,
  playwright + Chromium, three.js, CJK font) and runs a test render. On macOS and Windows it installs into ~/.monozukuri/venv.
license: MIT
compatibility: macOS・Linux・Windows（PowerShell・Git Bash・WSL）。Python 3.10 以上（Windows は 3.12 がいちばん確実）と Node.js が要る。Claude Code・Claude アプリ・Codex などで動く
metadata:
  version: "0.8.0"
---

# 環境セットアップ

モック作成・レンダリング・確認ページづくりに必要なものを1回でそろえ、テストレンダリングまで確かめる。

日本語の文（会話の返事・表示）は、monozukuri-new-project スキルの `references/ai-words-ja.md`（AI ワード辞書）に従う。

コマンドの `<python>` は、monozukuri-setup（このスキル）が記録した Python。check_env.py の最後の行（「monozukuri のスクリプトは次の Python で実行する: <パス>」）か、`~/.cache/monozukuri/env.json` の `python`（Windows では区切りを / にした `python_posix`）。例：mac は `~/.monozukuri/venv/bin/python`、Windows は `~/.monozukuri/venv/Scripts/python.exe`、Linux（クラウドの作業環境）は `python3`。PowerShell では、引用符で囲んだパスで始まるコマンドの前に `&` を付ける（`& "C:/Users/山田 太郎/.monozukuri/venv/Scripts/python.exe" scripts/check_env.py`）。まだ記録が無いとき（最初のセットアップ）は、手順2のコマンドで setup.py を実行する。

## 聞き方
決めてほしいこと（どこで動かすか、cadquery を入れるか）は、選択式の問いの画面があればそれで聞く（Claude の AskUserQuestion など）。無ければ、番号付きの選択肢を文字で添えて聞く。1回に4問まで、1問に2〜4択、おすすめの案を先頭に「（おすすめ）」付きで置く。画面には「その他」が自動で付くので選択肢に入れない（文字で聞くときは最後に「その他」を付ける）。

## 言語（日本語・英語）
- ユーザーが書いた言語で答える。問いと選択肢も、その言語で書く（英語なら「（おすすめ）」は「(Recommended)」）。
- ユーザーが英語で書いているときは、setup.py と check_env.py に `--lang en` を付けて実行する（例：mac・Linux は `python3 scripts/setup.py --lang en`、Windows は `python scripts/setup.py --lang en`、確かめ直しは `<python> scripts/check_env.py --lang en`）。表と表示が英語になる。付けなければ今までどおり日本語。
- monozukuri-setup はプロジェクトを持たないので、言語は `--lang` で決める（環境変数 `MONOZUKURI_LANG` を前もって設定しておいてもよい。`MONOZUKURI_LANG=en コマンド` の形は PowerShell では使えない）。プロジェクトの言語はパラメータファイル（params/params_vNN.json）の `meta.lang`（`ja`／`en`、無ければ `ja`）。決め方・切り替え方は monozukuri-new-project スキルの `references/language.md`。
- 英語で使うときも日本語フォントは入れる（部品名や前の版の文字に日本語が残ることがある）。

## 手順

1. **どこで動かすかを決める**
   - AI がユーザーの PC（Mac・Windows・Linux）で動いているなら（Claude Code・Codex など）、PC に入れる。プロジェクトを PC のフォルダに置くなら、レンダリングも PC でするのがいちばん手間が少ない（クラウドとの同期が要らない）。
   - クラウドの作業環境で動いているなら（Claude アプリなど）、そこに入れる。セッションが新しくなるたびに入れ直しが要る。
   - 置き場所：macOS と Windows では Python のパッケージをプロジェクトの外の仮想環境 `~/.monozukuri/venv` に入れる（`--venv <フォルダ>` で変更可）。Linux（クラウド）では今までどおり、setup.py を実行した Python に入れる。特定の Python に直接入れたいときは `--python <Python>`（conda なら `--python python`）、仮想環境を使わないときは `--no-venv`。

2. **セットアップを実行する**（このスキルの基準ディレクトリからの相対パス）
   ```bash
   python3 scripts/setup.py    # mac・Linux（前からの bash scripts/setup.sh でも同じ）
   python scripts/setup.py     # Windows（python が無い、または Microsoft Store が開くときは py -3.12 scripts/setup.py）
   ```
   - 通常は cadquery も入れる（モックを STEP でもエクスポートできる）。STL だけでよいときは `--no-cad` を付ける（cadquery は数百MBあり、入れるのに数分かかる）。ほかのオプションは `--lang en`・`--venv <フォルダ>`・`--no-venv`・`--python <Python>`（`--help` で説明が出る）。
   - コマンドのタイムアウトは長め（10分）にする（Claude Code では timeout 600000）。cadquery・cascadio・Chromium・three.js のダウンロードに時間がかかる。
   - 何度実行しても安全。入っているものは飛ばす。

3. **結果の表を読む**
   - 最後に `check_env.py` が表を出す。`NG` が残ったら下の「つまずいたとき」で直し、`<python> scripts/check_env.py` だけを再実行する。
   - `任意` は無くても動く（cascadio は STEP を読むとき、cadquery はモックを STEP でエクスポートするときだけ必要。無ければモックは STL だけになる）。
   - テストレンダリングの PNG のパスが出るので、画像を見る機能で開いて一度だけ確かめる（Claude は Read）：等角の図に影、右側面の図に段差と面取りの明暗が見えること。見られない環境では、ユーザーに開いてもらい、影と明暗が見えるかを聞く。
   - 最後の行「monozukuri のスクリプトは次の Python で実行する: <パス>」（英語では「Run the monozukuri scripts with this Python: <path>」）のパスが `<python>`。以後の monozukuri のコマンドは、その Python で実行する（例：`<python> tools/mock.py v01`）。Windows では区切りが / のパスが出て、空白があれば " で囲んである。

4. **ユーザーへの報告は1〜2文**：準備できたこと、入らなかったものがあればその影響（例：「STEP は読めないので STL でエクスポートしてください」）。

## つまずいたとき

| 症状 | 対処 |
|---|---|
| `externally-managed-environment` | setup.py が自動で `--break-system-packages` を付けて再試行する。それでも失敗したら仮想環境を使う（`python3 scripts/setup.py --venv ~/.monozukuri/venv`） |
| mac で仮想環境が作れない（Python 3.10 以上が無い） | `brew install python@3.12` のあと `python3.12 scripts/setup.py`（仮想環境は setup.py を実行した Python から作る） |
| mac で STEP をエクスポートすると落ちる（Segmentation fault / Abort trap） | cascadio と CadQuery の読み込み順の問題。テンプレートの `geom.py` は CadQuery を先に読むので、古いプロジェクトは monozukuri-new-project の `scaffold.py --update-tools` でツールを新しくする |
| Chromium が起動しない | `<python> -m playwright install chromium`。クラウドの作業環境では入っているはずなので、`PLAYWRIGHT_BROWSERS_PATH` を確認 |
| three.js が入らない（npm がない） | mac は `brew install node`、Windows は `winget install -e --id OpenJS.NodeJS.LTS` のあと AI のアプリを開き直す（PATH を読み直すため）。入れられない環境では、作業環境（クラウド）側でレンダリングする |
| 日本語フォントが見つからない | mac はヒラギノ、Linux は `fonts-noto-cjk` を入れる（Windows は游ゴシック・メイリオが最初から入っている）。入れられない場合、図の日本語が□になるだけでレンダリング自体はできる |
| cadquery が入らない | Python のバージョンに合う版が無いことがある（3.10〜3.12 が確実）。入らなくても STL のモックと確認ページは使える。STEP が要るときは conda（`conda install -c conda-forge cadquery`）を試す |
| Windows で `python` が無い・Microsoft Store が開く | python.org の Python 3.12（x64）か `winget install -e --id Python.Python.3.12` で入れ、AI のアプリを開き直してから `py -3.12 scripts/setup.py` |
| ARM64 の Windows | x64 版の Python（python.org の「Windows installer (64-bit)」）で実行する（ARM64 版の Python では setup.py が止めて案内する） |
| Windows で「DLL load failed」「読み込めません」 | Microsoft Visual C++ 再頒布可能パッケージを入れる：`winget install -e --id Microsoft.VCRedist.2015+.x64` |
| Windows で cadquery・cascadio が入らない（Python 3.13 以降） | Python 3.12 で仮想環境を作り直す：古い仮想環境のフォルダ（`~/.monozukuri/venv`）を消してから `py -3.12 scripts/setup.py` |
| Windows でファイルが見つからない・書けない（プロジェクトが OneDrive の中、パスが長い） | プロジェクトを `C:/work/` のような浅い場所に置く |
| Windows で「仮想環境を作れませんでした」と出て、確認ページのサーバーが動いている | `<python> <scripts>/serve_review.py <プロジェクト> --stop`（`<scripts>` は monozukuri-review-page スキルの `scripts/`）で止めてから、もう一度実行する |
| AI のサンドボックスでダウンロードや `~/` への書き込みが止められる（Codex の既定の設定など。mac・Windows とも） | setup.py はネットワークと、`~/.monozukuri/`・`~/.cache/monozukuri/` への書き込みが要る。ユーザーの許可を得て、サンドボックスの外で実行する（またはユーザーに、手順2のコマンドを setup.py の絶対パスにして実行してもらう） |
| テストレンダリングがタイムアウト | WebGL がソフトウェアレンダリング（SwiftShader）で遅い環境。もう一度だけ実行し、それでもだめなら幅を小さく（`--width 1200`） |

## 置き場所
- three.js と環境の記録は `~/.cache/monozukuri/`（`MONOZUKURI_CACHE` で変更可）。`~` は、Windows ではユーザーのフォルダ（`C:/Users/<名前>`）。
- 環境の記録 `env.json` に日本語フォントの場所と、使う Python（`python`。Windows では区切りを / にした `python_posix` も）が入る。比較画像・断面図はそのフォントを使う。
- macOS と Windows の Python のパッケージは `~/.monozukuri/venv`（プロジェクトの外。`--venv` で変更可）。Python は mac が `bin/python`、Windows が `Scripts/python.exe`。
