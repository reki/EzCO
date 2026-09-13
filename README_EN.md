# EzCo

A lightweight comic viewer application

**Supported OS**: Windows (10/11 recommended)

## Development

Most of the code in this program was implemented with the assistance of AI (Claude-4-Sonnet). This collaboration with an AI assistant has enabled efficient and high-quality software development.

## Features

### Basic Features
- Image file display (PNG, JPG, GIF, BMP, TIFF, WebP)
- Archive file support (ZIP, 7Z, RAR, CBZ, CBR, TAR, TAR.GZ, TAR.BZ2, TAR.XZ, GZ, BZ2, XZ, PDF)
- Mouse gesture operations
- Bookmark functionality
- History tracking
- Image movement and zoom functionality
- Window position, size, and maximized-state memory (saved on exit even if no file is open)

### Multi-language Support
- **Automatic system language detection**: Automatically detects the system's default language on application startup
- **Supported languages**: **Japanese** (primary), **English** (secondary)
- **Language switching**: Change language from settings screen
- **Language file locations**: 
  - Execution folder's `langs` directory (priority)
  - Application's built-in `resources/langs` directory

### Debug Features
- **Debug mode**: Can be enabled from settings screen
- **Log files**: When debug mode is enabled, timestamped log files are automatically generated in the `logs` folder
- **Detailed logs**: Detailed operation logs for file processing, archive extraction, image loading, etc.
- **Error logs**: Automatic log recording when errors occur

### Tabs
- **Multiple files at once**: The tab bar appears only when there are two or more tabs
- **Tab menu**: New, close, reopen tab, and move left / right / first / last. Reopen is disabled when there is nothing to restore
- **Tab list**: Open the sidebar from Extensions → Sidebar to jump between open tabs
- **Tabs in fullscreen**: A View menu checkbox chooses whether the tab bar stays visible in fullscreen
- **Tab switching**: Default shortcuts are Ctrl+1–9 for the 1st–9th tabs, and Ctrl+0 / Ctrl+End for the last tab
- **Tab bar**: Fixed width. Long names are elided; hover shows the full name. Middle-click closes that tab
- **Menus**: Assigned keyboard shortcuts appear on the right of matching menu items
- **Open**: "Open File" uses the current tab; "Open File in New Tab" opens new tabs; "Open Folder" picks a folder
- **Multiple paths**: Images open as pages in one tab. Whether archives and folders get their own tabs is a setting (archives do by default). Tab order follows the drop or selection order
- **File dialog**: The first "Supported Files" filter includes images, archives, plugin extensions, and state files
- **Save state**: "Save State As..." (Ctrl+S on first profile) writes every tab's file and page to a `.ezs` file
- **Restore state**: Open or drop a `.ezs`. If files are already open, choose Close All, Add to Open Tabs, Open in New Window, or Cancel
- **Drag and drop**: Follows Settings (current tab or new tab). After the first group, archives or folders set to own-tab open as extra tabs
- **History and bookmarks**: Click opens in the current tab; Ctrl+click or middle-click opens a new tab. Right-click can choose either
- **Reopen last file**: Opens only the latest history item, not every tab

### Plugin Settings
- **On/Off**: Enable or disable each plugin. Off removes it from extension handling and unmounts its sidebar
- **Loading method**: Built-in, plugin, or Don't load per extension
- **Duplicate ids**: Choose which source to load at startup. The choice is saved and the dialog does not return unless a new unresolved duplicate id appears. Change it later with Choose duplicate plugins in Plugin Settings (applies on OK / Apply)
- **Don't load**: Skip files of that extension (replaces the old Archive Settings dialog)
- **Settings export/import**: Save and restore the current profile as YAML from the main settings dialog

### UI Font Settings
- **Font family**: Automatically detects available fonts from Windows registry and font folder
- **Font size**: Configurable from 8 to 64px
- **Text color and background color**: Freely configurable with color picker
- **Transparency**: Configurable from 0 (transparent) to 255 (opaque)
- **Popup display**: Applied to overlay display during gesture operations

