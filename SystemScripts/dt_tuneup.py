#!/usr/bin/env python3
"""
Draw Things Tuneup Script

Scans and cleans up Draw Things configuration files:
- Validates JSON config files against actual model files
- Removes entries for missing models/LoRAs
- Finds orphaned model files not in any config
- Reports disk usage
- Clears app caches

Usage:
    python3 dt_tuneup.py [--fix] [--verbose]
    python3 dt_tuneup.py --clear-cache [--dry-run]
    python3 dt_tuneup.py --clear-net-cache [--dry-run]

Options:
    --fix              Actually remove invalid entries (default: dry-run)
    --clear-cache      Clear all Draw Things caches
    --clear-net-cache  Clear only network cache (model catalogs)
    --dry-run          Preview what would be cleared without deleting
    --verbose          Show detailed output
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ValidationResult:
    """Results from validating a config file."""
    config_file: str
    total_entries: int = 0
    valid_entries: int = 0
    missing_files: list[str] = field(default_factory=list)
    
    @property
    def invalid_count(self) -> int:
        return len(self.missing_files)
    
    @property
    def is_clean(self) -> bool:
        return self.invalid_count == 0


class DrawThingsTuneup:
    """Validates and cleans up Draw Things configuration."""
    
    # Config files and their file reference keys
    CONFIG_FILES = {
        "custom.json": ["file", "autoencoder", "text_encoder", "clip_encoder"],
        "custom_lora.json": ["file"],
        "custom_controlnet.json": ["file"],
        "custom_textual_inversions.json": ["file"],
    }
    
    # Cache directories to manage
    CACHE_DIRS = [
        "Library/Caches",
        "Library/Caches/net",
    ]
    
    def __init__(self, models_dir: Path | None = None, verbose: bool = False):
        self.models_dir = models_dir or self._default_models_dir()
        self.container_dir = self._default_container_dir()
        self.verbose = verbose
        
    @staticmethod
    def _default_models_dir() -> Path:
        """Get the default Draw Things Models directory."""
        return Path.home() / "Library/Containers/com.liuliu.draw-things/Data/Documents/Models"
    
    @staticmethod
    def _default_container_dir() -> Path:
        """Get the default Draw Things container directory."""
        return Path.home() / "Library/Containers/com.liuliu.draw-things/Data"
    
    def log(self, message: str, always: bool = False) -> None:
        """Print message if verbose or always."""
        if self.verbose or always:
            print(message)
    
    def validate_config(self, config_name: str) -> ValidationResult:
        """Validate a single config file."""
        config_path = self.models_dir / config_name
        result = ValidationResult(config_file=config_name)
        
        if not config_path.exists():
            self.log(f"  Config not found: {config_name}")
            return result
        
        try:
            with open(config_path) as f:
                entries = json.load(f)
        except json.JSONDecodeError as e:
            self.log(f"  Invalid JSON in {config_name}: {e}", always=True)
            return result
        
        if not isinstance(entries, list):
            self.log(f"  {config_name} is not a list", always=True)
            return result
        
        result.total_entries = len(entries)
        file_keys = self.CONFIG_FILES[config_name]
        
        for entry in entries:
            entry_valid = True
            entry_name = entry.get("name", entry.get("file", "unknown"))
            
            for key in file_keys:
                if key in entry:
                    file_name = entry[key]
                    file_path = self.models_dir / file_name
                    if not file_path.exists():
                        entry_valid = False
                        self.log(f"  Missing: {file_name} (referenced by '{entry_name}')")
            
            if entry_valid:
                result.valid_entries += 1
            else:
                result.missing_files.append(entry_name)
        
        return result
    
    def fix_config(self, config_name: str) -> int:
        """Remove entries with missing files from a config. Returns count removed."""
        config_path = self.models_dir / config_name
        
        if not config_path.exists():
            return 0
        
        try:
            with open(config_path) as f:
                entries = json.load(f)
        except (json.JSONDecodeError, TypeError):
            return 0
        
        if not isinstance(entries, list):
            return 0
        
        file_keys = self.CONFIG_FILES[config_name]
        valid_entries = []
        
        for entry in entries:
            entry_valid = True
            for key in file_keys:
                if key in entry:
                    file_path = self.models_dir / entry[key]
                    if not file_path.exists():
                        entry_valid = False
                        break
            
            if entry_valid:
                valid_entries.append(entry)
        
        removed_count = len(entries) - len(valid_entries)
        
        if removed_count > 0:
            with open(config_path, "w") as f:
                json.dump(valid_entries, f, indent=2)
        
        return removed_count
    
    def find_orphaned_models(self) -> list[str]:
        """Find model files not referenced in any config."""
        # Collect all referenced files
        referenced: set[str] = set()
        
        for config_name, file_keys in self.CONFIG_FILES.items():
            config_path = self.models_dir / config_name
            if not config_path.exists():
                continue
            
            try:
                with open(config_path) as f:
                    entries = json.load(f)
            except (json.JSONDecodeError, TypeError):
                continue
            
            if not isinstance(entries, list):
                continue
            
            for entry in entries:
                for key in file_keys:
                    if key in entry:
                        referenced.add(entry[key])
        
        # Find all .ckpt files
        all_models = set(f.name for f in self.models_dir.glob("*.ckpt"))
        
        # Orphaned = exists but not referenced
        orphaned = sorted(all_models - referenced)
        
        return orphaned
    
    def get_disk_usage(self) -> dict[str, int]:
        """Get disk usage statistics."""
        total = 0
        by_type: dict[str, int] = {
            "models": 0,
            "loras": 0,
            "other": 0,
        }
        
        for f in self.models_dir.glob("*.ckpt"):
            size = f.stat().st_size
            total += size
            
            name = f.name.lower()
            if "_lora_" in name or name.endswith("_lora.ckpt"):
                by_type["loras"] += size
            else:
                by_type["models"] += size
        
        by_type["total"] = total
        return by_type
    
    def get_cache_info(self) -> dict[str, Any]:
        """Get information about cache directories."""
        cache_info: dict[str, Any] = {
            "directories": [],
            "total_size": 0,
            "total_files": 0,
        }
        
        for cache_subdir in self.CACHE_DIRS:
            cache_path = self.container_dir / cache_subdir
            if not cache_path.exists():
                continue
            
            dir_info = {
                "path": str(cache_path),
                "name": cache_subdir,
                "size": 0,
                "files": 0,
            }
            
            try:
                for f in cache_path.rglob("*"):
                    if f.is_file():
                        dir_info["files"] += 1
                        dir_info["size"] += f.stat().st_size
            except PermissionError:
                pass
            
            cache_info["directories"].append(dir_info)
            cache_info["total_size"] += dir_info["size"]
            cache_info["total_files"] += dir_info["files"]
        
        return cache_info
    
    def clear_cache(self, dry_run: bool = True, clear_all: bool = False) -> dict[str, Any]:
        """Clear Draw Things cache directories.
        
        Args:
            dry_run: If True, only report what would be deleted.
            clear_all: If True, clear all caches including model caches.
            
        Returns:
            Dict with cleared directories and sizes.
        """
        result: dict[str, Any] = {
            "cleared": [],
            "total_size": 0,
            "total_files": 0,
            "dry_run": dry_run,
        }
        
        caches_dir = self.container_dir / "Library/Caches"
        if not caches_dir.exists():
            return result
        
        # Define what to clear based on mode
        if clear_all:
            # Clear everything in Caches
            dirs_to_clear = [
                ("net", "Network cache (model catalogs)"),
                ("qwen_image", "Qwen model cache"),
                ("com.liuliu.draw-things", "App cache database"),
                ("mfa_v2", "MFA cache"),
            ]
        else:
            # Just clear network cache (safe refresh)
            dirs_to_clear = [
                ("net", "Network cache (model catalogs)"),
            ]
        
        for subdir, description in dirs_to_clear:
            cache_path = caches_dir / subdir
            if not cache_path.exists():
                continue
            
            try:
                size = sum(f.stat().st_size for f in cache_path.rglob("*") if f.is_file())
                files = sum(1 for f in cache_path.rglob("*") if f.is_file())
            except PermissionError:
                continue
            
            if files == 0:
                continue
            
            result["cleared"].append({
                "path": str(cache_path),
                "name": description,
                "size": size,
                "files": files,
            })
            result["total_size"] += size
            result["total_files"] += files
            
            if not dry_run:
                shutil.rmtree(cache_path)
                cache_path.mkdir(parents=True, exist_ok=True)
        
        return result
    
    def run_clear_cache(self, dry_run: bool = True, clear_all: bool = False) -> bool:
        """Run cache clearing operation."""
        print("Draw Things Cache Management")
        print(f"Container: {self.container_dir}")
        print()
        
        def format_size(bytes_val: int) -> str:
            for unit in ["B", "KB", "MB", "GB"]:
                if bytes_val < 1024:
                    return f"{bytes_val:.1f} {unit}"
                bytes_val /= 1024
            return f"{bytes_val:.1f} TB"
        
        # Show current cache info
        print("=== Current Cache Status ===")
        cache_info = self.get_cache_info()
        
        for dir_info in cache_info["directories"]:
            print(f"  {dir_info['name']}: {format_size(dir_info['size'])} ({dir_info['files']} files)")
        
        print(f"  Total: {format_size(cache_info['total_size'])} ({cache_info['total_files']} files)")
        print()
        
        if cache_info["total_size"] == 0:
            print("✓ Cache is already empty")
            return True
        
        # Clear cache
        mode = "all caches" if clear_all else "network cache only"
        if dry_run:
            print(f"=== Would Clear ({mode}, dry-run) ===")
        else:
            print(f"=== Clearing {mode} ===")
        
        result = self.clear_cache(dry_run=dry_run, clear_all=clear_all)
        
        if not result["cleared"]:
            print("  Nothing to clear")
            return True
        
        for item in result["cleared"]:
            action = "Would delete" if dry_run else "Deleted"
            print(f"  {action}: {item['name']}")
            print(f"    Path: {item['path']}")
            print(f"    Size: {format_size(item['size'])} ({item['files']} files)")
        
        print()
        
        if dry_run:
            print(f"Would free: {format_size(result['total_size'])}")
            print()
            if clear_all:
                print("Run --clear-cache without --dry-run to actually clear.")
            else:
                print("Run --clear-net-cache without --dry-run to actually clear.")
                print("Use --clear-cache to clear all caches including model caches.")
        else:
            print(f"✓ Freed: {format_size(result['total_size'])}")
            print()
            if clear_all:
                print("Note: Draw Things will re-cache models on next use (slower first load).")
            else:
                print("Note: Draw Things will re-download model catalogs on next launch.")
        
        return True
    
    def run(self, fix: bool = False) -> bool:
        """Run the full tuneup. Returns True if all clean."""
        print(f"Draw Things Tuneup")
        print(f"Models directory: {self.models_dir}")
        print()
        
        if not self.models_dir.exists():
            print(f"ERROR: Models directory not found!", file=sys.stderr)
            return False
        
        all_clean = True
        
        # Validate each config
        print("=== Config Validation ===")
        for config_name in self.CONFIG_FILES:
            result = self.validate_config(config_name)
            
            if result.total_entries == 0:
                status = "not found or empty"
            elif result.is_clean:
                status = f"{result.valid_entries} entries OK"
            else:
                status = f"{result.valid_entries}/{result.total_entries} valid, {result.invalid_count} missing"
                all_clean = False
            
            print(f"  {config_name}: {status}")
            
            if fix and not result.is_clean:
                removed = self.fix_config(config_name)
                if removed > 0:
                    print(f"    → Removed {removed} invalid entries")
        
        print()
        
        # Find orphaned models
        print("=== Orphaned Models (not in any config) ===")
        orphaned = self.find_orphaned_models()
        if orphaned:
            print(f"  Found {len(orphaned)} orphaned model files:")
            for name in orphaned[:10]:  # Show first 10
                print(f"    - {name}")
            if len(orphaned) > 10:
                print(f"    ... and {len(orphaned) - 10} more")
        else:
            print("  None found")
        
        print()
        
        # Disk usage
        print("=== Disk Usage ===")
        usage = self.get_disk_usage()
        
        def format_size(bytes_val: int) -> str:
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if bytes_val < 1024:
                    return f"{bytes_val:.1f} {unit}"
                bytes_val /= 1024
            return f"{bytes_val:.1f} PB"
        
        print(f"  Models: {format_size(usage['models'])}")
        print(f"  LoRAs:  {format_size(usage['loras'])}")
        print(f"  Total:  {format_size(usage['total'])}")
        
        print()
        
        if all_clean:
            print("✓ All configs are clean!")
        else:
            if fix:
                print("✓ Fixed invalid entries")
            else:
                print("⚠ Issues found. Run with --fix to clean up.")
        
        return all_clean


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Draw Things configuration tuneup and validation"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Remove invalid config entries (default: dry-run)"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear all Draw Things caches"
    )
    parser.add_argument(
        "--clear-net-cache",
        action="store_true",
        help="Clear only network cache (model catalogs)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        help="Override Models directory path"
    )
    
    args = parser.parse_args()
    
    tuneup = DrawThingsTuneup(
        models_dir=args.models_dir,
        verbose=args.verbose
    )
    
    if args.clear_cache or args.clear_net_cache:
        clear_all = args.clear_cache  # --clear-cache = all, --clear-net-cache = network only
        success = tuneup.run_clear_cache(dry_run=args.dry_run, clear_all=clear_all)
    else:
        success = tuneup.run(fix=args.fix)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
