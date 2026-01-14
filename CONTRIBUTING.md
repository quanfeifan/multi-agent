# Contributing to Multi-Agent Framework

Thank you for your interest in contributing to the Multi-Agent Framework! This document provides guidelines and instructions for contributors.

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other community members

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Poetry or pip for dependency management
- Git

### Setting Up the Development Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/multi-agent.git
cd multi-agent

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check src/
black src/

# Run type checking
mypy src/
```

## Project Structure

```
multi-agent/
├── src/multi_agent/
│   ├── agent/          # Agent implementations
│   ├── cli/            # Command-line interface
│   ├── config/         # Configuration loading
│   ├── execution/      # Task execution engines
│   ├── models/         # Data models
│   ├── state/          # State management
│   ├── tools/          # MCP tool integration
│   ├── tracing/        # Tracing and metrics
│   └── utils/          # Utilities
├── tests/              # Test files
├── docs/               # Documentation
├── examples/           # Example configurations
└── specs/              # Feature specifications
```

## Making Changes

### Branching Strategy

1. Create a branch from `master`
2. Name your branch descriptively (e.g., `feature/add-new-pattern`)
3. Make your changes
4. Write tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

### Code Style

We use:
- **Black** for code formatting
- **Ruff** for linting
- **mypy** for type checking
- **pytest** for testing

Run all checks before submitting:

```bash
black src/
ruff check --fix src/
mypy src/
pytest
```

### Documentation

- Add docstrings to all public functions and classes
- Use Google-style docstrings
- Update API reference for new APIs
- Add examples for new features

### Testing

- Write unit tests for all new functionality
- Write integration tests for user-facing features
- Aim for >80% code coverage
- Use descriptive test names

## Pull Request Process

1. Update the CHANGELOG.md
2. Ensure all tests pass
3. Update documentation if needed
4. Submit your PR with a clear description
5. Respond to review feedback

## Feature Requests

For large features, please:
1. Open an issue to discuss first
2. Get consensus on the approach
3. Create a specification in `specs/`
4. Implement following the specification

## Questions?

Feel free to open an issue for questions or discussions.
