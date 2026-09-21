# 開発時の注意

セットアップ、Launch、ビルド、pytest の起動は [CONTRIBUTING.md](../CONTRIBUTING.md) が正です。ここは、動かし始めてから迷いやすいことだけです。全体構造は [ARCHITECTURE.md](ARCHITECTURE.md)、判断は [DECISIONS.md](DECISIONS.md) です。

---

## 必要環境（要点）

- Windows
- Python `>=3.10,<3.14`（[`pyproject.toml`](../pyproject.toml)。推奨は CONTRIBUTING どおり 3.12）
- [Poetry](https://python-poetry.org/docs/#installation)
- 初期化は Launch の「▶ 初期化 (poetry run init-env)」またはタスク「EzCo: 初期化」

存在しないコマンドは書きません。ターミナルから同じことをする例は CONTRIBUTING にあります。

---

## データの置き場

実行時のルートは `get_data_root()` です。[`data_location.py`](../src/ez_co/utils/data_location.py)。`user.json` の `data_location` が `user` / `exe` / `custom` です。

| モード | ルート |
| --- | --- |
| `user`（未設定時もこちら） | `%APPDATA%/EzCo` |
| `exe` | `get_project_root()`（開発中はリポジトリ直下） |
| `custom` | `custom_path` |

`config.db`、`plugins/`、デバッグ時の `logs/` はルートの下です。同意バージョンは場所設定と同じ `user.json` にあります。

UI には `%APPDATA%` と出さず「このユーザーのデータフォルダ」と書きます（`ui-strings.mdc`）。

**なぜ:** テストや手元の実験が、使っている本体の DB を壊さないようにするためです。[DECISIONS.md](DECISIONS.md#test-layout)

---

## テスト

- 置き場は本番と同じ階層。`src/ez_co/plugins/manager.py` → `tests/ez_co/plugins/test_manager_*.py`
- **1ソース : n テストファイル**。1 テストファイルが 2 ソースを兼ねない
- 先頭の docstring に `対象: モジュールパス`
- 共通土台は `tests/conftest.py`
- 本番の `%APPDATA%`、リポジトリの `config.db`、プラグイン singleton は触らない
- `MainWindow` 全体や描画の自動テストは書かない
- 実行は Launch「▶ テスト (poetry run pytest)」または `poetry run pytest`

特定ファイルだけなら `poetry run pytest tests/ez_co/handlers/test_file_handler_prefetch_follow.py` です。

---

## デバッグ設定

[`Config.debug`](../src/ez_co/config.py) にあるものだけです。

| キー | 既定 | 意味 |
| --- | --- | --- |
| `debug.enabled` | `False` | デバッグモード。ログファイルを出す |
| `debug.keep_archive_handles` | `False` | ZIP / TAR などのハンドル保持 |
| `debug.cache_archive_metadata` | `True` | アーカイブ一覧の fingerprint cache |
| `debug.show_error_log` | `False` | エラーログ表示 |

先読み窓は `cache.prefetch_pages`（設定の既定 **5**）。メモリ上限は `cache.memory_limit`（`Config` の既定 `"256MB"`、新規設定では物理RAM 16GiB以上で `"512MB"`）。推奨値の決め方は [IMAGE_LOADING.md](IMAGE_LOADING.md#推奨値とオンデマンド実測) です。

ログディレクトリは `logs_dir()` = `get_data_root() / "logs"` です。

---

## py-spy

Launch の「py-spy: top / record SVG / record speedscope」と [`.vscode/pyspy.ps1`](../.vscode/pyspy.ps1) を使います。

`.venv/Scripts/python.exe` は venvlauncher なので、py-spy は中を見れません。スクリプトは `pyvenv.cfg` の `base-executable` を使い、venv の site-packages を `PYTHONPATH` に載せます。

SVG の出力先はリポジトリ直下の `py-spy-ezco.svg` です（スクリプトの `-o`）。

---

## ビルド

Nuitka の Launch（「▶ ビルド」「▶ ビルド (--safe-mode)」「▶ 頒布用zip」「▶ インストーラ」）に任せます。`collect` で実行中の `EzCo.exe` が消せなくても失敗にしない、は `workflow.mdc` です。サンプルプラグインの ZIP は **「EzCo: プラグインZIP」** または `poetry run pack-plugins` です。出力は `<フォルダ>-<version>.zip`。manifest の誤りはログしてスキップし、最後に成功／失敗件数を出します。

---

## エージェント向けルール

Cursor はこのリポジトリの [`.cursor/rules/`](../.cursor/rules/) を読みます。他ツール向けの短い入口は [AGENTS.md](../AGENTS.md) です。
