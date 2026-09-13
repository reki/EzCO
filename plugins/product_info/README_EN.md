# DLsite / DMM Product Info

Sidebar plugin for the current folder. Shows `info.json` and `folder.jpg` when present. Otherwise it fetches from the web if the folder or file name looks like a DLsite, DMM, or DLSoft id. Results are display-only and are not written to the folder.

| Field | Value |
| --- | --- |
| ID | `com.ezco.product_info` |
| Version | `1.0.0` |
| Kind | Sidebar |
| ZIP | `dist-sample-plugins/product_info.zip` |
| Entry | `plugin:ProductInfoPlugin` |
| LICENSE | None (License button stays `-`) |

## Usage

1. Put `product_info.zip` in the `plugins/` folder next to the executable
2. Start EzCo
3. Open the sidebar from the View menu, or bind a shortcut / gesture
4. Use Plugin Settings → Settings to turn web fetch on or off

Recognized ids include:

- DLsite: `RJ01530423` (`[RVBA]J` plus digits)
- DMM: `d_802808`
- DLSoft: `xxx_1234`

While fetching, the sidebar stays empty. Failures do not change the folder.

## Settings

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `fetch_web` | bool | `true` | Fetch from the web when `info.json` is missing |

## Actions

`register_sidebar` registers a toggle. The public id is `plugin:com.ezco.product_info:sidebar:product_info`. `toggle_product_info_dock` is an alias for older shortcut bindings.

## Development

Source lives in `plugins/product_info/`. Fetching uses the standard library only. Put that folder in the data `plugins/` directory to load it. Packaged ZIP is in `dist-sample-plugins/`.

See the [Plugin Reference](../../resources/UserManual/files/plugin-reference-en.html) and [docs/plugins.md](../../docs/plugins.md).
