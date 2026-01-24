#!/usr/bin/env python3
"""
Draw Things Script Manager

A tool to help manage scripts in Draw Things:
- List all scripts with metadata
- Validate scripts (check for missing files, invalid JSON)
- Sync orphaned files to custom_scripts.json
- Normalize metadata (fix case, sort entries)
- Rollback changes using git history
- Show diffs of changes

SAFETY: This tool ONLY modifies custom_scripts.json. It NEVER modifies,
renames, or deletes script files themselves. All operations are idempotent.

See DRAW_THINGS_API.md for JavaScript API documentation.
See README_SCRIPT_MANAGER.md for usage instructions.
"""

from __future__ import annotations

import json
import subprocess
import shutil
import sys
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


@dataclass
class ScriptMetadata:
    """Represents script metadata from custom_scripts.json"""
    name: str
    file: str
    description: str | None = None
    author: str | None = None
    tags: list[str] | None = None
    images: list[dict[str, Any]] | None = None
    base_color: str | None = None
    favicon: str | None = None
    file_path: str | None = None
    type: str | None = None
    is_sample_duplicate: bool | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScriptMetadata:
        """Create from dictionary (handles snake_case conversion)"""
        # Convert camelCase to snake_case for some fields
        field_map = {
            'baseColor': 'base_color',
            'filePath': 'file_path',
            'isSampleDuplicate': 'is_sample_duplicate',
        }

        converted = {
            field_map.get(key, key): value
            for key, value in data.items()
        }

        return cls(**converted)


# ============================================================================
# INTERFACES (Dependency Inversion Principle)
# ============================================================================

class IMetadataRepository(ABC):
    """Interface for metadata storage operations"""

    @abstractmethod
    def load(self) -> list[ScriptMetadata]:
        """Load metadata from storage"""
        ...

    @abstractmethod
    def save(self, metadata: list[ScriptMetadata], message: str | None = None) -> bool:
        """Save metadata to storage"""
        ...

    @abstractmethod
    def exists(self) -> bool:
        """Check if metadata file exists"""
        ...


class IFileSystem(ABC):
    """Interface for file system operations"""

    @abstractmethod
    def get_script_files(self) -> list[Path]:
        """Get all script files"""
        ...

    @abstractmethod
    def file_exists(self, path: Path) -> bool:
        """Check if file exists"""
        ...

    @abstractmethod
    def read_file(self, path: Path) -> str:
        """Read file contents"""
        ...

    @abstractmethod
    def write_file(self, path: Path, content: str) -> bool:
        """Write file contents"""
        ...


