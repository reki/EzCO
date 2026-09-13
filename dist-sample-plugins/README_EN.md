# Packaged sample plugins

The `.zip` files here are ready-made samples. Copy them into the `plugins/` folder in the data directory (Settings → data location).

For development, use the unpacked folders under `plugins/` in the repo. Point the data location at the executable folder to load those folders directly. Rebuild a ZIP only when you distribute it.

| File | What it does |
| --- | --- |
| `example_png.zip` | Opens `.png` through a plugin |
| `example_zip.zip` | Opens `.zip` through a plugin |
| `example_txt.zip` | Renders `.txt` as image pages |
| `product_info.zip` | Product info sidebar |
| `error_setup.zip` | Raises in `setup()` |
| `error_callback.zip` | Raises from a callback |

See [README.md](README.md) for a zip-from-source snippet.
