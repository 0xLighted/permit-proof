"""
PermitProof - Stage 2 Database Management & CRUD CLI
Provides comprehensive CRUD operations for Users/Cards, Devices, and Pre-Approval Jobs.
Includes both CLI subcommands and an interactive menu for live demonstration.
"""

import sys
import os
import argparse
import json
import uuid

from server.db import db
from server.crypto import (
    get_master_secret,
    derive_keys,
    compute_device_id_hash,
    compute_card_id_hash
)


def _get_crypto_keys():
    master = get_master_secret()
    k_dev, k_card, k_msg = derive_keys(master)
    return k_dev, k_card, k_msg


# ==============================================================================
# Users / Cards CRUD
# ==============================================================================

def cmd_users_list(args):
    users = db.list_users(active_only=getattr(args, "active_only", False))
    print(f"\n--- Registered Users ({len(users)}) ---")
    if not users:
        print("No users found.")
        return
    print(f"{'Role':<12} {'Active':<8} {'Full Name':<20} {'Email':<30} {'Card Hash (Prefix)'}")
    print("-" * 85)
    for u in users:
        act = "YES" if u.get("active") == 1 else "NO"
        print(f"{u.get('role', ''):<12} {act:<8} {u.get('full_name', ''):<20} {u.get('email', ''):<30} {u.get('card_id_hash', '')[:16]}...")
    print()


def cmd_users_add(args):
    card_hash = args.card_hash
    if not card_hash:
        if args.uid_hex:
            raw_uid = bytes.fromhex(args.uid_hex.replace(":", "").replace(" ", ""))
            _, k_card, _ = _get_crypto_keys()
            card_hash = compute_card_id_hash(k_card, raw_uid)
            print(f"[+] Computed card_id_hash from UID ({args.uid_hex}): {card_hash}")
        else:
            print("[-] Error: Provide either --card-hash (64 hex) or --uid-hex (e.g. 04A1B2C3)")
            return

    db.upsert_user(
        card_id_hash=card_hash,
        full_name=args.name,
        email=args.email,
        role=args.role,
        active=1 if args.active else 0
    )
    print(f"[+] User '{args.name}' ({args.role}) successfully saved.")
    print(f"    card_id_hash: {card_hash}")


def cmd_users_get(args):
    user = db.get_user(args.card_hash)
    if not user:
        print(f"[-] User not found with card hash: {args.card_hash}")
        return
    print("\n--- User Details ---")
    for k, v in user.items():
        print(f"  {k}: {v}")
    print()


def cmd_users_delete(args):
    ok = db.delete_user(args.card_hash)
    if ok:
        print(f"[+] User deleted: {args.card_hash}")
    else:
        print(f"[-] User not found: {args.card_hash}")


# ==============================================================================
# Devices CRUD
# ==============================================================================

def cmd_devices_list(args):
    devices = db.list_devices(active_only=getattr(args, "active_only", False))
    print(f"\n--- Registered Devices ({len(devices)}) ---")
    if not devices:
        print("No devices found.")
        return
    print(f"{'Room ID':<22} {'Active':<8} {'Display Name':<25} {'Device Hash (Prefix)'}")
    print("-" * 85)
    for d in devices:
        act = "YES" if d.get("active") == 1 else "NO"
        disp = d.get("display_name") or "(none)"
        print(f"{d.get('room_id', ''):<22} {act:<8} {disp:<25} {d.get('device_id_hash', '')[:16]}...")
    print()


def cmd_devices_add(args):
    dev_hash = args.device_hash
    if not dev_hash:
        if args.canonical_id:
            k_dev, _, _ = _get_crypto_keys()
            dev_hash = compute_device_id_hash(k_dev, args.canonical_id)
            print(f"[+] Computed device_id_hash from canonical ID '{args.canonical_id}': {dev_hash}")
        else:
            print("[-] Error: Provide either --device-hash or --canonical-id (e.g. pi-room-101)")
            return

    db.upsert_device(
        device_id_hash=dev_hash,
        room_id=args.room,
        active=1 if args.active else 0,
        display_name=args.display_name
    )
    print(f"[+] Device registered for room '{args.room}'.")
    print(f"    device_id_hash: {dev_hash}")


def cmd_devices_get(args):
    dev = db.get_device(args.device_hash)
    if not dev:
        print(f"[-] Device not found: {args.device_hash}")
        return
    print("\n--- Device Details ---")
    for k, v in dev.items():
        print(f"  {k}: {v}")
    print()


def cmd_devices_delete(args):
    ok = db.delete_device(args.device_hash)
    if ok:
        print(f"[+] Device deleted: {args.device_hash}")
    else:
        print(f"[-] Device not found: {args.device_hash}")


# ==============================================================================
# Jobs CRUD
# ==============================================================================

