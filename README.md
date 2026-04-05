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

- Python 3.12+
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

# Run migrations
python -m peewee_migrate create init
python -m peewee_migrate migrate

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
┌──────────────────────────────────────────────────────────────────┐
│                    Access Control Middleware                     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    Nginx Reverse Proxy                   │    │
│  └────────┬────────────────────────┬────────────────────────┘    │
│           │                        │                            │
│  ┌────────▼────────┐    ┌──────────▼───────┐    ┌────────────┐   │
│  │ REST API Loop   │    │ Event Stream     │    │ Distributed│   │
│  │ (FastAPI)       │    │ Processor        │    │ Locking    │  │
│  │                 │    │ (FastAPI Tasks)  │    │ (Redis)    │  │
│  └────────┬────────┘    └──────────┬───────┘    └────────────┤  │
│           │                       │                    ▲       │
│  ┌────────▼───────────────────────▼────────┐         │       │
│  │         Peewee ORM Layer                 │         │       │
│  │  - Models, Schemas, Relationships        │         │       │
│  └────────┬──────────────────────┬──────────┘         │       │
│           │                      │                    │       │
│  ┌────────▼───────────┐  ┌───────▼──────┐  ┌────────▼─────┐ │
│  │  PostgreSQL DB     │  │   SQLite     │  │   Redis      │ │
│  │  (Production)      │  │  (Dev/Test)  │  │  (Locking,   │ │
│  │                    │  │              │  │   Fallback)  │ │
│  └────────────────────┘  └──────────────┘  └──────────────┘ │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         Device Integrations & Controllers             │  │
│  │  - Hikvision ISAPI (vendored, configurable)          │  │
│  │  - Mock Device Controller (dev/demo)                 │  │
│  │  - Extensible vendor architecture                    │  │
│  └───────────────────────────────────────────────────────┘  │
│                           ▲                                   │
│                           │                                   │
│  ┌────────────────────────┴──────────────────────────────┐  │
│  │     Vault Secret Management (Credentials)             │  │
│  │  - Device auth tokens                                │  │
│  │  - Database credentials                              │  │
│  │  - API keys                                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│          Queue Management for Resilience                       │
│  - Redis Primary (fast, distributed)                          │
│  - SQLite Fallback Queue (on-disk persistence)                │
│  - Queue Manager (automatic failover & recovery)              │
└────────────────────────────────────────────────────────────────┘
```

### Key Components

- **REST API** (`app/routers/`): Device control, event querying, status endpoints
- **Event Processing** (`app/models.py`, `app/schemas.py`): Standardized event structures via Peewee ORM
- **Device Drivers** (`app/devices/`): Vendor-specific ISAPI implementations with mock support
- **Database** (`migrations/`, `app/models.py`): Peewee-backed PostgreSQL/SQLite persistent storage
- **Queue Manager** (`app/queue_manager.py`): In-memory + persistent SQLite queue with Redis fallback for event processing resilience
- **Redis Helper** (`app/redis_helper.py`): Distributed locking, connection pooling, async queue operations, and health checks
- **Secrets Management** (`app/vault_helper.py`, `app/crypto.py`): HashiCorp Vault integration for credential handling and encryption utilities
- **Reverse Proxy** (`deploy/nginx/`): Nginx configuration for TLS termination and load balancing

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
│   ├── database.py          # Database connections & Peewee setup
│   ├── models.py            # Peewee ORM models
│   ├── schemas.py           # Pydantic schemas
│   ├── vault_helper.py      # Vault integration
│   ├── queue_manager.py     # Event queue with Redis/SQLite fallback
│   ├── redis_helper.py      # Redis client, locking, health checks
│   ├── devices/             # Device vendor implementations
│   │   ├── __init__.py
│   │   ├── base.py          # Base DeviceDriver interface
│   │   ├── factory.py       # Device controller factory
│   │   └── vendors/         # Vendor-specific implementations
│   │       ├── hikvision.py # Hikvision ISAPI driver
│   │       └── mock.py      # Mock device driver (testing/demo)
│   └── routers/             # API endpoint groups
│       ├── __init__.py
│       ├── devices.py       # Device management endpoints
│       ├── events.py        # Event processing endpoints
│       └── health.py        # Health check endpoints
├── deploy/                  # Deployment configurations
│   ├── services/            # Systemd service & timer files
│   │   ├── access-control.service
│   │   └── access-control.timer
│   ├── nginx/               # Reverse proxy configuration
│   │   └── nginx.conf       # Production nginx setup
│   └── vault/               # Vault configuration
│       └── vault-config.hcl # Vault server setup
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
# Install dependencies (includes test packages)
pip install -r requirements.txt

# Run all tests with pytest
pytest

# Run with coverage report
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_devices.py -v

# Run async tests
pytest tests/test_async.py -v -s
```

### Database Migrations

```bash
# Create a new migration
python -m peewee_migrate create migration_name

# Apply pending migrations
python -m peewee_migrate migrate

# Show migration status
python -m peewee_migrate status

# Rollback last migration
python -m peewee_migrate rollback
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
- ✅ Device credentials never stored locally; fetched from Vault on-demand
- ✅ Database passwords encrypted with industry standards
- ✅ HTTPS enforced via Nginx reverse proxy with TLS termination
- ✅ Rate limiting on sensitive endpoints
- ✅ Complete audit trail of all device access and configuration changes
- ✅ Input validation on all API endpoints with Pydantic schemas
- ✅ SQL injection protection via Peewee ORM parameterized queries
- ✅ Distributed locking via Redis prevents race conditions
- ✅ Event queue fallback ensures no message loss during Redis outages

## Troubleshooting

### Connection Refused to Device

```
Error: ConnectionError: Unable to connect to device at 192.168.1.100
```

**Solution**: Verify device IP, network connectivity, and that device credentials are correct in Vault.

### Database Migration Failures

```
Error: peewee_migrate.MigrateException: ...
```

**Solution**: 
```bash
# Check migration status
python -m peewee_migrate status

# Rollback and re-apply migrations (development only)
python -m peewee_migrate rollback
python -m peewee_migrate migrate
```

### Redis/Queue Issues

```
Error: ConnectionError: Cannot connect to Redis
```

**Solution**: Queue Manager automatically falls back to SQLite queue storage. Check Redis connectivity:
```bash
redis-cli ping  # Should return PONG
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
- [Peewee](http://docs.peewee-orm.com/) - ORM with multi-database support
- [peewee-migrate](https://github.com/klen/peewee_migrate) - Database migrations
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [Redis](https://redis.io/) - Distributed locking and message queues
- [HashiCorp Vault](https://www.vaultproject.io/) - Secrets management
- [Docker](https://www.docker.com/) - Containerization

---

**Version**: 1.0.0  
**Last Updated**: April 5, 2026  
**Maintainer**: Tariq Mohammed
