# Auto page

Turns pages on each visible tab by calling the next-page or go-to-page action.

| Item | Value |
| --- | --- |
| ID | `com.ezco.auto_page` |
| Version | `1.0.0` |
| Kind | Sidebar |
| Entry | `plugin:AutoPagePlugin` |
| LICENSE | `LICENSE.md` at the plugin root |

## Use

1. Place this folder directly under `plugins/` in the data folder
2. Start EzCo (restart after adding it)
3. Enable it in Plugin Settings
4. Open the Auto page sidebar

The sidebar has a start page, an end page, an interval in seconds, From current page, Through current page, Start, and Loop. While running, Start becomes Stop. The initial interval is a plugin setting, default 1.0 seconds, from 0.1 seconds to 10 minutes, with one decimal place. Tabs whose interval has not been edited use that value, and a new setting applies from the next interval. A tab whose interval was edited in the sidebar keeps its own value. The initial loop is also a plugin setting, default on. Tabs whose checkbox has not been changed use that value, and a new setting applies from the next turn. A tab whose checkbox was changed in the sidebar keeps its own on or off.

Each tab can run on its own. Start stays disabled while the tab has no pages. The fields show the shortcut-target tab. Only a visible tab advances. Hidden time is not caught up; after the tab is visible again, it stays on the current page until one interval passes. A split view advances a visible tab. The page slider can stay closed.

Inside the range, it advances from the current page. Starting outside the range moves to the start page immediately. On the end page, Loop returns to the start page. With Loop unchecked, it stops. A manual page change stops that tab. When the file changes, start returns to 1, end returns to the new page count, and the tab stops.
