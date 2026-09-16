# Config Types Probe

Test plugin. Registers every host config type and shows the stored values in a sidebar. Not for production.

| Item | Value |
| --- | --- |
| ID | `com.ezco.config_types` |
| Version | `1.0.0` |
| Kind | Sidebar |
| ZIP | `dist-sample-plugins/config_types-1.0.0.zip` |
| Entry | `plugin:ConfigTypesPlugin` |
| LICENSE | Root `LICENSE.md` |

Types: `bool` / `string` / `int` / `float` / `color` / `date` / `datetime` / `choice` / `font`. `date` and `datetime` store Unix seconds (number). `color` stores `#RRGGBB`.

## Usage

1. Put `config_types.zip`, or this folder, directly under the data folder `plugins/`
2. Start EzCo (restart if it was already running)
3. Enable this plugin in Plugin Settings
4. Open Settings on the row and try each control
5. After OK / Apply, check that the Config types sidebar matches the Stored line

Turn the plugin off when you are done.

## Development

Source is `plugins/config_types/`. Place that folder under the data `plugins/` directory to load it unpacked. Packaged ZIP is in `dist-sample-plugins/`.
