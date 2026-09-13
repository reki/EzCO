# DLSite/DMM 商品情報

現在開いているフォルダの商品情報をサイドバーに出すプラグインです。`info.json` と `folder.jpg` があればそれを表示します。無いときはフォルダ名／ファイル名の DLsite・DMM・DLSoft 番号から Web 取得します。取得結果は表示用だけで、フォルダへは書きません。

| 項目 | 値 |
| --- | --- |
| ID | `com.ezco.product_info` |
| バージョン | `1.0.0` |
| 種別 | サイドバー |
| ZIP | `dist-sample-plugins/product_info.zip` |
| 入口 | `plugin:ProductInfoPlugin` |
| LICENSE | なし（設定のライセンスボタンは `-`） |

## 使い方

1. `product_info.zip` を実行ファイル旁の `plugins/` 直下に置く
2. EzCo を起動
3. 表示メニューからサイドバーを出す。ショートカット／ジェスチャーにも割り当てできる
4. プラグイン設定の「設定」で Web 取得の ON/OFF を変えられる

認識する ID の例:

- DLsite: `RJ01530423` など（`[RVBA]J` + 数字）
- DMM: `d_802808`
- DLSoft: `xxx_1234`

取得中は空表示のままです。失敗してもフォルダは変わりません。

## 設定

| キー | 型 | 既定 | 内容 |
| --- | --- | --- | --- |
| `fetch_web` | bool | `true` | `info.json` が無いとき Web から取得する |

## アクション

`register_sidebar` により開閉が自動登録されます。公開 ID は `plugin:com.ezco.product_info:sidebar:product_info` です。以前の本体アクション名を残すため `toggle_product_info_dock` をエイリアスにしています。

## 開発

ソースは `plugins/product_info/` です。取得は標準ライブラリのみです。データフォルダの `plugins/` にこのフォルダを置けばそのまま読めます。配布 ZIP は `dist-sample-plugins/` です。

ホスト API の一覧はユーザーマニュアルの [プラグインリファレンス](../../resources/UserManual/files/plugin-reference.html) と [docs/plugins.md](../../docs/plugins.md) を見てください。
