# Contributing to Access Control Middleware

Thank you for your interest in contributing to the Access Control Middleware project! This document provides guidelines and instructions for contributing.

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be respectful and professional in all interactions.

## Getting Started

### Prerequisites

- Python 3.12+
- Git
- virtualenv or venv
- Docker & Docker Compose (for integration testing)
- PostgreSQL 14+ (optional, for testing with production DB)

### Development Setup

1. **Fork the repository** on GitHub

2. **Clone your fork**

```bash
git clone https://github.com/yourusername/access-control-middleware.git
cd AccessControlMiddleware
```

3. **Create a feature branch**

```bash
git checkout -b feature/your-feature-name
# or for bug fixes:
git checkout -b fix/your-bug-fix-name
```

4. **Set up development environment**

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt

# Install pre-commit hooks (for code quality)
pre-commit install
```

5. **Create .env file**

```bash
cp .env.example .env
# Edit .env with your local settings (use defaults for mock mode)
```

## Development Workflow

### Code Style

We follow **PEP 8** with the following tools:

- **Black**: Code formatter (88-character line length)
- **isort**: Import sorting
- **Pylint**: Linting
- **MyPy**: Static type checking (type hints required)

**Before committing:**

```bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Check types
mypy app/

# Lint
pylint app/
```

Or use the pre-commit hook:

```bash
pre-commit run --all-files
```

### Type Hints

**All new code must include type hints.** Example:

```python
from typing import Optional, List
from app.models import Device

def get_devices_by_location(
    location_id: int,
    include_offline: bool = False
) -> List[Device]:
    """
    Retrieve devices by location.
    
    Args:
        location_id: Location database ID
        include_offline: Include offline devices in results
        
    Returns:
        List of Device objects matching the location
    """
    # implementation
```

### Docstrings

Use Google-style docstrings for all public functions and classes:

```python
def authenticate_device(
    device_id: str,
    username: str,
    password: str
) -> Dict[str, Any]:
    """
    Authenticate with a physical access control device.
    
    Establishes a session with the target device using credentials
    from HashiCorp Vault. Credentials are never stored locally.
    
    Args:
        device_id: Unique device identifier
        username: ISAPI username (typically "admin")
        password: ISAPI password (encrypted in Vault)
        
    Returns:
        Authentication response containing session token and metadata
        
    Raises:
        DeviceConnectionError: If unable to reach the device
        AuthenticationError: If credentials are invalid
        
    Example:
        >>> auth = authenticate_device("device-001", "admin", "secret")
        >>> auth["session_id"]
        "abc123xyz..."
    """
    pass
```

### Testing Requirements

**All new features must include tests** with minimum **80% code coverage**.

```bash
# Run tests with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_devices.py -v

# Run tests matching pattern
pytest -k "test_device_unlock" -v
```

**Test structure:**

```
tests/
├── test_api.py
├── test_devices.py
├── test_database.py
├── conftest.py  # Shared fixtures
└── fixtures/
    ├── devices.json
    └── credentials.json
```

**Example test:**

```python
import pytest
from app.devices import DeviceManager
from app.schemas import Device

@pytest.fixture
def device_manager():
    return DeviceManager(mode="mock")

def test_unlock_device(device_manager):
    """Test unlocking a device."""
    device_id = "test-device-001"
    
    # Act
    result = device_manager.unlock(device_id, duration_seconds=5)
    
    # Assert
    assert result.is_success
    assert result.device_id == device_id
```

### Commit Messages

Follow **Conventional Commits** format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (formatting)
- `refactor`: Code refactoring (no functionality change)
- `perf`: Performance improvement
- `test`: Adding/updating tests
- `chore`: Build, dependencies, etc.
- `ci`: CI/CD configuration

**Examples:**

```
feat(devices): add support for biometric readers

- Implement BiometricDevice class extending DeviceDriver
- Add parsing for fingerprint event types
- Update schemas to support biometric data

Closes #123
```

```
fix(api): handle device timeout gracefully

Previously failed when device didn't respond in 30s.
Now returns 504 Gateway Timeout with retry suggestion.

Fixes #456
```

```
docs: update device integration guide

Add PostgreSQL setup and troubleshooting section.
```

### Pull Request Process

1. **Keep PRs focused** - One feature or fix per PR
2. **Update documentation** if adding new features
3. **Add tests** - Minimum 80% coverage
4. **Run quality checks** before submitting

```bash
# Pre-submission checklist
pytest --cov=app
black app/ tests/
mypy app/
pylint app/
```

5. **Push to your fork** and **create a Pull Request** to `main` branch

6. **PR Description template:**

```markdown
## Description
Brief description of what this PR does.

## Motivation
Why is this change needed?

## Testing
How was this tested? Include steps to reproduce.

## Screenshots (if applicable)
Add before/after screenshots for UI changes.

## Breaking Changes
- List any breaking API changes
- Document migration path for users

## Checklist
- [ ] Tests pass locally (`pytest`)
- [ ] Code follows style guidelines (Black, isort, MyPy)
- [ ] Documentation updated
- [ ] New dependencies added to requirements.txt
- [ ] No hardcoded credentials or secrets
```

7. **Address review comments** - Be open to feedback
8. **Maintainers will merge** once approved

## Adding Support for a New Device Vendor

1. **Research the device API** - Understand protocol/authentication
2. **Create implementation** in `app/devices/vendors/vendor_name.py`
3. **Extend base class:**

```python
from app.devices.base import DeviceDriver
from typing import Dict, Any

class VendorNameDevice(DeviceDriver):
    """Support for VendorName access control devices."""
    
    async def unlock(self, duration_seconds: int = 5) -> Dict[str, Any]:
        """Unlock the device."""
        pass
    
    async def lock(self) -> Dict[str, Any]:
        """Lock the device."""
        pass
    
    async def get_status(self) -> Dict[str, Any]:
        """Get device status."""
        pass
```

4. **Add integration tests** in `tests/test_devices.py`
5. **Document in** `docs/SUPPORTED_DEVICES.md`
6. **Update** `app/devices/__init__.py` device registry

## Security Considerations

- **Never commit secrets** - use .env and Vault
- **No hardcoded paths** - use environment variables
- **Input validation** - always validate user input
- **SQL injection prevention** - use ORM (never raw SQL)
- **Password handling** - never log passwords
- **API keys** - rotate regularly, store in Vault

### Vulnerability Reporting

Found a security issue? Please email [maintainer@example.com](mailto:maintainer@example.com) instead of creating a public issue. Include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if you have one)

## Documentation

Update documentation when adding new features:

- **README.md** - User-facing installation/quick start
- **docs/ARCHITECTURE.md** - System design decisions
- **docs/API.md** - Endpoint documentation
- **Docstrings** - Code-level documentation
- **comments** - Explain "why", not "what"

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Getting Help

- 📚 **Documentation**: [docs/](../docs/) directory
- 💬 **Discussions**: GitHub Discussions tab
- 📧 **Email**: See [CONTRIBUTING.md](CONTRIBUTING.md)
- 🐛 **Issues**: Check existing issues first

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [Pydantic](https://docs.pydantic.dev/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

Thank you for contributing! 🎉
