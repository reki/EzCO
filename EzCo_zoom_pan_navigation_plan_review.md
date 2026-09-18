# EzCo 拡大時読書順ナビゲーション Plan レビュー

対象: `zoom_pan_navigation_da4bfe57.plan.md`

## 総評

方針は良い。このまま実装へ進めてよい。

特に以下は妥当。

- モードを `page / left / right` の3択に限定
- 既定値を従来互換の `page`
- 実際にはみ出している場合だけ画像内移動する
- 1画面分ずつ進め、最後の端数だけ重複を許す
- 次／前を完全な逆順として扱う
- 見開きは合成後の表示画像1枚として扱う
- 座標計算を描画なしでテストする
- 回転後の画面上の上下左右を基準にする

漫画ビューアとしての用途にも合っている。

---

# 1. 【修正推奨】ページ境界の「開始角」の判断を MainWindow に持たせすぎない

Planでは、

```text
ページ境界を越える
↓
MainWindow が次画像の開始角を予約
↓
set_image()
↓
予約した角へ配置
```

となっている。

ページ変更そのものを MainWindow が担当するのは自然だが、

```text
left mode の next は右上
left mode の previous は左下
right mode の next は左上
right mode の previous は右下
```

という viewport navigation policy まで MainWindow が知ると、
ImageView と MainWindow に拡大ナビゲーションの責任が分散する。

## 推奨

MainWindow は、

```text
次ページへ進む
前ページへ戻る
```

だけを担当する。

開始位置の計算・予約・適用は ImageView 側へ集約する。

概念例:

```python
consumed = image_view.try_zoom_navigation(
    direction="next",
    mode="left",
)
```

画像内移動できた場合:

```text
True
→ ページ変更しない
```

端まで到達していた場合:

```text
False
→ MainWindow が改ページ
→ ImageView に「次に表示する画像の開始位置」を予約させる
```

例えば:

```python
image_view.prepare_page_transition(
    direction="next",
    mode="left",
)
```

その後 `set_image()` が予約状態を消費して配置する。

MainWindow は「右上」「左下」などの具体的な角を知らない。

これにより、

```text
MainWindow
= page transition ownership

ImageView
= viewport / pan navigation ownership
```

と責任分界が明確になる。

---

# 2. 座標系を1つに固定する

今回の処理では、

- 回転
- zoom
- viewport size
- image offset
- image bounds

が絡む。

移動計算の途中で、

```text
original image coordinates
scaled image coordinates
viewport/device coordinates
```

を混ぜないこと。

## 推奨

ナビゲーション計算はすべて、

```text
回転・拡大後に実際に画面へ表示される画像矩形
+
viewport矩形
+
現在offset
```

という同一座標系で行う。

Planの

> 実際に描画された回転後画像と表示領域から移動限界を求める

という方針をそのまま徹底する。

---

# 3. 片軸だけはみ出す場合の規則を明文化する

テスト対象には既に、

```text
縦横片側だけのはみ出し
```

が入っているので良い。

挙動だけ明文化しておくと実装がぶれない。

## 横方向だけはみ出す

`left`:

```text
右端 → 左へ → 左端 → 改ページ
```

`right`:

```text
左端 → 右へ → 右端 → 改ページ
```

## 縦方向だけはみ出す

左右方向へ移動できないため、
`left` / `right` ともに、

```text
上 → 下 → 下端 → 改ページ
```

となる。

## どちらも収まっている

画像内移動せず即改ページ。

---

# 4. 「1画面分」の定義

基本は、

```text
横移動量 = viewport内で画像を表示できる幅
縦移動量 = viewport内で画像を表示できる高さ
```

とする。

端で、

```text
remaining < viewport span
```

なら端へclampする。

その結果だけ直前表示との重複を許可する。

つまり意図は、

```text
通常移動
→ 前回の範囲をなるべく再表示しない

端
→ 見落とし防止のため重複可
```

とする。

---

# 5. next / previous を別実装にしすぎない

前操作は次操作の完全逆順なので、
可能なら同じnavigation modelから求める。

例えば、

```text
reading direction
+1 = next
-1 = previous
```

のように扱い、

`left` と `right` も方向パラメータで反転できる構造が望ましい。

ただし抽象化しすぎて読みにくくなるなら、
座標計算helperを共有する程度でよい。

目的は、

```text
nextだけ直したらpreviousが壊れる
```

状態を避けること。

---

# 6. pending start position は必ず一度だけ消費する

ページ境界用に開始位置を予約する場合、

```text
pending anchor
```

は `set_image()` 成功時に一度だけ消費し、
必ずclearする。

以下で残留しないことを確認する。

- 読み込み失敗
- 本を閉じる
- 別ファイルを開く
- mode変更
- zoom解除
- 通常のページジャンプ
- スライダーによるページ移動

特に通常のページジャンプへ前回のpending cornerが漏れると、
突然右下や左下から表示される可能性がある。

「次／前操作による連続読書ナビゲーション」と
「任意ページジャンプ」を分ける。

---

# 7. 拡大判定は zoom値ではなく overflowを基準にする現在案で良い

Planでは、

> 倍率だけでなく画像が表示領域から実際にはみ出している場合

としている。

これは重要なので維持する。

例えばzoom値が高くても、
元画像が小さければviewportに収まる可能性がある。

逆に何らかの表示条件でoverflowしていれば、
実際のpan可能性を見た方が正確。

判断基準は、

```text
can_pan_x
can_pan_y
```

でよい。

---

# 8. mode変更時の現在offsetはそのままでよい

`left` → `right` へ設定変更した瞬間に、
現在表示位置まで強制的に左上/右上へ移動させる必要はない。

次の「次ページ／前ページ」入力から
新しいnavigation policyを適用すれば十分。

設定変更とviewport移動を結び付けない方が自然。

---

# 9. テスト追加推奨

Planのテスト項目は良い。

さらに以下があると安心。

## exact fit

```text
image span == viewport span
```

はpan不可。

浮動小数誤差で1px未満の移動を繰り返さない。

## very small remainder

```text
残り 1px
```

でも端へclampし、その次で改ページ。

## reverse symmetry

任意の内部位置について、

```text
next
↓
previous
```

で元位置へ戻れるケースを確認。

端数clampが入るケースは完全一致しない場合があるため、
reading sequenceとして逆順になることを確認。

## pending anchor isolation

通常ページジャンプでは
ページ境界用pending anchorを使用しない。

---

# 最終評価

機能自体はEzCoの方向性に非常に合っている。

これは単なる便利機能ではなく、

```text
拡大
↓
スクロールバーやドラッグで位置調整
```

を毎回行わず、

```text
次
↓
読書順に次の未表示領域
↓
端まで読んだら改ページ
```

にできるため、
コミック閲覧時の操作感を直接改善する機能。

今回のPlanで大きな変更は不要。

主な修正推奨は1点:

> **具体的な開始角・pan traversal policyは ImageView が所有し、MainWindow はページ変更だけを所有する。**

この責任分界を守れば、
今後ナビゲーション方式を追加・調整してもMainWindowへ条件分岐が広がりにくい。
