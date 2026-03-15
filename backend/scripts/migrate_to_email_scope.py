#!/usr/bin/env python3
"""
Migrate dumps/ and token storage to email-scoped layout.

Before: dumps/{Name}/
After:  dumps/{email}/{Name}/

Idempotent — safe to run multiple times.

Usage:
  python backend/scripts/migrate_to_email_scope.py --email-map "Lenin:user@gmail.com,Appa:user@gmail.com"
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DUMPS_BASE = Path(__file__).resolve().parent.parent / "dumps"
USERS_FILE = DATA_DIR / "users.json"
TOKENS_FILE = DATA_DIR / "google_tokens.json"


def load_users():
    return json.loads(USERS_FILE.read_text())


def save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2))


def migrate(email_map: dict, dry_run=False):
    users = load_users()
    changed = False

    for user in users:
        name = user["name"]
        uid = user["id"]
        email = email_map.get(name) or email_map.get(uid)
        if not email:
            print(f"  SKIP {name} — no email mapping provided")
            continue

        email = email.strip().lower()

        # Skip if already has correct email
        if user.get("email") == email:
            print(f"  OK   {name} already has email={email}")
        else:
            user["email"] = email
            changed = True
            print(f"  SET  {name} → email={email}")

        old_path = DUMPS_BASE / name
        new_path = DUMPS_BASE / email / name

        if old_path.exists() and not new_path.exists():
            # Check it's not already under an email directory
            if old_path.parent == DUMPS_BASE:
                print(f"  MOVE {old_path} → {new_path}")
                if not dry_run:
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(old_path), str(new_path))
                changed = True
        elif new_path.exists():
            print(f"  OK   {new_path} already exists")
        else:
            print(f"  CREATE {new_path}")
            if not dry_run:
                new_path.mkdir(parents=True, exist_ok=True)
            changed = True

    if not dry_run:
        save_users(users)
        print("  users.json updated")

    # Migrate google_tokens.json: flat dict → email-keyed dict
    if TOKENS_FILE.exists():
        tokens = json.loads(TOKENS_FILE.read_text())
        # Detect if already migrated (keys are email addresses)
        already_migrated = any("@" in k for k in tokens.keys())
        if not already_migrated:
            # Find the primary email (the one with the most users)
            all_emails = list(set(email_map.values()))
            if len(all_emails) == 1:
                owner_email = all_emails[0].lower()
            else:
                owner_email = all_emails[0].lower()
                print(f"  NOTE: Assigning existing token to {owner_email}")
            new_tokens = {owner_email: tokens}
            if not dry_run:
                TOKENS_FILE.write_text(json.dumps(new_tokens, indent=2))
                print(f"  google_tokens.json migrated (owner: {owner_email})")
            else:
                print(f"  DRY: would assign existing token to {owner_email}")
        else:
            print("  google_tokens.json already migrated (email-keyed)")

    print("\nMigration complete." + (" (DRY RUN)" if dry_run else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate to email-scoped dumps layout")
    parser.add_argument("--email-map", required=True,
                        help='Comma-separated "Name:email" pairs')
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without making changes")
    args = parser.parse_args()

    email_map = {}
    for pair in args.email_map.split(","):
        name, email = pair.strip().split(":", 1)
        email_map[name.strip()] = email.strip()

    print(f"Email mappings: {email_map}")
    print(f"Dumps base: {DUMPS_BASE}")
    print()
    migrate(email_map, dry_run=args.dry_run)