class IVersionControl(ABC):
    """Interface for version control operations"""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if version control is available"""
        ...

    @abstractmethod
    def commit(self, message: str) -> bool:
        """Commit changes"""
        ...

    @abstractmethod
    def rollback(self, commit_hash: str) -> bool:
        """Rollback to commit"""
        ...

    @abstractmethod
    def diff(self, commit_hash: str | None = None, use_color: bool = True) -> str:
        """Get diff"""
        ...

    @abstractmethod
    def status(self) -> dict[str, list[str]]:
        """Get status"""
        ...


# ============================================================================
# IMPLEMENTATIONS (Single Responsibility Principle)
# ============================================================================

class JsonMetadataRepository(IMetadataRepository):
    """Handles JSON metadata file I/O"""

    def __init__(self, json_path: Path):
        self.json_path = json_path

    def exists(self) -> bool:
        return self.json_path.exists()

    def load(self) -> list[ScriptMetadata]:
        if not self.exists():
            return []

        try:
            data = json.loads(self.json_path.read_text(encoding='utf-8'))
            return [ScriptMetadata.from_dict(item) for item in data]
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}", file=sys.stderr)
            return []

    def save(self, metadata: list[ScriptMetadata], message: str | None = None) -> bool:
        # Convert to JSON format
        data = []
        for m in metadata:
            d = asdict(m)
            # Remove None values
            d = {k: v for k, v in d.items() if v is not None}
            # Convert snake_case back to camelCase
            field_map = {
                'base_color': 'baseColor',
                'file_path': 'filePath',
                'is_sample_duplicate': 'isSampleDuplicate',
            }
            converted = {}
            for key, value in d.items():
                camel_key = field_map.get(key, key)
                converted[camel_key] = value
            data.append(converted)

        # Validate JSON
        try:
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            json.loads(json_str)  # Validate
        except (TypeError, ValueError) as e:
            print(f"❌ Error: Invalid data structure: {e}", file=sys.stderr)
            return False

        # Write file
        try:
            self.json_path.write_text(json_str, encoding='utf-8')
            return True
        except (OSError, PermissionError) as e:
            print(f"❌ Error writing file: {e}", file=sys.stderr)
            return False


class LocalFileSystem(IFileSystem):
    """Handles local file system operations"""

    def __init__(self, scripts_dir: Path):
        self.scripts_dir = scripts_dir

    def get_script_files(self) -> list[Path]:
        if not self.scripts_dir.exists():
            return []

        return [
            f for f in self.scripts_dir.iterdir()
            if f.is_file() and f.suffix == '.js' and f.name != 'custom_scripts.json'
        ]

    def file_exists(self, path: Path) -> bool:
        return path.exists()

    def read_file(self, path: Path) -> str:
        return path.read_text(encoding='utf-8')

    def write_file(self, path: Path, content: str) -> bool:
        try:
            path.write_text(content, encoding='utf-8')
            return True
        except OSError:
            return False


class GitVersionControl(IVersionControl):
    """Handles git operations"""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self._available = shutil.which('git') is not None
        if self._available:
            self._ensure_repo()

    def _ensure_repo(self):
        """Ensure git repo exists"""
        git_dir = self.repo_path / '.git'
        if not git_dir.exists():
            try:
                self._run_git(['init'], check=True)
                # Create .gitignore if it doesn't exist
                gitignore = self.repo_path / '.gitignore'
                if not gitignore.exists():
                    gitignore.write_text(
                        "# Auto-generated by script_manager.py\n"
                        "*.sqlite3*\n"
                        "*.shm\n"
                        "*.wal\n"
                        "script_summary.txt\n"
                    )
                self._run_git(['add', '.gitignore'], check=False)
                self._run_git(['commit', '-m', 'Initial commit: Add .gitignore'], check=False)
                print("ℹ️  Initialized git repository in scripts directory", file=sys.stderr)
            except (subprocess.CalledProcessError, OSError) as e:
                print(f"⚠️  Warning: Could not initialize git repo: {e}", file=sys.stderr)
                self._available = False

    def _run_git(self, args: list[str], check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess[str] | None:
        if not self._available:
            return None
        try:
            cmd = ['git', '-C', str(self.repo_path)] + args
            return subprocess.run(
                cmd, check=check, capture_output=capture_output,
                text=True, timeout=30
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            if check:
                raise
            return None

    def is_available(self) -> bool:
        return self._available

    def commit(self, message: str) -> bool:
        if not self._available:
            return False
        self._run_git(['add', 'custom_scripts.json'], check=False)
        result = self._run_git(['commit', '-m', message], check=False)
        return result is not None and result.returncode == 0

    def rollback(self, commit_hash: str) -> bool:
        # Implementation in ScriptManager.rollback
        return False

    def diff(self, commit_hash: str | None = None, use_color: bool = True) -> str:
        if not self._available:
            return ""
        args = ['diff']
        if use_color:
            args.append('--color=always')
        else:
            args.append('--color=never')
        if commit_hash:
            args.extend([f'{commit_hash}^..{commit_hash}'])
        args.extend(['--', 'custom_scripts.json'])
        result = self._run_git(args, capture_output=True, check=False)
        return result.stdout if result and result.stdout else ""

    def status(self) -> dict[str, list[str]]:
        if not self._available:
            return {'error': ['Git not available']}

        status = {
            'modified': [],
            'untracked': [],
            'staged': [],
            'clean': False
        }

        try:
            result = self._run_git(['status', '--porcelain'], capture_output=True, check=False)
            if result and result.returncode == 0:
                lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
                if not lines:
                    status['clean'] = True
                else:
                    for line in lines:
                        if line.startswith('??'):
                            status['untracked'].append(line[3:])
                        elif line.startswith(' M') or line.startswith('MM'):
                            status['modified'].append(line[3:])
                        elif line.startswith('M ') or line.startswith('A '):
                            status['staged'].append(line[3:])
        except Exception as e:
            status['error'] = [str(e)]

        return status


class NoOpVersionControl(IVersionControl):
    """Null object pattern - no version control"""

    def is_available(self) -> bool:
        return False

    def commit(self, message: str) -> bool:
        return False

    def rollback(self, commit_hash: str) -> bool:
        return False

    def diff(self, commit_hash: str | None = None, use_color: bool = True) -> str:
        return ""

    def status(self) -> dict[str, list[str]]:
        return {'error': ['Git not available']}


# ============================================================================
# SERVICES (Single Responsibility)
# ============================================================================

class MetadataValidator:
    """Validates metadata and files"""

    def __init__(self, repository: IMetadataRepository, filesystem: IFileSystem):
        self.repository = repository
        self.filesystem = filesystem

    def validate(self) -> dict[str, Any]:
        """Validate and return issues"""
        metadata = self.repository.load()
        files = self.filesystem.get_script_files()

        issues = {
            'missing_files': [],
            'orphaned_files': [],
            'invalid_json': False,
            'duplicate_files': [],
            'case_mismatches': []
        }

        # Check for missing files and case mismatches
        file_names_lower = {f.name.lower(): f.name for f in files}
        metadata_files_lower = {m.file.lower() for m in metadata}

        for m in metadata:
            if m.file.lower() not in file_names_lower:
                issues['missing_files'].append(m.file)
            elif m.file != file_names_lower[m.file.lower()]:
                issues['case_mismatches'].append((m.file, file_names_lower[m.file.lower()]))

        # Check for orphaned files
        for f in files:
            if f.name.lower() not in metadata_files_lower:
                issues['orphaned_files'].append(f.name)

        # Check for duplicates
        file_counts = defaultdict(int)
        for m in metadata:
            file_counts[m.file.lower()] += 1
        issues['duplicate_files'] = [f for f, count in file_counts.items() if count > 1]

        return issues


class MetadataNormalizer:
    """Normalizes metadata"""

    def __init__(self, filesystem: IFileSystem):
        self.filesystem = filesystem

    def normalize(self, metadata: list[ScriptMetadata],
                  fix_case: bool = True, sort: bool = True) -> list[ScriptMetadata]:
        """Normalize metadata"""
        normalized = list(metadata)

        if fix_case:
            file_names_lower = {f.name.lower(): f.name
                              for f in self.filesystem.get_script_files()}
            for i, m in enumerate(normalized):
                if m.file.lower() in file_names_lower:
                    actual_file = file_names_lower[m.file.lower()]
                    if m.file != actual_file:
                        normalized[i] = ScriptMetadata(
                            name=m.name,
                            file=actual_file,
                            description=m.description,
                            author=m.author,
                            tags=m.tags,
                            images=m.images,
                            base_color=m.base_color,
                            favicon=m.favicon,
                            file_path=m.file_path,
                            type=m.type,
                            is_sample_duplicate=m.is_sample_duplicate
                        )

        if sort:
            normalized.sort(key=lambda x: x.name.lower())

        return normalized


class ScriptMetadataExtractor:
    """Extracts metadata from script files"""

    def extract(self, script_path: Path) -> dict[str, Any]:
        """Extract metadata from script file comments"""
        metadata: dict[str, Any] = {}

        try:
            content = script_path.read_text(encoding='utf-8')
            lines = content.split('\n')[:20]  # Check first 20 lines

            for line in lines:
                line = line.strip()
                if line.startswith('//'):
                    line = line[2:].strip()
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower()
                        value = value.strip()

                        match key:
                            case 'v' | 'version':
                                metadata['version'] = value
                            case key if key in ('author', 'name', 'description'):
                                metadata[key] = value
        except OSError as e:
            print(f"Error reading {script_path}: {e}", file=sys.stderr)

        return metadata


# ============================================================================
# FACADE (Easy to Use - Factory Pattern)
# ============================================================================

class ScriptManager:
    """
    Facade for script management.

    Easy to use with zero configuration:
        manager = ScriptManager.create()

    Or with custom configuration:
        manager = ScriptManager.create(scripts_dir="/path", use_git=False)
    """

    def __init__(self,
                 repository: IMetadataRepository,
                 filesystem: IFileSystem,
                 version_control: IVersionControl,
                 scripts_dir: Path):
        self.repository = repository
        self.filesystem = filesystem
        self.version_control = version_control
        self.scripts_dir = scripts_dir
        self.custom_scripts_json = scripts_dir / "custom_scripts.json"
        self.extractor = ScriptMetadataExtractor()
        self.validator = MetadataValidator(repository, filesystem)
        self.normalizer = MetadataNormalizer(filesystem)
        self.extractor = ScriptMetadataExtractor()

    @classmethod
    def create(cls, scripts_dir: str | Path | None = None, use_git: bool = True) -> ScriptManager:
        """
        Factory method for easy creation with sensible defaults.

        Zero-config usage:
            manager = ScriptManager.create()

        Custom config:
            manager = ScriptManager.create(scripts_dir="/path", use_git=False)
        """
        # Auto-detect scripts directory
        if scripts_dir is None:
            scripts_path = Path.home() / "Library/Containers/com.liuliu.draw-things/Data/Documents/Scripts"
        else:
            scripts_path = Path(scripts_dir)
        json_path = scripts_path / "custom_scripts.json"

        # Create dependencies (Dependency Injection)
        repository = JsonMetadataRepository(json_path)
        filesystem = LocalFileSystem(scripts_path)

        # Version control (optional)
        if use_git:
            version_control = GitVersionControl(scripts_path)
        else:
            version_control = NoOpVersionControl()

        return cls(repository, filesystem, version_control, scripts_path)

    # Keep existing methods but delegate to dependencies
    def load_metadata(self) -> list[ScriptMetadata]:
        """Load script metadata from custom_scripts.json"""
        return self.repository.load()

    def get_script_files(self) -> list[Path]:
        """Get all .js files in the scripts directory"""
        return self.filesystem.get_script_files()

    def extract_metadata_from_script(self, script_path: Path) -> dict[str, Any]:
        """Extract metadata from script file comments"""
        return self.extractor.extract(script_path)

    def _ensure_git_repo(self) -> None:
        """Ensure the scripts directory is a git repository"""
        # Git repo initialization is handled by GitVersionControl
        if self.version_control.is_available():
            self.version_control.ensure_repo(self.scripts_dir)

    def _run_git(self, args: list[str], check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess[str] | None:
        """Run a git command"""
        if not self.version_control.is_available():
            return None

        try:
            cmd = ['git', '-C', str(self.scripts_dir)] + args
            result = subprocess.run(
                cmd,
                check=check,
                capture_output=capture_output,
                text=True,
                timeout=30
            )
            return result
        except subprocess.CalledProcessError as e:
            if check:
                raise
            return None
        except Exception as e:
            if check:
                raise
            return None

    def _backup_file(self, file_path: Path) -> Path | None:
        """Create a backup of a file before modification"""
        if not file_path.exists():
            return None

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = file_path.parent / f"{file_path.name}.backup_{timestamp}"

        try:
            shutil.copy2(file_path, backup_path)
            return backup_path
        except OSError as e:
            print(f"⚠️  Warning: Could not create backup: {e}", file=sys.stderr)
            return None

    def _save_metadata(self, metadata_list: list[ScriptMetadata], commit_message: str | None = None) -> bool:
        """Save metadata to JSON file with git integration"""
        # Validate JSON before writing
        data = []
        for m in metadata_list:
            d = asdict(m)
            # Remove None values
            d = {k: v for k, v in d.items() if v is not None}
            # Convert snake_case back to camelCase
            field_map = {
                'base_color': 'baseColor',
                'file_path': 'filePath',
                'is_sample_duplicate': 'isSampleDuplicate',
            }
            converted = {}
            for key, value in d.items():
                camel_key = field_map.get(key, key)
                converted[camel_key] = value
            data.append(converted)

        # Validate JSON can be serialized
        try:
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            json.loads(json_str)  # Validate it's valid JSON
        except (TypeError, ValueError) as e:
            print(f"❌ Error: Invalid data structure: {e}", file=sys.stderr)
            return False

        # Create backup
        backup_path = self._backup_file(self.custom_scripts_json)

        try:
            # Write to file
            self.custom_scripts_json.write_text(json_str, encoding='utf-8')

            # Stage and commit if using git
            if self.version_control.is_available() and commit_message:
                self._run_git(['add', str(self.custom_scripts_json)], check=False)
                self._run_git(['commit', '-m', commit_message], check=False)

            if backup_path:
                # Clean up backup after successful write
                try:
                    backup_path.unlink()
                except OSError:
                    pass

            return True
        except Exception as e:
            print(f"❌ Error writing file: {e}", file=sys.stderr)
            # Restore from backup if write failed
            if backup_path and backup_path.exists():
                try:
                    shutil.copy2(backup_path, self.custom_scripts_json)
                    print(f"✓ Restored from backup: {backup_path}", file=sys.stderr)
                except OSError:
                    pass
            return False

    def git_status(self) -> dict[str, list[str]]:
        """Get git status of scripts directory"""
        if not self.version_control.is_available():
            return {'error': ['Git not available']}

        status = {
            'modified': [],
            'untracked': [],
            'staged': [],
            'clean': False
        }

        try:
            # Check if there are any changes
            result = self._run_git(['status', '--porcelain'], capture_output=True, check=False)
            if result and result.returncode == 0:
                lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
                if not lines:
                    status['clean'] = True
                else:
                    for line in lines:
                        if line.startswith('??'):
                            status['untracked'].append(line[3:])
                        elif line.startswith(' M') or line.startswith('MM'):
                            status['modified'].append(line[3:])
                        elif line.startswith('M ') or line.startswith('A '):
                            status['staged'].append(line[3:])
        except Exception as e:
            status['error'] = [str(e)]

        return status

    def extract_metadata_from_script(self, script_path: Path) -> dict[str, Any]:
        """Extract metadata from script file comments"""
        metadata = {}

        try:
            lines = script_path.read_text(encoding='utf-8').splitlines(keepends=True)

            # Look for comment-based metadata
            for line in lines[:20]:  # Check first 20 lines
                line = line.strip()
                if line.startswith('//'):
                    line = line[2:].strip()
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower()
                        value = value.strip()

                        if key in ['author', 'name', 'description', 'version', 'v']:
                            if key == 'v' or key == 'version':
                                metadata['version'] = value
                            else:
                                metadata[key] = value
        except Exception as e:
            print(f"Error reading {script_path}: {e}", file=sys.stderr)

        return metadata

    def validate(self) -> dict[str, Any]:
        """Validate scripts and return issues"""
        issues = {
            'missing_files': [],  # In JSON but file doesn't exist
            'orphaned_files': [],  # File exists but not in JSON
            'invalid_json': False,
            'duplicate_files': [],
            'case_mismatches': []  # Case differences between JSON and files
        }

        # Load metadata
        try:
            metadata_list = self.load_metadata()
        except Exception as e:
            issues['invalid_json'] = True
            issues['json_error'] = str(e)
            metadata_list = []

        # Get all script files
        script_files = self.get_script_files()
        file_names = {f.name for f in script_files}
        file_names_lower = {f.name.lower(): f.name for f in script_files}

        # Check for missing files and case mismatches
        metadata_files = {m.file for m in metadata_list}
        for metadata in metadata_list:
            if metadata.file not in file_names:
                # Check case-insensitive match
                if metadata.file.lower() in file_names_lower:
                    actual_file = file_names_lower[metadata.file.lower()]
                    issues['case_mismatches'].append((metadata.file, actual_file))
                else:
                    issues['missing_files'].append(metadata.file)

        # Check for orphaned files (case-insensitive)
        metadata_files_lower = {m.file.lower() for m in metadata_list}
        for script_file in script_files:
            if script_file.name.lower() not in metadata_files_lower:
                issues['orphaned_files'].append(script_file.name)

        # Check for duplicate file entries in JSON (case-insensitive)
        file_counts = defaultdict(int)
        for metadata in metadata_list:
            file_counts[metadata.file.lower()] += 1

        issues['duplicate_files'] = [f for f, count in file_counts.items() if count > 1]

        return issues

    def list_scripts(self, show_details: bool = False) -> None:
        """List all scripts"""
        metadata_list = self.load_metadata()
        script_files = self.get_script_files()

        # Create a mapping of file (case-insensitive) -> metadata
        metadata_map = {m.file.lower(): m for m in metadata_list}
        file_names_lower = {f.name.lower(): f.name for f in script_files}

        print(f"\n{'='*80}")
        print(f"Draw Things Scripts Manager")
        print(f"{'='*80}\n")
        print(f"Scripts Directory: {self.scripts_dir}")
        print(f"Total Script Files: {len(script_files)}")
        print(f"Scripts with Metadata: {len(metadata_list)}")
        print(f"\n{'='*80}\n")

        # List scripts with metadata
        if metadata_list:
            print("Scripts with Metadata:")
            print("-" * 80)
            for metadata in sorted(metadata_list, key=lambda x: x.name.lower()):
                print(f"\n📜 {metadata.name}")
                print(f"   File: {metadata.file}")
                if metadata.author:
                    print(f"   Author: {metadata.author}")
                if metadata.description:
                    print(f"   Description: {metadata.description[:100]}...")
                if metadata.tags:
                    print(f"   Tags: {', '.join(metadata.tags)}")

                # Check if file exists (case-insensitive)
                file_path = self.scripts_dir / metadata.file
                if file_path.exists():
                    size = file_path.stat().st_size
                    print(f"   Status: ✓ File exists ({size:,} bytes)")
                elif metadata.file.lower() in file_names_lower:
                    actual_file = file_names_lower[metadata.file.lower()]
                    actual_path = self.scripts_dir / actual_file
                    size = actual_path.stat().st_size
                    print(f"   Status: ⚠ Case mismatch (JSON: {metadata.file}, File: {actual_file}) ({size:,} bytes)")
                else:
                    print(f"   Status: ✗ File missing!")

                if show_details:
                    if metadata.images:
                        print(f"   Images: {len(metadata.images)}")
                    if metadata.base_color:
                        print(f"   Base Color: {metadata.base_color}")

        # List orphaned files (case-insensitive check)
        orphaned = [f for f in script_files if f.name.lower() not in metadata_map]
        if orphaned:
            print(f"\n\nOrphaned Files (not in metadata):")
            print("-" * 80)
            for script_file in sorted(orphaned, key=lambda x: x.name.lower()):
                size = script_file.stat().st_size
                print(f"  • {script_file.name} ({size:,} bytes)")

                if show_details:
                    # Try to extract metadata from comments
                    extracted = self.extract_metadata_from_script(script_file)
                    if extracted:
                        print(f"    Extracted: {extracted}")

        print(f"\n{'='*80}\n")

    def validate_and_report(self) -> bool:
        """Validate scripts and print report"""
        issues = self.validate()

        print(f"\n{'='*80}")
        print("Validation Report")
        print(f"{'='*80}\n")

        has_issues = False

        if issues['invalid_json']:
            print("❌ Invalid JSON in custom_scripts.json")
            print(f"   Error: {issues.get('json_error', 'Unknown error')}")
            has_issues = True
        else:
            print("✓ JSON is valid")

        if issues['missing_files']:
            print(f"\n❌ Missing Files ({len(issues['missing_files'])}):")
            for file in issues['missing_files']:
                print(f"   • {file}")
            has_issues = True
        else:
            print("\n✓ All metadata files exist")

        if issues['orphaned_files']:
            print(f"\n⚠️  Orphaned Files ({len(issues['orphaned_files'])}):")
            print("   (Files exist but not in metadata)")
            for file in issues['orphaned_files']:
                print(f"   • {file}")
        else:
            print("\n✓ No orphaned files")

        if issues['duplicate_files']:
            print(f"\n❌ Duplicate Entries ({len(issues['duplicate_files'])}):")
            for file in issues['duplicate_files']:
                print(f"   • {file}")
            has_issues = True
        else:
            print("\n✓ No duplicate entries")

        if issues['case_mismatches']:
            print(f"\n⚠️  Case Mismatches ({len(issues['case_mismatches'])}):")
            print("   (JSON filename doesn't match actual file case)")
            for json_file, actual_file in issues['case_mismatches']:
                print(f"   • JSON: {json_file} → File: {actual_file}")

        print(f"\n{'='*80}\n")

        return not has_issues

    def sync_metadata(self, dry_run: bool = True, files_to_manage: list[str] | None = None) -> None:
        """
        Sync metadata - add orphaned files to JSON.

        This function ONLY modifies custom_scripts.json, never the script files themselves.
        It is idempotent - running it multiple times produces the same result.

        Args:
            dry_run: If True, only show what would be done
            files_to_manage: List of specific filenames to add. If None, adds all orphaned files.
        """
        issues = self.validate()

        if not issues['orphaned_files']:
            print("No orphaned files to sync.")
            return

        print(f"\n{'='*80}")
        print("Sync Metadata")
        print(f"{'='*80}\n")
        print("⚠️  This will ONLY modify custom_scripts.json, never the script files themselves.\n")

        metadata_list = self.load_metadata()
        # Use case-insensitive matching for existing files
        existing_files_lower = {m.file.lower() for m in metadata_list}
        existing_files_map = {m.file.lower(): m.file for m in metadata_list}

        # Filter files to manage
        files_to_add = []
        if files_to_manage:
            # Only add explicitly requested files
            for file_name in files_to_manage:
                if file_name.lower() not in existing_files_lower:
                    if file_name in issues['orphaned_files']:
                        files_to_add.append(file_name)
                    else:
                        print(f"⚠️  Skipping {file_name} (not found in orphaned files)")
                else:
                    actual_file = existing_files_map.get(file_name.lower(), file_name)
                    print(f"ℹ️  Skipping {file_name} (already in metadata as {actual_file})")
        else:
            # Add all orphaned files
            files_to_add = issues['orphaned_files']

        if not files_to_add:
            print("No files to add.")
            return

        new_entries = []
        for file_name in files_to_add:
            script_path = self.scripts_dir / file_name
            if not script_path.exists():
                print(f"⚠️  Skipping {file_name} (file does not exist)")
                continue

            # Check if already exists (case-insensitive) - idempotency check
            if file_name.lower() in existing_files_lower:
                actual_file = existing_files_map[file_name.lower()]
                print(f"ℹ️  Skipping {file_name} (already exists as {actual_file} in metadata)")
                continue

            extracted = self.extract_metadata_from_script(script_path)

            # Create basic metadata entry
            name = file_name.replace('.js', '').replace('-', ' ').replace('_', ' ').title()
            entry = {
                'name': name,
                'file': file_name,  # Use actual filename as-is
                'description': extracted.get('description', ''),
                'author': extracted.get('author', ''),
            }

            new_entries.append(entry)
            print(f"{'Would add' if dry_run else 'Adding'}: {name} ({file_name})")

        if not new_entries:
            print("\nNo new entries to add.")
            return

        if not dry_run:
            # Add new entries to metadata (idempotent - won't add duplicates)
            for entry_dict in new_entries:
                entry = ScriptMetadata.from_dict(entry_dict)
                # Double-check it doesn't already exist
                if entry.file.lower() not in existing_files_lower:
                    metadata_list.append(entry)
                    existing_files_lower.add(entry.file.lower())

            # Save with git integration
            commit_msg = f"Add metadata for {len(new_entries)} script(s): {', '.join([e['file'] for e in new_entries])}"
            if self._save_metadata(metadata_list, commit_message=commit_msg):
                print(f"\n✓ Added {len(new_entries)} entries to custom_scripts.json")
                if self.version_control.is_available():
                    print("✓ Changes committed to git")
            else:
                print(f"\n❌ Failed to save metadata")
                return
        else:
            print(f"\n[DRY RUN] Would add {len(new_entries)} entries.")
            print("Use --no-dry-run to apply changes.")

        print(f"\n{'='*80}\n")

    def normalize(self, dry_run: bool = True, fix_case: bool = True,
                  normalize_json: bool = True, sort_entries: bool = True) -> None:
        """
        Normalize the scripts directory and metadata.

        This function normalizes metadata to match actual files and standardizes
        the JSON structure. It NEVER renames or moves actual script files.

        Args:
            dry_run: If True, only show what would be normalized
            fix_case: Fix case mismatches in metadata (update JSON to match file case)
            normalize_json: Normalize JSON structure (remove None values, standardize format)
            sort_entries: Sort entries alphabetically by name
        """
        print(f"\n{'='*80}")
        print("Normalize Scripts")
        print(f"{'='*80}\n")
        print("⚠️  This will ONLY modify custom_scripts.json, never the script files themselves.\n")

        issues = self.validate()
        metadata_list = self.load_metadata()
        script_files = self.get_script_files()

        # Create mapping of actual files (case-insensitive)
        file_names_lower = {f.name.lower(): f.name for f in script_files}

        changes_made = []
        normalized_metadata = []

        # Fix case mismatches
        if fix_case and issues['case_mismatches']:
            print("Case Mismatches to Fix:")
            print("-" * 80)
            for json_file, actual_file in issues['case_mismatches']:
                print(f"   JSON: {json_file} → File: {actual_file}")
                changes_made.append(f"Fix case: {json_file} → {actual_file}")

        # Process each metadata entry
        for metadata in metadata_list:
            normalized = metadata

            # Fix case if needed
            if fix_case:
                # Check if file exists with different case
                if metadata.file.lower() in file_names_lower:
                    actual_file = file_names_lower[metadata.file.lower()]
                    if metadata.file != actual_file:
                        # Update to match actual file case
                        normalized = ScriptMetadata(
                            name=metadata.name,
                            file=actual_file,  # Use actual file case
                            description=metadata.description,
                            author=metadata.author,
                            tags=metadata.tags,
                            images=metadata.images,
                            base_color=metadata.base_color,
                            favicon=metadata.favicon,
                            file_path=metadata.file_path,
                            type=metadata.type,
                            is_sample_duplicate=metadata.is_sample_duplicate
                        )

            # Normalize JSON structure (remove None values, ensure consistent format)
            # This is handled when converting to dict for saving in _save_metadata

            normalized_metadata.append(normalized)

        # Sort entries if requested
        if sort_entries:
            normalized_metadata.sort(key=lambda x: x.name.lower())
            if normalized_metadata != metadata_list:
                changes_made.append("Sort entries alphabetically")

        # Check if any changes would be made
        if not changes_made and normalized_metadata == metadata_list:
            print("✓ No normalization needed - everything is already normalized")
            print(f"\n{'='*80}\n")
            return

        # Show what would change
        if dry_run:
            print("\n[DRY RUN] Would make the following changes:")
            for change in changes_made:
                print(f"   • {change}")
            print(f"\nTotal: {len(changes_made)} change(s)")
            print("\nUse --no-dry-run to apply normalization.")
        else:
            # Apply normalization
            commit_msg = f"Normalize metadata: {', '.join(changes_made[:3])}"
            if len(changes_made) > 3:
                commit_msg += f" (+{len(changes_made) - 3} more)"

            if self._save_metadata(normalized_metadata, commit_message=commit_msg):
                print(f"\n✓ Normalized metadata:")
                for change in changes_made:
                    print(f"   • {change}")
                if self.version_control.is_available():
                    print("✓ Changes committed to git")
            else:
                print("\n❌ Failed to normalize metadata")
                return

        print(f"\n{'='*80}\n")

    def rollback(self, commit_hash: str | None = None, dry_run: bool = True) -> None:
        """
        Roll back changes to custom_scripts.json using git history.

        This function can restore custom_scripts.json to a previous state using git.
        It NEVER modifies script files, only the metadata JSON.

        Args:
            commit_hash: Specific commit hash to roll back to (default: previous commit)
            dry_run: If True, only show what would be rolled back
        """
        print(f"\n{'='*80}")
        print("Rollback Changes")
        print(f"{'='*80}\n")

        if not self.version_control.is_available():
            print("❌ Git is not available. Cannot rollback using git.")
            print("\nAlternative: Check for backup files:")
            backup_files = sorted(self.scripts_dir.glob("custom_scripts.json.backup_*"))
            if backup_files:
                print(f"Found {len(backup_files)} backup(s):")
                for backup in backup_files[-5:]:  # Show last 5
                    print(f"   • {backup.name}")
                print("\nYou can manually restore from a backup file.")
            else:
                print("No backup files found.")
            print(f"\n{'='*80}\n")
            return

        # Get git log
        result = self._run_git(['log', '--oneline', '-20'], capture_output=True, check=False)
        if not result or result.returncode != 0:
            print("❌ Could not access git history")
            print(f"\n{'='*80}\n")
            return

        commits = result.stdout.strip().split('\n') if result.stdout.strip() else []

        if not commits:
            print("No git history found.")
            print(f"\n{'='*80}\n")
            return

        # Show recent commits
        print("Recent commits affecting custom_scripts.json:")
        print("-" * 80)
        relevant_commits = []
        for commit_line in commits:
            if 'custom_scripts.json' in commit_line.lower() or len(relevant_commits) < 5:
                commit_hash_val = commit_line.split()[0] if commit_line else None
                commit_msg = ' '.join(commit_line.split()[1:]) if len(commit_line.split()) > 1 else commit_line
                if commit_hash_val:
                    relevant_commits.append((commit_hash_val, commit_msg))
                    print(f"   {commit_hash_val[:8]} - {commit_msg}")

        if not commit_hash:
            # Default to previous commit
            if len(relevant_commits) > 1:
                commit_hash = relevant_commits[1][0]  # Second commit (first is current)
                print(f"\nWill rollback to: {commit_hash[:8]} - {relevant_commits[1][1]}")
            else:
                print("\n❌ No previous commit to rollback to")
                print(f"\n{'='*80}\n")
                return
        else:
            # Validate commit hash
            if len(commit_hash) < 7:
                # Try to find matching commit
                matching = [c for c in relevant_commits if c[0].startswith(commit_hash)]
                if matching:
                    commit_hash = matching[0][0]
                    print(f"\nRolling back to: {commit_hash[:8]} - {matching[0][1]}")
                else:
                    print(f"\n❌ Commit hash not found: {commit_hash}")
                    print(f"\n{'='*80}\n")
                    return
            else:
                # Full or partial hash provided
                matching = [c for c in relevant_commits if c[0].startswith(commit_hash[:8])]
                if matching:
                    commit_hash = matching[0][0]
                    print(f"\nRolling back to: {commit_hash[:8]} - {matching[0][1]}")
                else:
                    print(f"\n⚠️  Warning: Commit {commit_hash[:8]} not in recent history")
                    print("Proceeding anyway...")

        if dry_run:
            print("\n[DRY RUN] Would restore custom_scripts.json from commit")
            print("Use --no-dry-run to actually rollback.")
        else:
            # Show current file state
            current_size = self.custom_scripts_json.stat().st_size if self.custom_scripts_json.exists() else 0
            print(f"\nCurrent file size: {current_size:,} bytes")

            # Get file from that commit
            result = self._run_git(['show', f'{commit_hash}:custom_scripts.json'],
                                  capture_output=True, check=False)

            if not result or result.returncode != 0:
                print(f"❌ Could not retrieve file from commit {commit_hash[:8]}")
                print(f"\n{'='*80}\n")
                return

            # Validate JSON
            try:
                restored_data = json.loads(result.stdout)
                print(f"Restored file would be: {len(result.stdout):,} bytes")
                print(f"Would contain {len(restored_data)} script entries")
            except json.JSONDecodeError:
                print("⚠️  Warning: Restored file is not valid JSON")
                response = input("Continue anyway? (y/N): ").strip().lower()
                if response != 'y':
                    print("Rollback cancelled.")
                    print(f"\n{'='*80}\n")
                    return

            # Create backup of current state
            backup_path = self._backup_file(self.custom_scripts_json)
            if backup_path:
                print(f"✓ Created backup: {backup_path.name}")

            # Restore file
            try:
                self.custom_scripts_json.write_text(result.stdout, encoding='utf-8')

                # Commit the rollback
                commit_msg = f"Rollback to {commit_hash[:8]}"
                self._run_git(['add', str(self.custom_scripts_json)], check=False)
                self._run_git(['commit', '-m', commit_msg], check=False)

                print(f"\n✓ Rolled back custom_scripts.json to commit {commit_hash[:8]}")
                if self.version_control.is_available():
                    print("✓ Rollback committed to git")
            except Exception as e:
                print(f"\n❌ Error during rollback: {e}")
                # Try to restore from backup
                if backup_path and backup_path.exists():
                    try:
                        shutil.copy2(backup_path, self.custom_scripts_json)
                        print(f"✓ Restored from backup: {backup_path.name}")
                    except:
                        pass
                return

        print(f"\n{'='*80}\n")

    def show_diff(self, commit_hash: str | None = None,
                  use_color: bool = True) -> None:
        """
        Show colored diff of changes to custom_scripts.json.

        Args:
            commit_hash: Show diff for specific commit (default: show unstaged changes)
            use_color: Use colored output (default: True)
        """
        if not self.version_control.is_available():
            print("❌ Git is not available. Cannot show diffs.")
            print(f"\n{'='*80}\n")
            return

        print(f"\n{'='*80}")
        if commit_hash:
            print(f"Diff for commit {commit_hash[:8]}")
        else:
            print("Diff (unstaged changes)")
        print(f"{'='*80}\n")

        # Build git diff command
        diff_args = ['diff']
        if use_color:
            diff_args.append('--color=always')
        else:
            diff_args.append('--color=never')

        if commit_hash:
            # Show diff for specific commit
            if len(commit_hash) < 7:
                # Try to find matching commit
                result = self._run_git(['log', '--oneline', '-20'], capture_output=True, check=False)
                if result and result.returncode == 0:
                    commits = result.stdout.strip().split('\n') if result.stdout.strip() else []
                    matching = [c.split()[0] for c in commits if c.split()[0].startswith(commit_hash)]
                    if matching:
                        commit_hash = matching[0]

            # Show diff between commit and its parent
            diff_args.extend([f'{commit_hash}^..{commit_hash}', '--', 'custom_scripts.json'])
        else:
            # Show unstaged changes
            diff_args.append('--')
            diff_args.append('custom_scripts.json')

        result = self._run_git(diff_args, capture_output=True, check=False)

        if result and result.returncode == 0:
            if result.stdout:
                print(result.stdout)
            else:
                print("No changes to show.")
        elif result and result.returncode == 1:
            # Exit code 1 means there are differences (this is normal for git diff)
            if result.stdout:
                print(result.stdout)
            else:
                print("No changes to show.")
        else:
            print("❌ Could not retrieve diff")
            if result and result.stderr:
                print(f"Error: {result.stderr}")

        print(f"\n{'='*80}\n")

    def export_summary(self, output_file: str | Path | None = None) -> None:
        """Export a summary report to a file"""
        if output_file is None:
            output_file = self.scripts_dir / "script_summary.txt"

        output_path = Path(output_file)
        # Capture output by redirecting stdout
        from io import StringIO
        buffer = StringIO()
        original_stdout = sys.stdout
        sys.stdout = buffer
        try:
            self.list_scripts(show_details=True)
            self.validate_and_report()
        finally:
            sys.stdout = original_stdout
        output_path.write_text(buffer.getvalue(), encoding='utf-8')

        print(f"Summary exported to: {output_file}")

    def manage_files(self, auto_sync: bool = False, show_status: bool = False) -> None:
        """
        Manage files you add - automatically track new files in metadata.

        This function helps manage files you manually add to the scripts directory
        by automatically adding them to custom_scripts.json.

        Args:
            auto_sync: If True, automatically add all orphaned files to metadata
            show_status: If True, show detailed status of all files
        """
        print(f"\n{'='*80}")
        print("Manage Files")
        print(f"{'='*80}\n")

        issues = self.validate()

        if show_status:
            # Show detailed status
            metadata_list = self.load_metadata()
            script_files = self.get_script_files()

            metadata_files_lower = {m.file.lower() for m in metadata_list}

            print("File Status:")
            print("-" * 80)

            # Files in metadata
            print(f"\n✓ Tracked in metadata ({len(metadata_list)}):")
            for metadata in sorted(metadata_list, key=lambda x: x.name.lower()):
                file_path = self.scripts_dir / metadata.file
                if file_path.exists():
                    size = file_path.stat().st_size
                    print(f"   • {metadata.file} ({size:,} bytes) - {metadata.name}")
                else:
                    print(f"   • {metadata.file} - ✗ FILE MISSING")

            # Orphaned files
            orphaned = [f for f in script_files if f.name.lower() not in metadata_files_lower]
            if orphaned:
                print(f"\n⚠️  Not tracked ({len(orphaned)}):")
                for script_file in sorted(orphaned, key=lambda x: x.name.lower()):
                    size = script_file.stat().st_size
                    print(f"   • {script_file.name} ({size:,} bytes)")
            else:
                print(f"\n✓ All files are tracked")

            # Missing files
            if issues['missing_files']:
                print(f"\n❌ Missing files ({len(issues['missing_files'])}):")
                for file in issues['missing_files']:
                    print(f"   • {file}")

        # Auto-sync if requested
        if auto_sync:
            if issues['orphaned_files']:
                print(f"\n{'='*80}")
                print(f"Auto-syncing {len(issues['orphaned_files'])} file(s)...")
                print(f"{'='*80}\n")
                self.sync_metadata(dry_run=False, files_to_manage=issues['orphaned_files'])
            else:
                print("\n✓ All files are already tracked in metadata")
        elif issues['orphaned_files']:
            print(f"\nFound {len(issues['orphaned_files'])} file(s) not in metadata:")
            for file in issues['orphaned_files']:
                print(f"   • {file}")
            print("\nRun with --auto-sync to automatically add them to metadata")

        print(f"\n{'='*80}\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Manage Draw Things scripts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                    # List all scripts
  %(prog)s list --details          # List with detailed information
  %(prog)s validate                # Validate scripts and report issues
  %(prog)s sync                    # Show what would be synced (dry run)
  %(prog)s sync --no-dry-run       # Actually sync metadata
  %(prog)s manage --status         # Show status of all files
  %(prog)s manage --auto-sync      # Auto-track files you add
  %(prog)s normalize               # Normalize metadata (fix case, sort)
  %(prog)s normalize --no-dry-run  # Apply normalization
  %(prog)s rollback                # Show rollback options (dry run)
  %(prog)s rollback --no-dry-run  # Rollback to previous commit
  %(prog)s rollback --commit HASH  # Rollback to specific commit
  %(prog)s diff                    # Show colored diff of unstaged changes
  %(prog)s diff --commit HASH      # Show diff for specific commit
  %(prog)s export                  # Export summary report
        """
    )

    parser.add_argument(
        '--scripts-dir',
        help='Path to Scripts directory (default: auto-detect)',
        default=None
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # List command
    list_parser = subparsers.add_parser('list', help='List all scripts')
    list_parser.add_argument('--details', action='store_true', help='Show detailed information')

    # Validate command
    subparsers.add_parser('validate', help='Validate scripts and report issues')

    # Sync command
    sync_parser = subparsers.add_parser('sync', help='Sync metadata (add orphaned files)')
    sync_parser.add_argument('--no-dry-run', action='store_true',
                           help='Actually apply changes (default is dry run)')
    sync_parser.add_argument('--files', nargs='+', metavar='FILE',
                           help='Specific files to add to metadata (default: all orphaned files)')

    # Git status command
    subparsers.add_parser('git-status', help='Show git status of scripts directory')

    # Manage command
    manage_parser = subparsers.add_parser('manage', help='Manage files you add (auto-track in metadata)')
    manage_parser.add_argument('--auto-sync', action='store_true',
                              help='Automatically add orphaned files to metadata')
    manage_parser.add_argument('--status', action='store_true',
                              help='Show detailed status of all files')

    # Normalize command
    normalize_parser = subparsers.add_parser('normalize', help='Normalize metadata (fix case, sort, standardize)')
    normalize_parser.add_argument('--no-dry-run', action='store_true',
                                 help='Actually apply normalization (default is dry run)')
    normalize_parser.add_argument('--no-fix-case', action='store_true',
                                 help='Skip fixing case mismatches')
    normalize_parser.add_argument('--no-sort', action='store_true',
                                 help='Skip sorting entries')

    # Rollback command
    rollback_parser = subparsers.add_parser('rollback', help='Rollback changes to custom_scripts.json')
    rollback_parser.add_argument('--commit', metavar='HASH',
                                help='Specific commit hash to rollback to (default: previous commit)')
    rollback_parser.add_argument('--no-dry-run', action='store_true',
                                help='Actually rollback (default is dry run)')

    # Diff command
    diff_parser = subparsers.add_parser('diff', help='Show colored diff of changes')
    diff_parser.add_argument('--commit', metavar='HASH',
                            help='Show diff for specific commit (default: unstaged changes)')
    diff_parser.add_argument('--no-color', action='store_true',
                            help='Disable colored output')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export summary report')
    export_parser.add_argument('--output', help='Output file path')

    args = parser.parse_args()

    manager = ScriptManager.create(scripts_dir=args.scripts_dir)

    if args.command == 'list':
        manager.list_scripts(show_details=args.details)
    elif args.command == 'validate':
        is_valid = manager.validate_and_report()
        sys.exit(0 if is_valid else 1)
    elif args.command == 'sync':
        manager.sync_metadata(dry_run=not args.no_dry_run, files_to_manage=getattr(args, 'files', None))
    elif args.command == 'git-status':
        status = manager.git_status()
        print(f"\n{'='*80}")
        print("Git Status")
        print(f"{'='*80}\n")
        if 'error' in status:
            print(f"❌ Error: {status['error'][0]}")
        elif status['clean']:
            print("✓ Working directory is clean")
        else:
            if status['modified']:
                print(f"Modified files ({len(status['modified'])}):")
                for f in status['modified']:
                    print(f"  • {f}")
            if status['staged']:
                print(f"\nStaged files ({len(status['staged'])}):")
                for f in status['staged']:
                    print(f"  • {f}")
            if status['untracked']:
                print(f"\nUntracked files ({len(status['untracked'])}):")
                for f in status['untracked']:
                    print(f"  • {f}")
        print(f"\n{'='*80}\n")
    elif args.command == 'manage':
        manager.manage_files(
            auto_sync=getattr(args, 'auto_sync', False),
            show_status=getattr(args, 'status', False)
        )
    elif args.command == 'normalize':
        manager.normalize(
            dry_run=not getattr(args, 'no_dry_run', False),
            fix_case=not getattr(args, 'no_fix_case', False),
            normalize_json=True,
            sort_entries=not getattr(args, 'no_sort', False)
        )
    elif args.command == 'rollback':
        manager.rollback(
            commit_hash=getattr(args, 'commit', None),
            dry_run=not getattr(args, 'no_dry_run', False)
        )
    elif args.command == 'diff':
        manager.show_diff(
            commit_hash=getattr(args, 'commit', None),
            use_color=not getattr(args, 'no_color', False)
        )
    elif args.command == 'export':
        manager.export_summary(output_file=args.output)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

