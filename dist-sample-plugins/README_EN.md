# Packaged sample plugins

The `.zip` files here are ready-made samples. Copy them into the `plugins/` folder in the data directory (Settings → data location). Restart EzCo after copying. On/off and handler changes apply on Plugin Settings OK / Apply; no restart.

EzCo does not inspect plugin code. Placed code runs with the same privileges as the app. Full notice: [plugins/README_EN.md](../plugins/README_EN.md).

For development, use the unpacked folders under `plugins/` in the repo. Point the data location at the executable folder to load those folders directly. Rebuild a ZIP only when you distribute it.

| File | What it does |
| --- | --- |
| `example_png-1.0.0.zip` | Opens `.png` through a plugin. Root file is `LICENSE` (no extension) |
| `example_zip-1.1.0.zip` | Opens `.zip` through a plugin. Root file is `LICENSE.txt` |
| `example_txt-1.0.0.zip` | Renders `.txt` as image pages. Root file is `LICENSE.md` |
| `product_info-1.0.0.zip` | Product info sidebar. No LICENSE |
| `error_setup-1.0.0.zip` | Raises in `setup()`. All three LICENSE files; viewer shows md |
| `error_callback-1.0.0.zip` | Raises from a callback. txt and bare LICENSE; viewer shows txt |
| `config_types-1.0.0.zip` | Registers every config type (bool / string / int / float / int_range / float_range / path / password / color / date / datetime / choice / font) |
| `example_filter-1.0.0.zip` | Display filter. Overlays color and a label. Font size is an `int_range` with `sync` and `reload` |

Rebuild from source with task **“EzCo: プラグインZIP”** or `poetry run pack-plugins`. One folder: `poetry run pack-plugins example_txt`. Output is `<folder>-<version>.zip`. Invalid manifests are logged and skipped; the command prints success / fail counts.