### Other Features
- **Virtual Path Function**: Direct specification of files within archives (`archive://path#filename` format)
- **Image List Display**: Popup display of current file list
- **Image Slide Sidebar**: Thumbnail view for page overview and quick navigation
- **Page Slider Dialog**: Intuitive page navigation with slider interface
- **Mouse Lock Function**: Fix mouse cursor to center of screen
- **Image Rotation Function**: 90-degree rotation of images
- **Always on Top**: Keep window always in front
- **Minimum Scale Toggle**: Toggle minimum display scale of images
- **Automatic filename encoding detection**: Automatic decoding of Japanese filenames in archives
- **Image prefetching**: Enables fast page turning
- **Settings export/import**: Save and restore the current profile's settings in YAML format
- **State files**: Save open tabs to a `.ezs` file and restore them by opening or dropping it

### Comic Display
- **Single page / Spread (right) / Spread (left)**: Switch from the Comic menu
- **Spread (right)**: Right page is axis N, left is N+1 (right-bound)
- **Spread (left)**: Left page is axis N, right is N+1 (left-bound)
- **Spread-unit navigation**: Next/previous moves two pages. The last odd page is shown alone
- **Selected page as axis**: The slider-selected page becomes the first page of the spread
- **Slider direction**: Right is first for single page and spread (right). Left is first only for spread (left)

### Profiles
- **Add, manage, and switch from the menu**: Profile menu for add, rename/delete, and selection
- **New profiles copy the current settings**: Viewer, shortcuts, plugin handlers, and so on. Bookmarks and history stay empty
- **Settings are per profile**: Page mode, background, language, shortcuts, plugin selection, and more
- **Bookmarks and history are isolated** per profile
- **The default profile cannot be deleted**
- **CLI**: `--profile=name` / `-p name` uses that profile for the session only (if missing, the last profile is used; nothing is created)

### Plugins
- Place a `.zip` or a folder with `manifest.json` in the `plugins/` folder next to the executable (or the repo root while developing)
- If more than one plugin has the same id, choose which one to load at startup. The choice is saved and the dialog does not return unless a new unresolved duplicate id appears. Change it later with Choose duplicate plugins in Plugin Settings
- In Plugin Settings, turn plugins on or off and choose built-in, plugin, or Don't load per extension. OK reloads the open files
- The plugin list shows ID without version. Column widths and order can be changed and are saved
- Built-in handlers win by default for known extensions
- Enabled plugin extensions appear in the file dialog under "Supported Files" and "Plugin formats", and in folder scans
- Samples: sources in `plugins/`, packaged ZIPs in [`dist-sample-plugins/`](dist-sample-plugins/) (PNG, ZIP, text pages, product info sidebar)
- Developer reference: [docs/plugins.md](docs/plugins.md), [Plugin Reference](resources/UserManual/files/plugin-reference-en.html) in the user manual, each plugin `README_EN.md`, [plugins/README.md](plugins/README.md)

## Development Environment Setup

### Prerequisites

