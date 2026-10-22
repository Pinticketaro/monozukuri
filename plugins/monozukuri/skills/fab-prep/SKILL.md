---
name: fab-prep
description: >
  This skill should be used when the user asks to "加工データを書き出して", "レーザー用のSVG/DXFにして",
  "カーフ補正して", "3MFにして", "製作前にチェックして", "この形で刷れる？切れる？", "オーバーハングを見て",
  "部分試作を切り出して", "この角だけ刷りたい", "USBの所だけ試したい", or is about to cut or print a
  monozukuri project (laser cutting, FDM 3D printing) from a mock or a human-made model (STL/STEP).
  Checks the model against digital-fabrication requirements and the registered machines (material safety,
  hole-to-edge distance, line spacing, wall thickness, overhangs, bridges, bed size), exports laser SVG/DXF
  with kerf compensation and FDM 3MF, and cuts out a region for a partial prototype.
metadata:
  version: "0.4.0"
---

# 加工の準備（製作前チェック・加工データ・部分試作）

4つの関所の後半を受け持つ。**部分試作**（一部分だけ先に作って実物と合わせる）と**本番**（全体を切る・刷る）の手前で、
形を技術要件と自分の機材に照らし、機械に渡すデータを作る。

スクリプトはこのスキルの `scripts/`（new-project で作ったプロジェクトなら `tools/` にも同じものがある）。
- `fab_check.py`：製作前チェック → `out/<版>/check/`
- `export_fab.py`：加工データ → `out/<版>/fab/`
- `cut_region.py`：部分試作の切り出し → `out/<版>/partial/<名前>/`
- `fabkit.py`：共通の部品（直接は使わない）

環境が足りないとき（import エラー、three.js がない、ezdxf がない）は先に setup スキルを実行する。
判断の根拠は new-project スキルの `references/fab-requirements.md`・`fab-safety.md`。

## 前提：部品ごとの「作り方」
どのスクリプトも、部品が **laser（レーザーで切る板）／fdm（3Dプリント）／none（既製品・中身。加工しない）** のどれかを知る必要がある。
- モック：寸法ファイルの `meta.parts` に書く（雛形に例がある）。`mock.py` が `scene.json` に写す。
  ```json
  "parts": {"top_plate": {"process": "laser", "material": "アクリル", "t": "t_top"},
            "frame":     {"process": "fdm", "material": "PLA", "print": {"flip": true}},
            "content":   {"process": "none"}}
  ```
  `t` は板厚のキー（fab の `t_*`）、`print` は刷る向き（`flip` で上下を返す、`rot: [x, y, z]` 度）。
- 人が作ったモデル（Fusion などの STL / STEP）：`out/vNN/scene.json` の部品に同じ項目を書く。
- 書いていない部品は形から推定し（薄くて上下の断面が同じなら laser）、結果に「推定」と出る。**推定のまま本番データを作らない**。ユーザーに確かめて書き足す。
- 0.3 以前に作ったプロジェクトには `meta.parts` が無い。最初に一度、部品のキー（`scene.json` の key）ごとに書き足す（版を上げる）。

## 手順

### 1. 製作前チェック（まずこれ）
```bash
python3 tools/fab_check.py vNN --render          # プロジェクトの tools から
python3 <scripts>/fab_check.py --root <プロジェクト> vNN --render
python3 <scripts>/fab_check.py --root <プロジェクト> --scene out/vNN/scene.json   # 人が作ったモデル
```
- `check/check.md` に NG／注意／確認 の表、`check_laser.png`・`check_fdm.png` に番号の付いた図、`--render` で `check_3d.png`（3Dプリント部品を刷る向きで、橙＝45°超のオーバーハング、紫＝天井・ブリッジ、赤＝薄い壁）。
- **図は Read で1回ずつ見る**。印の位置が問題の所と合っているか確かめてから伝える。
- ユーザーへは NG と注意を短く、直し方の案と一緒に。例：「角R8のせいでネジ穴の中心から縁まで4.5mm（基準5.1mm）。hole_inset を 7 にするか、角Rを 5 にする」。
- 直すのは寸法ファイルを1つ上の版にして（1つの版で変える条件は1つ）、モック → チェックをやり直す。
- 「確認」は人が決めること（ラボ次第の材料、まだ初期値の値、ボルト穴の等級など）。初期値が残っていれば試し片へ（new-project の手順5）、機材が未登録なら machines スキルへ案内する。
- 確認ページに載せるときは、`check_*.png` を manifest の `images` に group「製作前チェック」で入れ、NG・注意を `summary` か `notes` に書く。