def cmd_jobs_list(args):
    jobs = db.list_jobs(technician_id=getattr(args, "tech", None), status=getattr(args, "status", None))
    print(f"\n--- Pre-Approval Jobs ({len(jobs)}) ---")
    if not jobs:
        print("No jobs found.")
        return
    print(f"{'Job ID':<18} {'Status':<12} {'Done':<6} {'Technician (Prefix)':<24} {'Tasks'}")
    print("-" * 85)
    for j in jobs:
        done = "YES" if j.get("is_complete") == 1 else "NO"
        tasks_summary = ", ".join(j.get("tasks", []))[:30]
        print(f"{j.get('job_id', ''):<18} {j.get('status', ''):<12} {done:<6} {j.get('technician_id', '')[:16]}... {tasks_summary}")
    print()


def cmd_jobs_create(args):
    job_id = args.job_id or f"job-{uuid.uuid4().hex[:8]}"
    tasks = args.tasks or ["Default inspection task"]
    try:
        res = db.create_job(
            job_id=job_id,
            supervisor_id=args.supervisor,
            technician_id=args.technician,
            device_id_hash=args.device,
            tasks=tasks
        )
        print(f"[+] Pre-approval job created: {job_id} (Status: pending)")
        if args.auto_accept:
            db.update_job_status(job_id, "accepted", technician_id=args.technician)
            print(f"[+] Job auto-accepted -> ACTIVE pre-approval for room tap!")
    except Exception as e:
        print(f"[-] Failed to create job: {e}")


def cmd_jobs_update(args):
    ok, reason = db.update_job_status(args.job_id, args.status)
    if ok:
        print(f"[+] Job '{args.job_id}' status updated to '{args.status}'.")
    else:
        print(f"[-] Failed to update job status: {reason}")


def cmd_jobs_delete(args):
    ok = db.delete_job(args.job_id)
    if ok:
        print(f"[+] Job deleted: {args.job_id}")
    else:
        print(f"[-] Job not found: {args.job_id}")


# ==============================================================================
# Interactive Demo Mode
# ==============================================================================

def interactive_menu():
    db.init_schema()
    while True:
        print("\n" + "=" * 60)
        print("  PERMITPROOF DATABASE MANAGEMENT CLI (DEMO MODE)")
        print("=" * 60)
        print("  [1] Users: List all users")
        print("  [2] Users: Register new technician / supervisor")
        print("  [3] Users: Delete a user")
        print("  [4] Devices: List all devices")
        print("  [5] Devices: Register new Pi device / room")
        print("  [6] Devices: Delete a device")
        print("  [7] Jobs: List all inspection jobs")
        print("  [8] Jobs: Create & Pre-Approve a new job")
        print("  [9] Jobs: Update job status (accept/complete/revoke)")
        print("  [s] Seed default demo fixtures (Alice & Jasmine)")
        print("  [q] Exit")
        print("-" * 60)
        choice = input("Enter choice: ").strip().lower()

        if choice == "q":
            print("Goodbye!")
            break
        elif choice == "1":
            cmd_users_list(argparse.Namespace(active_only=False))
        elif choice == "2":
            name = input("Full Name: ").strip()
            email = input("Email address: ").strip()
            role = input("Role (technician/supervisor) [technician]: ").strip().lower() or "technician"
            uid = input("Physical Card UID hex (e.g. 04A1B2C3) [leave blank to enter hash]: ").strip()
            if uid:
                cmd_users_add(argparse.Namespace(name=name, email=email, role=role, uid_hex=uid, card_hash=None, active=True))
            else:
                card_hash = input("64-hex Card Hash: ").strip()
                cmd_users_add(argparse.Namespace(name=name, email=email, role=role, uid_hex=None, card_hash=card_hash, active=True))
        elif choice == "3":
            h = input("Enter Card Hash to delete: ").strip()
            cmd_users_delete(argparse.Namespace(card_hash=h))
        elif choice == "4":
            cmd_devices_list(argparse.Namespace(active_only=False))
        elif choice == "5":
            room = input("Room ID (e.g. server-room-beta): ").strip()
            canon = input("Canonical Pi ID (e.g. pi-room-beta) [blank to enter hash]: ").strip()
            disp = input("Display Name [optional]: ").strip() or None
            if canon:
                cmd_devices_add(argparse.Namespace(room=room, canonical_id=canon, device_hash=None, display_name=disp, active=True))
            else:
                d_hash = input("64-hex Device Hash: ").strip()
                cmd_devices_add(argparse.Namespace(room=room, canonical_id=None, device_hash=d_hash, display_name=disp, active=True))
        elif choice == "6":
            h = input("Enter Device Hash to delete: ").strip()
            cmd_devices_delete(argparse.Namespace(device_hash=h))
        elif choice == "7":
            cmd_jobs_list(argparse.Namespace(tech=None, status=None))
        elif choice == "8":
            users = db.list_users()
            devices = db.list_devices()
            if not users or not devices:
                print("[-] Need at least one registered user and device. Run seed [s] first!")
                continue
            print("\nAvailable Users:")
            for i, u in enumerate(users):
                print(f"  [{i}] {u['full_name']} ({u['role']}) -> {u['card_id_hash'][:16]}...")
            sup_idx = input("Select Supervisor index [0]: ").strip() or "0"
            tech_idx = input("Select Technician index [0]: ").strip() or "0"

            print("\nAvailable Devices:")
            for i, d in enumerate(devices):
                print(f"  [{i}] {d['room_id']} -> {d['device_id_hash'][:16]}...")
            dev_idx = input("Select Device index [0]: ").strip() or "0"

            task_input = input("Enter inspection tasks (comma-separated): ").strip()
            tasks = [t.strip() for t in task_input.split(",") if t.strip()] or ["Inspect cooling manifolds"]

            sup_hash = users[int(sup_idx)]["card_id_hash"]
            tech_hash = users[int(tech_idx)]["card_id_hash"]
            dev_hash = devices[int(dev_idx)]["device_id_hash"]

            cmd_jobs_create(argparse.Namespace(
                job_id=None,
                supervisor=sup_hash,
                technician=tech_hash,
                device=dev_hash,
                tasks=tasks,
                auto_accept=True
            ))
        elif choice == "9":
            job_id = input("Job ID: ").strip()
            st = input("New status (accepted, skipped, completed, revoked): ").strip().lower()
            cmd_jobs_update(argparse.Namespace(job_id=job_id, status=st))
        elif choice == "s":
            from server.scripts.seed import seed_database
            seed_database()


