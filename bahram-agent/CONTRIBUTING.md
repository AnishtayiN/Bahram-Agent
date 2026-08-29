# Contributing to Bahram Agent

Thank you for your interest in contributing to Bahram Agent! This document provides guidelines and instructions for contributing.

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Git
- pip or poetry

### Installation

```bash
# Clone the repository
git clone https://github.com/AnishtayiN/Bahram-Agent.git
cd Bahram-Agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

## 📝 How to Contribute

### 1. Fork the Repository
```bash
# Fork on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/Bahram-Agent.git
cd Bahram-Agent
```

### 2. Create a Branch
```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Or a bug fix branch
git checkout -b fix/your-bug-fix
```

### 3. Make Your Changes
- Follow the code style (PEP 8)
- Add tests for new features
- Update documentation if needed

### 4. Run Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=bahram

# Run specific test
pytest tests/test_specific.py
```

### 5. Commit Your Changes
```bash
# Stage changes
git add .

# Commit with a descriptive message
git commit -m "feat: add new feature description"

# Or for bug fixes
git commit -m "fix: fix bug description"
```

### 6. Push and Create PR
```bash
# Push to your fork
git push origin feature/your-feature-name

# Create a Pull Request on GitHub
```

## 📋 Commit Message Convention

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Examples:
```
feat: add support for new LLM provider
fix: resolve memory leak in conversation handler
docs: update API documentation
test: add unit tests for task planner
```

## 🧪 Testing Guidelines

### Writing Tests
```python
# tests/test_example.py
import pytest
from bahram.core.example import ExampleClass

class TestExampleClass:
    """Tests for ExampleClass."""
    
    def test_initialization(self):
        """Test class initialization."""
        obj = ExampleClass()
        assert obj is not None
    
    def test_method(self):
        """Test class method."""
        obj = ExampleClass()
        result = obj.method()
        assert result == expected_value
```

### Running Tests
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_example.py

# Run tests matching a pattern
pytest -k "test_method"

# Run with coverage report
pytest --cov=bahram --cov-report=html
```

## 📚 Code Style

### Python Style Guide
- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints
- Maximum line length: 100 characters
- Use meaningful variable names

### Example
```python
from typing import Optional, List

def process_data(
    data: List[str],
    uppercase: bool = False,
    max_length: Optional[int] = None,
) -> List[str]:
    """Process input data.
    
    Args:
        data: List of strings to process
        uppercase: Convert to uppercase if True
        max_length: Maximum length of output strings
        
    Returns:
        Processed list of strings
    """
    result = []
    for item in data:
        if uppercase:
            item = item.upper()
        if max_length:
            item = item[:max_length]
        result.append(item)
    return result
```

## 🐛 Reporting Bugs

### Bug Report Template
```markdown
**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Environment:**
- OS: [e.g., Windows 10]
- Python Version: [e.g., 3.10]
- Bahram Agent Version: [e.g., 1.0.0]
```

## 💡 Feature Requests

### Feature Request Template
```markdown
**Is your feature request related to a problem?**
A clear and concise description of what the problem is.

**Describe the solution you'd like**
A clear and concise description of what you want to happen.

**Describe alternatives you've considered**
A clear and concise description of any alternative solutions or features you've considered.

**Additional context**
Add any other context or screenshots about the feature request here.
```

## 📞 Questions?

If you have questions, feel free to:
- Open an issue
- Start a discussion on GitHub
- Contact the maintainers

## 🙏 Thank You!

Thank you for contributing to Bahram Agent! Your help is appreciated.
