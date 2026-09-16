# Error Register Probe

確認用です。マニフェストに `sidebar` も `permissions.filter` も書かず、`setup()` から `register_sidebar` を呼びます。本番では使いません。

| 項目 | 値 |
| --- | --- |
| ID | `com.ezco.error_register` |
| バージョン | `1.0.0` |
| 種別 | 確認用（setup のみ） |
| ZIP | `dist-sample-plugins/error_register-1.0.0.zip` |
| 入口 | `plugin:ErrorRegisterPlugin` |
| LICENSE | `LICENSE.md` |

## 使い方

1. `error_register.zip` を実行ファイル旁の `plugins/` 直下に置く
2. EzCo を起動（追加したあとは再起動）
3. プラグイン設定でこのプラグインを有効にして適用する
4. 状態列が「失敗: 権限がない登録がありました」になることを確認する

確認が終わったらプラグインを無効にしてください。

## 開発

ソースは `plugins/error_register/` です。データフォルダの `plugins/` にこのフォルダを置けばそのまま読めます。配布 ZIP は `dist-sample-plugins/` です。
