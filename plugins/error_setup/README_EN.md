# Error Setup Probe

Test plugin. `setup()` always raises. Not for production.

| Field | Value |
| --- | --- |
| ID | `com.ezco.error_setup` |
| Version | `1.0.0` |
| Kind | Sidebar (setup only) |
| ZIP | `dist-sample-plugins/error_setup.zip` |
| Entry | `plugin:ErrorSetupPlugin` |
| LICENSE | Ships `LICENSE.md`, `LICENSE.txt`, and `LICENSE`. The viewer must show `LICENSE.md` |

## Usage

1. Put `error_setup.zip` in `plugins/` next to the executable
2. Start EzCo (restart if it was already running)
3. Enable the plugin in Plugin Settings and apply
4. The status column should show Failed
5. If Development → “Show error log when an error occurs” is on, a stack-trace dialog also appears

Disable the plugin when you are done.

## Development

Source is `plugins/error_setup/`. Put that folder in the data `plugins/` directory to load it. Packaged ZIP is in `dist-sample-plugins/`.
