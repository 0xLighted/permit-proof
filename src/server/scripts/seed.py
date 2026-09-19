"""
PermitProof - Stage 2 Database Seeder CLI
Seeds SQLite database with canonical devices, users, and pre-approved jobs.
Hashes are deterministically derived from MASTER_SECRET.
"""

import sys
import os

from server.crypto import (
    get_master_secret,
    derive_keys,
    compute_device_id_hash,
    compute_card_id_hash
)
from server.db import db

CANONICAL_PI_ID = "pi-server-room-001"
ROOM_ID = "server-room-alpha"
RAW_CARD_UID = b"\x04\xa2\xb3\xc4\xd5\xe6\xf7"
SUPERVISOR_PSEUDO_UID = b"\x04\x99\x88\x77\x66\x55\x44"


def seed_database():
    db.init_schema()
    master = get_master_secret()
    k_device, k_card, _ = derive_keys(master)

    device_hash = compute_device_id_hash(k_device, CANONICAL_PI_ID)
    tech_card_hash = compute_card_id_hash(k_card, RAW_CARD_UID)
    sup_card_hash = compute_card_id_hash(k_card, SUPERVISOR_PSEUDO_UID)

    print("=" * 80)
    print("  PERMITPROOF STAGE 2 DATABASE SEEDING")
    print("=" * 80)
    print(f"Database Path: {db.db_path}")

    devices_to_seed = [
        ("pi-server-room-001", "server-room-alpha", "Server Room Alpha Reader"),
        ("charlie-pi", "server-room-charlie", "Charlie Pi Reader Station"),
        ("raspberrypi", "server-room-pi", "Default Raspberry Pi Station")
    ]

    device_hashes = {}
    for dev_id, room_id, display_name in devices_to_seed:
        d_hash = compute_device_id_hash(k_device, dev_id)
        device_hashes[dev_id] = d_hash
        db.upsert_device(
            device_id_hash=d_hash,
            room_id=room_id,
            active=1,
            display_name=display_name
        )
        print(f"[+] Device Registered: {dev_id} -> Room: {room_id}")
        print(f"    device_id_hash: {d_hash}")

    # 2. Upsert Supervisor
    db.upsert_user(
        card_id_hash=sup_card_hash,
        full_name="Alice Supervisor",
        email="supervisor@permitproof.local",
        role="supervisor",
        active=1
    )
    print(f"[+] User Registered: Alice Supervisor (Role: supervisor)")
    print(f"    supervisor_id_hash: {sup_card_hash}")

    # 3. Upsert Technician
    db.upsert_user(
        card_id_hash=tech_card_hash,
        full_name="Jasmine Zurayn",
        email="technician@permitproof.local",
        role="technician",
        active=1
    )
    print(f"[+] User Registered: Jasmine Zurayn (Role: technician)")
    print(f"    technician_id_hash: {tech_card_hash}")

    # 4. Upsert Jobs & Pre-Approve for devices
    for dev_id, room_id, _ in devices_to_seed:
        d_hash = device_hashes[dev_id]
        job_id = f"job-demo-{room_id.split('-')[-1]}"
        existing = db.list_jobs(technician_id=tech_card_hash)
        if not any(j["job_id"] == job_id for j in existing):
            db.create_job(
                job_id=job_id,
                supervisor_id=sup_card_hash,
                technician_id=tech_card_hash,
                device_id_hash=d_hash,
                tasks=[
                    "Inspect server rack A1 cooling manifolds",
                    "Verify redundant UPS battery cell health",
                    "Audit physical cage tamper seals"
                ]
            )
            db.update_job_status(job_id=job_id, new_status="accepted", technician_id=tech_card_hash)
            print(f"[+] Pre-Approval Job Created & Accepted: {job_id} ({room_id})")
        else:
            print(f"[*] Pre-Approval Job already present: {job_id}")

    print("=" * 80)
    print("  SEEDING COMPLETE - SYSTEM READY FOR VERIFICATION")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    seed_database()
