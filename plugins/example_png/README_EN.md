# Example PNG Loader

Sample image plugin. Opens `.png` through the plugin and overlays a color tint plus the label プラグイン読み込み表示. Not for production.

| Field | Value |
| --- | --- |
| ID | `com.ezco.example.png` |
| Version | `1.0.0` |
| Kind | File (image) |
| ZIP | `dist-sample-plugins/example_png.zip` |
| Entry | `loader:FileLoader` |
| LICENSE | Root `LICENSE` (no extension; plain-text display check) |

## Usage

1. Put `example_png.zip` in the `plugins/` folder next to the executable
2. Start EzCo (restart if it was already running)
3. Enable the plugin in Plugin Settings
4. Set the `.png` loader to this plugin (Built-in is the default)

The overlay means the plugin handled the file. Switch back to Built-in or disable the plugin when you are done.

There are no settings or custom actions.

## Development

Source lives in `plugins/example_png/`. Put that folder in the data `plugins/` directory to load it. Packaged ZIP is in `dist-sample-plugins/`.

See the [Plugin Reference](../../resources/UserManual/files/plugin-reference-en.html) and [docs/plugins.md](../../docs/plugins.md).
