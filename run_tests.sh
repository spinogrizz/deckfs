#!/bin/bash

# Simple test runner script for stream-deck-fs

echo "=== Stream Deck FS Test Runner ==="
echo

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Installing test dependencies..."
    pip install pytest pytest-cov pytest-mock
    echo
fi

# Run tests with proper Python path
echo "🧪 Running tests..."
PYTHONPATH=. python -m pytest tests/ -v

echo
echo "✅ Tests completed!"
echo
echo "Other available test commands:"
echo "  PYTHONPATH=. python -m pytest tests/ -v                    # Basic test run"
echo "  PYTHONPATH=. python -m pytest tests/ -vv -s                # Verbose with output"
echo "  PYTHONPATH=. python -m pytest tests/ --cov=src             # With coverage"
echo "  PYTHONPATH=. python -m pytest tests/test_debouncer.py -v   # Single file"