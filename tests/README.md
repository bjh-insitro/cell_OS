# Test Suite

This directory contains the test suite for Cell OS.

## Structure

- **unit/**: Unit tests that test individual components in isolation. These tests should be fast and mock external dependencies (like databases).
- **integration/**: Integration tests that test how components work together or with external systems (like SQLite).
- **e2e/**: End-to-end tests that test the full application flow.

## Running Tests

To run all tests:
```bash
pytest
```

To run only unit tests:
```bash
pytest tests/unit
```

To run only integration tests:
```bash
pytest tests/integration
```
