#!/usr/bin/env python3
"""
Test suite for Draw Things Script Manager

Run with: python3 -m pytest test_script_manager.py -v
Or: python3 test_script_manager.py
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the script manager
import script_manager


class TestScriptManager(unittest.TestCase):
    """Test cases for ScriptManager"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.scripts_dir = self.test_dir / "Scripts"
        self.scripts_dir.mkdir()
        self.custom_scripts_json = self.scripts_dir / "custom_scripts.json"

        # Create manager with test directory
        self.manager = script_manager.ScriptManager.create(
            scripts_dir=str(self.scripts_dir),
            use_git=False  # Disable git for tests
        )

    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_empty_metadata(self):
        """Test loading metadata from non-existent file"""
        metadata = self.manager.load_metadata()
        self.assertEqual(metadata, [])

    def test_load_valid_metadata(self):
        """Test loading valid metadata"""
        test_data = [
            {
                "name": "Test Script",
                "file": "test.js",
                "author": "Test Author",
                "description": "Test description"
            }
        ]
        with open(self.custom_scripts_json, 'w') as f:
            json.dump(test_data, f)

        metadata = self.manager.load_metadata()
        self.assertEqual(len(metadata), 1)
        self.assertEqual(metadata[0].name, "Test Script")
        self.assertEqual(metadata[0].file, "test.js")

    def test_load_invalid_json(self):
        """Test loading invalid JSON"""
        with open(self.custom_scripts_json, 'w') as f:
            f.write("invalid json{")

        metadata = self.manager.load_metadata()
        self.assertEqual(metadata, [])

    def test_get_script_files(self):
        """Test getting script files"""
        # Create some test files
        (self.scripts_dir / "script1.js").write_text("// test")
        (self.scripts_dir / "script2.js").write_text("// test")
        (self.scripts_dir / "not_a_script.txt").write_text("test")

        files = self.manager.get_script_files()
        file_names = {f.name for f in files}

        self.assertIn("script1.js", file_names)
        self.assertIn("script2.js", file_names)
        self.assertNotIn("not_a_script.txt", file_names)
        self.assertNotIn("custom_scripts.json", file_names)

    def test_extract_metadata_from_script(self):
        """Test extracting metadata from script comments"""
        script_content = """//@api-1.0
// author: Test Author
// description: Test description
// version: 1.0

const test = "test";
"""
        script_path = self.scripts_dir / "test.js"
        script_path.write_text(script_content)

        metadata = self.manager.extract_metadata_from_script(script_path)
        self.assertEqual(metadata.get('author'), 'Test Author')
        self.assertEqual(metadata.get('description'), 'Test description')

    def test_validate_no_issues(self):
        """Test validation with no issues"""
        # Create matching file and metadata
        (self.scripts_dir / "test.js").write_text("// test")
        test_data = [{"name": "Test", "file": "test.js"}]
        with open(self.custom_scripts_json, 'w') as f:
            json.dump(test_data, f)

        issues = self.manager.validate()
        self.assertFalse(issues['invalid_json'])
        self.assertEqual(len(issues['missing_files']), 0)
        self.assertEqual(len(issues['orphaned_files']), 0)

    def test_validate_missing_file(self):
        """Test validation with missing file"""
        test_data = [{"name": "Test", "file": "missing.js"}]
        with open(self.custom_scripts_json, 'w') as f:
            json.dump(test_data, f)

        issues = self.manager.validate()
        self.assertIn("missing.js", issues['missing_files'])

    def test_validate_orphaned_file(self):
        """Test validation with orphaned file"""
        (self.scripts_dir / "orphaned.js").write_text("// test")
        test_data = []
        with open(self.custom_scripts_json, 'w') as f:
            json.dump(test_data, f)

        issues = self.manager.validate()
        self.assertIn("orphaned.js", issues['orphaned_files'])

    def test_validate_case_mismatch(self):
        """Test validation with case mismatch"""
        (self.scripts_dir / "Test.js").write_text("// test")
        test_data = [{"name": "Test", "file": "test.js"}]
        with open(self.custom_scripts_json, 'w') as f:
            json.dump(test_data, f)

        issues = self.manager.validate()
        self.assertEqual(len(issues['case_mismatches']), 1)
        self.assertEqual(issues['case_mismatches'][0][0], "test.js")
        self.assertEqual(issues['case_mismatches'][0][1], "Test.js")

    def test_validate_duplicate_entries(self):
        """Test validation with duplicate entries"""
        (self.scripts_dir / "test.js").write_text("// test")
        test_data = [
            {"name": "Test 1", "file": "test.js"},
            {"name": "Test 2", "file": "test.js"}
        ]
        with open(self.custom_scripts_json, 'w') as f:
            json.dump(test_data, f)

        issues = self.manager.validate()
        self.assertIn("test.js", issues['duplicate_files'])

    def test_sync_metadata_dry_run(self):
        """Test sync metadata in dry run mode"""
        (self.scripts_dir / "orphaned.js").write_text("// test\n// author: Test Author")
        test_data = []
        with open(self.custom_scripts_json, 'w') as f:
            json.dump(test_data, f)

        # Should not modify file in dry run
        self.manager.sync_metadata(dry_run=True)

        # File should still be empty
        with open(self.custom_scripts_json, 'r') as f:
            data = json.load(f)
        self.assertEqual(len(data), 0)

    def test_sync_metadata_idempotent(self):
        """Test that sync is idempotent"""
        (self.scripts_dir / "test.js").write_text("// test\n// author: Test Author")

        # First sync
        self.manager.sync_metadata(dry_run=False)

        # Second sync should not add duplicate
        self.manager.sync_metadata(dry_run=False)

        # Should only have one entry
        with open(self.custom_scripts_json, 'r') as f:
            data = json.load(f)

        test_entries = [e for e in data if e['file'] == 'test.js']
        self.assertEqual(len(test_entries), 1)

    def test_sync_metadata_selective(self):
        """Test syncing only specific files"""
        (self.scripts_dir / "file1.js").write_text("// test")
        (self.scripts_dir / "file2.js").write_text("// test")

        # Only sync file1
        self.manager.sync_metadata(dry_run=False, files_to_manage=["file1.js"])

        with open(self.custom_scripts_json, 'r') as f:
            data = json.load(f)

        file_names = {e['file'] for e in data}
        self.assertIn("file1.js", file_names)
        self.assertNotIn("file2.js", file_names)

    def test_save_metadata_validates_json(self):
        """Test that save_metadata validates JSON"""
        metadata_list = [
            script_manager.ScriptMetadata(
                name="Test",
                file="test.js",
                description="Test"
            )
        ]

        # Should succeed
        result = self.manager._save_metadata(metadata_list, commit_message=None)
        self.assertTrue(result)

        # Verify file was written
        self.assertTrue(self.custom_scripts_json.exists())
        with open(self.custom_scripts_json, 'r') as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)

    def test_save_metadata_creates_backup(self):
        """Test that save_metadata creates backup"""
        # Create initial file
        initial_data = [{"name": "Initial", "file": "initial.js"}]
        with open(self.custom_scripts_json, 'w') as f:
            json.dump(initial_data, f)

        metadata_list = [
            script_manager.ScriptMetadata(
                name="Test",
                file="test.js"
            )
        ]

        # Save should create backup
        backup_path = self.manager._backup_file(self.custom_scripts_json)
        self.assertIsNotNone(backup_path)
        self.assertTrue(backup_path.exists())

        # Clean up
        if backup_path.exists():
            backup_path.unlink()

    def test_script_metadata_from_dict(self):
        """Test ScriptMetadata.from_dict with camelCase conversion"""
        data = {
            "name": "Test",
            "file": "test.js",
            "baseColor": "#FF0000",
            "filePath": "/path/to/file",
            "isSampleDuplicate": True
        }

        metadata = script_manager.ScriptMetadata.from_dict(data)
        self.assertEqual(metadata.name, "Test")
        self.assertEqual(metadata.base_color, "#FF0000")
        self.assertEqual(metadata.file_path, "/path/to/file")
        self.assertEqual(metadata.is_sample_duplicate, True)


