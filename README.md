# monozukuri

レーザー加工・3Dプリントのものづくりで、**立体のモック → 確認ページ → フィードバック → 次の版** を速く回すための Claude プラグイン。
モックは形と比率を決めるための粗い立体で、最終形は Fusion などで人がモデル化する前提です。モデル化した結果（STL / STEP）も同じ確認ページで見比べられます。

## できること

- **setup**：描画・断面・比較に必要なもの（shapely、manifold3d、trimesh、cascadio、playwright＋Chromium、three.js、日本語フォント）をまとめて入れ、テスト描画まで確かめる
- **new-project**：寸法ファイル（形の寸法＋加工の値と信頼度）、モック生成、試し片の生成、描画・断面・比較・寸法表のスクリプト、段階チェックリスト、引き継ぎ資料、Git 設定の雛形を作り、最初のモックを描く
- **review-page**：モックや人が作ったモデルを描画して前の版と比べ、プロジェクトごとの確認ページに版を追加して公開する。ページに書かれたフィードバックを Claude が読み、反映したら返信を付ける

デジタルファブリケーションの技術要件（レーザーのカーフとはめあい、FDM のクリアランス・インサート・形の限界、データ形式と単位、パラメトリック設計と版管理、組み立てと仕上げ、レーザーで切ってはいけない材料）を、出典つきの参照資料として同梱しています。中心の考え方は「公開されている数値は初期値。試し片で自分の機材の値を測って使う」です。

詳しくは [plugins/monozukuri/README.md](plugins/monozukuri/README.md)。

## 入れ方

**Claude Code**
```
/plugin install monozukuri --marketplace Pinticketaro/monozukuri
```
または
```
/plugin marketplace add Pinticketaro/monozukuri
/plugin install monozukuri@pinticketaro
```

**Claude アプリ（デスクトップ・Web）**
[Releases](https://github.com/Pinticketaro/monozukuri/releases) の `monozukuri.plugin` をダウンロードし、チャットに添付して追加する。

## 構成

```
.claude-plugin/marketplace.json   マーケットプレイスの定義
plugins/monozukuri/               プラグイン本体
  skills/setup/                   環境セットアップ
  skills/new-project/             雛形・試し片・技術要件の参照資料
  skills/review-page/             描画・比較・確認ページ・フィードバック
```

## 注意

- 技術要件の数値は、出典ごとに【実測】【指針】【規格】【経験則】を区別して載せていますが、どれも自分の機材での確認が前提です。
- レーザー加工の材料の可否はラボ（機械）ごとに異なります。所属ラボのルールを優先してください。

## ライセンス

MIT
