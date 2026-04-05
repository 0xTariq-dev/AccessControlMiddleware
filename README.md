# Access Control Middleware

**Production-grade, open-source middleware for multi-vendor access control devices.**

Integrates with external authentication systems, processes real-time security events, manages multiple devices simultaneously, and provides a comprehensive REST API with enterprise-grade audit logging.

## Features

- 🔐 **Multi-Vendor Support**: Native integration with Hikvision ISAPI and extensible architecture for other vendors
- 📡 **Real-Time Event Processing**: Stream security events from devices with reliable message queuing
- 🔑 **Flexible Authentication**: Supports external identity providers and OAuth 2.0
- 📊 **Enterprise Audit Logging**: Complete audit trails for compliance and security investigations
- 🐳 **Container-Ready**: Pre-configured for Docker and Kubernetes deployments
- 🔒 **Secrets Management**: HashiCorp Vault integration for secure credential handling
- 🧪 **Comprehensive Testing**: Unit tests, integration tests, and mocking support
- 📈 **Scalable Architecture**: Async/await with FastAPI, connection pooling, and horizontal scaling ready

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for containerized deployment)
- PostgreSQL 14+ (or SQLite for development)
- Optional: HashiCorp Vault for secrets management

### Installation

#### Option 1: Local Development (venv)

```bash
# Clone the repository
git clone https://github.com/yourusername/access-control-middleware.git
cd AccessControlMiddleware

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file from template
cp .env.example .env

# Run migrations (if using PostgreSQL)
python -m alembic upgrade head

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Option 2: Docker Compose (Recommended)

```bash
# Clone and navigate to project
git clone https://github.com/yourusername/access-control-middleware.git
cd AccessControlMiddleware

# Create environment file
cp .env.example .env

# Start all services (FastAPI, PostgreSQL, Redis, Vault)
docker-compose up -d

# Verify services are running
docker-compose ps

# View logs
docker-compose logs -f middleware
```

### Configuration

Create a `.env` file in the project root using the provided template:

```bash
cp .env.example .env
```

Key environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@localhost/acm_db` |
| `DEVICE_MODE` | Device integration mode | `mock` (development), `isapi` (production) |
| `VAULT_URL` | HashiCorp Vault address | `http://localhost:8200` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `LOG_LEVEL` | Application logging level | `INFO`, `DEBUG`, `ERROR` |

See [.env.example](.env.example) for complete configuration options.

## Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                 Access Control Middleware                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐    ┌────────────┐   │
│  │ REST API     │      │ Event Stream │    │ Database   │   │
│  │ (FastAPI)    │      │ (Redis Queue)│    │(PostgreSQL)│   │
│  └──────────────┘      └──────────────┘    └────────────┘   │
│          │                     │                    │        │
│          └─────────────────────┼────────────────────┘        │
│                                │                             │
│                    ┌───────────────────────┐                 │
│                    │  Device Integrations  │                 │
│                    │  - Hikvision ISAPI    │                 │
│                    │  - Other Vendors      │                 │
│                    │  (Mock for testing)   │                 │
│                    └───────────────────────┘                 │
│                                │                             │
│                         ┌──────────────┐                    │
│                         │ Vault Secrets│                    │
│                         │ Management   │                    │
│                         └──────────────┘                     │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

- **REST API** (`app/routers/`): Device control, event querying, status endpoints
- **Event Processing** (`app/models.py`, `app/schemas.py`): Standardized event structures
- **Device Drivers** (`app/devices/`): Vendor-specific ISAPI implementations
- **Database** (`migrations/`): PostgreSQL-backed persistent storage
- **Authentication** (`app/crypto.py`, `app/vault_helper.py`): Encryption and credential management

## API Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

Example: Turn off a device relay

```bash
curl -X POST http://localhost:8000/api/v1/devices/{device_id}/actions/unlock \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"action": "unlock", "duration": 5}'
```

## Deployment

### Production Deployment with Systemd

Copy the systemd service file to your system:

```bash
sudo cp deploy/services/access-control.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable access-control.service
sudo systemctl start access-control.service
```

View logs:

```bash
sudo journalctl -u access-control.service -f
```

