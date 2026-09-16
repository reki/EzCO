# Example Filter

Sample display filter. Overlays a teal tint and label on the open image. Font size is an `int_range` with `sync=True` and `reload=True`. Not for production.

| Field | Value |
| --- | --- |
| ID | `com.ezco.example.filter` |
| Version | `1.0.0` |
| Kind | Filter |
| ZIP | `dist-sample-plugins/example_filter-1.0.0.zip` |
| Entry | `plugin:ExampleFilterPlugin` |
| LICENSE | Root `LICENSE.md` |
| Public ID | `plugin:com.ezco.example.filter:overlay` |

Turning the plugin on does not run `process`. Enable Overlay in the Filter menu. Plugin on/off and the filter pipe are separate.

`config_types` uses `int_range` with `sync` only. This sample also sets `reload` so the overlay size updates after the slider.

## Usage

1. Put `example_filter-1.0.0.zip`, or this folder, directly under the data folder `plugins/`
2. Start EzCo (restart if it was already running)
3. Enable this plugin in Plugin Settings
4. Open an image
5. Enable Overlay in the Filter menu
6. Change Font size from that menu's Settings, or from Settings on the plugin row

After 0.5s idle the value is saved and the label size changes. Turn the filter off when you are done.

## Development

Source is `plugins/example_filter/`. Place that folder under the data `plugins/` directory to load it unpacked. Packaged ZIP is in `dist-sample-plugins/`.

See the [Plugin Reference](../../resources/UserManual/files/plugin-reference-en.html) and [docs/plugins.md](../../docs/plugins.md).
