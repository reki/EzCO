# 設計判断

コードだけでは消えやすい「なぜそうしたか」の索引です。本文の主役は [ARCHITECTURE.md](ARCHITECTURE.md) と [IMAGE_LOADING.md](IMAGE_LOADING.md) と [plugins.md](plugins.md) にあります。

推測で過去の意思決定は作りません。根拠が無い項目は Why に「不明」と書きます。

形式は Context / Current decision / Why / Consequences / Status です。

---

<a id="viewer-first"></a>

## ビュワー主軸（本棚を作らない）

### Context

コミックを開いて見るアプリとして大きくなってきた。本棚やライブラリを足す提案は出やすい。

### Current decision

本棚・ライブラリ・ファイル管理 UI は作らない。開いたファイル／フォルダ／アーカイブを見る。履歴とブックマークは「また開く」用であり、書庫を整理する機能ではない。

### Why

製品方針（開発者確認）。このアプリはビュワーが主軸で、ファイルを管理する目的はない。README も「お手軽なコミックビューワー」と書いている。

### Consequences

スキャンしてコレクションを作る画面、タグ付け、未読管理は本体の対象外。必要なら利用者がエクスプローラ等でファイルを置く。

### Status

採用中。

---

## 描画は本体、プラグインは画像バイトまで

### Context

プラグインで独自ビューアを持ちたくなる。

### Current decision

描画・ズーム・見開き・ページ送り・キャッシュは本体。プラグインは Qt / PIL が読める画像バイトまで。アーカイブの中身を別プラグインへ回さない。サイドバーは widget / layout を渡すだけ。表示画像を書き換えるときは `permissions.filter` と `register_filter`。画素処理は本体の pipe が台帳の ID を辿るときだけ。

### Why

[`.cursor/rules/plugins.mdc`](../.cursor/rules/plugins.mdc)。ビュワー主軸をプラグインに渡さない。

### Consequences

`MainWindow` やドックの貼り付けをプラグインから触らない。見開きやキャッシュの変更は本体側。

### Status

採用中。

---

## プラグインはコールバック側（サンドボックスではない）

### Context

本体内部を import すると、リファクタのたびにプラグインが壊れる。ネットワークや想定外ファイルへのアクセスを OS サンドボックスで止められないか、という案も出た。

### Current decision

プラグインはホストから呼ばれる側。`import ez_co` と他プラグインの import は禁止。`main` は実行しない。プロセス分離もファイル／ネットワークの隔離もしない。悪意への備えは、初回プラグイン導入時の警告（同意）で足りる。

### Why

結合事故防止。[plugins.md](plugins.md) と `plugins.mdc`。OS サンドボックスは対応量に見合わず、このビュワーでは不要（開発者確認）。置いたコードはアプリと同じ権限で動く。検査もしない。

### Consequences

信頼は配布者と、導入時に同意した使用者。`permissions` は callback などの出し分けであり、隔離ではない。

### Status

採用中。

---

## プラグインは本体 Config を上書きしない

### Context

設定 API を広げると、本体の YAML / DB をプラグインが壊せる。

### Current decision

可変な `Config` を渡さない。`host.get_app_config()` は読み取り専用（いまは `language` / `viewer` / `cache` / `ui_font`）。固有値は `plugin_settings`（hashed `plugin_id`）だけ。他プラグインの行は読めない。

### Why

[`.cursor/rules/plugin-data.mdc`](../.cursor/rules/plugin-data.mdc)。今書けなくても後から穴を開けない。

### Consequences

`set_app_config` のような口は足さない。拡張子優先・ON/OFF・重複選択・同意は本体の設定。

### Status

採用中。

---

## 提供物は manifest が正

### Context

`setup()` の中だけで形式やサイドバーを登録すると、本体は実行するまで何を提供するか分からない。

### Current decision

担当形式は `manifest.json` の `formats`。本体がロード時に読む。プラグイン API に `register_format` は無い。サイドバーの有無は `sidebar`。`register_sidebar` は宣言済みだけ通す。未宣言は読み込み失敗。プラグイン設定の状態は「失敗: 権限がない登録がありました」。

