# Example ZIP Loader

Sample archive plugin. Opens `.zip` through the plugin and shows images inside as pages. Encrypted ZIP (ZipCrypto / AES) uses the host password dialog (`host.ask_password`). Images get a color overlay and label. Not for production.

| Field | Value |
| --- | --- |
| ID | `com.ezco.example.zip` |
| Version | `1.1.0` |
| Kind | File (archive) |
| ZIP | `dist-sample-plugins/example_zip.zip` |
| Entry | `loader:FileLoader` |
| LICENSE | Root `LICENSE.txt` (plain-text display check) |

## Usage

1. Put `example_zip.zip` in the `plugins/` folder next to the executable
2. Start EzCo (restart if it was already running)
3. Enable the plugin in Plugin Settings
4. Set the `.zip` loader to this plugin (Built-in is the default)

Password-protected ZIPs open the host password dialog. Cancel leaves the archive closed.

There are no settings or custom actions.

## Development

Source lives in `plugins/example_zip/`. `pyzipper` comes from the host. Put that folder in the data `plugins/` directory to load it. Packaged ZIP is in `dist-sample-plugins/`.

See the [Plugin Reference](../../resources/UserManual/files/plugin-reference-en.html) and [docs/plugins.md](../../docs/plugins.md).
