# Example Text Pages

A general-purpose sample that opens `.txt` as image pages. The body is wrapped into PNGs so Next / Previous in the host moves through the text. The sidebar sets font, colors, margins, and horizontal / vertical reading. Changes apply immediately.

| Field | Value |
| --- | --- |
| ID | `com.ezco.example_txt` |
| Version | `1.0.0` |
| Kind | File (archive) |
| ZIP | `dist-sample-plugins/example_txt.zip` |
| Entry | `plugin:TextImagePlugin` |

## Usage

1. Put `example_txt.zip` in the `plugins/` folder in the data directory
2. Start EzCo (restart if it was already running)
3. Enable the plugin in Plugin Settings
4. Open a `.txt` file (Built-in does not handle `.txt`, so this loader is used once enabled)

Until you save a font, the host UI font is used. When a change alters the page count, the view restarts from the first character of the page you were on. Combinations that cannot fit a single line are rejected and the sidebar is restored. If the view does not update, press Refresh in the sidebar.

## Development

Source lives in `plugins/example_txt/`. Put that folder in the data `plugins/` directory to load it. Packaged ZIP is in `dist-sample-plugins/`.

See the [Plugin Reference](../../resources/UserManual/files/plugin-reference-en.html) and [docs/plugins.md](../../docs/plugins.md).