### Why

本体が実行前に知るため。`workflow.mdc` / `plugins.mdc`。権限（`permissions`）と混ぜない。

### Consequences

新しい形式やサイドバーを足すときは、先に manifest を書く。

### Status

採用中。

---

## 権限は manifest.permissions

### Context

非表示のサイドバーでも `current_changed` を受け取り、裏でネットワークしていた。プラグイン側で間引くと、本体が止められない。

### Current decision

権限は `manifest.permissions`。既知キーは `inactive_callback` と `filter`。値は JSON の `true` / `false` だけ。文字列や数値は読み込み失敗。プラグイン API の引数では受け取らない。サイドバーを登録したプラグインは、ドックが全部非表示なら `current_changed` を受け取らない。非表示でも欲しいときだけ `inactive_callback: true`。表示画像を書き換える `register_filter` は `filter: true` が必須。無ければ読み込み失敗。プラグイン設定の状態は「失敗: 権限がない登録がありました」。

### Why

ホスト強制の default-deny。Android 風の許可 UI を作るためではなく、本体が止められるようにするため。会話と `plugins.mdc` で確定。

### Consequences

新しい「本体だけが止められる力」は API ではなく manifest に載せる。未知キーは無視。`"false"` を False と読まない（`bool("false")` は True になるため）。

### Status

採用中。

---

## 画像フィルターは台帳と pipe を分ける

### Context

ビルドイン補正とプラグイン加工を別ルートにすると、メニューと適用順が分岐する。プラグイン OFF で pipe から ID を消すと、再 ON・再起動で有効状態を忘れる。

### Current decision

ビルドインもプラグインも同じ `register_filter` 台帳。適用・メニュー・有効化は公開 ID だけ見る。`config.filters.pipe` は有効化した順の ID リスト。無効化は pipe から除く。プラグイン自体の OFF は `clear_plugin` が台帳だけ落とす。pipe の ID は残し、再 ON で `register_filter` すれば同じ位置で戻る。プラグインの値は `register_config`。v1 の `process` は同期・短時間。processed cache と順の D&D は今回やらない。

### Why

会話で確定。ChatGPT 指示書の interceptor / ロードオーダー / 別 Processor メニューは採用しない。

### Consequences

空 pipe と `builtin:basic` の identity は同一オブジェクト（copy なし）。未登録 ID はスキップ。プラグイン ON とフィルター pipe は別。

### Status

採用中。

---

## 原画オブジェクトをプラグインに渡さない

### Context

cache へ再格納しなくても、受け取った `PIL.Image` を in-place に変えると cache 内の原画が壊れる。

### Current decision

実効フィルターがあるときだけ working copy を1回作る。プラグインの `process` には cache と同一のオブジェクトを渡さない。失敗はその段をログしてスキップする。

### Why

原画キャッシュを表示経路の加工から守る。IMAGE_LOADING の Decode → cache → pipe → `ImageView`。

### Consequences

空 pipe は最速。v1 は表示都度 pipe。ズーム／パン／回転は既存 QImage 側なので再 pipe しない。

### Status

採用中。

---

## 商品情報の cache は product ID 単位

### Context

同一フォルダに別商品 ID のファイルが並ぶ。folder path で Web 結果を覚えると、RJ111 の取得を RJ222 が再利用する。取得中に別 ID へ移ると、古い結果が画面を上書きしうる。

### Current decision

cache key は `(kind, product_id)`。完了時に今の `_product_key` と一致しない結果は捨てる。走っている QThread は `quit()` しない。

### Why

スキップは既に product ID、cache だけ folder だった。会話と追加修正の P0。

### Consequences

info.json があるときはファイル優先（現行どおり）。同じ ID のページ送りは今までどおり再取得しない。

### Status

採用中。

---

## 配布は ZIP または展開フォルダ。DLL は未対応

### Context

`DllBackend` の口がある。

### Current decision

読むのは `.zip` と `manifest.json` 付きフォルダ。`DllBackend.load` は常に `None`。

### Why

実装どおり。未対応を「予定」とは書かない。

