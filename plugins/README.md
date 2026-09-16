# EzCo プラグイン

データフォルダ（設定の「データの置き場」。既定はこのユーザーのデータフォルダ）の `plugins/` に ZIP、または `manifest.json` 付きの展開フォルダを置くと、独自の画像／アーカイブ形式、サイドバー、表示フィルターを追加できます。開発時にリポジトリのこのフォルダを使うときは、置き場を実行ファイルと同じフォルダにしてください。

開発者向けの契約・API リファレンスは [docs/plugins.md](../docs/plugins.md) とユーザーマニュアルの [プラグインリファレンス](../resources/UserManual/files/plugin-reference.html) にあります。各プラグインの説明はフォルダ内の `README.md` です。配布用 ZIP は [dist-sample-plugins/](../dist-sample-plugins/) です。英語は [README_EN.md](README_EN.md) です。

## 注意

本体はプラグインの中身を検査しません。ZIP やフォルダに含まれるコードは、置いた時点で EzCo と同じ権限で動きます。悪意のあるコードや欠陥による損害について、EzCo の開発者は責任を負いません。配布元を信頼できるか、必要ならソースを自分で確認してから置いてください。責任はプラグインの配布者と、それを導入した使用者にあります。起動時の確認文は `src/ez_co/resources/plugin_consent/` の Markdown です。文面を変えたら同じフォルダの `version.txt` を上げてください。

## 再起動と設定の反映

- **再起動が必要**: `plugins/` に新しい ZIP／フォルダを置いたとき、置いたものを消したとき
- **プラグイン設定の OK / 適用で足りる**: ON/OFF、拡張子の読み込み方式、重複プラグインの選び直し。開いているファイルの再読み込みとサイドバーの付け直しもここで行う
- 起動中にファイルを足しただけでは一覧に出ません

## ユーザー向け

1. `.zip`、または `manifest.json` のあるフォルダをデータフォルダの `plugins/` 直下に置く（その下の入れ子は読まれません）。場所は設定の「データの置き場」です
2. EzCo を起動する（すでに起動中なら、追加したあと再起動）。プラグインがあるのにまだ同意していないときは、はい／いいえの確認が出ます。はいならこのユーザーの同意バージョンを保存し、重複があればその次に選択ダイアログ、そのあとロードします。いいえならその起動ではロードせず、設定メニューにプラグイン設定も出しません。次回起動でもまた聞きます。同意の文面を変えてバージョンが上がったときも再表示します
3. メニューのプラグイン設定で、プラグインの ON/OFF と拡張子ごとの読み込み方式（ビルドイン／プラグイン／読み込まない）を選ぶ。スキーマがあるプラグインは「設定」から項目を変えられ、OK するとすぐ保存される。ルートに `LICENSE.md` / `LICENSE.txt` / `LICENSE` があれば「ライセンス」から読めます（優先順はこの順。表示は保証ではない）。本体ダイアログの OK / 適用では開いているファイルを再読み込みし、無効にしたプラグインのサイドバーは消えます。有効なサイドバーの開閉や、プラグインが登録したアクションはショートカット／ジェスチャーに割り当てできます
4. ビルドインと同じ拡張子は、既定ではビルドインが使われます
5. 一覧の列はドラッグで幅変更・並べ替えできます。幅と列順は保存されます
6. 有効なプラグインの拡張子は、「ファイルを開く」ダイアログの「対応しているファイル」と「プラグイン形式」に入ります。フォルダを開いたときのスキャン対象にも含まれます

同じ `id` のプラグインが複数あるときは、起動時にどれを読むか（または読まないか）を選びます。選んだ内容は保存され、新しい重複 `id` が出ない限り次回は聞きません。選び直すときはプラグイン設定の「重複プラグインの選択」です（OK / 適用で反映。再起動は不要）。選ばれなかったものは一覧に理由付きで残ります。DLL プラグインは未対応です。

## このフォルダのサンプル

ここはソースです。データ置き場を実行フォルダにすると、これらのフォルダがそのまま読み込まれます。配布用 ZIP は [`dist-sample-plugins/`](../dist-sample-plugins/) です。

| フォルダ | 内容 |
| --- | --- |
| `example_png/` | `.png` をプラグイン経由で開く確認用。色とラベルを重ねます。[README](example_png/README.md) |
| `example_zip/` | `.zip` をプラグイン経由で開く確認用。パスワードダイアログの呼び出しも含みます。[README](example_zip/README.md) |
| `example_txt/` | `.txt` をページ画像として開く一般向けサンプル。サイドバーで字体・色・縦読み／横読みを即時反映します。[README](example_txt/README.md) |
| `product_info/` | 商品情報サイドバー。`info.json` と `folder.jpg` を表示。無いときはフォルダ／ファイル名の DLsite / DMM 番号から Web 取得（設定で OFF 可。フォルダには書かない）。[README](product_info/README.md) |
| `error_setup/` | 確認用。`setup()` で例外を出す。[README](error_setup/README.md) |
| `error_callback/` | 確認用。サイドバーの「エラー」ボタンでコールバック例外を出す。[README](error_callback/README.md) |
| `config_types/` | 確認用。設定種別（bool / string / int / float / int_range / float_range / path / password / color / date / datetime / choice / font）を全部登録する。[README](config_types/README.md) |
| `example_filter/` | 確認用。表示フィルター。青緑の色とラベルを重ね、文字サイズを `int_range`（`sync` と `reload`）で変える。[README](example_filter/README.md) |

配布 ZIP の作り直しはタスク **「EzCo: プラグインZIP」** または `poetry run pack-plugins` です。出力先は [`dist-sample-plugins/`](../dist-sample-plugins/) です。

サンプルの色重ねは確認用です。本番プラグインでは不要です。

## 最小構成

```
my_plugin/   または my_plugin.zip
├── manifest.json
├── src/
│   └── loader.py
├── langs/
    ├── ja.json
    └── en.json
└── LICENSE.md   # 任意。LICENSE.txt / LICENSE でも可。設定から表示
```

ファイルローダーは `manifest.json` の `formats` と `read_entry` などを実装します。サイドバーは `sidebar: true` を書いたうえで `setup` で `host.load_ui` / `host.register_sidebar` します。表示フィルターは `permissions.filter: true` を書いたうえで `setup` で `host.register_filter` します。未宣言の登録はエラーです。開閉は自動でアクション登録されます。旧ショートカット ID を残すときは `aliases` を渡します。独自処理は `host.register_action` です。コンストラクタは `Class(root, get_text, host)` です。`ez_co` は import できません（結合事故防止であり、サンドボックスではありません）。設定上の正体は `manifest.id(ver:version)` です。ダイアログの ID 列はバージョンなしの `id` だけです。同じ `id` は同時に1つだけロードします。詳細はマニュアルを見てください。
