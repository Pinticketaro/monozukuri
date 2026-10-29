# テストピースで決めた数値だけでカットし、印刷する

モック→確認→人によるCAD化→製作の流れを速く失敗なく回すいちばんの決め手は、公開されている数値を「初期値」と割り切ることです。そのうえで、製作の前にテストピースで自分の機材の値を測り、CADのユーザーパラメータへ戻す閉ループを作ります。測る値は、カーフ、はめあい代、穴の補正量、インサート穴径、そして実際の板厚です。この手間を省けない理由は、出典どうしのずれが圧入とすきまばめの差と同じくらい大きいことにあります。3 mmアクリルのCO2カーフは、Ponokoの実測で0.125 mm、CutLaserCutの指針で0.18 mmです。FDMの圧入クリアランスは、同じ大学ラボの表でもBambu H2Dで0〜0.05 mm、Ultimaker S7で0.2 mmと4倍以上違います。二つ目の決め手は単位の関所です。STLは単位を持たないので、25.4倍（インチ）や1000倍（メートル）の事故が起きます。読み込むたびに既知の寸法を一つ測れば、これは確実に止められます。三つ目は安全面で、PVCなどの塩素系材料、ポリカーボネート、ABS、PTFEなどはどの出典でも禁止です。一方でMDF、POM、EVA、ポリウレタンフォーム、PETGは、ラボによって可否が分かれます。プラグインは保守側の既定値を持ったうえで、「所属ラボのリストを確認する」手順を必須にすべきです。組み立てでは、ミスミ仕様で3 mmアクリル板が±0.7 mmという板厚公差が積み上げを支配します。そこで、実測した板厚から印刷部品の寸法を決め、ばらつきは圧縮フォームで吸収する設計にします。

**区分の表記**：本レポートでは、数値ごとに次の区分を付けます。【実測】は出典が自分で測った値です。【指針】はメーカー、加工サービス、大学ラボが公表している表や推奨値です。JIS/ISOは【規格】と書きますが、扱いは指針と同じです。【経験則】は測定の裏付けがない実務上の目安です。【計算】は他の数値から算術で出した値で、信頼度は元の値の区分に従います。「推論」と書いたものは、出典を組み合わせて導いた設計判断です。

## 4つの関所で流れを区切ると手戻りが局所化する

