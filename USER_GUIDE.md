# Draw Things Script Manager - User Guide

## Quick Start

### 1. Check Your Scripts

See what scripts you have and their status:

```bash
python3 script_manager.py list
```

For more details:

```bash
python3 script_manager.py list --details
```

**Example output:**
```
📜 Creative Upscale
   File: creative-upscale.js
   Author: Liu Liu
   Description: Generate up to 4x upscaled image...
   Status: ✓ File exists (2,857 bytes)
```

### 2. Validate Your Scripts

Check for any issues (missing files, orphaned files, etc.):

```bash
python3 script_manager.py validate
```

**What it checks:**
- ✓ JSON validity
- ✓ Missing files (in metadata but file doesn't exist)
- ⚠️ Orphaned files (file exists but not in metadata)
- ⚠️ Case mismatches (filename case differences)
- ❌ Duplicate entries

### 3. Add Orphaned Files to Metadata

If you have script files that aren't in `custom_scripts.json`:

**First, preview what would be added (safe - no changes):**
```bash
python3 script_manager.py sync
```

**Then, actually add them:**
```bash
python3 script_manager.py sync --no-dry-run
```

**Or add only specific files:**
```bash
python3 script_manager.py sync --no-dry-run --files "MyScript.js" "AnotherScript.js"
```

**Important:** This only modifies `custom_scripts.json` - your script files are never touched!

### 4. Check Git Status

See what changed (if git is enabled):

```bash
python3 script_manager.py git-status
```

### 5. Export a Report

Generate a summary report:

```bash
python3 script_manager.py export
```

Or save to a specific file:

```bash
python3 script_manager.py export --output my_report.txt
```

## Common Workflows

### Workflow 1: First Time Setup

You have some script files but no metadata:

```bash
# 1. See what you have
python3 script_manager.py list

# 2. Check for issues
python3 script_manager.py validate

# 3. Add all orphaned files to metadata
python3 script_manager.py sync --no-dry-run

# 4. Verify everything is good
python3 script_manager.py validate
```

### Workflow 2: Adding a New Script

You just added a new script file:

```bash
# 1. Validate to see the new orphaned file
python3 script_manager.py validate

# 2. Add just that one file
python3 script_manager.py sync --no-dry-run --files "MyNewScript.js"

# 3. Verify it was added
python3 script_manager.py list
```

### Workflow 3: Regular Maintenance

Check everything is in order:

```bash
# Quick health check
python3 script_manager.py validate

# If there are orphaned files, preview what would be added
python3 script_manager.py sync

# If you want to add them, run with --no-dry-run
python3 script_manager.py sync --no-dry-run
```

### Workflow 4: Before Making Manual Changes

Before manually editing `custom_scripts.json`:

```bash
# 1. Check current status
python3 script_manager.py validate

# 2. Check git status (if using git)
python3 script_manager.py git-status

# 3. Make your manual changes to custom_scripts.json

# 4. Validate again to make sure everything is still good
python3 script_manager.py validate
```

## Safety Features

### ✅ What the Tool Does

- ✅ **Only modifies `custom_scripts.json`** - Never touches your script files
- ✅ **Dry-run by default** - Shows what would change before making changes
- ✅ **Idempotent** - Safe to run multiple times
- ✅ **Git integration** - Automatically tracks changes
- ✅ **Backup before changes** - Creates backups automatically

### ❌ What the Tool Never Does

- ❌ Never modifies, renames, or deletes script files
- ❌ Never changes script file contents
- ❌ Never removes entries from metadata (unless you manually edit JSON)

## Examples

### Example 1: Discovering Orphaned Files

```bash
$ python3 script_manager.py validate

⚠️  Orphaned Files (3):
   • FUNK-DT Env Probe.js
   • FUNK-Negative Prompt Presets.js
   • Wildcards-funkatron_0.1.js
```

### Example 2: Previewing Sync

```bash
$ python3 script_manager.py sync

⚠️  This will ONLY modify custom_scripts.json, never the script files themselves.

Would add: Funk Dt Env Probe (FUNK-DT Env Probe.js)
Would add: Funk Negative Prompt Presets (FUNK-Negative Prompt Presets.js)
Would add: Wildcards Funkatron 0.1 (Wildcards-funkatron_0.1.js)

[DRY RUN] Would add 3 entries.
Use --no-dry-run to apply changes.
```

### Example 3: Selective Sync

```bash
$ python3 script_manager.py sync --no-dry-run --files "FUNK-DT Env Probe.js"

⚠️  This will ONLY modify custom_scripts.json, never the script files themselves.

Adding: Funk Dt Env Probe (FUNK-DT Env Probe.js)

✓ Added 1 entries to custom_scripts.json
✓ Changes committed to git
```

## Tips

1. **Always preview first**: Run `sync` without `--no-dry-run` to see what would change
2. **Use selective sync**: Use `--files` to add only specific files you want to manage
3. **Regular validation**: Run `validate` periodically to catch issues early
4. **Git is your friend**: If git is available, all changes are automatically tracked
5. **Idempotent operations**: Don't worry about running commands multiple times - it's safe!

## Troubleshooting

### "Invalid JSON" error

If you get an invalid JSON error, check `custom_scripts.json` for syntax errors. The tool won't modify it if it's invalid.

### "File missing" warnings

If a file is listed as missing, check if:
- The file was deleted
- The filename in JSON has wrong case (check case mismatches)
- The file is in a different location

### Git not working

If git commands fail, the tool will continue to work but won't track changes. Make sure git is installed and the directory isn't locked.

## Getting Help

```bash
python3 script_manager.py --help
python3 script_manager.py list --help
python3 script_manager.py sync --help
```

