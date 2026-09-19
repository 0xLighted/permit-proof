"""
PermitProof - CLI Tools Test Suite
Verifies database management CRUD script (manage.py) and table viewer (db_viewer.py).
"""

import pytest
import os
import argparse

TEST_DB_PATH = "test_permitproof_cli.db"
os.environ["DATABASE_PATH"] = TEST_DB_PATH
os.environ.setdefault("MASTER_SECRET", "abf913629a0e2ef8560e9af135e97fa436f965bc47b80c47e3d5c0b861c6cc52")

from server.db import db
from server.scripts.manage import (
    cmd_users_add,
    cmd_users_list,
    cmd_users_delete,
    cmd_devices_add,
    cmd_devices_list,
    cmd_devices_delete,
    cmd_jobs_create,
    cmd_jobs_update,
    cmd_jobs_delete
)
from server.scripts.db_viewer import print_table_view


@pytest.fixture(autouse=True)
def setup_cli_test_db():
    db.init_schema()
    db.reset_tables()
    yield
    db.reset_tables()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass


def test_cli_users_crud(capsys):
    # Add user with physical card UID
    cmd_users_add(argparse.Namespace(
        name="Charlie Engineer",
        email="charlie@permitproof.local",
        role="technician",
        uid_hex="04A1B2C3D4",
        card_hash=None,
        active=True
    ))
    users = db.list_users()
    assert len(users) == 1
    assert users[0]["full_name"] == "Charlie Engineer"
    card_hash = users[0]["card_id_hash"]

    # List users
    cmd_users_list(argparse.Namespace(active_only=False))
    captured = capsys.readouterr()
    assert "Charlie Engineer" in captured.out

    # Delete user
    cmd_users_delete(argparse.Namespace(card_hash=card_hash))
    assert len(db.list_users()) == 0


def test_cli_devices_crud(capsys):
    # Add device with canonical ID
    cmd_devices_add(argparse.Namespace(
        room="server-room-gamma",
        canonical_id="pi-room-gamma",
        device_hash=None,
        display_name="Gamma Unit",
        active=True
    ))
    devices = db.list_devices()
    assert len(devices) == 1
    assert devices[0]["room_id"] == "server-room-gamma"
    dev_hash = devices[0]["device_id_hash"]

    # List devices
    cmd_devices_list(argparse.Namespace(active_only=False))
    captured = capsys.readouterr()
    assert "server-room-gamma" in captured.out

    # Delete device
    cmd_devices_delete(argparse.Namespace(device_hash=dev_hash))
    assert len(db.list_devices()) == 0


def test_cli_jobs_crud():
    # Setup supervisor, tech, device
    db.upsert_user("s" * 64, "Supervisor", "sup@test.com", "supervisor")
    db.upsert_user("t" * 64, "Tech", "tech@test.com", "technician")
    db.upsert_device("d" * 64, "room-x", 1)

    # Create job with auto-accept
    cmd_jobs_create(argparse.Namespace(
        job_id="job-cli-test",
        supervisor="s" * 64,
        technician="t" * 64,
        device="d" * 64,
        tasks=["Verify rack cooling"],
        auto_accept=True
    ))
    job = db.find_accepted_job("t" * 64, "d" * 64)
    assert job is not None
    assert job["job_id"] == "job-cli-test"
    assert job["status"] == "accepted"

    # Update job status
    cmd_jobs_update(argparse.Namespace(job_id="job-cli-test", status="completed"))
    job_updated = db.list_jobs()
    assert job_updated[0]["status"] == "completed"
    assert job_updated[0]["is_complete"] == 1

    # Delete job
    cmd_jobs_delete(argparse.Namespace(job_id="job-cli-test"))
    assert len(db.list_jobs()) == 0


def test_cli_db_viewer_methods(capsys):
    db.upsert_user("u" * 64, "Test User", "test@test.com", "technician")
    tables = db.get_table_names()
    assert "users" in tables
    assert "devices" in tables
    assert "jobs" in tables

    count = db.get_table_count("users")
    assert count == 1

    cols = db.get_table_columns("users")
    assert "card_id_hash" in cols
    assert "full_name" in cols

    rows = db.get_table_rows("users", limit=10, offset=0)
    assert len(rows) == 1
    assert rows[0]["full_name"] == "Test User"

    print_table_view("users", rows, cols, page=0, total_rows=1, page_size=10)
    captured = capsys.readouterr()
    assert "TABLE: users" in captured.out
    assert "Test User" in captured.out
