#!/usr/bin/env python3
"""
VSTrustee — Final merged app with security-question support
Save as: password_final_code_vstrustee_final.py
Requires: bcrypt, cryptography, pyperclip
Install: pip install bcrypt cryptography pyperclip
"""

import os
import sqlite3
import time
import json
import secrets
import string
import shutil
import csv
import smtplib
import bcrypt
from email.message import EmailMessage
from cryptography.fernet import Fernet
from datetime import datetime
from tkinter import *
from tkinter import ttk, messagebox, filedialog, simpledialog
import pyperclip

# ---------------- Paths & Defaults ----------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "vault.db")
KEY_PATH = os.path.join(APP_DIR, "vault.key")
SETTINGS_PATH = os.path.join(APP_DIR, "pm_settings.json")
ICON_PATH = os.path.join(APP_DIR, "vstrustee.ico")

DEFAULT_SETTINGS = {
    "smtp_server": "",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_pass": "",
    "email_from": "",
    "auto_lock_seconds": 300,
    "clipboard_clear_seconds": 10,
    "otp_length": 6,
    "expiry_days": 90,
    "dark_mode_default": False
}

if not os.path.exists(SETTINGS_PATH):
    with open(SETTINGS_PATH, "w") as f:
        json.dump(DEFAULT_SETTINGS, f, indent=2)

with open(SETTINGS_PATH, "r") as f:
    SETTINGS = json.load(f)

# ---------------- Key & Encryption ----------------
if not os.path.exists(KEY_PATH):
    with open(KEY_PATH, "wb") as kf:
        kf.write(Fernet.generate_key())
FERNET_KEY = open(KEY_PATH, "rb").read()
fernet = Fernet(FERNET_KEY)

# ---------------- Database ----------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

# Create tables (idempotent)
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    master_hash BLOB NOT NULL,
    email TEXT,
    phone TEXT,
    sec_question TEXT,
    sec_answer_hash BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS vault (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    site TEXT NOT NULL,
    login TEXT NOT NULL,
    password_blob BLOB NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")
conn.commit()

# try to add columns if older DB lacks them (safe)
try:
    cur.execute("ALTER TABLE users ADD COLUMN sec_question TEXT")
    cur.execute("ALTER TABLE users ADD COLUMN sec_answer_hash BLOB")
    conn.commit()
except Exception:
    pass

pyperclip.determine_clipboard()

# ---------------- Utilities ----------------
def hash_master(password: str) -> bytes:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def verify_master(stored: bytes, provided: str) -> bool:
    try:
        return bcrypt.checkpw(provided.encode(), stored)
    except Exception:
        return False

def encrypt_value(plaintext: str) -> bytes:
    return fernet.encrypt(plaintext.encode())

def decrypt_value(blob: bytes) -> str:
    return fernet.decrypt(blob).decode()

def gen_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))

def password_strength(pw: str) -> str:
    score = 0
    if len(pw) >= 8: score += 1
    if any(c.isupper() for c in pw): score += 1
    if any(c.isdigit() for c in pw): score += 1
    if any(not c.isalnum() for c in pw): score += 1
    if score <= 1: return "Weak"
    if score == 2: return "Medium"
    return "Strong"

def send_email(to_addr: str, subject: str, body: str) -> bool:
    try:
        if not SETTINGS.get("smtp_server"):
            return False
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SETTINGS.get("email_from") or SETTINGS.get("smtp_user")
        msg["To"] = to_addr
        msg.set_content(body)
        s = smtplib.SMTP(SETTINGS.get("smtp_server"), SETTINGS.get("smtp_port"))
        s.starttls()
        s.login(SETTINGS.get("smtp_user"), SETTINGS.get("smtp_pass"))
        s.send_message(msg)
        s.quit()
        return True
    except Exception as e:
        print("Email send failed:", e)
        return False

