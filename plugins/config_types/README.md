# Config Types Probe

確認用です。ホストが扱う設定種別を全部登録し、保存値をサイドバーに出します。本番では使いません。

| 項目 | 値 |
| --- | --- |
| ID | `com.ezco.config_types` |
| バージョン | `1.0.0` |
| 種別 | サイドバー |
| ZIP | `dist-sample-plugins/config_types-1.0.0.zip` |
| 入口 | `plugin:ConfigTypesPlugin` |
| LICENSE | ルートの `LICENSE.md` |

登録する型は `bool` / `string` / `int` / `float` / `int_range` / `float_range` / `path` / `password` / `color` / `date` / `datetime` / `choice` / `font` です。`date` と `datetime` の保存値は Unix 秒（数値）、`color` は `#RRGGBB` 文字列、`password` は DPAPI です。`int_range` は `sync=True`（`reload` なし）の例です。

## 使い方

1. `config_types.zip`、またはこのフォルダをデータフォルダの `plugins/` 直下に置く
2. EzCo を起動（追加したあとは再起動）
3. プラグイン設定でこのプラグインを有効にする
4. 一覧の「設定」を開き、各種別の入力を確認する
5. OK / 適用のあと、サイドバー「設定種別」の表示と「保存値」が一致することを確認する

確認が終わったらプラグインを無効にしてください。

## 開発

ソースは `plugins/config_types/` です。データフォルダの `plugins/` にこのフォルダを置けばそのまま読めます。配布 ZIP は `dist-sample-plugins/` です。