class TestIdempotency(unittest.TestCase):
    """Test idempotency of operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.scripts_dir = self.test_dir / "Scripts"
        self.scripts_dir.mkdir()
        self.custom_scripts_json = self.scripts_dir / "custom_scripts.json"
        self.manager = script_manager.ScriptManager.create(
            scripts_dir=str(self.scripts_dir),
            use_git=False
        )

    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_multiple_syncs_same_result(self):
        """Test that multiple syncs produce the same result"""
        (self.scripts_dir / "test.js").write_text("// test")

        # Run sync multiple times
        for _ in range(3):
            self.manager.sync_metadata(dry_run=False)

        # Should only have one entry
        with open(self.custom_scripts_json, 'r') as f:
            data = json.load(f)

        self.assertEqual(len(data), 1)
        test_entries = [e for e in data if e['file'] == 'test.js']
        self.assertEqual(len(test_entries), 1)

    def test_validate_idempotent(self):
        """Test that validate is idempotent"""
        (self.scripts_dir / "test.js").write_text("// test")
        test_data = [{"name": "Test", "file": "test.js"}]
        with open(self.custom_scripts_json, 'w') as f:
            json.dump(test_data, f)

        # Run validate multiple times
        results = []
        for _ in range(3):
            issues = self.manager.validate()
            results.append(issues)

        # All results should be identical
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])


class TestSafety(unittest.TestCase):
    """Test safety features - ensure we never modify script files"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.scripts_dir = self.test_dir / "Scripts"
        self.scripts_dir.mkdir()
        self.custom_scripts_json = self.scripts_dir / "custom_scripts.json"
        self.manager = script_manager.ScriptManager.create(
            scripts_dir=str(self.scripts_dir),
            use_git=False
        )

    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sync_never_modifies_script_files(self):
        """Test that sync never modifies script files"""
        script_path = self.scripts_dir / "test.js"
        original_content = "// original content\nconst test = 'test';"
        script_path.write_text(original_content)

        # Run sync
        self.manager.sync_metadata(dry_run=False)

        # Script file should be unchanged
        self.assertEqual(script_path.read_text(), original_content)

    def test_sync_only_modifies_json(self):
        """Test that sync only modifies custom_scripts.json"""
        script_path = self.scripts_dir / "test.js"
        script_path.write_text("// test")

        # Get initial JSON state
        initial_json_exists = self.custom_scripts_json.exists()

        # Run sync
        self.manager.sync_metadata(dry_run=False)

        # JSON should be modified
        self.assertTrue(self.custom_scripts_json.exists())

        # Script file should be untouched
        self.assertTrue(script_path.exists())
        self.assertEqual(script_path.read_text(), "// test")


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestScriptManager))
    suite.addTests(loader.loadTestsFromTestCase(TestIdempotency))
    suite.addTests(loader.loadTestsFromTestCase(TestSafety))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)

