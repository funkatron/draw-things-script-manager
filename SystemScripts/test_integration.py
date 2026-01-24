#!/usr/bin/env python3
"""
Integration tests for Draw Things Script Manager

These tests verify end-to-end functionality with realistic scenarios.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
import script_manager


class TestIntegration(unittest.TestCase):
    """Integration tests with realistic scenarios"""

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

    def test_full_workflow(self):
        """Test a complete workflow: validate -> sync -> validate again"""
        # Create some script files
        (self.scripts_dir / "script1.js").write_text("//@api-1.0\n// author: Author One")
        (self.scripts_dir / "script2.js").write_text("//@api-1.0\n// author: Author Two")

        # Initial state: no metadata
        issues = self.manager.validate()
        self.assertEqual(len(issues['orphaned_files']), 2)

        # Sync all orphaned files
        self.manager.sync_metadata(dry_run=False)

        # After sync: should have metadata
        metadata = self.manager.load_metadata()
        self.assertEqual(len(metadata), 2)

        # Validate again: should have no orphaned files
        issues = self.manager.validate()
        self.assertEqual(len(issues['orphaned_files']), 0)

    def test_case_insensitive_matching(self):
        """Test that case differences are handled correctly"""
        # Create file with uppercase
        (self.scripts_dir / "TestScript.js").write_text("// test")

        # Add metadata with lowercase
        test_data = [{"name": "Test", "file": "testscript.js"}]
        with open(self.custom_scripts_json, 'w') as f:
            json.dump(test_data, f)

        # Should detect case mismatch, not missing file
        issues = self.manager.validate()
        self.assertEqual(len(issues['missing_files']), 0)
        self.assertEqual(len(issues['case_mismatches']), 1)

    def test_sync_with_existing_metadata(self):
        """Test syncing when metadata already exists"""
        # Create existing metadata
        test_data = [{"name": "Existing", "file": "existing.js"}]
        with open(self.custom_scripts_json, 'w') as f:
            json.dump(test_data, f)

        # Create existing file
        (self.scripts_dir / "existing.js").write_text("// existing")

        # Create new orphaned file
        (self.scripts_dir / "new.js").write_text("// new")

        # Sync should only add new file
        self.manager.sync_metadata(dry_run=False)

        metadata = self.manager.load_metadata()
        file_names = {m.file for m in metadata}
        self.assertIn("existing.js", file_names)
        self.assertIn("new.js", file_names)
        self.assertEqual(len(metadata), 2)

    def test_multiple_operations_idempotent(self):
        """Test that running operations multiple times is safe"""
        (self.scripts_dir / "test.js").write_text("// test")

        # Run sync multiple times
        for i in range(5):
            self.manager.sync_metadata(dry_run=False)

        # Should still only have one entry
        metadata = self.manager.load_metadata()
        self.assertEqual(len(metadata), 1)

        # Run validate multiple times
        for i in range(5):
            issues = self.manager.validate()
            self.assertEqual(len(issues['orphaned_files']), 0)

    def test_selective_sync_workflow(self):
        """Test syncing only specific files"""
        (self.scripts_dir / "file1.js").write_text("// file1")
        (self.scripts_dir / "file2.js").write_text("// file2")
        (self.scripts_dir / "file3.js").write_text("// file3")

        # Sync only file1 and file3
        self.manager.sync_metadata(
            dry_run=False,
            files_to_manage=["file1.js", "file3.js"]
        )

        metadata = self.manager.load_metadata()
        file_names = {m.file for m in metadata}

        self.assertIn("file1.js", file_names)
        self.assertNotIn("file2.js", file_names)
        self.assertIn("file3.js", file_names)

        # file2 should still be orphaned
        issues = self.manager.validate()
        self.assertIn("file2.js", issues['orphaned_files'])


if __name__ == '__main__':
    unittest.main(verbosity=2)