調査した出典の中に、物理製品のモックから製作までの段階定義を直接与えるものはありませんでした。ただし、Fab Academyと大学のファブラボが共通して行っている手順から、次の関所構成が導けます（推論）。第1関所は**モック**で、段ボール、低インフィルの粗い印刷、Blenderのレンダーなどを使い、大きさ、比率、手触り、おおまかな配置を確認します。第2関所は**テストピース（クーポン）**で、この機械とこの材料でのカーフ、クリアランス、インサート穴径を決めます。第3関所は**部分機能スライス**で、ケースの一角にUSB切り欠きとネジボスを一つ入れた程度のものを作り、実物部品との取り合いを確かめます。最後が**本番製作**です。カーフとはめあいのコーム試験は、Fab Academyの「computer-controlled cutting」週で毎年課される標準の課題で、2026年度のコホートでも続いています ([Fab Academy 2026 Rwanda](https://fabacademy.org/2026/labs/rwanda/Group_Assignment/computer_controled_cutting.html))。All3DPとUAL CCIは、どちらも「他人の公差値に頼るな」「本番の前に必ず小さなサンプルを試せ」と明言しています ([All3DP](https://all3dp.com/2/3d-printing-tolerances-test-fdm/)、[UAL CCI](https://wiki.cci.arts.ac.uk/books/digital-fabrication-lab/page/design-the-clearance-and-tolerance))。

モックから人によるCAD化への受け渡しでは、Blenderなどのメッシュ（OBJ/STL）を**参照用の下敷き**としてだけ使い、Fusionでは描き直すのが安全です（推論）。CadQueryのドキュメントは「STLは非可逆な形式」と明記していて、パラメトリックに編集するならSTEPを使うよう勧めています ([CadQuery](https://cadquery.readthedocs.io/en/latest/intro.html))。確認とフィードバックの段階では、GitHubの3Dビューアが役に立ちます。10 MB以下のSTLなら、加工に送るファイルそのものをブラウザで回して見せられるので、スクリーンショットではなく実データでレビューできます ([GitHub Docs](https://docs.github.com/en/repositories/working-with-files/using-files/working-with-non-code-files))。ただし、はめあいや手触りはレンダーでは分からないので、そこはテストピースと部分スライスで確認します。

## レーザー加工の公開値は出発点にすぎない

### カーフはCO2で0.12〜0.20 mm、ダイオードは出典ごとに一桁ずれる

デスクトップCO2で3 mm材をカットしたときのカーフは、およそ0.12〜0.20 mmです。板厚が増えると広がり、10〜12 mmでは約0.3 mmになります。下の表は、プラグインの初期値（seed）として使える公開値の一覧です。

| 材料・板厚 | 値（mm、全幅） | 区分 | 出典 |
|---|---|---|---|
| アクリル 3 / 5 / 6 mm（40 W CO2、出力98） | 0.125 / 0.130 / 0.140 | 実測 | [Ponoko](https://www.ponoko.com/blog/ponoko/figuring-out-kerf-for-precision-parts/) |
| 合板 3 mm／ハードボード 3 mm | 0.20 / 0.19 | 実測 | [Ponoko](https://www.ponoko.com/blog/ponoko/figuring-out-kerf-for-precision-parts/) |
| アクリル 1–3 / 5–8 / 10–15 mm | 0.18 / 0.21 / 0.30 | 指針 | [CutLaserCut](https://cutlasercut.com/drawing-resources/expert-tips/laser-kerf/) |
| バーチ合板 3 / 6 / 12 mm | 0.20 / 0.22 / 0.30 | 指針 | [CutLaserCut](https://cutlasercut.com/drawing-resources/expert-tips/laser-kerf/) |
| MDF 3 / 6 / 12 mm | 0.16 / 0.20 / 0.28 | 指針 | [CutLaserCut](https://cutlasercut.com/drawing-resources/expert-tips/laser-kerf/) |
| 段ボール 4.40 mm（速度2.5／出力100） | 部品寸法の減り 0.11–0.20、速度0.5では0.57 | 実測→計算 | [MIT CBA](https://fab.cba.mit.edu/classes/863.20/CBA/people/group/reports/laser.html) |
| 段ボール（出力・速度を振った試験） | 0.2–0.375 | 実測 | [Fab Academy Kamakura](https://fabacademy.org/2019/labs/kamakura/assignments/week04/) |
| 10 Wダイオード、3 mm MDF、3パス | 0.05 | 実測（1名・未検証） | [Box Studio](https://box-studio.cc/blog/2026-05-en-kerf-reference-table-by-machine) |
| ダイオード一般 | 0.1–0.4、別の箇所では0.15–0.50。X/Y方向で0.05–0.10の差 | 経験則（同一ページ内で矛盾） | [EngraverHQ](https://engraverhq.com/guides/laser-cutter-kerf/) |

この表から読み取るべきことは三つあります。一つ目に、**同じ機種クラスでも3 mmアクリルで0.06 mmの差がある**（Ponoko 0.125 vs CutLaserCut 0.18）ことです。カーフ補正なしでスロットとタブを同じ寸法で描くと、合わせ目のすきまは約2×カーフになります ([Vectosolve](https://vectosolve.com/blog/laser-kerf-press-fit-guide))。この0.06 mmの差は、圧入とガタつきの境目にそのまま影響します。二つ目に、**速度が遅いとカーフが大きく広がる**ことです。MITの測定では、速度を2.5から0.5に落とすと減りが約3倍になりました。カーフは材料だけでなく、設定の組み合わせに属する値です。三つ目に、**ダイオードの値は信頼できない**ことです。0.05 mmの実測と0.1〜0.5 mmの経験則が食い違う理由は、どの出典も確認していません。ダイオードのカーフはV字形になり、カット面の下端だけを測ると狭く見える、というのは一つの仮説です。CutLaserCutとPonokoは、カーフがシート内の位置、直線と曲線、X方向とY方向で変わることも挙げています ([CutLaserCut](https://cutlasercut.com/drawing-resources/expert-tips/laser-kerf/))。したがってプラグインは、カーフを（機械、材料、実測板厚、出力・速度・パス数、レンズ・焦点）の組ごとに保存し、条件が一つでも変われば再測定を促すべきです。

**定義の食い違い**にも注意が要ります。100 mm角をカットして99.7 mmになった場合、EngraverHQは「カーフ0.3 mm」と書き、Box Studioは「(100−実測)/2 = 片側0.15 mm」と書きます ([EngraverHQ](https://engraverhq.com/guides/laser-cutter-kerf/)、[Box Studio](https://box-studio.cc/blog/2026-05-en-kerf-reference-table-by-machine))。Kamakuraは「(穴幅−カットアウト幅)/2」で計算しています。式の上ではこれはカーフの全幅にあたりますが、出典自身は「片側」と表記しています。プラグインは**k＝カーフの全幅、オフセット量＝k/2**と定義を固定し、入力画面にもそう書くべきです。補正は閉じた輪郭に対してk/2ずつ行い、外形は外へ、穴は内へずらします。LightBurnの「Kerf Offset」には半分の値を入れます ([EngraverHQ](https://engraverhq.com/guides/laser-cutter-kerf/))。補正値を入れたら小箱をテストカットします。緩ければ値を下げ、叩き込まないと入らなければ上げ、0.02〜0.05 mm刻みで追い込みます。何も変えていないのに合いがずれ始めたら、まずレンズを疑います ([Box Studio](https://box-studio.cc/blog/2026-05-en-kerf-reference-table-by-machine))。

### はめあいはコームで決め、アクリルは圧入しない

| 項目 | 値 | 区分 | 出典 |
|---|---|---|---|
| 段ボール 4.40 mm（実測）のスロット幅 | 4.25–4.30が最適（板厚より0.10–0.15狭い）、4.20は固いが可、4.60はガタつく | 実測 | [MIT CBA](https://fab.cba.mit.edu/classes/863.20/CBA/people/group/reports/laser.html) |
| 段ボール 3.0 mmのスロット幅 | 2.70が最適、2.65は固め、2.50は非常にきつい。別チームは2.5が最適 | 実測 | [Fab Academy Kamakura](https://fabacademy.org/2019/labs/kamakura/assignments/week04/) |
| 合板の圧入 | 約1カーフきつくする。すきまばめは呼び寸法のまま（約2×カーフのすきま） | 経験則 | [Vectosolve](https://vectosolve.com/blog/laser-kerf-press-fit-guide) |
| 線どうしの間隔 | 0.5 mm未満だと焼け落ちる | 指針 | [CutLaserCut](https://cutlasercut.com/drawing-resources/expert-tips/laser-kerf/) |
| 細部の幅 | 1 mm未満は脆く反りやすい。カットアウト幅は板厚以上 | 指針 | [CutLaserCut](https://cutlasercut.com/drawing-resources/expert-tips/laser-kerf/) |
| 穴径と板厚の比 | 板厚の50%以上（同じ記事の別の箇所では60%以上） | 指針（記事内で矛盾） | [SendCutSend](https://sendcutsend.com/blog/how-to-export-a-dxf-from-inkscape-for-laser-cutting/) |
| アクリル切り欠きの内角R | 0.5 mm以上（0.26 mmでも効果が目に見えた） | 経験則 | [Ponoko](https://www.ponoko.com/blog/wp-json/wp/v2/posts/50031) |
| リビングヒンジ（3 mm材） | リンク幅＝板厚。90°曲げには23リンク以上が必要で幅69 mm、内側R 44 mm | 計算 | [DefProc](https://www.defproc.co.uk/analysis/lattice-hinge-design-minimum-bend-radius/) |

最適なスロット幅は、MITでは板厚より0.10〜0.15 mm狭い値、Kamakuraでは0.3〜0.5 mm狭い値でした。この差は、描いた寸法の中にカーフ補正の有無と各機械のカーフがそのまま含まれていることから来ています。つまり「スロットを何mm狭く描くか」は持ち運べる数値ではありません。プラグインは、**板厚を実測し、スロットを呼び寸法T±0.20 mmの範囲で0.05 mm刻み、約9本並べたコームを本番と同じシートでカットする**手順を標準にすべきです（MITの方式から導いた推論）。アクリルについては、圧入の実測データが見つかりませんでした。Ponokoは、アクリルがボルトの締め過ぎで内角から割れると警告しています。したがってアクリルは**すきまばめ＋ネジまたは接着**を既定とし、圧入は推奨しません（推論）。

### 実際の板厚はシートごとに測る

Trotecによれば、キャスト（GS）アクリルの板厚ばらつきは約±15%、押出（XT）は±5%です ([Trotec](https://troteclaser.com/en-ca/learn-support/helpcenter/material-handling-acrylic))【指針】。ミスミの筐体用アクリル板は3 mmで±0.7 mm、5 mmで±0.8 mmで、押出のほうが精度が良いとしています ([ミスミ](https://jp.misumi-ec.com/vona2/s_cate/アクリル板2mm/))【指針】。±0.7 mmは3 mmに対して約±23%にあたり、Trotecの±15%（約±0.45 mm）より広くなります。出典によって幅が違いますが、どちらも「呼び寸法で設計するな」という結論で一致しています。Glowforgeのユーザーは、同じ銘柄の2枚の間に0.18 mmの差を実測しています ([Glowforge community](https://community.glowforge.com/t/proofgrade-headaches/43494))【実測】。プラグインは、スロット幅の計算に**ノギスで測った実板厚の入力を必須**とし、呼び寸法だけでは計算を拒否する設計にすべきです。

材料の選び方では、Trotecの性格付けが判断材料になります。キャストは両面ともきれいにカットでき、彫刻すると白く曇ります。押出はカット面が炎で磨いたようになりますが、彫刻は推奨されず、カット時の周波数は5 kHz以下にします ([Trotec](https://troteclaser.com/en-ca/learn-support/helpcenter/material-handling-acrylic))。キーボードプレートのように彫刻とネジ穴が多い部品ではキャストを、積層ケースのように板厚の揃いが大事なカット専用部品では押出を選ぶのが合理的です（推論）。

### 設定は試験グリッドで決め、メーカー条件は最低出力を確認する

Trotecのアクリルカットの指針は次のとおりです。出力は60 W以上、目安は板厚1 mmあたり約10 Wです。エアアシストは0.2 bar以下、6 mmを超える板では焦点を板厚の約1/3の深さに合わせます。周波数はキャストで5〜20 kHz、押出で5 kHz以下です。周波数が低すぎるとカット面にびびり跡が出て、速度が遅すぎると火災の危険が増します ([Trotec](https://troteclaser.com/en-ca/learn-support/helpcenter/material-handling-acrylic))【指針】。xTool P2は55 W、Glowforge Proは45 Wなので ([xTool](https://xtool.com/pages/xtool-p2-vs-glowforge))、デスクトップ機はTrotecの前提である60 Wを下回ります。この指針はそのまま使えず、自機で試験グリッドをカットして条件を決める必要があります。MITの段ボールの出力・速度・PPIスイープでは、PPI 175、出力60〜80、速度5.0以上のいずれかの条件でカットしきれませんでした ([MIT CBA](https://fab.cba.mit.edu/classes/863.20/CBA/people/group/reports/laser.html))【実測】。条件出しの手順は、板厚を測る→出力と速度のグリッドをカットする→きれいに抜ける最速の条件を選ぶ→その条件でカーフを測る→コーム→小さな組立品→本番、の順です（推論）。フォームは低出力、高速、空気圧を下げた複数パスでカットします。高い空気圧は薄いシートを持ち上げ、炎を煽ります ([Thunder Laser](https://www.thunderlaserusa.com/blog/laser-cut-foam))【指針、メーカー】。

加工範囲は、xTool P2が600×305 mm、Glowforge Proが495×297 mmです。どちらもパススルーに対応しています ([xTool](https://xtool.com/pages/xtool-p2-vs-glowforge))【指針、ベンダー比較ページ】。プラグインは、部品の外形に余白（推論で片側5〜10 mm）を足したものがベッドに収まるかを確認し、収まらなければ分割を提案すべきです。

## FDMは寸法・向き・ネジ受けの三つで失敗する

### クリアランスはプリンタごとに4倍違うので、3段のテストピースで決める

| 用途 | 値（mm） | 区分 | 出典 |
|---|---|---|---|
| スナップ／すべりのクリアランス、PLA/PETG | 0.2–0.3（屋外0.25） | 経験則（メーカーブログ） | [QIDI](https://qidi3d.com/ja/blogs/print-lab/3d-printed-snap-fit-joints-clearance-guide) |
| 同、ABS/ASA/ナイロン | 0.3–0.5（ASAを密閉チャンバーで印刷する場合0.40） | 経験則 | [QIDI](https://qidi3d.com/ja/blogs/print-lab/3d-printed-snap-fit-joints-clearance-guide) |
| 圧入／中間ばめ／すきまばめ（0.4ノズル） | ≤0.05 / 0.08–0.2 / ≥0.25 | 経験則 | [All3DP](https://all3dp.com/2/3d-printing-tolerances-test-fdm/) |
| Bambu H2D：一般／着脱／可動／圧入／タッピング下穴 | 0.1 / 0.15–0.2 / ≥0.2 / 0–0.05 / −0.2–0 | 指針（大学ラボ） | [UAL CCI](https://wiki.cci.arts.ac.uk/books/digital-fabrication-lab/page/design-the-clearance-and-tolerance) |
| Ultimaker S7：一般／着脱／可動／圧入 | 0.2 / 0.3 / ≥0.4 / 0.2 | 指針（大学ラボ） | [UAL CCI](https://wiki.cci.arts.ac.uk/books/digital-fabrication-lab/page/design-the-clearance-and-tolerance) |
| 垂直穴の拡大補正（CAD） | +0.2（4 mm穴を4.2 mmで描く） | 経験則 | [Pollen AM](https://www.pollen.am/design_for_3d_printing_holes) |
| Bambu Studio「X-Y hole compensation」 | PLA 0.05、PETG/ABS 0.1、ナイロン0.15 | 指針（記事中の例と符号が矛盾） | [Bambu Wiki](https://wiki.bambulab.com/en/knowledge-sharing/3d-prints-shrinkage) |

同じ大学ラボの表でも、圧入の値はH2Dで0〜0.05 mm、S7で0.2 mmと大きく違います。**Ender-3（0.4 mmノズル、ボーデン）でどちらに近い値になるかは、どの出典にもありません**。精度の高いH2Dの値より、S7の緩めの値（一般0.2 mm）から始めるのが妥当です（推論・未検証）。決め方はQIDIの方法がいちばん速く、設計クリアランス、+0.1 mm、−0.1 mmの3段のテストピースを印刷して選びます。30分以内に使える値が見つかるとされています ([QIDI](https://qidi3d.com/ja/blogs/print-lab/3d-printed-snap-fit-joints-clearance-guide))。All3DPの方法では、校正キューブを3〜5個印刷し、各軸を同じ位置で3回以上測ります。最大と最小の差を初期クリアランスとし、その半分を±公差とします。例えば20.1/20.0/19.9 mmなら±0.1 mmです ([All3DP](https://all3dp.com/2/3d-printing-tolerances-test-fdm/))。

穴は、垂直方向の穴が小さく仕上がるのが共通の挙動です。Hubsは決まった補正量を示しておらず、精度が必要なら小さめに印刷してドリルで仕上げるよう勧めています ([Hubs](https://hubs.com/knowledge-base/how-design-parts-fdm-3d-printing))。補正は**スライサーの穴補正かCADのオフセットのどちらか一方だけ**で行います。両方かけると二重に補正されます（推論）。Bambu Wikiは記事内の作例で符号が食い違っているので、正の値で穴が広がるかどうかを1回印刷して確かめてから使います。収縮補正率は「実測÷設計×100」で求め、自動の円穴補正の対象は直径50 mm以下です ([Bambu Wiki](https://wiki.bambulab.com/en/knowledge-sharing/3d-prints-shrinkage))。

### 形状の限界は45°・5 mm・2×ノズルを使い、TDSの値は最良条件とみなす

Hubsは、オーバーハングは45°まで品質を落とさず印刷でき、5 mmを超えるブリッジは垂れやサポート跡の危険があるとしています ([Hubs](https://hubs.com/knowledge-base/how-design-parts-fdm-3d-printing))【指針】。一方BambuのTDSは、PLA Basicでオーバーハング55°・ブリッジ30 mm、ASAで約70°・約40 mmとしています ([Bambu PLA TDS](https://www.additive-x.com/shop/mpattachments/file/viewonline/id/494/product_id/2236)、[Bambu ASA TDS](https://polyalkemi.no/wp-content/uploads/2024/01/Bambu_ASA_Technical_Data_Sheet.pdf))【指針】。この食い違いは、TDSが専用プロファイルと強い冷却を使った最大値であることから来ています。オープンフレームのEnder-3では、Hubsの45°/5 mmを設計目標にすべきです。そのほかの規則は次のとおりです。壁はノズル径の2倍以上、0.4 mmノズルなら0.8 mmにします ([Pollen AM](https://www.pollen.am/design_for_3d_printing_holes))【経験則】。直径5 mm未満の垂直ピンは外周だけで構成されて弱くなります。ベッドに接する縁はフィレットではなく45°の面取りにすると、エレファントフットと反りが減ります。XY方向の角はノズル径程度の丸みが必ず付きます ([Hubs](https://hubs.com/knowledge-base/how-design-parts-fdm-3d-printing))【指針】。水平方向のネジ穴は、上側がオーバーハングになって垂れるので、ティアドロップ形にするか部品を90°回して印刷します ([Pollen AM](https://www.pollen.am/design_for_3d_printing_holes))。

強度については、BambuのTDS（ISO 527）でZ方向の引張強度がXY方向の84〜90%です。PLAは39対35 MPa、ASAは37対31 MPaです ([Bambu PLA TDS](https://www.additive-x.com/shop/mpattachments/file/viewonline/id/494/product_id/2236)、[Bambu ASA TDS](https://polyalkemi.no/wp-content/uploads/2024/01/Bambu_ASA_Technical_Data_Sheet.pdf))【実測】。ただしこれは理想的な試験片での値で、実際の部品では層の谷が応力集中点になります ([Hubs](https://hubs.com/knowledge-base/how-design-parts-fdm-3d-printing))。荷重は層に沿う向きで受けるように部品を配置します。HackSpace誌の非公式な曲げ試験では、外周を2本増やすほうが、インフィルを10%増やすより、フィラメント1 mあたりの強度向上が約2.5倍大きくなりました（0.25 m/kg対0.64 m/kg）。著者自身は一般化しないよう注意しています ([HackSpace](https://magazine.raspberrypi.com/articles/experiments-with-strong-3d-prints))【実測・非公式】。

### ヒートセットインサートの穴径は出典間で0.3 mm違う

| サイズ | インサート長 / 外径 / 穴径 / 最小壁（mm） | 区分 | 出典 |
|---|---|---|---|
| M2 | 3.0 / 3.6 / 3.2 / 1.3 | 指針 | [CNC Kitchen（3DJake）](https://www.3djake.com/cnc-kitchen/threaded-inserts-set-standard) |
| M2.5 | 4.0 / 4.6 / 4.0 / 1.6 | 指針 | 同上 |
| M3（標準／ショート） | 5.7・3.0 / 4.6 / 4.0 / 1.6 | 指針 | 同上、[ruthex M3S](https://3djake.com/ruthex/threaded-insert-m3s-100-pieces) |
| M4 | 8.1 / 6.3 / 5.6 / 2.1 | 指針 | 同上 |
| M5 | 9.5 / 7.1 / 6.4 / 2.6 | 指針 | 同上 |

ruthexのドリルセットの寸法はCNC Kitchenの表と一致します ([ruthex](https://www.3djake.ch/de-CH/ruthex/hss-bohrerset-fuer-gewindeeinsaetze))。食い違いがあるのはUW–Madisonの指針で、穴を「インサート外径より0.2〜0.4 mm小さく」とし、M3の例として外径−0.3 mmを挙げています ([UW–Madison ME Design Lab](https://medesignlab.me.wisc.edu/?p=162))。外径4.6 mmのM3では**CNC Kitchenの4.0 mmに対しUWは約4.3 mm**になります。CNC Kitchen自身もM3の試験で4.0〜4.4 mmの穴を3方向で試しています ([CNC Kitchen](https://www.cnckitchen.com/blog/tipps-amp-tricks-fr-gewindeeinsaetze-im-3d-druck-3awey))。印刷すると穴はさらに小さく仕上がります。このため、**インサート穴径は4.0〜4.4 mmのテストピースで自機に合わせて決める値**です。Printablesに専用の試験モデルがあります ([Printables](https://printables.com/model/1040630-threaded-insert-hole-tolerance-test))。こて温度も出典で分かれます。CNC Kitchenは印刷温度+10〜20 °C（PLAで約225 °C）、UWは+20 °C程度でPLAは240〜260 °Cとしています。共通する手順は次のとおりです。止まり穴はインサート長+1 mm、約90%まで溶かし込んでから平らな工具で面一に押さえ、15〜30秒冷まし、軸を面に垂直に保ちます。外周は2本ではなく4本、インフィルは25%以上にします ([CNC Kitchen](https://www.cnckitchen.com/blog/tipps-amp-tricks-fr-gewindeeinsaetze-im-3d-druck-3awey)、[UW–Madison](https://medesignlab.me.wisc.edu/?p=162))。ボスの外径は「穴径+2×最小壁」で求め、M3なら7.2 mm以上、M2なら5.8 mm以上になります【計算】。

### 材料はPLAの57 °Cを境に選び分ける

Bambu PLA BasicはHDT 57 °C（0.45 MPa）、Tg 60 °Cです。Bambu ASAはHDT 100 °C（0.45 MPa）、Vicat 106 °Cです ([Bambu PLA TDS](https://www.additive-x.com/shop/mpattachments/file/viewonline/id/494/product_id/2236)、[Bambu ASA TDS](https://polyalkemi.no/wp-content/uploads/2024/01/Bambu_ASA_Technical_Data_Sheet.pdf))【実測】。PETGの約69 °Cは販売店の要約値で、荷重条件が書かれていません ([Solid Print 3D](https://www.solidprint3d.co.uk/?p=67129))。Prusaは、ASA・ABS・PCには筐体（エンクロージャー）を推奨し、PLA・PETG・Flexには不要としています。ベッド温度はPLA 50〜60 °C、PETG 70〜90 °C、ASA 90〜110 °C、ABS 95〜110 °Cです ([Prusa KB](https://help.prusa3d.com/article/material-table_2324))【指針】。ABSはPLAより反りやすいとされています ([Hubs](https://hubs.com/knowledge-base/how-design-parts-fdm-3d-printing))。したがって、筐体のないEnder-3で300 mm級の平たい部品を印刷するなら、PLAかPETGを既定にします。ASAやABSは筐体の用意を前提条件にすべきです（推論）。室内の机上なら、PLAで熱の面は足ります。車内や窓際のように高温や紫外線にさらされる用途ではASAにします。反り対策のブリム幅や反り量と部品長の関係は、数値の出典が取得できませんでした。

## 単位を書き込める形式で受け渡し、読み込むたびに1寸法を測る

受け渡しの形式は、単位が誰に解釈されるかで選びます。3MFはXMLをZIPにまとめた形式で、model要素の`unit`属性（例：`unit="millimeter"`）に単位を明示し、材料、色、メタデータ、変換も含められます ([3MF Core Spec](https://github.com/slic3r/Slic3r/wiki/3MF-Document-Core-Specification))。PrusaSlicerとOrcaSlicerはプロジェクトの設定も3MFで読み書きします ([OrcaSlicer source](https://git.trueserve.org/PublicCodeMirror/OrcaSlicer-bambulab/src/commit/b7ae342e8e43bb7c35619518b2d6e223509b44a8/src/libslic3r/Format/3mf.cpp))。STEPは`SI_UNIT(.MILLI.,.METRE.)`のように単位をエンティティとして持ちますが、それを尊重するかどうかは読み込む側のツール次第です ([Salome forum](https://discourse.salome-platform.org/t/units-on-step-import/564))。STLは単位を持たず非可逆です ([CadQuery](https://cadquery.readthedocs.io/en/latest/intro.html))。PrusaSlicerは小さすぎるモデルを「インチのようだ」と推定して変換を持ちかけます。Blender 3.5でUnit Scaleを0.01にしていたユーザーが、2 mm厚の部品でこの警告を受けました。「Scene Units」にチェックを入れて書き出すと、0×0×0 mmになりました。この不具合は修正されないまま閉じられています ([Blender #106334](https://projects.blender.org/blender/blender/issues/106334))。Curaでも同様のサイズ違いが繰り返し報告されています ([Ultimaker community](https://community.ultimaker.com/topic/36539-import-blender-model-cura-convert-to-wrong-size))。

| 受け渡し | 推奨形式 | 理由・注意 |
|---|---|---|
| モック（Blender）→ Fusion | OBJ/STL、参照用の下敷きとしてだけ使う | メッシュは編集しない。Fusionで描き直す（推論） |
| Fusion → スライサー | 3MF（STLも可。その場合は寸法を確認） | 3MFは単位と設定を持てる ([3MF Spec](https://github.com/slic3r/Slic3r/wiki/3MF-Document-Core-Specification)) |
| Fusion → レーザー | スケッチからDXF、またはSVG。mmで | 色＝加工条件のチャンネル ([Fab Academy Kamakura](https://fabacademy.org/2019/labs/kamakura/assignments/week04/)) |
| CAD間・保管 | STEP | B-repで、単位を明示して持つ ([CadQuery](https://cadquery.readthedocs.io/en/latest/intro.html)) |

InkscapeからDXFを作るときは、次の点に注意します。単位は「表示単位」ではなく、ドキュメントのプロパティの「ドキュメント単位」で設定します。テキストはパスに変換し、ページ外の図形は保存時に消えるのでページ内に収めます。書き出しは「エクスポート」ではなく「名前を付けて保存」からDXF（R14）を選び、ダイアログでは基本単位を明示します。送る前に開いた輪郭と重複線を消し、いちばん大きい輪郭の寸法で縮尺を確認します ([SendCutSend](https://sendcutsend.com/blog/how-to-export-a-dxf-from-inkscape-for-laser-cutting/))【指針】。LightBurnのフォーラムには「SVG import scaling issue」や「Size of DXF is different once imported」といったスレッドが繰り返し立っていて、単位と縮尺の事故がよくある失敗であることを示しています ([LightBurn forum](https://forum.lightburnsoftware.com/t/inkscape-svg-import-scaling-issue/156583))。カーフ補正は内側と外側の輪郭を区別するので、**閉じたパス**が前提です ([EngraverHQ](https://engraverhq.com/guides/laser-cutter-kerf/))。

ここから導くプラグインの規則は一つです。**読み込みのたびに、既知の寸法（例えば100 mmの基準正方形やプレートの全幅）を一つ測るまで先へ進まない**ことです。25.4倍や1000倍の事故は、これだけで止まります（推論）。なお、Inkscapeの96 px/in（旧版は90 px/in、Illustratorは72 pt/in）による1.067倍・1.333倍のずれ、DXFの`$INSUNITS = 4`（mm）、BlenderのUnit Scaleを0.001にする設定は広く知られていますが、今回の調査では一次資料を取得できていません。チェックリストには「未検証」と記して載せるべきです。

## パラメトリック設計はテストピースの値を受け取る器として作る

Fusionでの作法は、ACE Makerspaceのガイドとオートデスクのブログでまとまります。スケッチは編集のたびに完全拘束にします。Fusionは未拘束の形状をスケッチを開かずにドラッグできてしまうからです。拘束状態の色表示は当てにしません。スケッチは1フィーチャーにつき1枚に保ちます。原点は対称形状の中心に置き、寸法は「人に説明するとおり」に入れます。グリッドスナップはオフにします。構築平面は既存の形状に固定し、投影はスケッチを測った面と同じ面から明示的に行います。パターンは、対称性が後で変わりうるなら円形パターンより鏡像を使います ([ACE Makerspace](https://www.acemakerspace.org/?p=64146))。正接拘束は、寸法を変えたときにソルバーが形状を反転させる報告があります ([Autodesk forum](https://forums.autodesk.com/t5/fusion-support-forum/unpredictable-parametric-solving-with-tangent-constraints-in/m-p/12567420))。物理的な部品はそれぞれ独自の原点を持つ**コンポーネント**にします。編集中のコンポーネントをアクティブにしないと、フィーチャーが最上位に付いてしまいます ([Autodesk blog](https://www.autodesk.com/products/fusion-360/blog/?p=268))。仕上げに、**寸法を変えてモデルが意図どおり追従するかを確かめる「フレックステスト」**を行います ([ACE Makerspace](https://www.acemakerspace.org/?p=64146))。

このループの要は、テストピースの結果をそのまま受け取れる名前付きユーザーパラメータです。最低限、`t_plate`/`t_case`（実測板厚）、`kerf`、`clr_fit`/`clr_slide`、`insert_hole`、壁厚を持たせ、テストピースの記録から転記します（推論）。プレートのように格子とパラメータで決まる平面形状には、コードCADが向いています。CadQueryはOpenCascadeを核にSTEP/DXFの入出力ができ、少ないコードで完全にパラメトリックなモデルを作れます ([CadQuery](https://cadquery.readthedocs.io/en/latest/intro.html))。build123dは、OpenSCADのCSGでは手作業の近似になるフィレットを、トポロジー検索で選んだエッジに直接かけられます。日本語版ドキュメントもあります ([build123d](https://build123d.readthedocs.io/en/latest/OpenSCAD.html)、[日本語版](https://build123d-ja.readthedocs.io/ja/latest/OpenSCAD.html))。ただし、OpenSCADへの批判は競合側の文書から来ている点に注意が要ります。Kamakuraは、スロット幅を掃引したカーフ・コームのSVGをスクリプトで生成しています ([Fab Academy Kamakura](https://fabacademy.org/2019/labs/kamakura/assignments/week04/))。テストピースそのものをパラメトリックに生成する好例です。FreeCADは1.0でトポロジカルネーミング問題の緩和策を入れましたが、保守者自身が「完全には解決していない」と述べています ([FreeCAD wiki](https://wiki.freecad.org/Topological_naming_problem/en))。

版管理では、Fusionのタイムラインはテキストとして差分を取れません。そこでGitでは、テキストのもの（コードCAD、`params.csv`、SVG/DXF、記録）を通常管理し、.f3d、.blend、STEP、大きなSTL/3MFはGit LFSに載せます。LFSは`git lfs install`の後に`git lfs track "*.拡張子"`を実行し、`.gitattributes`をコミットします。既存の履歴には`git lfs migrate`が必要です ([Git LFS](https://git-lfs.com/))。GitHubはSTLを10 MBまで3D表示し、埋め込みもできます。画像の差分表示（2-up、スワイプ、オニオンスキン）も使えます ([GitHub Docs](https://docs.github.com/en/repositories/working-with-files/using-files/working-with-non-code-files))。そこで、版ごとのパラメータ表とレンダーPNGを残せば、バイナリでもレビューができます（推論）。ファイル名は`<project>_<part>_v<NN>.<ext>`とし、機械に送るたびに`v03-plate-kerf0.15`のようなタグを打つと、どの条件で何をカットしたかを後から追えます（推論）。「ドキュメントが揃っている」とは何かの基準には、DIN SPEC 3105が使えます。これは技術ごとに必要書類を定めていて、例えば3Dプリント物にはCADモデル、PCBにはレイアウト・回路図・BOMを求めます ([openhardware.science](https://openhardware.science/?p=4069))。

測定の記録は、All3DPの方式（同じ位置で3回以上測り、ばらつきも記録する）を基本にします ([All3DP](https://all3dp.com/2/3d-printing-tolerances-test-fdm/))。インサートのようにデータシートがある部品は、ネジ径ではなくメーカー推奨値から寸法を取ります ([UAL CCI](https://wiki.cci.arts.ac.uk/books/digital-fabrication-lab/page/design-the-clearance-and-tolerance))。記録の列は、項目、呼び値とその出典、実測値n1〜n3、平均、ばらつき、基準面、測定器、日付、対応するCADパラメータ名とします（推論）。

## 組み立ては板厚公差をフォームで吸収し、アクリルの縁を守る

### ネジ穴は規格表から、アクリルは縁と締め付けに余裕を持たせる

| 呼び | 1級 / 2級 / 3級 ボルト穴径（mm） | 座ぐり径 | 区分 | 出典 |
|---|---|---|---|---|
| M2 | 2.2 / 2.4 / 2.6 | 7 | 規格 | [JIS B 1001（NBK抜粋）](https://static.nbk1560.com/images/en-US/product/technical_data/boltana_zagurikei_NBK/boltana_zagurikei_NBK_1.pdf) |
| M3 | 3.2 / 3.4 / 3.6 | 9 | 規格 | 同上 |
| M4 | 4.3 / 4.5 / 4.8 | 11 | 規格 | 同上 |

JIS B 1001の抜粋にはM2.5が載っていません。M2.5の値は、規格の原本かミスミのカタログで確認すべきです。アクリルについてACRYLITE（レーム）は、穴の中心から縁までを穴径の1.5倍以上取るよう指示しています。大きな板を通しボルトで留める場合は、熱と湿気による伸縮を見込んでボルト径の2倍以上の穴を空け、ゴムのグロメットを使うよう勧めています ([ACRYLITE](https://www.acrylite.co/resources/knowledge-base/article/how-far-in-should-I-drill-a-hole-from-the-edge-of-acrylic-sheet))【指針】。「2倍」は大判のグレージング向けの規則で、キーボード程度の部品にはそのまま当てはまりません。JISの2〜3級の穴にワッシャーを組み合わせるのが妥当な折衷です（推論）。M3の2級穴3.4 mmに1.5倍則を当てると、縁距離は5.1 mm以上になります【計算】。下穴なしでアクリルにネジを打つと割れます ([ニュースイッチ](https://newswitch.jp/p/9704))。印刷部品に何度も着脱するネジにはインサートを使い、アクリルは貫通穴とナットまたはスペーサーで受けます（推論）。

### 積み上げはワーストケースで見積もり、スラックは圧縮フォームに集める

ミスミの±0.7 mm（3 mmアクリル）にPORONの厚み公差（4701-50で±10%、30 lb/ft³グレードで±20%）が重なります ([Rogers PORON 4701-50](https://www.rogerscorp.com/elastomeric-material-solutions/poron-industrial-polyurethanes/poron-4701-50))。その結果、プレート、フォーム、PCB、ケースの積層は1 mm以上ずれうるのです。公差の積み上げには、ワーストケース（T＝Σ|aᵢ|Tᵢ）とRSS（√Σ(aᵢTᵢ)²）があります。Wevolverの例では、5部品の積層がワーストケースで±0.45 mm、RSSで±0.24 mmになります。部品数が3〜4程度、少量生産、一台の失敗も許されない場面ではワーストケースが推奨されています ([Wevolver](https://www.wevolver.com/article/tolerance-stack-up-analysis-worst-case-vs-rss-methods))。RSSは多数の部品が分布から抜き取られることを前提にしているので、一品ものの手作りでは**ワーストケースを使うか、そもそも板を実測して印刷側の寸法（プレート溝の高さ、スペーサー高さ）を合わせ込む**のが正しいやり方です（推論）。印刷は、安く調整できる層だからです。

フォームの材料には、PORONの微細セルウレタンが適しています。圧縮永久ひずみは70 °Cで10%以下、力とたわみの曲線は「比較的平坦」で、厚みは0.30〜12.7 mmが揃っています。常時圧縮されるガスケットや、プレートとPCBの間のフォームに向きます ([Rogers PORON](https://www.rogerscorp.com/elastomeric-material-solutions/poron-industrial-polyurethanes/poron-4701-50)、[Rogers設計ガイド](https://tools.rogerscorp.com/documents/993/hpf/poron/industrial/Sealing-Gasketing-Design-Guide.aspx))【実測、メーカー典型値】。ただしRogersのページは、最も密度の高いグレードのCFD25%を207 kPaと269 kPaの二通りで載せていて、自社ページ内で食い違っています。Evazote EV30（架橋EVA/PE）は、25%圧縮を22時間かけた後の永久ひずみが、30分回復後で13%、24時間回復後で4%です。圧縮応力は25%で39 kPa、50%で100 kPaです ([Polyformes](https://poly.gwp.co.uk/foam-materials/evazote/evazote-ev30/))【実測、メーカー】。EVAは回復が遅いので、ほとんど圧縮しないケース内の充填材や脚に回すのが合理的です（推論）。目標の圧縮率20〜40%はガスケット実務の経験則ですが、Rogersのガイドは単一の推奨値を示していません。圧縮量はネジの締め付けトルクで決めず、印刷した硬いボス（圧縮ストッパー）の高さで決めます（推論）。キーボード界隈で、ガスケットの厚みと圧縮量を実測した資料は見つかりませんでした。

### アクリルは溶剤とCA接着剤を縁から遠ざけ、必要なら焼きなます

レーザーカットした縁や穴には残留応力があり、本来は無害な溶剤でもクラックが生じます。Glowforgeのユーザーは、カット面付近の煤を変性アルコールで拭いたところ、縁から最長約13 mmの割れが入ったと報告しています ([Glowforge community](https://community.glowforge.com/t/warning-when-cleaning-acrylic/30490))【経験則・事例】。アルコールと応力の組み合わせでPMMAにクレーズが発生・成長することは、学術文献にもあります ([PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10052915/))。ACRYLITEの焼きなまし手順は次のとおりです。80 °C（±6 °C）に予熱し、板厚6 mm以下なら2時間（それより厚ければ板厚mm÷3時間）加熱します。その後、2時間以上かけて60 °C以下まで冷やします（8 mm以下で約10 °C/h）。カットした縁の応力だけが目的なら、2時間加熱と2時間冷却の短縮版で足ります。溶剤接着の後は6時間以上待ってから焼きなまし、穴には熱風が通るよう向きを決めます ([ACRYLITE](https://www.acrylite.co/resources/knowledge-base/article/what-is-annealing-and-what-are-the-procedures-for-annealing-acrylic-sheet))【指針】。PLEXIGLASは冷間曲げの最小半径を、キャストで板厚の180倍超、押出で300倍超としています ([Trinseo](https://www.trinseo.com/solutions/acrylic-extruded-sheets/fabrication-guidelines-faqs))。

### 印刷部品の外観は120番から始め、プライマーの膜厚を合わせに見込む

FacFoxの塗装下地の手順は次のとおりです。120番の耐水ペーパーで水研ぎを始めます（それより粗い番手は表面を荒らすとしています）。フィラープライマーを吹いて24時間以上乾かし、220〜320番で研ぎます。凹みにはパテを入れ、再度プライマーを吹いて400番まで仕上げます。光沢仕上げなら1500番以上まで進めます。艶消し黒の「検査コート」を吹くと欠陥が見えます ([FacFox](https://facfox.com/docs/kb/how-to-get-a-smooth-finish-on-your-fdm-3d-printed-parts))【指針】。塗膜は寸法を食うので、インサート穴、プレートの溝、合わせ面はマスキングし、インサートは塗装の後に入れます（推論。塗膜厚の出典は未取得）。

USB-Cの切り欠きは、レセプタクルではなくケーブル側のオーバーモールドに合わせて寸法を取ります。QEDAのフットプリントは、USB Type-C仕様Rel. 2.0を参照してオーバーモールドの幅を12.35 mmとしています ([QEDA](https://git.cuvoodoo.info/kingkevin/qeda_library/src/branch/usb-cable-tester/connector/connector_usb-c_plug.yaml))。DigiKeyのフォーラムでは、データシートにオーバーモールドの長さが載っていない事例が報告され、余裕が1 mm未満だったため「実物で確かめよ」と助言されています ([DigiKey forum](https://forum.digikey.com/t/overmold-size-of-the-usb-c-male-end/70874))。高さ6.5 mmとよく言われる値は確認できていません。手持ちのいちばん太いケーブルでテストピースを作るべきです。

## 安全の禁止事項は「全ラボで禁止」と「ラボ次第」に分けて持つ

| 材料 | 判定 | 理由 | 出典 |
|---|---|---|---|
| PVC・塩素系全般（ビニール、合成皮革、Sintra/Forex、Kydex） | 全面禁止 | 塩素・HClが出て、レンズ・ミラー・金属部を腐食する。PVCフォームボードは塩素が重量の約57%。換気では解決しない | [UW Fab Lab](https://fablab.cs.washington.edu/wp-content/uploads/2023/02/Laser-Cutter-Approved-Materials-2022.12.29.pdf)、[Thunder Laser](https://www.thunderlaserusa.com/blog/laser-cut-foam) |
| ポリカーボネート | 全面禁止 | 赤外線をよく吸収し、カットしきれずに溶ける。変色し、火災の危険がある | [UW](https://fablab.cs.washington.edu/wp-content/uploads/2023/02/Laser-Cutter-Approved-Materials-2022.12.29.pdf) |
| ABS | 全面禁止 | シアン化物ガスが出て、溶けて発火する | [UW](https://fablab.cs.washington.edu/wp-content/uploads/2023/02/Laser-Cutter-Approved-Materials-2022.12.29.pdf) |
| HDPE | 全面禁止 | 溶けて発火する | [UW](https://fablab.cs.washington.edu/wp-content/uploads/2023/02/Laser-Cutter-Approved-Materials-2022.12.29.pdf) |
| PTFE | 全面禁止 | フィルターで除去できない。屋外に排気すると鳥に致命的 | [UW](https://fablab.cs.washington.edu/wp-content/uploads/2023/02/Laser-Cutter-Approved-Materials-2022.12.29.pdf) |
| ガラス繊維、コート付き炭素繊維 | 全面禁止 | 樹脂やコーティングが燃えて有害ガスを出す | [UW](https://fablab.cs.washington.edu/wp-content/uploads/2023/02/Laser-Cutter-Approved-Materials-2022.12.29.pdf) |
| Br・Cl・F・Iを含むもの、C–N結合を持つもの、難燃と表示されたもの | 全面禁止（一般則） | 有毒ガス、火災、機械の損傷 | [Bristol Hackspace](https://wiki.bristolhackspace.org/equipment/cnc/laser/materials) |
| ポリスチレンフォーム（XPS/EPS）、HIPS | 禁止または要注意 | UWは「レーザー火災の原因の第1位」とする。BristolはPS/HIPSを禁止。CutLaserCutはHIPSのカーフを載せている | [UW](https://fablab.cs.washington.edu/wp-content/uploads/2023/02/Laser-Cutter-Approved-Materials-2022.12.29.pdf)、[Bristol](https://wiki.bristolhackspace.org/equipment/cnc/laser/materials)、[CutLaserCut](https://cutlasercut.com/drawing-resources/expert-tips/laser-kerf/) |
| MDF | ラボ次第 | UWはホルムアルデヒドと光学系への害を理由に禁止。Bristolは許可 | 同上 |
| POM（デルリン） | ラボ次第 | UWは「危険なガスが出る」として禁止。Bristolは許可 | 同上 |
| EVAフォーム | ラボ次第 | Thunder Laserは「安全」、UWは禁止（塩素が出るというUWの説明は、純EVAには塩素がないので疑わしい） | [Thunder Laser](https://www.thunderlaserusa.com/blog/laser-cut-foam)、[UW](https://fablab.cs.washington.edu/wp-content/uploads/2023/02/Laser-Cutter-Approved-Materials-2022.12.29.pdf) |
| PUフォーム（PORON系を含む） | ラボ次第 | Thunder Laserは「安全」だが、C–N結合を含むのでBristolの一般則では禁止 | [Thunder Laser](https://www.thunderlaserusa.com/blog/laser-cut-foam)、[Bristol](https://wiki.bristolhackspace.org/equipment/cnc/laser/materials) |
| PET/PETG、ナイロン | ラボ次第 | Bristolは禁止。CutLaserCutはPETGのカーフを載せている | [Bristol](https://wiki.bristolhackspace.org/equipment/cnc/laser/materials)、[CutLaserCut](https://cutlasercut.com/drawing-resources/expert-tips/laser-kerf/) |
| PP、PLA | 要監視 | PPは溶けて発火しうるので常時監視。PLAはカットしきれずに溶けがち | [Bristol](https://wiki.bristolhackspace.org/equipment/cnc/laser/materials) |
| 合板 | 条件付き許可 | Bristolは船舶用合板を不可、UWは無処理の合板のみ可 | 同上 |

この表で実務上最も大事なのは、キーボードのガスケットで定番のPORONがポリウレタンであり、Bristolの一般則ではレーザー加工が禁止になる点です。フォームをレーザーカットするなら、EVAかPEを所属ラボのリストで確認してから使います。PU系は刃物でカットするのが保守側の選択です（推論）。材料はSDSかリサイクルコード（「3」やPVC、Vの表示）で特定し、見た目では判断しません。誤ってPVCをカットしたら、蓋を閉じたまま排気を最大で30分以上回し、その後で光学系を清掃します ([Thunder Laser](https://www.thunderlaserusa.com/blog/laser-cut-foam))。運転の規則は次の三つです。**窓を開けて扇風機を回すのは排気ではない**ので、筐体からの排気に粒子フィルターと活性炭を組み合わせます。エアアシストは炎を煽りうるので、**運転中の機械から決して離れない** ([Thunder Laser](https://www.thunderlaserusa.com/blog/laser-cut-foam)、[Fab Academy Kamakura](https://fabacademy.org/2019/labs/kamakura/assignments/week04/))。リストにない材料は、UWではSDSを提出して承認を得る必要があります。調査では、ダイオードレーザー（445〜455 nm）用保護メガネのOD値を示す一次資料は取得できませんでした。オープンフレームのダイオード機を使うなら、ここは別途確認すべき最優先の欠落です。

## 出典の食い違いと、自機で測って決める値

| 値 | 食い違いの内容 | 扱い |
|---|---|---|
| CO2カーフ、3 mmアクリル | 0.125（Ponoko 実測） vs 0.18 mm（CutLaserCut 指針） | 初期値0.15、正方形かコームで実測 |
| ダイオードカーフ | 0.05（実測1件） vs 0.1–0.5 mm（経験則）。X/Yで0.05–0.10の差 | 信頼度低と表示し、X/Y別に実測 |
| カーフの定義 | 全幅（EngraverHQ） vs 片側（Box Studio）。Kamakuraは式と表記が不一致 | k＝全幅、オフセット＝k/2に固定 |
| レーザーの最適スロット | 板厚−0.10〜0.15（MIT） vs 板厚−0.3〜0.5 mm（Kamakura） | 持ち運べない値。T±0.20を0.05刻みで並べたコームで決める |
| アクリルの板厚公差 | キャスト±15%（Trotec） vs 3 mmで±0.7 mm（ミスミ） | シートごとに数点を実測 |
| FDMの圧入クリアランス | 0–0.05（H2D） vs 0.2 mm（S7）、≤0.05（All3DP） | 3段のテストピース（±0.1）で決める |
| オーバーハング／ブリッジ | 45°/5 mm（Hubs） vs 55–70°/30–40 mm（Bambu TDS） | Ender-3では45°/5 mmで設計 |
| M3インサート穴 | 4.0（CNC Kitchen・ruthex） vs 外径−0.3≈4.3 mm（UW） | 4.0〜4.4のテストピースで決める |
| インサートのこて温度 | PLA約225 °C（CNC Kitchen） vs 240–260 °C（UW） | 低い側から上げていく |
| Bambuの穴補正の符号 | 記事内の作例と符号が矛盾 | 1回印刷して向きを確認 |
| アクリルの穴径 | ボルト径の2倍以上（ACRYLITE、大判向け） vs JIS 2〜3級 | 小物はJIS 2〜3級＋ワッシャー |
| PORONのCFD（最高密度グレード） | 207 vs 269 kPa（同じページ内） | データシートの原本で確認 |
| MDF、POM、EVA、PU、PETG、PS | ラボによって許可と禁止が分かれる | 所属ラボのリストを必須確認、既定は警告 |

自分の機材で測って決めるべき値は、次のとおりです。機械・材料・設定の組ごとのカーフ（X/Y別）、シートごとの実板厚、レーザーのはめあいコームの最適幅、FDMの一般・着脱・圧入クリアランス、穴補正量（スライサーかCADのどちらか一方）、インサート穴径とこて温度、出力と速度のカット条件、フォームの実厚と圧縮量、USB-Cケーブルのオーバーモールド実寸です。今回は一次資料で確認できず、**未検証の経験則**として扱うべき値もあります。Inkscapeの96/90 px/in、DXFの$INSUNITS、Blenderの単位設定、M3ナットトラップの対辺5.5 mmに0.2〜0.3 mmを足す値、タッピング下穴2.5〜2.8 mm、USB-C開口13×7 mm、PCB下の逃げ1〜2 mm、ガスケットの圧縮率20〜40%、マスキングテープやハニカムベッドの影響、ベッドに収まらない部品を分割するときの継ぎ手の寸法です。

## monozukuriチェックリスト（段階別）

| 段階 | 確認項目 | 合格基準 | 根拠 |
|---|---|---|---|
| モック | 大きさ、比率、配置、手触りを確認したか | 確認の結果を決定記録に残した | 推論 |
| モック→CAD | メッシュを参照用にだけ使い、Fusionで描き直したか | 編集対象がB-repになっている | [CadQuery](https://cadquery.readthedocs.io/en/latest/intro.html) |
| CAD | 主要寸法を名前付きユーザーパラメータにしたか（t, kerf, clr, insert_hole） | 寸法を変えると意図どおり追従する（フレックステスト） | [ACE Makerspace](https://www.acemakerspace.org/?p=64146) |
| CAD | 部品ごとにコンポーネントにし、スケッチを完全拘束にしたか | Body1のような名前が残っていない | [Autodesk](https://www.autodesk.com/products/fusion-360/blog/?p=268) |
| CAD | 取り合い寸法がすべて実測値かデータシートに遡れるか | 測定記録に3回以上の値とばらつきがある | [All3DP](https://all3dp.com/2/3d-printing-tolerances-test-fdm/) |
| テストピース（レーザー） | 実板厚、出力・速度グリッド、カーフ（X/Y）、コームを本番のシートでカットしたか | 結果をCADのパラメータに転記した | [MIT CBA](https://fab.cba.mit.edu/classes/863.20/CBA/people/group/reports/laser.html)、[Box Studio](https://box-studio.cc/blog/2026-05-en-kerf-reference-table-by-machine) |
| テストピース（FDM） | ±0.1の3段はめあい片、インサート穴片（4.0〜4.4）、校正キューブ | 選んだ値と条件を記録した | [QIDI](https://qidi3d.com/ja/blogs/print-lab/3d-printed-snap-fit-joints-clearance-guide)、[Printables](https://printables.com/model/1040630-threaded-insert-hole-tolerance-test) |
| 部分スライス | USB切り欠き、ボス一つ、PCBの一角を実物で合わせたか | 最も太いケーブルが奥まで挿さる | [DigiKey forum](https://forum.digikey.com/t/overmold-size-of-the-usb-c-male-end/70874) |
| 書き出し | 3MF（印刷）、DXF/SVG mm（レーザー）、STEP（保管） | ファイル名に部品名と版がある | [3MF Spec](https://github.com/slic3r/Slic3r/wiki/3MF-Document-Core-Specification) |
| 読み込み | 既知寸法を一つ測ったか | 25.4倍、1000倍、1.067倍、1.333倍のずれがない | [Blender #106334](https://projects.blender.org/blender/blender/issues/106334) |
| レーザー前 | 閉じたパス、重複線なし、テキストはパス化、色と条件の対応、内側からカットする、線間0.5 mm以上 | プレビューで確認した | [SendCutSend](https://sendcutsend.com/blog/how-to-export-a-dxf-from-inkscape-for-laser-cutting/)、[CutLaserCut](https://cutlasercut.com/drawing-resources/expert-tips/laser-kerf/)、[Kamakura](https://fabacademy.org/2019/labs/kamakura/assignments/week04/) |
| レーザー前 | 材料をSDSかリサイクルコードで特定し、ラボのリストで許可を確認したか | 禁止表の全面禁止に当たらない | [UW](https://fablab.cs.washington.edu/wp-content/uploads/2023/02/Laser-Cutter-Approved-Materials-2022.12.29.pdf)、[Bristol](https://wiki.bristolhackspace.org/equipment/cnc/laser/materials) |
| レーザー中 | 排気とフィルター、立ち会い、消火器 | 終了まで機械から離れない | [Thunder Laser](https://www.thunderlaserusa.com/blog/laser-cut-foam) |
| 印刷前 | 45°とブリッジ5 mm以内、壁0.8 mm以上、床面の縁は面取り、水平穴はティアドロップ | サポートが空洞内に入らない向き | [Hubs](https://hubs.com/knowledge-base/how-design-parts-fdm-3d-printing)、[Pollen AM](https://www.pollen.am/design_for_3d_printing_holes) |
| 印刷前 | 穴補正をCADかスライサーのどちらか一方だけで行ったか。材料は使用温度に合うか（PLAはHDT 57 °C） | ABS/ASAなら筐体がある | [Bambu Wiki](https://wiki.bambulab.com/en/knowledge-sharing/3d-prints-shrinkage)、[Prusa KB](https://help.prusa3d.com/article/material-table_2324) |
| 組み立て | ネジ穴はJIS 2〜3級、アクリルの縁距離は穴径の1.5倍以上、下穴あり | ワッシャーを入れ、締め付けは「軽く止まる」程度 | [JIS B 1001](https://static.nbk1560.com/images/en-US/product/technical_data/boltana_zagurikei_NBK/boltana_zagurikei_NBK_1.pdf)、[ACRYLITE](https://www.acrylite.co/resources/knowledge-base/article/how-far-in-should-I-drill-a-hole-from-the-edge-of-acrylic-sheet) |
| 組み立て | 積み上げをワーストケースで計算し、スラックをフォームに集めたか | 圧縮量がボスの高さで決まる | [Wevolver](https://www.wevolver.com/article/tolerance-stack-up-analysis-worst-case-vs-rss-methods) |
| 仕上げ | アクリルの縁にアルコールやCA接着剤を使っていないか。必要なら80 °C×2 h＋2 hで焼きなましたか | 縁と穴にクレーズがない | [ACRYLITE](https://www.acrylite.co/resources/knowledge-base/article/what-is-annealing-and-what-are-the-procedures-for-annealing-acrylic-sheet) |
| 仕上げ | 合わせ面とインサート穴をマスキングし、120→220/320→400番で仕上げたか | インサートは塗装後に入れる | [FacFox](https://facfox.com/docs/kb/how-to-get-a-smooth-finish-on-your-fdm-3d-printed-parts) |
| 版管理 | 加工に送ったファイル、パラメータ表、テストピースの記録をコミットしてタグを打ったか | 大きなバイナリはLFSに入っている | [Git LFS](https://git-lfs.com/) |

## 結論

この調査でいちばん大きく変わった見方は、「設計ルールの数値表」を参照資料の中心に据えるのは誤りだということです。出典どうしのずれは圧入とすきまばめの境目と同じ大きさがあり、レーザーの最適スロット幅のように、描いた寸法の中にその機械のカーフが溶け込んでいて持ち運べない数値もあります。したがってmonozukuriプラグインの参照資料は、数値を「初期値＋信頼度＋測り方」の三つ組で持つべきです。そのうえで、テストピースの結果をCADのユーザーパラメータへ戻す経路（記録表→`params.csv`→Fusion）こそを、プラグインが支援する本体にすべきです。こうすれば、人が行うCAD化の工程は「数値を思い出す作業」から「測った値を受け取る作業」に変わり、速さと失敗の少なさが両立します。

残っている穴もはっきりしています。ダイオードレーザーの保護メガネ、Ender-3固有の公差、POMやフォームのカーフ、分割継ぎ手の寸法、キーボードのガスケット圧縮量には、一次資料がありません。とくに安全面では、PORONがPU系であるため、ラボによってはレーザー加工自体が禁止という点が見落とされやすいところです。チェックリストで最初に止めるべき項目として扱います。
