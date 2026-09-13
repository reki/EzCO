# Packaged sample plugins

The `.zip` files here are ready-made samples. Copy them into the `plugins/` folder in the data directory (Settings → data location). Restart EzCo after copying. On/off and handler changes apply on Plugin Settings OK / Apply; no restart.

EzCo does not inspect plugin code. Placed code runs with the same privileges as the app. Full notice: [plugins/README_EN.md](../plugins/README_EN.md).

For development, use the unpacked folders under `plugins/` in the repo. Point the data location at the executable folder to load those folders directly. Rebuild a ZIP only when you distribute it.

| File | What it does |
| --- | --- |
| `example_png.zip` | Opens `.png` through a plugin. Root file is `LICENSE` (no extension) |
| `example_zip.zip` | Opens `.zip` through a plugin. Root file is `LICENSE.txt` |
| `example_txt.zip` | Renders `.txt` as image pages. Root file is `LICENSE.md` |
| `product_info.zip` | Product info sidebar. No LICENSE |
| `error_setup.zip` | Raises in `setup()`. All three LICENSE files; viewer shows md |
| `error_callback.zip` | Raises from a callback. txt and bare LICENSE; viewer shows txt |
| `config_types.zip` | Registers every config type (bool / string / int / float / color / date / datetime / choice / font) |

See [README.md](README.md) for a zip-from-source snippet.