def main():
    parser = argparse.ArgumentParser(description="PermitProof Database Management CLI")
    subparsers = parser.add_subparsers(dest="resource")

    # Users
    p_users = subparsers.add_parser("users", help="Manage users and cards")
    u_subs = p_users.add_subparsers(dest="action")
    p_u_list = u_subs.add_parser("list")
    p_u_list.add_argument("--active-only", action="store_true")

    p_u_add = u_subs.add_parser("add")
    p_u_add.add_argument("--name", required=True)
    p_u_add.add_argument("--email", required=True)
    p_u_add.add_argument("--role", choices=["technician", "supervisor"], default="technician")
    p_u_add.add_argument("--uid-hex", help="Physical Card UID hex (e.g. 04A1B2C3)")
    p_u_add.add_argument("--card-hash", help="Precomputed 64-hex card hash")
    p_u_add.add_argument("--active", action="store_true", default=True)

    p_u_get = u_subs.add_parser("get")
    p_u_get.add_argument("card_hash")

    p_u_del = u_subs.add_parser("delete")
    p_u_del.add_argument("card_hash")

    # Devices
    p_devices = subparsers.add_parser("devices", help="Manage Pi devices and rooms")
    d_subs = p_devices.add_subparsers(dest="action")
    p_d_list = d_subs.add_parser("list")
    p_d_list.add_argument("--active-only", action="store_true")

    p_d_add = d_subs.add_parser("add")
    p_d_add.add_argument("--room", required=True)
    p_d_add.add_argument("--canonical-id", help="Canonical Pi ID (e.g. pi-server-room-001)")
    p_d_add.add_argument("--device-hash", help="Precomputed 64-hex device hash")
    p_d_add.add_argument("--display-name")
    p_d_add.add_argument("--active", action="store_true", default=True)

    p_d_get = d_subs.add_parser("get")
    p_d_get.add_argument("device_hash")

    p_d_del = d_subs.add_parser("delete")
    p_d_del.add_argument("device_hash")

    # Jobs
    p_jobs = subparsers.add_parser("jobs", help="Manage pre-approval jobs")
    j_subs = p_jobs.add_subparsers(dest="action")
    p_j_list = j_subs.add_parser("list")
    p_j_list.add_argument("--tech")
    p_j_list.add_argument("--status")

    p_j_create = j_subs.add_parser("create")
    p_j_create.add_argument("--supervisor", required=True)
    p_j_create.add_argument("--technician", required=True)
    p_j_create.add_argument("--device", required=True)
    p_j_create.add_argument("--job-id")
    p_j_create.add_argument("--tasks", nargs="+")
    p_j_create.add_argument("--auto-accept", action="store_true")

    p_j_upd = j_subs.add_parser("update")
    p_j_upd.add_argument("--job-id", required=True)
    p_j_upd.add_argument("--status", required=True, choices=["accepted", "skipped", "completed", "revoked"])

    p_j_del = j_subs.add_parser("delete")
    p_j_del.add_argument("job_id")

    # Seed
    subparsers.add_parser("seed", help="Seed default demo fixtures")

    # Parse arguments
    args = parser.parse_args()

    db.init_schema()

    if not args.resource:
        interactive_menu()
        return

    if args.resource == "seed":
        from server.scripts.seed import seed_database
        seed_database()
        return

    action_map = {
        ("users", "list"): cmd_users_list,
        ("users", "add"): cmd_users_add,
        ("users", "get"): cmd_users_get,
        ("users", "delete"): cmd_users_delete,
        ("devices", "list"): cmd_devices_list,
        ("devices", "add"): cmd_devices_add,
        ("devices", "get"): cmd_devices_get,
        ("devices", "delete"): cmd_devices_delete,
        ("jobs", "list"): cmd_jobs_list,
        ("jobs", "create"): cmd_jobs_create,
        ("jobs", "update"): cmd_jobs_update,
        ("jobs", "delete"): cmd_jobs_delete,
    }

    handler = action_map.get((args.resource, getattr(args, "action", None)))
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