# ---------------- Application ----------------
class VSTrusteeApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("VSTrustee Password Manager")
        try:
            self.root.iconbitmap(ICON_PATH)
        except Exception:
            pass

        self.width = 1100
        self.height = 700
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.minsize(900, 600)

        # session & settings
        self.user_id = None
        self.last_activity = time.time()
        self.auto_lock_seconds = int(SETTINGS.get("auto_lock_seconds", 300))
        self.clipboard_clear_seconds = int(SETTINGS.get("clipboard_clear_seconds", 10))
        self.otp_length = int(SETTINGS.get("otp_length", 6))
        self.dark = bool(SETTINGS.get("dark_mode_default", False))
        self.locked = True

        # layout
        self.sidebar = Frame(self.root, width=220)
        self.sidebar.pack(side=LEFT, fill=Y, padx=8, pady=8)
        self.content = Frame(self.root)
        self.content.pack(side=RIGHT, fill=BOTH, expand=True, padx=8, pady=8)

        # animated background canvas
        self.bg_canvas = Canvas(self.content, highlightthickness=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.gradient_offset = 0
        self._animate_bg_running = True
        self._animate_bg()

        self._build_sidebar()

        # activity binding
        self.root.bind_all("<Any-KeyPress>", self._on_activity)
        self.root.bind_all("<Any-Button>", self._on_activity)

        # auto-lock monitor
        self._schedule_lock_check()

        # show login first
        self.show_login()

    # animated background
    def _animate_bg(self):
        if not self._animate_bg_running:
            return
        self.bg_canvas.delete("all")
        w = max(800, self.content.winfo_width() or (self.width - 240))
        h = max(400, self.content.winfo_height() or self.height)
        if self.dark:
            colors = ["#071226", "#0b2c45", "#133a57", "#1b3850", "#0f2740"]
        else:
            colors = ["#cfe8ff", "#e6f4ff", "#f0fbff", "#eaf4ff", "#d6ecff"]
        bar_w = max(80, int(w / 8))
        for i, c in enumerate(colors):
            x = ((i * bar_w) + self.gradient_offset) % (w + bar_w) - bar_w
            self.bg_canvas.create_rectangle(x, 0, x + bar_w, h, fill=c, outline=c)
        self.gradient_offset = (self.gradient_offset + 4) % (w + bar_w)
        self.root.after(45, self._animate_bg)

    def _build_sidebar(self):
        for w in self.sidebar.winfo_children():
            w.destroy()
        Label(self.sidebar, text="VSTrustee", font=("Segoe UI", 16, "bold")).pack(pady=(8, 12))
        Button(self.sidebar, text="Login", width=20, command=lambda: self.show_login()).pack(pady=6)
        Button(self.sidebar, text="Register", width=20, command=self.show_register).pack(pady=6)
        Button(self.sidebar, text="Vault", width=20, command=self.show_vault).pack(pady=6)
        Button(self.sidebar, text="Settings ⚙️", width=20, command=self.show_settings).pack(pady=6)
        Button(self.sidebar, text="Backup / Restore", width=20, command=self.show_backup).pack(pady=6)
        Button(self.sidebar, text="About", width=20, command=self.show_about).pack(pady=6)
        self.theme_var = IntVar(value=1 if self.dark else 0)
        Checkbutton(self.sidebar, text="Dark Mode", variable=self.theme_var, command=self._toggle_theme).pack(pady=(20, 6))
        Button(self.sidebar, text="Logout", width=20, command=self.logout).pack(side=BOTTOM, pady=12)

    def _toggle_theme(self):
        self.dark = bool(self.theme_var.get())
        SETTINGS["dark_mode_default"] = self.dark
        with open(SETTINGS_PATH, "w") as f:
            json.dump(SETTINGS, f, indent=2)
        self.show_current_page()

    # activity / auto-lock
    def _on_activity(self, event=None):
        self.last_activity = time.time()

    def _schedule_lock_check(self):
        def check():
            if self.user_id and (time.time() - self.last_activity) > self.auto_lock_seconds:
                self.locked = True
                self.user_id = None
                messagebox.showinfo("Auto-lock", "Application locked due to inactivity.")
                self.show_login()
            self.root.after(1000, check)
        self.root.after(1000, check)

    def clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()
        self.bg_canvas = Canvas(self.content, highlightthickness=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.gradient_offset = 0
        self._animate_bg()

    def show_current_page(self):
        if self.user_id:
            self.show_vault()
        else:
            self.show_login()

    # ---------------- Login / Register ----------------
    def show_login(self):
        self.clear_content()
        frame = Frame(self.content, padx=12, pady=12)
        frame.place(relx=0.08, rely=0.08, relwidth=0.84, relheight=0.84)
        Label(frame, text="Welcome to VSTrustee", font=("Segoe UI", 22, "bold")).pack(pady=(8, 12))
        form = Frame(frame); form.pack(pady=6)
        Label(form, text="Username:").grid(row=0, column=0, sticky=E, padx=6, pady=6)
        self.login_user_entry = Entry(form, width=36); self.login_user_entry.grid(row=0, column=1, padx=6, pady=6)
        Label(form, text="Master Password:").grid(row=1, column=0, sticky=E, padx=6, pady=6)
        self.login_pass_entry = Entry(form, show="*", width=36); self.login_pass_entry.grid(row=1, column=1, padx=6, pady=6)
        eye_btn = Button(form, text="👁️", width=3, command=self._toggle_login_eye); eye_btn.grid(row=1, column=2, padx=4)
        btns = Frame(frame); btns.pack(pady=8)
        Button(btns, text="Login", width=16, command=self.login).grid(row=0, column=0, padx=8)
        Button(btns, text="Register", width=16, command=self.show_register).grid(row=0, column=1, padx=8)
        Button(frame, text="Forgot Master Password?", command=self.forgot_password_flow, fg="blue").pack(pady=6)
        Button(frame, text="Open Settings", command=self.show_settings).pack(pady=6)

    def _toggle_login_eye(self):
        if self.login_pass_entry.cget("show") == "": self.login_pass_entry.configure(show="*")
        else: self.login_pass_entry.configure(show="")

    def show_register(self):
        self.clear_content()
        frame = Frame(self.content, padx=12, pady=12)
        frame.place(relx=0.12, rely=0.06, relwidth=0.76, relheight=0.88)
        Label(frame, text="Create an Account", font=("Segoe UI", 20, "bold")).pack(pady=6)
        frm = Frame(frame); frm.pack(pady=8)
        Label(frm, text="Username:").grid(row=0, column=0, sticky=E, padx=6, pady=6)
        eu = Entry(frm, width=36); eu.grid(row=0, column=1, padx=6, pady=6)
        Label(frm, text="Master Password:").grid(row=1, column=0, sticky=E, padx=6, pady=6)
        ep = Entry(frm, show="*", width=36); ep.grid(row=1, column=1, padx=6, pady=6)
        Button(frm, text="👁️", width=3, command=lambda: ep.configure(show="" if ep.cget("show")=="*" else "*")).grid(row=1, column=2, padx=4)
        Label(frm, text="Email (optional):").grid(row=2, column=0, sticky=E, padx=6, pady=6)
        ee = Entry(frm, width=36); ee.grid(row=2, column=1, padx=6, pady=6)
        Label(frm, text="Phone (optional):").grid(row=3, column=0, sticky=E, padx=6, pady=6)
        epn = Entry(frm, width=36); epn.grid(row=3, column=1, padx=6, pady=6)
        Label(frm, text="Recovery Question (optional):").grid(row=4, column=0, sticky=E, padx=6, pady=6)
        secq_var = StringVar(value="What is your favourite color?")
        OptionMenu(frm, secq_var,
                   "What is your favourite color?",
                   "What is your mother's maiden name?",
                   "What city were you born in?",
                   "What is the name of your first pet?",
                   "What primary school did you attend?").grid(row=4, column=1, padx=6, pady=6, sticky=W)
        Label(frm, text="Recovery Answer:").grid(row=5, column=0, sticky=E, padx=6, pady=6)
        era = Entry(frm, show="*", width=36); era.grid(row=5, column=1, padx=6, pady=6)
        Button(frame, text="Register", width=18, command=lambda: self._do_register(eu, ep, ee, epn, secq_var, era)).pack(pady=12)
        Button(frame, text="Back to Login", command=self.show_login).pack(pady=6)

    def _do_register(self, eu, ep, ee, epn, secq_var, era):
        u = eu.get().strip(); p = ep.get().strip()
        em = ee.get().strip() or None; ph = epn.get().strip() or None
        secq = secq_var.get().strip() or None; seca = era.get().strip() or None
        if not u or not p:
            messagebox.showwarning("Register", "username and password required"); return
        try:
            h = hash_master(p)
            ans_hash = bcrypt.hashpw(seca.lower().encode(), bcrypt.gensalt()) if seca else None
            cur.execute("INSERT INTO users (username, master_hash, email, phone, sec_question, sec_answer_hash) VALUES (?,?,?,?,?,?)",
                        (u, h, em, ph, secq, ans_hash))
            conn.commit()
            messagebox.showinfo("Register", "Account created"); self.show_login()
        except sqlite3.IntegrityError:
            messagebox.showerror("Register", "Username already exists")

    # ---------------- Login / Logout ----------------
    def login(self):
        user = self.login_user_entry.get().strip(); pw = self.login_pass_entry.get().strip()
        if not user or not pw:
            messagebox.showwarning("Login", "Enter credentials"); return
        cur.execute("SELECT id, master_hash FROM users WHERE username=?", (user,))
        row = cur.fetchone()
        if not row:
            messagebox.showerror("Login", "Invalid credentials"); return
        uid, master_hash = row
        if not verify_master(master_hash, pw):
            messagebox.showerror("Login", "Invalid credentials"); return
        self.user_id = uid; self.last_activity = time.time(); self.locked = False
        # If user has no security question, prompt to set it now
        cur.execute("SELECT sec_question FROM users WHERE id=?", (self.user_id,))
        sq = cur.fetchone()
        if sq and (sq[0] is None or sq[0] == ""):
            if messagebox.askyesno("Set Recovery", "You have not set a recovery security question. Set it now?"):
                self.set_security_question()
        self.show_vault()

    def logout(self):
        self.user_id = None; self.locked = True
        messagebox.showinfo("Logged out", "You have been logged out.")
        self.show_login()

    # ---------------- Forgot / Reset flows ----------------
    def forgot_password_flow(self):
        uname = simpledialog.askstring("Password Reset", "Enter your username:")
        if not uname:
            return
        cur.execute("SELECT id, email, sec_question, sec_answer_hash FROM users WHERE username=?", (uname,))
        r = cur.fetchone()
        if not r:
            messagebox.showerror("Not found", "User not found."); return
        uid, email, q, a_hash = r
        # Try security question first
        if q and a_hash:
            ans = simpledialog.askstring("Security Question", q, show="*")
            if ans and bcrypt.checkpw(ans.lower().encode(), a_hash):
                self._perform_password_reset(uid); return
            else:
                messagebox.showerror("Incorrect", "Security answer incorrect.")
        # fallback to email OTP
        if email:
            go = messagebox.askyesno("Recovery", "Security question not available or failed.\nTry Email OTP?")
            if go:
                self.reset_master_password_email(uname)
                return
        # else factory reset choice
        if messagebox.askyesno("Factory Reset", "No recovery available. Do factory reset (backup + erase)?"):
            self.factory_reset_flow()

    def reset_master_password_email(self, uname: str):
        cur.execute("SELECT id, email FROM users WHERE username=?", (uname,))
        r = cur.fetchone()
        if not r:
            messagebox.showerror("Not found", "User not found."); return
        uid, email = r
        if not email:
            messagebox.showerror("No email", "No email stored for this user."); return
        otp = "".join(secrets.choice("0123456789") for _ in range(self.otp_length))
        sent = send_email(email, "VSTrustee OTP", f"Your OTP is: {otp}")
        if not sent:
            messagebox.showerror("Email failed", "Could not send OTP. Check SMTP settings."); return
        entered = simpledialog.askstring("Enter OTP", "Enter the OTP sent to your email:")
        if entered != otp:
            messagebox.showerror("Invalid", "OTP incorrect."); return
        self._perform_password_reset(uid)

    def _perform_password_reset(self, uid: int):
        while True:
            p1 = simpledialog.askstring("New Password", "Enter new master password:", show="*")
            if p1 is None: return
            p2 = simpledialog.askstring("Confirm Password", "Confirm new master password:", show="*")
            if p1 == p2 and len(p1) >= 8:
                new_hash = hash_master(p1)
                cur.execute("UPDATE users SET master_hash=? WHERE id=?", (new_hash, uid))
                conn.commit()
                messagebox.showinfo("Success", "Master password reset successfully!"); return
            else:
                messagebox.showwarning("Invalid", "Passwords do not match or too short (min 8).")

    # ---------------- Backup / Restore / Factory ----------------
    def show_backup(self):
        self.clear_content()
        f = Frame(self.content, padx=12, pady=12); f.place(relx=0.12, rely=0.12, relwidth=0.76, relheight=0.76)
        Label(f, text="Backup / Restore", font=("Segoe UI", 16, "bold")).pack(pady=8)
        Button(f, text="Export DB Backup", width=22, command=self.export_db_backup).pack(pady=6)
        Button(f, text="Import DB (restore)", width=22, command=self.import_db_backup).pack(pady=6)
        Button(f, text="Factory Reset (create backup + erase)", width=28, command=self.factory_reset_flow).pack(pady=12)
        Button(f, text="Back", command=self.show_current_page).pack(pady=6)

    def export_db_backup(self):
        dest = filedialog.asksaveasfilename(title="Export DB backup", defaultextension=".db")
        if not dest: return
        try:
            shutil.copy2(DB_PATH, dest); messagebox.showinfo("Exported", f"Backup saved to: {dest}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def import_db_backup(self):
        src = filedialog.askopenfilename(title="Select DB backup to restore")
        if not src: return
        try:
            ts = int(time.time())
            if os.path.exists(DB_PATH):
                shutil.copy2(DB_PATH, DB_PATH + f".pre_restore_{ts}")
            shutil.copy2(src, DB_PATH)
            messagebox.showinfo("Restored", "Backup restored. Restart app to reload DB.")
        except Exception as e:
            messagebox.showerror("Restore failed", str(e))

    def factory_reset_flow(self):
        if not messagebox.askyesno("Factory Reset", "This will create a backup and erase vault. Continue?"):
            return
        ts = int(time.time())
        if os.path.exists(DB_PATH): shutil.copy2(DB_PATH, DB_PATH + f".bak_{ts}")
        if os.path.exists(KEY_PATH): shutil.copy2(KEY_PATH, KEY_PATH + f".bak_{ts}")
        try:
            if os.path.exists(DB_PATH): os.remove(DB_PATH)
            if os.path.exists(KEY_PATH): os.remove(KEY_PATH)
            with open(KEY_PATH, "wb") as f: f.write(Fernet.generate_key())
            # recreate DB and prompt admin creation
            conn2 = sqlite3.connect(DB_PATH); c2 = conn2.cursor()
            c2.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, master_hash BLOB NOT NULL,
                email TEXT, phone TEXT, sec_question TEXT, sec_answer_hash BLOB, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            c2.execute("""CREATE TABLE IF NOT EXISTS vault (
                id INTEGER PRIMARY KEY, user_id INTEGER, site TEXT NOT NULL, login TEXT NOT NULL,
                password_blob BLOB NOT NULL, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            conn2.commit(); conn2.close()
            uname = simpledialog.askstring("New Admin", "New master username:") or "admin"
            while True:
                p1 = simpledialog.askstring("New Password", "Enter new master password:", show="*")
                if p1 is None:
                    messagebox.showinfo("Canceled", "Factory reset canceled."); return
                p2 = simpledialog.askstring("Confirm", "Confirm new master password:", show="*")
                if p1 == p2 and len(p1) >= 8:
                    h = hash_master(p1)
                    conn3 = sqlite3.connect(DB_PATH); c3 = conn3.cursor()
                    c3.execute("INSERT INTO users (username, master_hash) VALUES (?,?)", (uname, h))
                    conn3.commit(); conn3.close(); break
                else:
                    messagebox.showwarning("Invalid", "Passwords do not match or too short.")
            global conn, cur
            try: conn.close()
            except: pass
            conn = sqlite3.connect(DB_PATH, check_same_thread=False); cur = conn.cursor()
            messagebox.showinfo("Done", "Factory reset complete."); self.show_login()
        except Exception as e:
            messagebox.showerror("Factory Reset failed", str(e))

    # ---------------- Settings ----------------
    def show_settings(self):
        win = Toplevel(self.root); win.title("Settings")
        try: win.iconbitmap(ICON_PATH)
        except: pass
        win.geometry("520x520")
        frm = Frame(win, padx=12, pady=12); frm.pack(fill=BOTH, expand=True)
        Label(frm, text="SMTP Server").grid(row=0, column=0, sticky=E, padx=6, pady=6)
        smtp_s = Entry(frm, width=40); smtp_s.grid(row=0, column=1); smtp_s.insert(0, SETTINGS.get("smtp_server", ""))
        Label(frm, text="SMTP Port").grid(row=1, column=0, sticky=E, padx=6, pady=6)
        smtp_p = Entry(frm, width=40); smtp_p.grid(row=1, column=1); smtp_p.insert(0, str(SETTINGS.get("smtp_port", 587)))
        Label(frm, text="SMTP User").grid(row=2, column=0, sticky=E, padx=6, pady=6)
        smtp_u = Entry(frm, width=40); smtp_u.grid(row=2, column=1); smtp_u.insert(0, SETTINGS.get("smtp_user", ""))
        Label(frm, text="SMTP Pass").grid(row=3, column=0, sticky=E, padx=6, pady=6)
        smtp_pw = Entry(frm, width=40, show="*"); smtp_pw.grid(row=3, column=1); smtp_pw.insert(0, SETTINGS.get("smtp_pass", ""))
        Label(frm, text="Email From").grid(row=4, column=0, sticky=E, padx=6, pady=6)
        smtp_from = Entry(frm, width=40); smtp_from.grid(row=4, column=1); smtp_from.insert(0, SETTINGS.get("email_from", ""))
        Label(frm, text="Auto-lock (sec)").grid(row=5, column=0, sticky=E, padx=6, pady=6)
        al = Entry(frm, width=20); al.grid(row=5, column=1, sticky=W); al.insert(0, str(SETTINGS.get("auto_lock_seconds", 300)))
        Label(frm, text="Clipboard clear (sec)").grid(row=6, column=0, sticky=E, padx=6, pady=6)
        cc = Entry(frm, width=20); cc.grid(row=6, column=1, sticky=W); cc.insert(0, str(SETTINGS.get("clipboard_clear_seconds", 10)))
        Label(frm, text="OTP length").grid(row=7, column=0, sticky=E, padx=6, pady=6)
        otp_e = Entry(frm, width=20); otp_e.grid(row=7, column=1, sticky=W); otp_e.insert(0, str(SETTINGS.get("otp_length", 6)))
        # Set / Update Security Question button (for logged-in user)
        Button(frm, text="Set / Update Security Question", width=28, command=self.set_security_question).grid(row=8, column=0, columnspan=2, pady=8)
        def save_settings():
            try:
                SETTINGS["smtp_server"] = smtp_s.get().strip()
                SETTINGS["smtp_port"] = int(smtp_p.get().strip())
                SETTINGS["smtp_user"] = smtp_u.get().strip()
                SETTINGS["smtp_pass"] = smtp_pw.get().strip()
                SETTINGS["email_from"] = smtp_from.get().strip()
                SETTINGS["auto_lock_seconds"] = int(al.get().strip())
                SETTINGS["clipboard_clear_seconds"] = int(cc.get().strip())
                SETTINGS["otp_length"] = int(otp_e.get().strip())
                with open(SETTINGS_PATH, "w") as f:
                    json.dump(SETTINGS, f, indent=2)
                self.auto_lock_seconds = int(SETTINGS.get("auto_lock_seconds", 300))
                self.clipboard_clear_seconds = int(SETTINGS.get("clipboard_clear_seconds", 10))
                messagebox.showinfo("Settings", "Saved"); win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save settings: {e}")
        Button(frm, text="Save Settings", command=save_settings).grid(row=9, column=0, columnspan=2, pady=12)

    def set_security_question(self):
        if not self.user_id:
            messagebox.showwarning("Not Logged In", "You must login first."); return
        questions = [
            "What is your favorite color?",
            "What is your pet’s name?",
            "What city were you born in?",
            "What is your favorite food?",
            "What was your childhood nickname?"
        ]
        # Ask user to choose via index
        choice = simpledialog.askstring("Security Question",
                                        "Choose question number:\n" + "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions)))
        if not choice or not choice.isdigit() or int(choice) not in range(1, len(questions) + 1):
            messagebox.showwarning("Invalid", "Invalid choice."); return
        chosen_q = questions[int(choice) - 1]
        ans = simpledialog.askstring("Security Answer", "Enter your answer (will be stored hashed):", show="*")
        if not ans or len(ans) < 2:
            messagebox.showwarning("Invalid", "Answer too short."); return
        ans_hash = bcrypt.hashpw(ans.lower().encode(), bcrypt.gensalt())
        cur.execute("UPDATE users SET sec_question=?, sec_answer_hash=? WHERE id=?", (chosen_q, ans_hash, self.user_id))
        conn.commit()
        messagebox.showinfo("Saved", "Security question updated.")

    # ---------------- Vault UI & actions ----------------
    def show_vault(self):
        if not self.user_id:
            messagebox.showwarning("Locked", "Please login first."); return
        self.clear_content()
        frame = Frame(self.content, padx=10, pady=10); frame.place(relx=0.02, rely=0.02, relwidth=0.96, relheight=0.96)
        header = Frame(frame); header.pack(fill=X)
        Label(header, text="VSTrustee Vault", font=("Segoe UI", 18, "bold")).pack(side=LEFT)
        Button(header, text="Logout", command=self.logout).pack(side=RIGHT, padx=6)
        Button(header, text="Export CSV", command=self.export_csv).pack(side=RIGHT, padx=6)
        ctrl = Frame(frame); ctrl.pack(fill=X, pady=6)
        Label(ctrl, text="Search:").grid(row=0, column=0, padx=6)
        self.search_e = Entry(ctrl, width=40); self.search_e.grid(row=0, column=1, padx=6)
        Button(ctrl, text="Search", command=self.search).grid(row=0, column=2, padx=6)
        Button(ctrl, text="Show All", command=self.refresh_table).grid(row=0, column=3, padx=6)
        form = Frame(frame); form.pack(fill=X, pady=6)
        Label(form, text="Site:").grid(row=0, column=0, padx=6, pady=4)
        self.site_e = Entry(form, width=36); self.site_e.grid(row=0, column=1, padx=6, pady=4)
        Label(form, text="Login:").grid(row=1, column=0, padx=6, pady=4)
        self.login_e = Entry(form, width=36); self.login_e.grid(row=1, column=1, padx=6, pady=4)
        Label(form, text="Password:").grid(row=2, column=0, padx=6, pady=4)
        self.pass_e = Entry(form, show="*", width=36); self.pass_e.grid(row=2, column=1, padx=6, pady=4)
        Button(form, text="👁️", width=3, command=lambda: self._toggle_entry_eye(self.pass_e)).grid(row=2, column=2, padx=4)
        Button(form, text="Generate", command=self._gen_into_entry).grid(row=2, column=3, padx=6)
        self.str_lbl = Label(form, text="Strength: -"); self.str_lbl.grid(row=3, column=1, sticky=W)
        self.pass_e.bind("<KeyRelease>", lambda e: self.str_lbl.config(text=f"Strength: {password_strength(self.pass_e.get())}"))
        Button(form, text="Add Entry", command=self.add_entry).grid(row=4, column=1, pady=8)
        cols = ("id", "site", "login", "created")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
        for c in cols:
            self.tree.heading(c, text=c.title()); self.tree.column(c, width=240)
        self.tree.pack(fill=BOTH, expand=True, pady=8)
        self.tree.bind("<Double-1>", self.on_row_double)
        btns = Frame(frame); btns.pack(pady=6)
        Button(btns, text="Refresh", command=self.refresh_table).grid(row=0, column=0, padx=6)
        Button(btns, text="View/Edit Selected", command=self.edit_selected).grid(row=0, column=1, padx=6)
        Button(btns, text="Delete Selected", command=self.delete_selected).grid(row=0, column=2, padx=6)
        Button(btns, text="Copy Password", command=self.copy_password).grid(row=0, column=3, padx=6)
        self.refresh_table()

    def _toggle_entry_eye(self, entry_widget):
        if entry_widget.cget("show") == "": entry_widget.configure(show="*")
        else: entry_widget.configure(show="")

    def _gen_into_entry(self):
        p = gen_password(16)
        self.pass_e.delete(0, END); self.pass_e.insert(0, p)
        self.str_lbl.config(text=f"Strength: {password_strength(p)}")

    def add_entry(self):
        site = self.site_e.get().strip(); loginv = self.login_e.get().strip(); pw = self.pass_e.get().strip()
        if not site or not loginv or not pw:
            messagebox.showwarning("Add", "All fields required"); return
        cur.execute("INSERT INTO vault (user_id, site, login, password_blob) VALUES (?,?,?,?)", (self.user_id, site, loginv, encrypt_value(pw)))
        conn.commit(); messagebox.showinfo("Saved", "Entry added")
        self.site_e.delete(0, END); self.login_e.delete(0, END); self.pass_e.delete(0, END); self.refresh_table()

    def refresh_table(self):
        for r in self.tree.get_children(): self.tree.delete(r)
        cur.execute("SELECT id, site, login, password_blob, created_at FROM vault WHERE user_id=?", (self.user_id,))
        rows = cur.fetchall()
        for r in rows:
            vid, site, loginv, blob, created = r
            created_str = (created.split(" ")[0] if isinstance(created, str) else str(created))
            self.tree.insert("", "end", values=(vid, site, loginv, created_str))

    def search(self):
        q = self.search_e.get().strip()
        for r in self.tree.get_children(): self.tree.delete(r)
        cur.execute("SELECT id, site, login, password_blob, created_at FROM vault WHERE user_id=? AND site LIKE ?", (self.user_id, f"%{q}%"))
        rows = cur.fetchall()
        for r in rows:
            vid, site, loginv, blob, created = r
            created_str = (created.split(" ")[0] if isinstance(created, str) else str(created))
            self.tree.insert("", "end", values=(vid, site, loginv, created_str))

    def on_row_double(self, event=None):
        sel = self.tree.selection()
        if not sel: return
        item = self.tree.item(sel[0]); vid = item["values"][0]
        cur.execute("SELECT site, login, password_blob, notes FROM vault WHERE id=?", (vid,))
        row = cur.fetchone()
        if not row: return
        site, loginv, blob, notes = row
        dec = decrypt_value(blob)
        dlg = Toplevel(self.root); dlg.title("View / Edit Entry")
        try: dlg.iconbitmap(ICON_PATH)
        except: pass
        dlg.geometry("520x340")
        Label(dlg, text="Site").pack(pady=4); e1 = Entry(dlg); e1.pack(pady=4); e1.insert(0, site)
        Label(dlg, text="Login").pack(pady=4); e2 = Entry(dlg); e2.pack(pady=4); e2.insert(0, loginv)
        Label(dlg, text="Password").pack(pady=4); e3 = Entry(dlg, show="*"); e3.pack(pady=4); e3.insert(0, dec)
        show_var = IntVar(value=0)
        def toggle_e():
            if show_var.get(): e3.configure(show="*"); show_var.set(0)
            else: e3.configure(show=""); show_var.set(1)
        Button(dlg, text="👁️", width=3, command=toggle_e).pack(pady=4)
        strength_lbl = Label(dlg, text=f"Strength: {password_strength(dec)}"); strength_lbl.pack(pady=2)
        def save():
            s = e1.get().strip(); l = e2.get().strip(); p = e3.get().strip()
            if not s or not l or not p:
                messagebox.showwarning("Save", "All fields required"); return
            cur.execute("UPDATE vault SET site=?, login=?, password_blob=? WHERE id=?", (s, l, encrypt_value(p), vid))
            conn.commit(); messagebox.showinfo("Saved", "Updated"); dlg.destroy(); self.refresh_table()
        def copy_pass():
            pyperclip.copy(dec)
            self.root.after(self.clipboard_clear_seconds * 1000, lambda: pyperclip.copy(""))
            messagebox.showinfo("Copied", "Password copied to clipboard (will clear shortly)")
        Button(dlg, text="Save", command=save).pack(pady=6)
        Button(dlg, text="Copy Password", command=copy_pass).pack(pady=6)

    def edit_selected(self): self.on_row_double()

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel: messagebox.showwarning("Delete", "Select a row"); return
        item = self.tree.item(sel[0]); vid = item["values"][0]
        if messagebox.askyesno("Delete", "Confirm delete?"):
            cur.execute("DELETE FROM vault WHERE id=?", (vid,)); conn.commit(); self.refresh_table()

    def copy_password(self):
        sel = self.tree.selection()
        if not sel: messagebox.showwarning("Copy", "Select a row"); return
        vid = self.tree.item(sel[0])["values"][0]
        cur.execute("SELECT password_blob FROM vault WHERE id=?", (vid,))
        blob = cur.fetchone()[0]; dec = decrypt_value(blob)
        pyperclip.copy(dec)
        self.root.after(self.clipboard_clear_seconds * 1000, lambda: pyperclip.copy(""))
        messagebox.showinfo("Copied", "Password copied to clipboard (auto-clear scheduled)")

    def export_csv(self):
        dest = filedialog.asksaveasfilename(title="Export CSV", defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not dest: return
        try:
            cur.execute("SELECT site, login, password_blob, created_at FROM vault WHERE user_id=?", (self.user_id,))
            rows = cur.fetchall()
            with open(dest, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f); writer.writerow(["site","login","password","created_at"])
                for site, loginv, blob, created in rows:
                    pw = decrypt_value(blob); writer.writerow([site, loginv, pw, created])
            messagebox.showinfo("Export", f"Exported {len(rows)} rows to {dest}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def show_about(self):
        self.clear_content(); f = Frame(self.content); f.place(relx=0.2, rely=0.2, relwidth=0.6, relheight=0.6)
        Label(f, text="VSTrustee", font=("Segoe UI", 20, "bold")).pack(pady=8)
        Label(f, text="A secure password manager — VSTrustee\n\nFeatures: Fernet encryption, bcrypt master, security Q recovery, email OTP fallback, auto-lock, clipboard clear, export, generator, dark mode.", wraplength=520).pack(pady=8)
        Button(f, text="Back", command=self.show_current_page).pack(pady=8)

# ---------------- Run ----------------
def main():
    root = Tk()
    app = VSTrusteeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
