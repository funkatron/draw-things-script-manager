#!/bin/bash
# Test runner for script manager

set -e

echo "Running Draw Things Script Manager Test Suite"
echo "=============================================="
echo ""

# Run unit tests
echo "Running unit tests..."
python3 test_script_manager.py
echo ""

# Run integration tests
echo "Running integration tests..."
python3 test_integration.py
echo ""

echo "=============================================="
echo "All tests passed! ✓"

