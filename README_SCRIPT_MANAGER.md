# Draw Things Script Manager

A Python tool to help manage scripts in Draw Things.

## Safety & Idempotency

**This tool is designed to be safe and idempotent:**

- ✅ **ONLY modifies `custom_scripts.json`** - Never touches your script files
- ✅ **Idempotent operations** - Running commands multiple times produces the same result
- ✅ **Git integration** - Automatically tracks changes with git (if available)
- ✅ **Backup before changes** - Creates backups before modifying files
- ✅ **Dry-run by default** - Shows what would change before making changes
- ✅ **Selective management** - Only manages files you explicitly specify

## Features

- **List Scripts**: View all scripts with their metadata
- **Validate**: Check for missing files, orphaned files, and JSON issues
- **Sync**: Add orphaned script files to `custom_scripts.json` (only modifies JSON, never script files)
- **Manage**: Auto-track files you manually add to the directory
- **Normalize**: Fix case mismatches, sort entries, and standardize metadata
- **Rollback**: Undo changes using git history
- **Diff**: Show colored diffs of changes
- **Git Status**: Show git status of the scripts directory
- **Export**: Generate a summary report

## Usage

### List all scripts

```bash
python3 script_manager.py list
```

Show detailed information:

```bash
python3 script_manager.py list --details
```

### Validate scripts

Check for issues (missing files, orphaned files, duplicate entries):

```bash
python3 script_manager.py validate
```

### Sync metadata

Add orphaned script files to `custom_scripts.json` (dry run by default):

```bash
# Preview what would be added (safe - only shows what would change)
python3 script_manager.py sync

# Actually apply changes (only modifies custom_scripts.json, never script files)
python3 script_manager.py sync --no-dry-run

# Only add specific files
python3 script_manager.py sync --no-dry-run --files "FUNK-DT Env Probe.js" "Wildcards.js"
```

**Important**: The sync command:
- ✅ Only modifies `custom_scripts.json`
- ✅ Never modifies, renames, or deletes script files
- ✅ Is idempotent (safe to run multiple times)
- ✅ Automatically commits changes to git (if git is available)

### Git status

Check git status of the scripts directory:

```bash
python3 script_manager.py git-status
```

### Manage files

Auto-track files you manually added to the directory:

```bash
# Show status of all files
python3 script_manager.py manage --status

# Automatically add orphaned files to metadata
python3 script_manager.py manage --auto-sync
```

### Normalize metadata

Fix case mismatches, sort entries, and standardize the JSON structure:

```bash
# Preview what would be normalized (safe - no changes)
python3 script_manager.py normalize

# Actually apply normalization
python3 script_manager.py normalize --no-dry-run

# Normalize without fixing case
python3 script_manager.py normalize --no-dry-run --no-fix-case

# Normalize without sorting
python3 script_manager.py normalize --no-dry-run --no-sort
```

**What normalization does:**
- Fixes case mismatches (e.g., `Detailer.js` in JSON but `detailer.js` on disk)
- Sorts entries alphabetically by name
- Standardizes JSON formatting

### Rollback changes

Undo changes to `custom_scripts.json` using git history:

```bash
# Preview rollback options (shows recent commits)
python3 script_manager.py rollback

# Rollback to previous commit
python3 script_manager.py rollback --no-dry-run

# Rollback to specific commit
python3 script_manager.py rollback --commit aae6f70 --no-dry-run
```

**Important**: Rollback only works if git is available and the file is tracked.

### Show diffs

View colored diffs of changes:

```bash
# Show unstaged changes
python3 script_manager.py diff

# Show diff for specific commit
python3 script_manager.py diff --commit aae6f70

# Show diff without color
python3 script_manager.py diff --no-color
```

### Export summary

Generate a detailed report:

```bash
python3 script_manager.py export
```

Or specify output file:

```bash
python3 script_manager.py export --output /path/to/report.txt
```

## Custom Scripts Directory

By default, the tool looks for scripts in:
```
~/Library/Containers/com.liuliu.draw-things/Data/Documents/Scripts
```

You can specify a different directory:

```bash
python3 script_manager.py --scripts-dir /path/to/scripts list
```

## What it does

### Validation

The validator checks for:
- **Missing files**: Scripts listed in `custom_scripts.json` but the file doesn't exist
- **Orphaned files**: `.js` files that aren't in `custom_scripts.json`
- **Duplicate entries**: Multiple entries for the same file in JSON
- **Invalid JSON**: Malformed JSON in `custom_scripts.json`

### Sync

The sync command:
1. Finds orphaned script files (files not in metadata)
2. Attempts to extract metadata from script comments (author, description, etc.)
3. Creates basic metadata entries
4. Adds them to `custom_scripts.json` (if `--no-dry-run` is used)

## Script Metadata Format

Scripts in `custom_scripts.json` can have the following fields:

- `name`: Display name
- `file`: Filename (required)
- `description`: Description of what the script does
- `author`: Author name
- `tags`: Array of tags (e.g., `["image-to-image", "wz"]`)
- `images`: Array of example images
- `baseColor`: Base color for UI
- `favicon`: Base64 encoded favicon

## Examples

### Quick health check

```bash
python3 script_manager.py validate
```

### Full report

```bash
python3 script_manager.py list --details > script_report.txt
python3 script_manager.py validate >> script_report.txt
```

### Auto-sync orphaned files

```bash
python3 script_manager.py sync --no-dry-run
```

### Normalize and standardize

```bash
# Fix case mismatches and sort entries
python3 script_manager.py normalize --no-dry-run
```

### View changes

```bash
# See what changed
python3 script_manager.py diff

# Check git status
python3 script_manager.py git-status
```

### Undo changes

```bash
# Rollback to previous commit
python3 script_manager.py rollback --no-dry-run
```

## Git Integration

The script manager automatically:
- Initializes a git repository if one doesn't exist
- Creates a `.gitignore` file to exclude database files
- Commits changes to `custom_scripts.json` with descriptive messages
- Tracks all metadata changes for easy rollback

Git integration is automatically enabled if git is available. The tool works without git, but you won't have version control features like rollback and diff.

## Requirements

- **Python 3.10+**
- No external dependencies (uses only standard library)
- Git (optional, for change tracking and rollback features)

