"""Initial database schema migration.

Creates core tables for device management, event logging, audit trails, and queuing.
"""

from peewee import (
    CharField,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    TextField,
    BooleanField,
    Model,
)
from datetime import datetime


def migrate(migrator, database, fake=False, **kwargs):
    """Write your migrations here."""

    @migrator.create_model
    class Device(Model):
        """Access control device."""

        device_id = CharField(unique=True, index=True)
        device_type = CharField()  # isapi, suprema, zkteco, mock
        vendor = CharField()  # hikvision, suprema, zkteco
        ip_address = CharField(unique=True, index=True)
        port = IntegerField(default=8000)
        # Credentials stored encrypted or in Vault
        username_enc = TextField(null=True)  # Encrypted
        password_enc = TextField(null=True)  # Encrypted
        device_mode = CharField(null=True)  # mock, real, or null (use global)
        auth_backend_url = CharField(null=True)  # Per-device override
        door_locked = BooleanField(default=False)
        last_heartbeat = DateTimeField(null=True)
        status = CharField(default="configuring")  # configuring, online, offline
        created_at = DateTimeField(default=datetime.utcnow)
        updated_at = DateTimeField(default=datetime.utcnow)

        class Meta:
            table_name = "devices"

    @migrator.create_model
    class EventLog(Model):
        """Security events from devices."""

        device = ForeignKeyField(Device, backref="events", on_delete="CASCADE")
        event_type = CharField(index=True)  # UnlockByCard, DoorAlarm, etc.
        event_data = TextField()  # JSON payload
        validation_result = CharField(default="pending")  # pending, success, error, timeout
        error_message = TextField(null=True)
        created_at = DateTimeField(default=datetime.utcnow, index=True)

        class Meta:
            table_name = "event_logs"

    @migrator.create_model
    class BackendConfig(Model):
        """Authentication backend configuration."""

        backend_url = CharField()
        auth_token = TextField()  # Encrypted or in Vault
        is_active = BooleanField(default=True)
        created_at = DateTimeField(default=datetime.utcnow)
        updated_at = DateTimeField(default=datetime.utcnow)

        class Meta:
            table_name = "backend_configs"

    @migrator.create_model
    class AuditLog(Model):
        """Immutable audit trail (append-only, no UPDATE/DELETE)."""

        event_type = CharField(index=True)  # device_registered, config_changed, token_accessed
        actor_id = CharField()  # User, service, or application
        resource_id = CharField(index=True)  # Device ID, config ID, etc.
        action = CharField()  # created, updated, deleted, accessed
        changes = TextField(null=True)  # JSON diff
        ip_address = CharField(null=True)
        status = CharField(default="success")  # success, failure
        reason = TextField(null=True)  # Reason for failure
        timestamp = DateTimeField(default=datetime.utcnow, index=True)

        class Meta:
            table_name = "audit_logs"

    @migrator.create_model
    class OperationQueue(Model):
        """Persistent queue for device operations (Redis fallback)."""

        device = ForeignKeyField(Device, backref="operations", on_delete="CASCADE")
        operation_type = CharField()  # register, configure, unlock, etc.
        payload = TextField()  # JSON operation data
        created_at = DateTimeField(default=datetime.utcnow)
        processed_at = DateTimeField(null=True)

        class Meta:
            table_name = "operation_queues"


def rollback(migrator, database, fake=False, **kwargs):
    """Write your rollback migrations here."""

    migrator.remove_model("operation_queues")
    migrator.remove_model("audit_logs")
    migrator.remove_model("backend_configs")
    migrator.remove_model("event_logs")
    migrator.remove_model("devices")
