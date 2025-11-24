#!/usr/bin/env python3
"""
SOLID-compliant version of Script Manager

This demonstrates how to refactor while maintaining easy setup.
Users can still use: ScriptManager.create() with zero config.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict
import json
import subprocess
import shutil

# ============================================================================
# INTERFACES (Dependency Inversion Principle)
# ============================================================================

class IMetadataRepository(ABC):
    """Interface for metadata storage operations"""

    @abstractmethod
    def load(self) -> List['ScriptMetadata']:
        """Load metadata from storage"""
        pass

    @abstractmethod
    def save(self, metadata: List['ScriptMetadata'], message: Optional[str] = None) -> bool:
        """Save metadata to storage"""
        pass

    @abstractmethod
    def exists(self) -> bool:
        """Check if metadata file exists"""
        pass


class IFileSystem(ABC):
    """Interface for file system operations"""

    @abstractmethod
    def get_script_files(self) -> List[Path]:
        """Get all script files"""
        pass

    @abstractmethod
    def file_exists(self, path: Path) -> bool:
        """Check if file exists"""
        pass

    @abstractmethod
    def read_file(self, path: Path) -> str:
        """Read file contents"""
        pass


class IVersionControl(ABC):
    """Interface for version control operations"""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if version control is available"""
        pass

    @abstractmethod
    def commit(self, message: str) -> bool:
        """Commit changes"""
        pass

    @abstractmethod
    def rollback(self, commit_hash: str) -> bool:
        """Rollback to commit"""
        pass

    @abstractmethod
    def diff(self, commit_hash: Optional[str] = None) -> str:
        """Get diff"""
        pass


# ============================================================================
# IMPLEMENTATIONS (Single Responsibility Principle)
# ============================================================================

class JsonMetadataRepository(IMetadataRepository):
    """Handles JSON metadata file I/O"""

    def __init__(self, json_path: Path):
        self.json_path = json_path

    def exists(self) -> bool:
        return self.json_path.exists()

    def load(self) -> List['ScriptMetadata']:
        if not self.exists():
            return []

        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [ScriptMetadata.from_dict(item) for item in data]
        except json.JSONDecodeError:
            return []

    def save(self, metadata: List['ScriptMetadata'], message: Optional[str] = None) -> bool:
        # Convert to JSON format
        data = []
        for m in metadata:
            d = m.to_dict()
            data.append(d)

        # Validate JSON
        try:
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            json.loads(json_str)  # Validate
        except (TypeError, ValueError):
            return False

        # Write file
        try:
            with open(self.json_path, 'w', encoding='utf-8') as f:
                f.write(json_str)
            return True
        except Exception:
            return False


class LocalFileSystem(IFileSystem):
    """Handles local file system operations"""

    def __init__(self, scripts_dir: Path):
        self.scripts_dir = scripts_dir

    def get_script_files(self) -> List[Path]:
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
            except Exception:
                self._available = False

    def _run_git(self, args: List[str], check: bool = True) -> Optional[subprocess.CompletedProcess]:
        if not self._available:
            return None
        try:
            cmd = ['git', '-C', str(self.repo_path)] + args
            return subprocess.run(cmd, check=check, capture_output=True, text=True, timeout=30)
        except Exception:
            return None

    def is_available(self) -> bool:
        return self._available

    def commit(self, message: str) -> bool:
        if not self._available:
            return False
        result = self._run_git(['add', 'custom_scripts.json'], check=False)
        result = self._run_git(['commit', '-m', message], check=False)
        return result is not None and result.returncode == 0

    def rollback(self, commit_hash: str) -> bool:
        # Implementation here
        return False

    def diff(self, commit_hash: Optional[str] = None) -> str:
        if not self._available:
            return ""
        args = ['diff', '--color=always']
        if commit_hash:
            args.extend([f'{commit_hash}^..{commit_hash}'])
        args.extend(['--', 'custom_scripts.json'])
        result = self._run_git(args, check=False)
        return result.stdout if result else ""


class NoOpVersionControl(IVersionControl):
    """Null object pattern - no version control"""

    def is_available(self) -> bool:
        return False

    def commit(self, message: str) -> bool:
        return False

    def rollback(self, commit_hash: str) -> bool:
        return False

    def diff(self, commit_hash: Optional[str] = None) -> str:
        return ""


# ============================================================================
# VALIDATOR (Single Responsibility)
# ============================================================================

