# Script Manager - Usage Examples

## Quick Reference

### Basic Commands

```bash
# List all scripts
python3 script_manager.py list

# List with details
python3 script_manager.py list --details

# Validate scripts (check for issues)
python3 script_manager.py validate

# Show git status
python3 script_manager.py git-status
```

### Managing Files

```bash
# Show status of all files
python3 script_manager.py manage --status

# Auto-track files you manually added
python3 script_manager.py manage --auto-sync
```

### Syncing Metadata

```bash
# Preview what would be added (safe)
python3 script_manager.py sync

# Add all orphaned files to metadata
python3 script_manager.py sync --no-dry-run

# Add only specific files
python3 script_manager.py sync --no-dry-run --files "MyScript.js" "AnotherScript.js"
```

### Normalizing

```bash
# Preview normalization (fix case, sort)
python3 script_manager.py normalize

# Apply normalization
python3 script_manager.py normalize --no-dry-run

# Normalize without fixing case
python3 script_manager.py normalize --no-dry-run --no-fix-case

# Normalize without sorting
python3 script_manager.py normalize --no-dry-run --no-sort
```

### Rolling Back

```bash
# Preview rollback options
python3 script_manager.py rollback

# Rollback to previous commit
python3 script_manager.py rollback --no-dry-run

# Rollback to specific commit
python3 script_manager.py rollback --commit aae6f70 --no-dry-run
```

### Viewing Diffs

```bash
# Show unstaged changes (colored)
python3 script_manager.py diff

# Show diff for specific commit
python3 script_manager.py diff --commit aae6f70

# Show diff without color
python3 script_manager.py diff --no-color
```

### Exporting

```bash
# Export summary report
python3 script_manager.py export

# Export to specific file
python3 script_manager.py export --output my_report.txt
```

## Common Workflows

### Workflow 1: First Time Setup

```bash
# 1. See what you have
python3 script_manager.py list

# 2. Check for issues
python3 script_manager.py validate

# 3. Auto-track all your scripts
python3 script_manager.py manage --auto-sync

# 4. Normalize everything
python3 script_manager.py normalize --no-dry-run

# 5. Verify
python3 script_manager.py validate
```

### Workflow 2: Adding a New Script

```bash
# 1. You manually add a script file to the directory

# 2. Check status
python3 script_manager.py manage --status

# 3. Auto-track it
python3 script_manager.py manage --auto-sync

# 4. Verify it was added
python3 script_manager.py list
```

### Workflow 3: Regular Maintenance

```bash
# Quick health check
python3 script_manager.py validate

# If there are orphaned files, preview what would be added
python3 script_manager.py sync

# If you want to add them
python3 script_manager.py sync --no-dry-run

# Normalize if needed
python3 script_manager.py normalize --no-dry-run
```

### Workflow 4: Undoing Changes

```bash
# 1. Made a change you don't like?
python3 script_manager.py normalize --no-dry-run

# 2. Want to undo it?
python3 script_manager.py rollback

# 3. Actually rollback
python3 script_manager.py rollback --no-dry-run

# 4. Verify
python3 script_manager.py validate
```

### Workflow 5: Full Audit

```bash
# Get complete picture
python3 script_manager.py list --details
python3 script_manager.py validate
python3 script_manager.py manage --status
python3 script_manager.py git-status

# Export full report
python3 script_manager.py export
```

## Command Options

### List
- `--details` - Show detailed information (images, colors, etc.)

### Sync
- `--no-dry-run` - Actually apply changes (default is dry-run)
- `--files FILE1 FILE2` - Only sync specific files

### Manage
- `--status` - Show detailed status of all files
- `--auto-sync` - Automatically add orphaned files to metadata

### Normalize
- `--no-dry-run` - Actually apply normalization
- `--no-fix-case` - Skip fixing case mismatches
- `--no-sort` - Skip sorting entries

### Rollback
- `--commit HASH` - Rollback to specific commit
- `--no-dry-run` - Actually rollback

### Export
- `--output FILE` - Output to specific file

## Safety Reminders

- ✅ All commands are **dry-run by default** (except `list` and `validate`)
- ✅ Only `custom_scripts.json` is modified - **never script files**
- ✅ All changes are **tracked in git** (if available)
- ✅ **Idempotent** - safe to run multiple times
- ✅ **Backups** are created automatically before changes

## Getting Help

```bash
# General help
python3 script_manager.py --help

# Command-specific help
python3 script_manager.py list --help
python3 script_manager.py sync --help
python3 script_manager.py normalize --help
```

