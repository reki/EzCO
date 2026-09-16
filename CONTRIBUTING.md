# Contributing to EzCo

[日本語](#japanese) | [English](#english)

---

## Japanese

EzCoへの貢献をありがとうございます。開発・実行・ビルドは **Cursor / VS Code の Launch と Task** から行います。

推奨エディタ: [Cursor](https://cursor.com/) または [VS Code](https://code.visualstudio.com/)。Python 拡張（debugpy）が必要です。

## 開発環境のセットアップ

前提: Windows、Python 3.10 以上（推奨 3.12）、[Poetry](https://python-poetry.org/docs/#installation)

1. **リポジトリをクローンしてフォルダを開く**
   ```bash
   git clone https://github.com/YOUR_USERNAME/ez_co.git
   ```
   Cursor / VS Code でそのフォルダを開きます。

2. **初期化**  
   実行とデバッグ（`F5`）から **「▶ 初期化 (poetry run init-env)」** を選ぶか、タスク **「EzCo: 初期化」** を実行します。Poetry の依存とコンパイラ確認が走ります。

3. **動作確認**  
   同じく **「Python: EzCo」** を選んで `F5` します。`PYTHONPATH=src` は `launch.json` で付きます。

その他の Launch:

| 名前 | 用途 |
| --- | --- |
| Python: EzCo | 通常起動 |
| Python: EzCo(Archive:False) | アーカイブ無効 |
| Python: EzCo(Profile:Test) | プロファイル「テスト」 |
| ▶ ビルド (poetry run build) | Nuitka 標準ビルド |
| ▶ ビルド (--safe-mode) | 最適化なしビルド |
| ▶ 頒布用zip (poetry run collect) | 頒布用 zip 作成 |
| ▶ インストーラ (poetry run installer) | Inno Setup インストーラ作成（PATH に ISCC） |
| ▶ 初期化 (poetry run init-env) | 環境初期化 |
| ▶ テスト (poetry run pytest) | テスト実行 |
| ▶ プラグインZIP (poetry run pack-plugins) | `plugins/` を `dist-sample-plugins/<名前>-<version>.zip` にする |
| py-spy: top / record … | プロファイラ |

ターミナルから同じことをする場合の例（通常は不要）:

```bash
poetry run init-env
poetry run python -m ez_co.main
poetry run build
poetry run build -- --safe-mode
poetry run collect
poetry run installer
poetry run pack-plugins
poetry run pytest
```

## 貢献の方法

### バグレポート
- [Bug Report Issue](../../issues/new?template=bug_report.md) を使う
- 再現手順と環境（OS、バージョン）を書く

### 機能リクエスト
- [Feature Request Issue](../../issues/new?template=feature_request.md) を使う
- 背景と理由を書く

### コード貢献

1. 既存 Issue を確認するか、新しく作る
2. ブランチを切る: `git checkout -b feature/your-feature-name`
3. 本体の書き方に合わせ、必要なところだけコメントする
4. **「Python: EzCo」** で手動確認する。自動テストは **「▶ テスト」** またはタスク **「EzCo: テスト」**。配布物を見るときだけ **「▶ ビルド」** または **「▶ ビルド (--safe-mode)」**
5. [Pull Request](../../compare) で変更内容を説明する

プラグインを触る場合は [docs/plugins.md](docs/plugins.md) と [plugins/README.md](plugins/README.md) を見てください。開発中は `plugins/` のフォルダがそのまま読めます。配布するときだけ **「EzCo: プラグインZIP」** または `poetry run pack-plugins` で [`dist-sample-plugins/`](dist-sample-plugins/) の `.zip` を作り直します。新しい ZIP／フォルダを置いたあとは再起動、ON/OFF や読み込み方式はプラグイン設定の OK / 適用で足ります。本体は中身を検査しません。全体構造は [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)、開発時の注意（データ場所・テスト配置・py-spy）は [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) です。

## コードスタイル

- PEP 8。エディタの Pylint（`.pylintrc`）を使う
- 必要なら `poetry run pylint src/ez_co`

### コミットメッセージ
```
type: 簡潔な説明

詳細な説明（必要に応じて）

- 変更点1
- 変更点2
```

**Type:** `feat` / `fix` / `docs` / `style` / `refactor` / `test` / `chore`

## ライセンス

貢献コードは本体と同じ [MIT License](LICENSE) です。依存ライブラリは [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) を見てください。pylint は GPL ですが開発専用で、アプリには入れません。

## 質問

[Issues](../../issues) で聞いてください。

---

## English

Thank you for contributing to EzCo. Development, run, and build are done from **Cursor / VS Code Launch and Tasks**.

Recommended editors: [Cursor](https://cursor.com/) or [VS Code](https://code.visualstudio.com/). The Python (debugpy) extension is required.

## Development Environment Setup

Requires Windows, Python 3.10+ (3.12 recommended), and [Poetry](https://python-poetry.org/docs/#installation).

1. Clone the repo and open the folder in Cursor / VS Code.
2. Run **“▶ 初期化 (poetry run init-env)”** from Run and Debug (`F5`), or the **“EzCo: 初期化”** task.
3. Start **“Python: EzCo”** with `F5`. `PYTHONPATH=src` is set in `launch.json`.

| Launch name | Purpose |
| --- | --- |
| Python: EzCo | Normal run |
| Python: EzCo(Archive:False) | Archives disabled |
| Python: EzCo(Profile:Test) | Profile “テスト” |
| ▶ ビルド (poetry run build) | Nuitka release build |
| ▶ ビルド (--safe-mode) | Build without extra optimization |
| ▶ 頒布用zip (poetry run collect) | Distribution zip |
| ▶ インストーラ (poetry run installer) | Inno Setup installer (ISCC on PATH) |
| ▶ 初期化 (poetry run init-env) | Environment setup |
| ▶ テスト (poetry run pytest) | Run tests |
| ▶ プラグインZIP (poetry run pack-plugins) | Pack `plugins/` into `dist-sample-plugins/<name>-<version>.zip` |
| py-spy: top / record … | Profiler |

CLI equivalents (optional):

```bash
poetry run init-env
poetry run python -m ez_co.main
poetry run build
poetry run build -- --safe-mode
poetry run collect
poetry run installer
poetry run pack-plugins
poetry run pytest
```

## How to Contribute

### Bug Reports
Use [Bug Report Issue](../../issues/new?template=bug_report.md). Include steps and environment.

### Feature Requests
Use [Feature Request Issue](../../issues/new?template=feature_request.md). Explain why.

### Code Contributions

1. Check or open an Issue.
2. `git checkout -b feature/your-feature-name`
3. Match existing style. Comment only where it helps.
4. Verify with **“Python: EzCo”**. Run tests with **“▶ テスト”** or the **“EzCo: テスト”** task. Use **“▶ ビルド”** or **“▶ ビルド (--safe-mode)”** only when you need a packaged build.
5. Open a [Pull Request](../../compare) and describe the change.

For plugins, see [docs/plugins.md](docs/plugins.md) and [plugins/README.md](plugins/README.md). Folders under `plugins/` load as-is while developing. Rebuild the `.zip` in [`dist-sample-plugins/`](dist-sample-plugins/) with **“EzCo: プラグインZIP”** or `poetry run pack-plugins` only when distributing. Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Local notes (data dir, tests, py-spy): [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Code Style

- PEP 8. Use the editor Pylint (`.pylintrc`).
- Optional: `poetry run pylint src/ez_co`

### Commit Messages
```
type: brief description

Detailed description (if needed)

- Change 1
- Change 2
```

**Types:** `feat` / `fix` / `docs` / `style` / `refactor` / `test` / `chore`

## License

Contributions are under the same [MIT License](LICENSE). Third-party licenses: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). pylint is GPL and is development-only; do not ship it with the app.

## Questions

Please ask in [Issues](../../issues).