class MetadataValidator:
    """Validates metadata and files"""

    def __init__(self, repository: IMetadataRepository, filesystem: IFileSystem):
        self.repository = repository
        self.filesystem = filesystem

    def validate(self) -> Dict:
        """Validate and return issues"""
        metadata = self.repository.load()
        files = self.filesystem.get_script_files()

        issues = {
            'missing_files': [],
            'orphaned_files': [],
            'case_mismatches': []
        }

        # Check for missing files
        file_names_lower = {f.name.lower(): f.name for f in files}
        for m in metadata:
            if m.file.lower() not in file_names_lower:
                issues['missing_files'].append(m.file)
            elif m.file != file_names_lower[m.file.lower()]:
                issues['case_mismatches'].append((m.file, file_names_lower[m.file.lower()]))

        # Check for orphaned files
        metadata_files_lower = {m.file.lower() for m in metadata}
        for f in files:
            if f.name.lower() not in metadata_files_lower:
                issues['orphaned_files'].append(f.name)

        return issues


# ============================================================================
# NORMALIZER (Single Responsibility)
# ============================================================================

class MetadataNormalizer:
    """Normalizes metadata"""

    def __init__(self, filesystem: IFileSystem):
        self.filesystem = filesystem

    def normalize(self, metadata: List['ScriptMetadata'],
                  fix_case: bool = True, sort: bool = True) -> List['ScriptMetadata']:
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
                            file=actual_file,  # Fix case
                            description=m.description,
                            author=m.author,
                            tags=m.tags,
                            images=m.images,
                            base_color=m.base_color,
                            favicon=m.favicon
                        )

        if sort:
            normalized.sort(key=lambda x: x.name.lower())

        return normalized


# ============================================================================
# FACADE (Easy to Use)
# ============================================================================

@dataclass
class ScriptMetadata:
    """Script metadata model"""
    name: str
    file: str
    description: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[List[str]] = None
    images: Optional[List[Dict]] = None
    base_color: Optional[str] = None
    favicon: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'ScriptMetadata':
        field_map = {
            'baseColor': 'base_color',
        }
        converted = {}
        for key, value in data.items():
            snake_key = field_map.get(key, key)
            converted[snake_key] = value
        return cls(**converted)

    def to_dict(self) -> Dict:
        d = {
            'name': self.name,
            'file': self.file,
        }
        if self.description:
            d['description'] = self.description
        if self.author:
            d['author'] = self.author
        if self.tags:
            d['tags'] = self.tags
        if self.images:
            d['images'] = self.images
        if self.base_color:
            d['baseColor'] = self.base_color
        if self.favicon:
            d['favicon'] = self.favicon
        return d


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
                 version_control: IVersionControl):
        self.repository = repository
        self.filesystem = filesystem
        self.version_control = version_control
        self.validator = MetadataValidator(repository, filesystem)
        self.normalizer = MetadataNormalizer(filesystem)

    @classmethod
    def create(cls,
               scripts_dir: Optional[str] = None,
               use_git: bool = True) -> 'ScriptManager':
        """
        Factory method for easy creation with sensible defaults.

        Zero-config usage:
            manager = ScriptManager.create()

        Custom config:
            manager = ScriptManager.create(scripts_dir="/path", use_git=False)
        """
        # Auto-detect scripts directory
        if scripts_dir is None:
            scripts_dir = Path.home() / "Library/Containers/com.liuliu.draw-things/Data/Documents/Scripts"

        scripts_path = Path(scripts_dir)
        json_path = scripts_path / "custom_scripts.json"

        # Create dependencies
        repository = JsonMetadataRepository(json_path)
        filesystem = LocalFileSystem(scripts_path)

        # Version control (optional)
        if use_git:
            version_control = GitVersionControl(scripts_path)
        else:
            version_control = NoOpVersionControl()

        return cls(repository, filesystem, version_control)

    def list_scripts(self) -> List[ScriptMetadata]:
        """List all scripts"""
        return self.repository.load()

    def validate(self) -> Dict:
        """Validate scripts"""
        return self.validator.validate()

    def normalize(self, fix_case: bool = True, sort: bool = True) -> bool:
        """Normalize metadata"""
        metadata = self.repository.load()
        normalized = self.normalizer.normalize(metadata, fix_case, sort)

        if normalized != metadata:
            message = "Normalize metadata"
            if self.version_control.is_available():
                success = self.repository.save(normalized, message)
                if success:
                    self.version_control.commit(message)
                return success
            return self.repository.save(normalized, message)
        return True

    def show_diff(self, commit_hash: Optional[str] = None) -> str:
        """Show diff"""
        return self.version_control.diff(commit_hash)


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == '__main__':
    # Zero-config usage (easiest!)
    manager = ScriptManager.create()

    # Or with minimal config
    # manager = ScriptManager.create(use_git=False)
    # manager = ScriptManager.create(scripts_dir="/custom/path")

    # Use it
    scripts = manager.list_scripts()
    print(f"Found {len(scripts)} scripts")

    issues = manager.validate()
    print(f"Validation issues: {len(issues.get('orphaned_files', []))} orphaned files")

    # Normalize
    manager.normalize()

    # Show diff
    diff = manager.show_diff()
    if diff:
        print(diff)

