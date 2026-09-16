# Error Callback Probe

Test plugin. The sidebar Error button raises in a callback. Not for production.

| Field | Value |
| --- | --- |
| ID | `com.ezco.error_callback` |
| Version | `1.0.0` |
| Kind | Sidebar |
| ZIP | `dist-sample-plugins/error_callback-1.0.0.zip` |
| Entry | `plugin:ErrorCallbackPlugin` |
| LICENSE | Ships `LICENSE.txt` and `LICENSE` (no md). The viewer must show `LICENSE.txt` |

## Usage

1. Put `error_callback.zip` in `plugins/` next to the executable
2. Start EzCo (restart if it was already running)
3. Enable the plugin in Plugin Settings
4. Open the Error probe sidebar and click Error
5. The app keeps running. If Development → “Show error log when an error occurs” is on, a stack-trace dialog appears

The same exception is raised if you bind the Error action to a shortcut. Disable the plugin when you are done.

## Development

Source is `plugins/error_callback/`. Put that folder in the data `plugins/` directory to load it. Packaged ZIP is in `dist-sample-plugins/`.