### Consequences

`.dll` を置いてもロードされない。警告ログだけ。

### Status

採用中（DLL は未実装）。

---

## 仮想パスで archive member を表す

### Context

アーカイブ内の 1 枚を、フォルダ内の実ファイルと同じページ列に載せたい。

### Current decision

`archive://アーカイブパス|エントリ名`。解析は `VirtualPathHandler`。

### Why

現行コードの表現。採用理由の古い文書は見当たらない（Why: 現行実装から、形式自体は確定。採用経緯は不明）。

### Consequences

キャッシュキーは `resolved_archive|filename`。実パスと混ぜて `current_files` に載る。

### Status

採用中。

---

<a id="zip-snapshot"></a>

## ZIP はスナップショット

### Context

フォルダのページ送りでは、隣のファイルを再計算することがある。ZIP の namelist を毎回取る動きと混同しやすい。

### Current decision

ZIP（および同様のアーカイブ一覧）は開いたときのエントリ一覧を使う。フォルダの「次ファイル再計算」とは分ける。ページごとの namelist は metadata cache で避ける。一覧そのものを毎ページ作り直さない。

### Why

開発中の確認。ZIP の namelist はハンドル非保持の member 参照であり、フォルダ走査の延長ではない。

### Consequences

アーカイブを差し替えたあとは fingerprint（mtime / size）が変われば cache が無効。session 切り替えでも cache は消える。

### Status

採用中。

---

<a id="prefetch-follow"></a>

## 先読みは現在位置追従の優先schedulerで処理する

### Context

連写 ZIP で先読みが効いていないように見えたため、まずページ移動後に先読み窓を追従させた。しかし実働は単一workerとFIFOのままで、古い未開始task、cache churn、0.4秒後の二重decodeにより、順送りでも先読みが枯渇し得た。

### Current decision

`next_file` / `prev_file` / `go_to_page` は `_move_to_index` 経由で `_prefetch_around` する。実働は `ImageLoadScheduler` の共通 `PriorityQueue` と設定された本数のworker。ページ移動ごとのgenerationとtaskごとの単調増加tokenで、古い未開始taskをqueueから除去する。すでにworkerが取得した旧taskも開始前検証で捨て、開始済みdecodeは中断しない。

優先方向は最後の改ページ方向と現在位置からの距離で決める。現在ページのcache missは引き続きGUI同期だが、未開始prefetchはforegroundがclaimし、background実行中なら同じ完了を待つ。

### Why

計測と再現テストで、窓へ追加されることだけでは処理順を保証できず、単一workerが古いtaskを消化する間に現在位置が先読みへ追いつく構造が確認できた。workerを増やすだけでは古い仕事と二重decodeも増えるため、priority・generation・decode所有権を同じschedulerへ集約した。

### Consequences

同一Plugin instanceの `list_entries` / `read_entry` はforegroundを含めPlugin単位で直列化する。archive metadataはsource単位で構築を共有し、異なるarchiveは並列に処理できる。現在ページの完全非同期化は含めない。

### Status

採用中。

---

## 画像読込worker数は起動時に解決してprocess内で固定する

### Context

固定3本では端末性能や負荷の好みに合わせられない。一方、設定保存後に新しいタブだけ別のworker数を使うと、同じprocess内でpool構成が混在し、「再起動後に反映」という説明とも矛盾する。

### Current decision

`cache.image_loader_workers` は `"auto"` または1～8。autoは論理CPU数から保守的に1～6を選び、CPU数を取得できない場合は3とする。起動プロファイルとruntime overrideを適用したあと、configured値、論理CPU数、effective値を `Config` に固定する。設定保存やプロファイル切替ではeffective値を変えず、次回起動から反映する。

worker poolはFileHandlerごとに所有する。shared scheduler化とruntime resizeは行わない。

### Why

pool再構築中のdecode・cache・session所有権を増やさず、全タブの挙動と設定画面の説明を一致させるため。auto上限6は、複数タブでFileHandlerごとのthread数が加算される点も考慮した保守値。

### Consequences

