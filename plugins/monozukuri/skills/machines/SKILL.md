---
name: machines
description: >
  This skill should be used when the user says "機材を登録して", "うちのプリンタ／レーザーを登録", "測った値を保存して",
  "試し片の結果を記録して", "前に測ったカーフを使って", "このプロジェクトに機材の値を入れて", "ラボではMDFは切れる",
  or after test coupons of a monozukuri project have been measured. Keeps one profile per machine (bed or work
  area, nozzle, the lab's material rules, and measured values such as kerf, clearances and insert holes per
  material and thickness), and applies them to a project as a new parameter version so the next project starts
  from measured values instead of published defaults.
metadata:
  version: "0.4.0"
---

# 機材プロファイル

公開されている数値は初期値で、カーフやクリアランスは機械ごとに「圧入とガタの差」ほど違う。一度測った値は機材に結び付けて残し、
次のプロジェクトでは初期値ではなく測った値から始める。スクリプトは `scripts/machines.py`（`--help` で使い方）。

## 機材プロファイルの中身
1台＝1つの JSON。`kind` が `laser` か `fdm`。
- `spec`：fdm は `bed_x`・`bed_y`・`bed_z`・`nozzle`、laser は `work_x`・`work_y`・`source`（"CO2 40W"、"ダイオード 10W" など）
- `rules`：ラボの材料の決まり。`allowed`（ラボ次第の材料のうち許可されているもの：MDF など）、`banned`（このラボで禁止）
- `values`：測った値。`key`（寸法ファイルの fab と同じ名前：`kerf`・`clr_fit`・`clr_slide`・`hole_comp`・`insert_hole` など）、`value`、`material`、`thickness`（レーザーの呼び板厚）、`settings`（出力・速度・層・温度）、`date`、`source`（どの試し片の何番か）、`n`（測った値）。古い値も残し、適用ではいちばん新しい日付を使う

板厚（`t_*`）は機材ではなくシートの値なので記録しない。シートごとに測る。

## 置き場所を決める（最初に一度）
既定は `~/.monozukuri/machines/`（`--lib` か環境変数 `MONOZUKURI_MACHINES` で変更）。
- **クラウドの作業環境はセッションが終わると消える**。ユーザーの PC がつながっていれば、PC のフォルダ（例：`~/monozukuri-machines`）に置いて、そこを `--lib` に渡す（PC 側のシェルで動かすか、ファイルを行き来させる）。つながっていなければ、作った JSON を SendUserFile で渡し、次に使うときに添付してもらう。GitHub のリポジトリに置く手もある（ユーザーが望めば）。
- どこに置いたかをユーザーに1文で伝える。
- 適用したプロジェクトには写しが `measurements/machines/<ID>.json` に入るので、プロジェクトだけでも再現できる。プロジェクトから機材の置き場へ戻すときはこの写しを使える。

## 手順

### 1. 登録する
足りない情報だけ AskUserQuestion でまとめて聞く：機種、造形範囲／加工範囲、ノズル径、置いてある場所、（レーザーなら）所属ラボで許可・禁止されている材料。
```bash
python3 scripts/machines.py new home-ender3 --kind fdm --name "自宅の Ender-3 V2" --spec bed_x=220 bed_y=220 bed_z=250 nozzle=0.4
python3 scripts/machines.py new lab-co2 --kind laser --name "ラボの CO2" --spec work_x=600 work_y=400 source="CO2 40W" --allow MDF --ban POM
```
ID は英数字と `-` `_`（ファイル名になる）。ラボの決まりは後から `rules <ID> --allow … --ban …` で足せる。

### 2. 測った値を記録する
試し片（new-project の `tools/coupons.py`）を切って・刷って測ったら記録する。
```bash
python3 scripts/machines.py record lab-co2 --key kerf --value 0.17 --material アクリル --thickness 3 \
  --settings "出力60% 速度15mm/s" --source "laser_3mm.svg カーフ四角" --n 0.16,0.17,0.18
python3 scripts/machines.py import-csv home-ender3 --csv <プロジェクト>/measurements/試し片記録.csv --material PLA
```
- `import-csv` は記録表の「選んだ値」と「反映先キー」がある行を取り込む。材料・板厚は行ごとに書けないので `--material`・`--thickness` で渡す（材料が混ざっていれば材料ごとに分けて実行するか、`record` で1つずつ）。
- 材料はメーカーや種類まで書くと、あとで食い違いに気づける（「アクリル（キャスト、アクリサンデー）」「PLA（eSUN）」）。
- 値の定義：カーフ k は切断溝の**全幅**（オフセットは k/2）、クリアランスは**片側**。コームの結果は `slot_delta`（板厚との差）として記録できる。

### 3. プロジェクトに適用する
```bash
python3 scripts/machines.py apply --project <プロジェクト> --laser lab-co2 --fdm home-ender3 --dry-run   # まず確かめる
python3 scripts/machines.py apply --project <プロジェクト> --laser lab-co2 --fdm home-ender3
```
- いちばん新しい寸法ファイルを1つ上の版にコピーし、機材・材料（・板厚）が合う値を `status: 実測`、`basis` に機材と日付と試し片を書いて置き換える。`meta.machines` に機材 ID、fdm の造形範囲を `bed_x`・`bed_y` に入れる。
- 材料は寸法ファイルの `meta.parts`（作り方と材料）から決める。決まらないときは `--material`・`--thickness`。
- 「未反映」に出た値（この機材・この材料ではまだ測っていない）は、試し片で測るようユーザーに伝える。
- 適用したら、その版でモックを作り直し、fab-prep スキルの製作前チェックを回すと、機材の範囲・ノズル径・ラボの決まりで判定される。`LOG.md` に「機材の値を適用」と書く。

## 決まり
- 他人の機材・他の材料・他の設定で測った値は持ち込まない。条件（機械・材料・出力・速度・焦点・ノズル・温度）が変わったら測り直して記録する。
- 値を推測で記録しない。記録するのはユーザーが測った値だけ。
- レンズ交換・ノズル交換・大きな調整をしたら、古い値はそのまま残し、新しく測った値を足す（日付で新しい方が使われる）。

## 報告
1〜2文：登録・記録・適用したこと（反映した値と、まだ測っていない値）と、置き場所。