チェックが見ていないもの：はめあい・取り合い（部分試作で）、材料の可否の最終判断（所属ラボのリスト）、モデル化で人が付ける細部。

### 2. 部分試作の切り出し（3つめの関所）
全体を作る前に、取り合いが怪しい所（USB の切り欠き、ネジ受け1つ、中身の角、分割の継ぎ目）だけを作って実物と合わせる。
```bash
python3 tools/cut_region.py vNN --list                                  # 部品ごとの範囲（mm）を見る
python3 tools/cut_region.py vNN --name usb --around 80,52 --size 30,20  # 点のまわり（高さを省くと全高）
python3 tools/cut_region.py vNN --name corner --box 60,30,0,95,60,25    # 箱で
python3 tools/cut_region.py vNN --region usb                            # 寸法ファイルの meta.regions.usb
```
- 座標はモデルのまま（平面図・断面図の目盛りと同じ）。場所は平面図（`slices.py --plan`）を見て決める。何度も使う範囲は寸法ファイルの `meta.regions` に `{"usb": {"box": [x0,y0,z0,x1,y1,z1], "note": "USB-C の切り欠き"}}` で残す。
- 加工しない部品（中身など）は既定で除く。合わせの確認に要るなら `--with-none`。
- `preview.png`（全体の中のどこか）と `pieces.png`（切り出した部品）を Read で見てから渡す。
- 出力：部品ごとの STL、元に STEP があれば正確に切った STEP、レーザーの板があればその部分の SVG / DXF と 3MF（`fab/`）、`partial.md`（確かめること）。
- 作ったら写真（定規と一緒に）を `photos/` に、測った値を `measurements/実測.md` に。確認ページに stage「部分試作」の版として載せてよい。

### 3. 加工データの書き出し（本番）
```bash
python3 tools/export_fab.py vNN                # 寸法ファイルの kerf でカーフ補正
python3 tools/export_fab.py vNN --no-kerf      # 加工ソフト（LightBurn の Kerf Offset など）で補正するとき
```
- レーザー：材料・板厚ごとに `laser_<材料>_<板厚>mm.svg / .dxf / .png`。単位 mm（SVG は width/height に mm、DXF は $INSUNITS=4）。外形は外へ・穴は内へ k/2 ずらす。赤＝切断、部品ごとに内側の穴 → 外形の順。機材の加工範囲に並べ、入らなければシートを分ける。
- 3Dプリント：部品ごとに `fdm_NN_<キー>.3mf`（mm）。刷る向き（`print`）にしてベッドの上に置く。
- **カーフ補正はデータか加工ソフトの一方だけ**。どちらにしたかをユーザーに伝える。
- `fab/fab.md` の「読み込んだら確かめる寸法」（いちばん大きい輪郭の大きさ）を必ず伝える。加工ソフトで違えば単位・解像度の取り違え（1/25.4、1.067倍、1.333倍）。
- **モックから書き出したデータは形を確かめるためのもの**。本番は、人がモデル化して確かめたモデル（STEP 推奨）から書き出す。モックから本番データを求められたら、そう伝えたうえで、チェックに NG が無く加工の値が実測なら書き出してよい。
- kerf が初期値のまま、または NG が残っているときは、書き出す前にそれを伝える。
- 渡すときは SVG・DXF・3MF・並べた図の PNG を SendUserFile で（PNG は render、データは attach）。加工に送ったらコミットしてタグ（`cut-1`、`print-1`）。

## 決まり
- 単位は mm、座標はモデルのまま。読み込むたびに既知の寸法を1つ確かめる（単位の関所）。
- 「推定」「初期値」「未登録」は隠さずユーザーに伝える。値を勝手に実測扱いにしない。
- レーザーの材料は、全面禁止なら止めて別の材料を提案、ラボ次第なら所属ラボのリストで確かめるよう伝える（machines スキルで機材にラボの決まりを登録しておくと、次から自動で判定される）。
- 出力は版のフォルダ（`out/vNN/…`）に作る。前の版の出力は上書きしない。

## 報告
2〜4文：NG と注意の要点と直し方の案、書き出したファイルと確かめる寸法、次の関所（部分試作か本番）。表の中身は繰り返さない。
