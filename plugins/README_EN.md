# EzCo plugins

Put a ZIP, or an unpacked folder with `manifest.json`, in the data folder `plugins/` (Settings → Data location; default is this user's data folder) to add image or archive formats, sidebars, and display filters. To use this repo folder while developing, set the data location to the same folder as the executable.

Developer contract and APIs: [docs/plugins.md](../docs/plugins.md) and the [Plugin Reference](../resources/UserManual/files/plugin-reference-en.html). Each plugin has a `README_EN.md`. Packaged ZIPs are in [dist-sample-plugins/](../dist-sample-plugins/). Rebuild with task **“EzCo: プラグインZIP”** or `poetry run pack-plugins`. Japanese: [README.md](README.md).

## Notice

EzCo does not inspect plugin code. Code in a ZIP or folder runs with the same privileges as the app once you place it. The EzCo developers are not responsible for damage from malicious or defective plugins. Trust the publisher, and read the source if needed. Responsibility lies with the plugin publisher and the person who installs it. The startup notice is Markdown under `src/ez_co/resources/plugin_consent/`. After changing the text, raise `version.txt` in that folder.

## Restart vs Apply

- **Restart required:** after you add a new ZIP or folder under `plugins/`, or remove one
- **Plugin Settings OK / Apply is enough:** on/off, per-extension handler, and changing a duplicate-id choice. Open files are reloaded and sidebars remounted here
- Adding a file while EzCo is running does not update the list until you restart

## For users

1. Place a `.zip`, or a folder that contains `manifest.json`, directly under the data folder `plugins/` (nested folders are ignored). The location is Settings → Data location
2. Start EzCo (restart if it was already running). If plugins are present and you have not accepted yet, a Yes / No dialog appears. Yes stores this user's consent version, then shows the duplicate-id dialog if needed, then loads. No does not load plugins this session and hides Plugin Settings from the menu. The question returns on the next start, and again if the consent version is raised
3. In Plugin Settings, turn plugins on or off and choose built-in, plugin, or Don't load per extension. Plugins with a settings schema can be changed from Settings; that saves immediately. If the root has `LICENSE.md`, `LICENSE.txt`, or `LICENSE` (in that order), License opens it. Display is not a guarantee. OK / Apply on the host dialog reloads open files and unmounts disabled sidebars. Sidebar toggles and plugin actions can be bound to shortcuts and gestures
4. For extensions the host already knows, the built-in handler is used by default
5. Drag list headers to resize or reorder columns. Layout is saved
6. Enabled plugin extensions appear in the file dialog under Supported Files and Plugin formats, and in folder scans

If more than one plugin has the same `id`, choose which one to load (or Don't load) at startup. The choice is saved and is not asked again unless a new unresolved duplicate id appears. Change it later with Choose duplicate plugins in Plugin Settings (OK / Apply; no restart). Unselected plugins stay in the list with a reason. DLL plugins are not supported.
