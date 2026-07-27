#!/usr/bin/env python3
"""
VSTrustee Recovery Tool
Modes:
  - factory-reset : resets vault (data loss) and sets a new master password
  - restore-backup : restore from a previously exported database file

Usage:
  python vstrustee_recovery_tool.py factory-reset --appdir "C:\\Path\\To\\App"
  python vstrustee_recovery_tool.py restore-backup --appdir "C:\\Path\\To\\App" --backup "C:\\backups\\vault.db"
"""

import os, sys, argparse, shutil, sqlite3, time, getpass
from cryptography.fernet import Fernet
import bcrypt

def backup_file(path):
    if not os.path.exists(path):
        return None
    ts = int(time.time())
    bak = f"{path}.bak_{ts}"
    shutil.copy2(path, bak)
    return bak

def create_new_keyfile(key_path):
    k = Fernet.generate_key()
    with open(key_path, "wb") as f:
        f.write(k)
    return k

def init_empty_db(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        master_hash BLOB NOT NULL,
        email TEXT,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS vault (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        site TEXT NOT NULL,
        login TEXT NOT NULL,
        password_blob BLOB NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    conn.commit()
    conn.close()

def set_master_user(db_path, username, password):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    h = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    cur.execute("INSERT INTO users (username, master_hash) VALUES (?, ?)", (username, h))
    conn.commit()
    conn.close()

def factory_reset(appdir):
    db_path = os.path.join(appdir, "vault.db")
    key_path = os.path.join(appdir, "vault.key")
    # backups
    db_bak = backup_file(db_path) if os.path.exists(db_path) else None
    key_bak = backup_file(key_path) if os.path.exists(key_path) else None
    print("Backups created:")
    print("DB backup:", db_bak)
    print("Key backup:", key_bak)

    # remove or move current files
    if os.path.exists(db_path):
        os.remove(db_path)
    if os.path.exists(key_path):
        os.remove(key_path)

    # create new key and DB
    create_new_keyfile(key_path)
    init_empty_db(db_path)

    print("New vault created. Please set a new master account.")
    username = input("Enter username for admin account (e.g. your email or name): ").strip() or "admin"
    while True:
        pw1 = getpass.getpass("Enter new master password: ")
        pw2 = getpass.getpass("Confirm new master password: ")
        if pw1 == pw2 and len(pw1) >= 8:
            set_master_user(db_path, username, pw1)
            print("Master user created.")
            break
        print("Passwords did not match or too short (min 8 chars). Try again.")
    print("Factory reset complete. Old data is backed up (if existed).")

def restore_backup(appdir, backup_path):
    db_path = os.path.join(appdir, "vault.db")
    key_path = os.path.join(appdir, "vault.key")
    if not os.path.exists(backup_path):
        print("Backup not found:", backup_path); return
    # create backups of current
    backup_file(db_path) if os.path.exists(db_path) else None
    backup_file(key_path) if os.path.exists(key_path) else None
    # copy backup into place
    shutil.copy2(backup_path, db_path)
    print("Restored DB from:", backup_path)
    print("If your backup needs a key, make sure vault.key is present in the app folder.")
    print("Restore complete.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["factory-reset","restore-backup"])
    parser.add_argument("--appdir", default=".", help="Path to VSTrustee app folder")
    parser.add_argument("--backup", default=None, help="Path to backup DB for restore-backup mode")
    args = parser.parse_args()

    appdir = os.path.abspath(args.appdir)
    os.makedirs(appdir, exist_ok=True)

    if args.mode == "factory-reset":
        factory_reset(appdir)
    elif args.mode == "restore-backup":
        if not args.backup:
            print("Please provide --backup path for restore-backup mode.")
            return
        restore_backup(appdir, args.backup)

if __name__ == "__main__":
    main()