設定画面は現在のeffective値を表示する。worker数を増やすと先読みが速くなる場合がある一方、複数タブではCPU・メモリ・I/O負荷が重なる。24論理CPUでの生成素材benchmarkでは通常画像は2本以上で改善したが、高解像度ZIPは256MB cacheに対して4本以上で追放と再decodeが増えた。単一端末の結果だけでCPU帯ごとのauto表は変更しない。詳細は [IMAGE_LOADING.md](IMAGE_LOADING.md#2026-09-21-の生成素材benchmark)。

### Status

採用中。

---

## metadata cache を先にし、重複 decode を次にした

### Context

体感とクラッシュ回避の改善候補が複数あった。

### Current decision

1. アーカイブ metadata cache
2. schedulerによるcache key単位のdecode所有権
プラグイン一覧 cache は後回し。

### Why

ページごとの namelist と、同期 `get_image_at` と worker の競合が先に効く、という優先（会話で確定）。

### Consequences

`debug.cache_archive_metadata`（既定 True）。foregroundがbackground decodeへ追いついた場合は同じ完了eventを待つ。タイムアウト後に同じ画像をforegroundでもdecodeするfallbackは持たない。

### Status

1 と 2 は実装済み。プラグイン一覧 cache は未着手。

---

## 現行ページは GUI 同期 load

### Context

先読み worker がある。現行ページも非同期にできる。

### Current decision

`get_image_at` が呼び出しスレッド（GUI）で同期的に読む。先読みだけ worker。

### Why

現行実装。なぜ同期のままかはコードから断定できない（Why: 不明）。体感上、現行ページの待ちはここが支配しやすい、とは実装から言える。

### Consequences

PriorityQueue を足しても、現行ページの同期待ちは残る。

### Status

採用中。

---

## アーカイブハンドルは既定で保持しない

### Context

`debug.keep_archive_handles` がある。ZIP / TAR は保持できる。7z / RAR は都度開閉。

### Current decision

既定は保持しない。保持時も 7z / RAR はここで保持しない。

### Why

コメントは「新しい方式」「都度開閉」「ディレクトリハンドルをすぐ離す」。ファイルロック防止などと断定できる根拠は無い（Why: 不明）。

### Consequences

非保持でも先読みは動かす（都度開閉）。metadata cache が namelist コストを抑える。

### Status

採用中。

---

## クラッシュは推測で直さない

### Context

「すぐ落ちる」を見当で直すと、スレッド寿命を取り違えやすい。

### Current decision

先に直前の呼び出しと、スレッドが残る調査ログを入れる。根拠が揃ってから直す。動いている `QThread` の Python 参照を、`wait()` せず捨てない。

### Why

[`.cursor/rules/workflow.mdc`](../.cursor/rules/workflow.mdc) と `plugins.mdc`。

### Consequences

調査ログを残したまま直す。ログだけのコミットもあり得る。

### Status

採用中。

---

<a id="test-layout"></a>

## テストは 1ソース n ファイル。本番データは触らない

### Context

巨大化したあと、1 ファイルが複数モジュールを兼ねると切れない。

### Current decision

置き場は本番と同じ階層。1 テストファイルが 2 ソースを兼ねない。本番の `%APPDATA%`、リポジトリの `config.db`、プラグイン singleton は触らない。`MainWindow` 全体や描画の自動テストは書かない。

### Why

[`.cursor/rules/tests.mdc`](../.cursor/rules/tests.mdc)。

### Consequences

共通土台は `tests/conftest.py`。import はフルパス。互換レイヤは置かない。

### Status

採用中。

---

## プラグイン API の互換ポリシー

### Context

`manifest.api_version` は `1` 必須。

### Current decision

包括的な後方互換ポリシーは明文化されていない。勝手に作らない。契約を変えたら `docs/plugins.md` とユーザーマニュアルを直す。

### Why

現行 docs。ChatGPT 指示書どおり、無いポリシーは「確認できない」と書く。

### Consequences

「互換のため残す」レイヤは置かない（tests.mdc）。

### Status

ポリシー未策定。`api_version` 1 のみ確定。
