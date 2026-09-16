# Error Register Probe

Test plugin. Calls `register_sidebar` from `setup()` with neither `sidebar` nor `permissions.filter` in the manifest. Not for production.

| Field | Value |
| --- | --- |
| ID | `com.ezco.error_register` |
| Version | `1.0.0` |
| Kind | Probe (setup only) |
| ZIP | `dist-sample-plugins/error_register-1.0.0.zip` |
| Entry | `plugin:ErrorRegisterPlugin` |
| LICENSE | `LICENSE.md` |

## Usage

1. Put `error_register.zip` in `plugins/` next to the executable
2. Start EzCo (restart if it was already running)
3. Enable the plugin in Plugin Settings and apply
4. The status column should show "Failed: A registration without permission"

Disable the plugin when you are done.

## Development

Source is `plugins/error_register/`. Put that folder in the data `plugins/` directory to load it. Packaged ZIP is in `dist-sample-plugins/`.