### Kubernetes Deployment

Ready for Kubernetes - see `deploy/` directory for Helm-ready configurations.

### Environment-Specific Configs

- **Development**: Use `DEVICE_MODE=mock` and SQLite
- **Testing**: Use `DEVICE_MODE=mock` and PostgreSQL with test fixtures
- **Production**: Use `DEVICE_MODE=isapi` with Vault, Redis, and PostgreSQL

## Development

### Project Structure

```
AccessControlMiddleware/
├── app/                      # Main application code
│   ├── __init__.py
│   ├── main.py              # FastAPI app initialization
│   ├── config.py            # Configuration management
│   ├── crypto.py            # Encryption utilities
│   ├── database.py          # Database connections
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── vault_helper.py      # Vault integration
│   ├── devices/             # Device vendor implementations
│   │   └── __init__.py
│   └── routers/             # API endpoint groups
│       └── __init__.py
├── deploy/                  # Deployment configs
│   ├── services/            # Systemd service files
│   ├── nginx/               # Reverse proxy configs
│   └── vault/               # Secrets management configs
├── migrations/              # Database migrations
│   └── 001_initial_schema.py
├── tests/                   # Test suite
│   └── __init__.py
├── docs/                    # Documentation
├── docker-compose.yml       # Local development setup
├── Dockerfile               # Container image
├── requirements.txt         # Python dependencies
├── pytest.ini              # Testing configuration
├── .env.example            # Environment template
└── README.md               # This file
```

### Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_devices.py -v
```

### Adding a New Device Vendor

1. Create a new driver in `app/devices/vendors/my_vendor.py`
2. Implement the `DeviceDriver` base class interface
3. Add integration tests in `tests/test_devices.py`
4. Update device initialization in `app/devices/__init__.py`
5. Document in `docs/VENDORS.md`

See [docs/VENDOR_INTEGRATION.md](docs/VENDOR_INTEGRATION.md) for detailed guidelines.

### Code Quality

```bash
# Format code with Black
black app/ tests/

# Type checking
mypy app/

# Linting
pylint app/

# Security scanning
bandit -r app/
```

## Security Considerations

- ✅ All credentials stored in HashiCorp Vault (not in .env for production)
- ✅ Database passwords encrypted with industry standards
- ✅ HTTPS enforced via Nginx reverse proxy
- ✅ Rate limiting on sensitive endpoints
- ✅ Complete audit trail of all device access
- ✅ Input validation on all API endpoints
- ✅ SQL injection protection via SQLAlchemy ORM

## Troubleshooting

### Connection Refused to Device

```
Error: ConnectionError: Unable to connect to device at 192.168.1.100
```

**Solution**: Verify device IP, network connectivity, and that device credentials are correct in Vault.

### Database Migration Failures

```
Error: alembic.util.exc.CommandError: Can't locate revision ...
```

**Solution**: 
```bash
# Reset migrations (development only)
rm -rf migrations/versions/*
python -m alembic stamp head
```

### Vault Token Expiration

The middleware monitors Vault token expiration. **Action required**: Refresh your Vault token or update credentials if tokens expire.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Code style guidelines (PEP 8, type hints required)
- Testing requirements (>80% coverage)
- Commit message conventions
- Pull request process
- Issue reporting guidelines

## License

This project is licensed under the **MIT License** - see [LICENSE](LICENSE) for details.

## Support & Community

- 📚 **Documentation**: See [docs/](docs/) directory
- 🐛 **Issue Tracker**: GitHub Issues
- 💬 **Discussions**: GitHub Discussions
- 📧 **Email**: See [CONTRIBUTING.md](CONTRIBUTING.md)

## Roadmap

- [ ] LDAP/Active Directory authentication provider
- [ ] Biometric device support (fingerprint readers)
- [ ] SMS/Email notifications for access events
- [ ] Advanced analytics dashboard
- [ ] Multi-tenancy support
- [ ] GraphQL API option

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - ORM
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [Docker](https://www.docker.com/) - Containerization

---

**Version**: 1.0.0  
**Last Updated**: April 5, 2026  
**Maintainer**: Tariq Mohammed