- **Python** (3.10 or higher, recommended: 3.12.5) - [Download](https://www.python.org/downloads/release/python-3125/)
- **Poetry** - [Installation Guide](https://python-poetry.org/docs/#installation)
- **Windows OS** (development and runtime environment)

### Recommended Development Environment

- **Cursor** (Recommended) - [Download](https://cursor.com/)
- **Visual Studio Code (VS Code)** - [Download](https://code.visualstudio.com/)

Both editors provide excellent Python development support with IntelliSense, debugging, and integrated terminal features.

### Build Tools

- **Nuitka** - [PyPI](https://pypi.org/project/Nuitka/) (automatically installed via Poetry)

### Tested Environment

This project has been developed and tested in the following environment:

#### Hardware
- **CPU**: Intel Core i7-13700KF (3.40 GHz)
- **RAM**: 64GB
- **Architecture**: x64

#### Software
- **OS**: Windows 11 Pro (24H2)
- **OS Build**: 26100.435.1
- **Python**: 3.12.5
- **Development Environment**: Cursor / VS Code

### Minimum System Requirements

#### Hardware
- **CPU**: x64 compatible processor
- **RAM**: 4GB or more (8GB or more recommended for builds)
- **Storage**: 2GB or more free space

#### Software
- **OS**: Windows 10/11 (64bit)
- **Python**: 3.10 or higher
- **.NET Framework**: 4.8 or higher (usually pre-installed on Windows)

### Installation

#### Automated Setup (Recommended)

```bash
# Use initialization script (recommended)
./init.sh
```

The `init.sh` script automatically performs the following:
- Install Poetry dependencies
- Check and configure C++ compiler
- Automatic MinGW-w64 download (if needed)
- Setup verification

#### Manual Installation

```bash
# Install dependencies
poetry install

# Install development dependencies (for Nuitka build)
poetry install --with dev
```

**Note**: Manual installation requires a C++ compiler for Nuitka builds separately.

### Execution

#### Running from Command Line

```bash
# Run in development mode
poetry run python -m ez_co.main

# Or
poetry run python src/ez_co/main.py
```

#### Running in VS Code

1. Open the project in VS Code
2. Press `F5` or select "Python: EzCo" from the "Run and Debug" panel
3. The application will start

※ Debug execution in development mode is possible with VS Code's `launch.json` configuration

## Build

### Build with Nuitka

This project supports build and execution on Windows only.

#### Automated Build (Recommended)

```bash
# Standard build (with optimizations)
./build.sh

# Safe mode build (no optimizations)
./build.sh --safe-mode
```

#### Build Script Features

The `build.sh` script automatically performs the following:

##### Standard Build (with optimizations)
- **LTO (Link Time Optimization)**: Improves runtime performance
- **Source code priority**: Prioritizes source code over bytecode
- **File size**: May be slightly larger
- **Build time**: Longer (5-15 minutes)

##### Safe Mode Build (no optimizations)
- **Basic build**: No optimization options
- **Safety focused**: Avoids compatibility issues
- **File size**: Slightly smaller
- **Build time**: Shorter (3-10 minutes)

#### Pre-build Preparation

Before executing the build, please verify the following:

```bash
# Run initialization script (first time only)
./init.sh
```

#### Manual Build

```bash
# Run Nuitka command directly
poetry run python -m nuitka --standalone --onefile --windows-icon-from-ico="resources/icon.ico" --windows-console-mode=disable --assume-yes-for-downloads --enable-plugin=pyside6 --include-package=ez_co --include-package=PIL --include-package=yaml --include-data-dir="src/ez_co/resources=ez_co/resources" --output-dir="build" --output-filename="EzCo.exe" src/ez_co/main.py
```

#### Build Output

- **Executable file**: `EzCo.exe` (created in project root)
- **Temporary files**: `build/` folder (automatically deleted after build completion)

#### Troubleshooting

##### When Build Errors Occur
1. **Run initialization**: Execute `./init.sh` to verify setup
2. **Safe mode**: Try `./build.sh --safe-mode`
3. **Dependencies**: Reinstall dependencies with `poetry install --with dev`

##### When Compiler Errors Occur
1. **Microsoft Visual Studio Build Tools** (Recommended)
   - Download from [official site](https://aka.ms/buildtools)
   - Select and install "C++ build tools"
2. **MinGW-w64** (Lightweight option)
   - Can be automatically installed with `./init.sh`
   - Manual installation also possible

##### When Memory Shortage Errors Occur
- **8GB or more RAM** recommended
- Try building in **safe mode**
- Close **other applications** to free up memory

#### Build Time Guidelines

- **Low-spec PC**: 10-20 minutes
- **Standard PC**: 5-15 minutes
- **High-spec PC**: 3-10 minutes

※ Initial builds may take longer due to additional component downloads

#### Quick Start Guide

Recommended procedure for first-time project setup:

```bash
# 1. Initialize (dependency and compiler setup)
./init.sh

# 2. Execute build
./build.sh

# 3. Run application
./EzCo.exe
```

#### Development and Build Workflow

```bash
# Development execution
poetry run python -m ez_co.main

# Pre-build verification
poetry run python src/ez_co/main.py

# Release build
./build.sh

# Safe build when issues occur
./build.sh --safe-mode
```

## Configuration

Application settings are stored per profile in `config.db` (SQLite). It is created on first startup. If only a legacy `bookmarks.db` exists, it is renamed to `config.db`. A leftover `config.yaml` can be imported via a confirmation dialog at startup.

### Main Configuration Items

#### Window Settings
- **Size and position**: Remember window size and position when the option is enabled
- **Sidebars**: Open panels, left/right placement, and widths are saved per profile and restored on the next launch or profile switch
- **Auto-resize**: Automatically adjust window size when loading images
- **Minimum size**: Minimum width and height of window
- **Always on top**: Keep window always in front

#### Viewer Settings
- **Background color**: Background color of image display area
- **Fit image to window**: Automatically adjust image to window size
- **Minimum scale limit**: Limit minimum image scale to 100%
- **Image move sensitivity**: Image movement sensitivity during mouse drag (0.5-2.0)
- **Page display mode**: Single / Spread (right) / Spread (left)
- **Selected page as axis**: Use the slider-selected page as the first page of the spread
- **Spread toggle preference**: Keep previous / Prefer right / Prefer left

#### History Settings
- **Maximum history count**: Upper limit of files saved in history (1-99)

#### Debug Settings
- **Debug mode**: Enable/disable detailed log output
- **Log files**: Generate timestamped log files in `logs` folder
- **Keep archive file handles**: Archive file handle retention setting (usually disabled recommended)

#### Cache Settings
- **Memory cache size**: Image memory cache size (e.g., 256MB, 1GB, 2.5GB)
- **Prefetch pages**: Number of pages to prefetch around current page (1-50 pages)

#### Plugin Settings
- **On/Off**: `plugins.enabled`. Missing ids are enabled. Off also unmounts the sidebar
- **Loading method**: Built-in, plugin, or Don't load per extension
- **Duplicate ids**: `plugins.source_choice`. Choose one source at startup or later in Plugin Settings
- **Don't load**: Files of that extension are not opened (archives and images)

#### Language Settings
- **Language code**: Language setting (system, ja, en)
- **System default**: Use system's default language

#### UI Font Settings
- **Font family**: Font for popup display
- **Font size**: Font size (8-64px)
- **Text color**: Popup text color
- **Background color**: Popup background color
- **Transparency**: Popup transparency (0-255)

#### Shortcut Settings
- **Keyboard shortcuts**: Keyboard assignments for each action
- **Mouse shortcuts**: Mouse operation assignments

#### Gesture Settings
- **Mouse gestures**: Mouse drag gesture operation assignments

#### Profiles
- **Current profile**: Menu selection or last used. CLI overrides for the session only
- **Add**: Copies the current settings (including plugin handlers). Bookmarks and history stay empty
- **Settings, bookmarks, and history**: Isolated per profile

## About Multi-language Support

### Overview
EzCo supports **Japanese** and **English**. The system's default language is automatically detected and the appropriate language is selected.

### Supported Languages
- **Japanese (ja)**: Primary language
- **English (en)**: Secondary language

### Automatic Language Selection
1. **Language specified in settings** (priority)
2. **System's default language**
3. **Japanese** (fallback)

### How to Change Language
1. Start the application
2. Open settings screen
3. Select language in "Language Settings"
4. Save settings
5. **Restart the application**

### Language File Locations
- **Execution folder**: `langs/ja.json`, `langs/en.json` (priority)
- **Built-in files**: `resources/langs/ja.json`, `resources/langs/en.json`

### Customization
You can override built-in language files by creating a `langs` directory in the execution folder and placing `ja.json` or `en.json` files.

```bash
EzCo.exe
└── langs/
    ├── ja.json  # Japanese customization
    └── en.json  # English customization
```

## About Debug Mode

### How to Enable
1. Start the application
2. Open settings screen
3. Check "Debug Mode" in the "Debug Settings" section
4. Save settings
5. Restart the application

### Log Files
- **Location**: `logs` directory in application execution folder
- **Filename**: `debug_YYYYMMDD_HHMMSS.log` (with timestamp)
- **Content**: Detailed logs for file processing, archive extraction, image loading, etc.

### Error Logs
- **Location**: Application execution folder
- **Filename**: `error_log_YYYYMMDD.txt` (with date)
- **Content**: Detailed information when errors occur

## About Plugin Settings

### Overview
EzCo lets you choose a loading method per extension. Use **Don't load** when a format is unused or folder scans are slow. This replaces the old Archive Settings dialog.

### How to Configure
1. Start the application
2. Open Settings → Plugin Settings
3. Toggle plugins and choose Built-in, a plugin, or Don't load for each extension
4. Press OK (open files are reloaded; disabled sidebars are removed)

### Effects of Settings

#### When Don't load is selected
- Files of that extension are not opened
- They are also skipped when opening a folder
- Works for both images and archives

#### When you only want images
- Set archive extensions such as ZIP, 7Z, and RAR to Don't load
- Only image files are shown

### Usage Examples

#### Example 1: Skip 7Z files
- Folders with many 7Z files load slowly
- In Plugin Settings, set `.7z` to Don't load

#### Example 2: Skip all archives
- You only want image files
- Set `.zip`, `.7z`, `.rar`, `.tar`, `.gz`, and similar extensions to Don't load

#### Example 3: Open only comic archives
- You only use CBZ and CBR
- Set other archive extensions to Don't load

### Settings Export/Import
- Export and import from the main settings dialog
- Saves and restores the current profile as YAML

### Important Notes
- OK reloads the files that are currently open
- Extensions set to Don't load are skipped during folder scans
- Older profiles that disabled archives show Don't load when you open Plugin Settings

### Supported Archive Formats
- **ZIP**: .zip
- **7-Zip**: .7z
- **RAR**: .rar
- **TAR**: .tar
- **TAR.GZ**: .tar.gz, .tgz
- **TAR.BZ2**: .tar.bz2, .tbz2
- **TAR.XZ**: .tar.xz, .txz
- **GZ**: .gz
- **BZ2**: .bz2
- **XZ**: .xz
- **CBZ**: .cbz (ZIP-based comic)
- **CBR**: .cbr (RAR-based comic)
- **PDF**: .pdf (pages rendered as-is; embedded images if rendering is unavailable)

## About Virtual Path Function

### Overview
EzCo allows you to directly specify and open specific image files within archive files. This feature enables quick display of specific images from large archive files.

### Virtual Path Format
```
archive://archive_file_path|filename_within_archive
```

### Usage Examples
- `archive://C:\comics\manga.zip|page001.jpg` - Specific image in ZIP file
- `archive://D:\books\comic.cbr|chapter1/001.png` - Image in folder within CBR file
- `archive:///home/user/comics/story.7z|cover.jpg` - Cover image in 7Z file
- `archive://C:\books\magazine.pdf|page_0001.png` - First page of a PDF

### Supported Archive Formats
- ZIP, 7Z, RAR, CBZ, CBR, TAR, TAR.GZ, TAR.BZ2, TAR.XZ, GZ, BZ2, XZ, PDF

### How to Use
1. **Command line arguments**: Specify virtual path when starting application
2. **File association**: Double-click file containing virtual path
3. **Drag & Drop**: Drag text file containing virtual path

### Notes
- Error occurs if archive file does not exist
- Filename within archive must be specified exactly
- Some filenames may not be recognized due to character encoding issues

## About Shortcut Settings

### Overview
EzCo allows you to set shortcuts for both keyboard and mouse. Multiple shortcuts can be assigned to each action, and settings can be exported/imported.

### How to Configure
1. Select "Shortcut Settings" from settings screen
2. Click "Add" to add new shortcut
3. Click "Edit" to modify existing shortcut
4. Click "Delete" to remove shortcut

### Keyboard Shortcuts
- **Modifier keys**: Ctrl, Alt, Shift, Meta (Windows key)
- **Special keys**: F1-F12, arrow keys, Home, End, PageUp, PageDown, Space, Enter, Escape, Tab, Backspace, Delete
- **Combinations**: `Ctrl+Shift+A`, `Alt+F4`, etc.

### Mouse Shortcuts
- **Mouse buttons**: Left click, right click, middle click, X1 button (back), X2 button (forward)
- **Wheel operations**: Wheel up, wheel down
- **Double click**: Double click

### Default Shortcuts
- **Page operations**: Left click/right click, arrow keys, Space
- **File operations**: Ctrl+arrow keys (previous/next file)
- **Zoom operations**: Wheel. Ctrl+0 prefers last-tab by default (reset zoom uses the same key)
- **Tab operations**: Ctrl+T (new), Ctrl+W (close), Ctrl+Shift+T (reopen), Ctrl+PageUp / PageDown (left / right), Ctrl+Home / End (first / last), Ctrl+1–9 (1st–9th), Ctrl+0 (last)
- **Display operations**: Return (fullscreen), Ctrl+T (always on top; same default as new tab)
- **Others**: Ctrl+L (image list), R (open last file), Ctrl+S (save state as), Ctrl+Shift+O (open file in new tab)
- **First launch only**: Default shortcuts and gestures are registered only when creating the first profile (or a new profile). Deleted assignments are not restored on the next start

### Export/Import Settings
- **Export**: Save the current profile's settings in YAML format
- **Import**: Overwrite the current profile's settings from a YAML file
- **Auto-completion**: Automatically add missing items during import

## About Mouse Gestures

### Overview
EzCo allows gesture operations by holding right-click and dragging the mouse. Complex operations can be executed quickly.

### Gesture Basics
- **Start**: Press right-click
- **Draw**: Drag mouse to specify direction
- **Execute**: Release right-click

### Direction Recognition
- **↑**: Drag upward
- **↓**: Drag downward
- **←**: Drag leftward
- **→**: Drag rightward

### Gesture Combinations
- **Single direction**: ← (previous comic), → (next comic), ↓ (exit)
- **Compound directions**: ↓→ (fullscreen), ↑↓ (open last file), →← (first page), ←→ (last page)

### How to Configure
1. Select "Gesture Settings" from settings screen
2. Click "Add" to register new gesture
3. Right-click drag in gesture drawing area
4. Select action to execute

### Default Gestures (first profile only)
- **←**: Previous comic
- **→**: Next comic
- **↓**: Close application
- **↓→**: Toggle fullscreen
- **↑↓**: Open last opened file
- **→←**: First page
- **←→**: Last page
- **↓→←**: Page slider

### Gesture Display
- **Real-time display**: Show current gesture while dragging
- **Action display**: Show assigned action name
- **Unassigned display**: Show "Unassigned" for gestures without assignments

### Export/Import Settings
- **Export**: Save gesture settings in JSON format
- **Import**: Restore gesture settings from JSON file
- **Validation**: Automatically exclude invalid actions

## About Image List Function

### Overview
Displays a popup list of currently opened files, allowing quick jump to any page.

### How to Display
- **Shortcut**: Ctrl+L (default)
- **Menu**: View → Image List

### Display Contents
- **Filename**: Filename within archive
- **Thumbnail**: Image preview (supported formats only)
- **Page number**: Current page position

### Operations
- **Click**: Jump to selected page
- **Keyboard**: Use arrow keys to select, Enter to confirm
- **Search**: Search by filename (partially supported)

### Display Options
- **Thumbnail size**: Adjust preview image size
- **Display count**: Number of files to display at once
- **Sort order**: By filename, by date, etc.

## About Image Slide Sidebar Function

### Overview
The Image Slide Sidebar displays thumbnail previews of all pages in a dockable sidebar, enabling quick navigation to any page.

### How to Display
- **Menu**: View → Image Slide
- **Shortcut**: Configurable (no default)

### Features
- **Thumbnail Display**: Automatic generation of preview images for each page
- **Real-time Updates**: Automatic reload when files change
- **Current Page Highlighting**: Visual emphasis on currently displayed page
- **Click Navigation**: Instant page jump by clicking thumbnails
- **Auto Scroll**: Automatic scrolling to keep current page visible

### Sidebar Characteristics
- **Dockable**: Can be docked to left or right areas
- **Size Adjustment**: Fixed width 200-350px
- **Show/Hide Toggle**: Easy toggle via menu or shortcut
- **Background Loading**: Lightweight operation with thumbnail generation in separate thread

### Supported Files
- **Image Files**: PNG, JPG, GIF, BMP, TIFF, WebP
- **Archive Files**: Images within ZIP, 7Z, RAR, CBZ, CBR

## About Page Slider Dialog Function

### Overview
The Page Slider Dialog provides intuitive page navigation through a modeless dialog with slider interface.

### How to Display
- **Shortcut**: Configurable (no default)
- **Menu**: View → Page Slider (when available in menu)

### Features
- **Real-time Slider**: Intuitive page selection via slider
- **Numeric Input**: Precise page number specification with spin box
- **Quick Jump**: One-click navigation to first/last page
- **Real-time Updates**: Automatic reflection of file changes and page navigation

### Dialog Characteristics
- **Modeless**: Can operate simultaneously with main window
- **Compact Design**: Small 300x100px window
- **Always Current**: Automatic updates when files change
- **State Persistence**: Settings maintained until dialog is closed

### Control Elements
- **Page Information**: Display of current page/total pages
- **Page Slider**: Page selection by dragging
- **Page Number Input**: Numeric input via keyboard
- **First Button**: Navigate to page 1
- **Last Button**: Navigate to final page

## About Cache Settings

### Overview
EzCo provides memory caching and prefetching features to improve image loading speed. These settings can significantly enhance page turning responsiveness.

### How to Configure
1. Start the application
2. Open the settings screen
3. Select the "Behavior" tab
4. Configure items in the "Cache Settings" section
5. Save settings

### Memory Cache Size

#### Overview
Sets the size of cache for storing loaded images in memory. Larger settings allow more images to be kept in memory, resulting in faster page turning.

#### Setting Values
- **Format**: String format (e.g., 256MB, 1GB, 2.5GB)
- **Default**: 256MB
- **Recommended range**: 128MB to 8GB

#### Setting Examples
- **Low-spec PC**: 128MB to 256MB
- **Standard PC**: 512MB to 1GB
- **High-spec PC**: 2GB to 8GB

#### Important Notes
- Setting values too large may cause system memory shortage
- Consider memory used by other applications when setting
- Setting changes are applied immediately

### Prefetch Pages

#### Overview
Sets how many pages before and after the current page to prefetch and cache. Larger settings enable more pages to be preloaded, allowing smoother page turning.

#### Setting Values
- **Range**: 1 to 50 pages
- **Default**: 15 pages
- **Recommended**: 10 to 30 pages

#### Operation Example
- **Setting 15**: Prefetch 15 pages before and after current page (31 pages total)
- **When current is page 10**: Cache pages 1-25

#### Optimization Points
- **High-speed SSD environment**: 10-15 pages (sufficient with smaller numbers due to fast loading)
- **HDD environment**: 20-30 pages (larger numbers due to slower loading)
- **Large files**: 5-10 pages (reduce memory usage)
- **Small files**: 25-50 pages (prefetch more pages)

### Cache Operation Specifications

#### Distance-based Eviction
When memory cache reaches its limit, images farthest from the current page are removed first. This prioritizes keeping images around the currently viewed page.

#### Prefetch Priority
1. **Current page**: Highest priority
2. **Next page**: High priority
3. **Previous page**: High priority
4. **2-3 pages before/after**: Medium priority
5. **Further pages**: Low priority

#### Background Processing
Prefetching runs in separate threads, so it doesn't affect main image display. However, in no-handle mode, prefetching may be limited for some archives.

### Performance Impact

#### Recommended Settings (Standard Environment)
```yaml
cache:
  memory_limit: "512MB"
  prefetch_pages: 15
```

#### Performance-focused Settings
```yaml
cache:
  memory_limit: "2GB"
  prefetch_pages: 30
```

#### Memory-saving Settings
```yaml
cache:
  memory_limit: "128MB"
  prefetch_pages: 5
```

## About File Handle Management

### Overview
EzCo allows you to choose file handle management methods when opening archive files and folders. This setting controls file locking and enables folder/file movement and deletion.

### File Handle Retention Modes

#### Normal Mode (Keep Archive File Handles: **Disabled**) [Recommended]
- **Operation**: Open/close files as needed
- **Advantages**:
  - No file locking occurs
  - Folder and file movement/deletion possible
  - Other applications can access files
- **Disadvantages**:
  - Slightly slower loading for large archive files
  - Possible delays when accessing network drives

#### Handle Retention Mode (Keep Archive File Handles: **Enabled**)
- **Operation**: Keep file handles open constantly
- **Advantages**:
  - Faster file access
  - Improved performance on network drives
- **Disadvantages**:
  - ⚠️ **File locking occurs**
  - Cannot move or delete folders/files
  - Other applications cannot access files

### How to Configure
1. Start the application
2. Open the settings screen
3. Select the "Development" tab
4. Toggle "Keep Archive File Handles" checkbox in "Debug Settings" section
5. Save settings

### Recommended Settings

#### General Use (Recommended)
```yaml
debug:
  keep_archive_handles: false
```
- Avoid file locking
- Free folder and file operations possible

#### Performance-focused Use
```yaml
debug:
  keep_archive_handles: true
```
- Highest speed file access
- Use only when you understand file locking occurs

### Target File Formats
This setting applies to the following file formats:
- **ZIP**: .zip, .cbz
- **TAR**: .tar, .tar.gz, .tar.bz2, .tar.xz
- **Compressed files**: .gz, .bz2, .xz
- **Folder scanning**: File search within directories

### Unaffected Formats
The following formats always have appropriate handle management:
- **7Z**: .7z (due to dedicated library)
- **RAR**: .rar, .cbr (due to dedicated library)

### Usage Examples

#### Example 1: During Comic Organization Work
- Setting: `keep_archive_handles: false`
- Reason: Frequent file moving, renaming, and deletion

#### Example 2: Reading-only Environment
- Setting: `keep_archive_handles: true`
- Reason: No file operations, prioritizing loading speed

#### Example 3: Network Drive Usage
- Setting: `keep_archive_handles: true`
- Reason: Minimize network delays

### Troubleshooting

#### Cannot Delete/Move Files
1. Check if "Keep Archive File Handles" is enabled in settings
2. Disable it and save settings
3. Restart application (if necessary)

#### Slow Loading Speed
1. Enable "Keep Archive File Handles" in settings
2. Increase memory cache size in cache settings
3. Adjust prefetch page count

#### Other Applications Cannot Access Files
1. Disable "Keep Archive File Handles" in settings
2. Close files in EzCo
3. Try accessing from other applications

## License

EzCo itself is under the [MIT License](LICENSE). See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for third-party licenses and the GPL/LGPL notes.

There is no standalone GPL/AGPL among runtime dependencies. Copyleft libraries are LGPL (PySide6, py7zr, pynput, pystray, and others). LGPL typically does not require publishing EzCo's source. pylint is GPL but is a development-only tool and is not shipped with the app. 