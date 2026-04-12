"""Deterministic task definitions with planted issues for the Code Review environment."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict


# ──────────────────────────────────────────────────────────────────────────────
# EASY TASK — Style violations + unused variable
# A simple utility module with two obvious issues: a PEP8 naming violation
# and an unused variable. Any competent reviewer should catch both.
# ──────────────────────────────────────────────────────────────────────────────

EASY_ORIGINAL = '''\
def calculate_total(items):
    total = 0
    for item in items:
        total += item["price"]
    return total
'''

EASY_MODIFIED = '''\
def CalculateTotal(items):
    total = 0
    unused_var = "debug"
    for item in items:
        total += item["price"]
    return total
'''

EASY_DIFF = '''\
--- a/utils.py
+++ b/utils.py
@@ -1,5 +1,7 @@
-def calculate_total(items):
+def CalculateTotal(items):
     total = 0
+    unused_var = "debug"
     for item in items:
         total += item["price"]
     return total
'''

# ──────────────────────────────────────────────────────────────────────────────
# MEDIUM TASK — Off-by-one logic bug in pagination
# A paginator that slices results incorrectly: uses `page * size` as the start
# index instead of `(page - 1) * size`, causing the first page to be skipped
# and the last page to overflow. Subtle enough to require careful reading.
# ──────────────────────────────────────────────────────────────────────────────

MEDIUM_ORIGINAL = '''\
def paginate(items, page, size):
    """Return a page of items (1-indexed page number)."""
    start = (page - 1) * size
    end = start + size
    return items[start:end]


def get_user_page(users, page, page_size=10):
    return paginate(users, page, page_size)
'''

MEDIUM_MODIFIED = '''\
def paginate(items, page, size):
    """Return a page of items (1-indexed page number)."""
    start = page * size
    end = start + size
    return items[start:end]


def get_user_page(users, page, page_size=10):
    return paginate(users, page, page_size)
'''

MEDIUM_DIFF = '''\
--- a/pagination.py
+++ b/pagination.py
@@ -1,7 +1,7 @@
 def paginate(items, page, size):
     """Return a page of items (1-indexed page number)."""
-    start = (page - 1) * size
+    start = page * size
     end = start + size
     return items[start:end]
 
 
 def get_user_page(users, page, page_size=10):
     return paginate(users, page, page_size)
'''

# ──────────────────────────────────────────────────────────────────────────────
# HARD TASK — SQL injection via f-string + insecure password hashing
# Two security vulnerabilities in a user authentication module:
# 1. SQL injection: user input interpolated directly into a query string
# 2. Weak hashing: MD5 used for password storage (cryptographically broken)
# Both are real CVE-class issues. Frontier models often miss the MD5 issue
# because the code "looks reasonable" at a glance.
# ──────────────────────────────────────────────────────────────────────────────

HARD_ORIGINAL = '''\
import hashlib
import sqlite3


def get_user(db_path: str, username: str):
    """Fetch a user record by username."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (username,),
    )
    row = cursor.fetchone()
    conn.close()
    return row


def hash_password(password: str) -> str:
    """Hash a password for storage."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    return hash_password(password) == stored_hash
'''

HARD_MODIFIED = '''\
import hashlib
import sqlite3


def get_user(db_path: str, username: str):
    """Fetch a user record by username."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT id, username, password_hash FROM users WHERE username = \'{username}\'"
    )
    row = cursor.fetchone()
    conn.close()
    return row


def hash_password(password: str) -> str:
    """Hash a password for storage."""
    return hashlib.md5(password.encode()).hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    return hash_password(password) == stored_hash
'''

HARD_DIFF = '''\
--- a/auth.py
+++ b/auth.py
@@ -5,10 +5,9 @@
 def get_user(db_path: str, username: str):
     """Fetch a user record by username."""
     conn = sqlite3.connect(db_path)
     cursor = conn.cursor()
     cursor.execute(
-        "SELECT id, username, password_hash FROM users WHERE username = ?",
-        (username,),
+        f"SELECT id, username, password_hash FROM users WHERE username = \'{username}\'"
     )
     row = cursor.fetchone()
     conn.close()
@@ -17,6 +16,6 @@
 
 def hash_password(password: str) -> str:
     """Hash a password for storage."""
-    return hashlib.sha256(password.encode()).hexdigest()
+    return hashlib.md5(password.encode()).hexdigest()
 
 
 def verify_password(password: str, stored_hash: str) -> bool:
'''


TASKS: Dict[str, dict] = {
    "easy": {
        "task_id": "easy",
        "pr_title": "Refactor: rename calculate_total utility function",
        "pr_description": (
            "Renames the calculate_total function and adds a debug variable "
            "during development. Ready for review."
        ),
        "files": [
            {
                "filename": "utils.py",
                "language": "python",
                "original": EASY_ORIGINAL,
                "modified": EASY_MODIFIED,
                "diff": EASY_DIFF,
            }
        ],
        "planted_issues": [
            {
                "issue_id": "easy-1",
                "filename": "utils.py",
                "line_start": 1,
                "line_end": 1,
                "severity": "warning",
                "category": "style",
                "description": "Function name 'CalculateTotal' violates PEP8 snake_case convention",
                "fix_hint": "Rename to 'calculate_total'",
            },
            {
                "issue_id": "easy-2",
                "filename": "utils.py",
                "line_start": 3,
                "line_end": 3,
                "severity": "info",
                "category": "maintainability",
                "description": "Variable 'unused_var' is assigned but never used",
                "fix_hint": "Remove the unused variable",
            },
        ],
        "max_steps": 5,
    },
    "medium": {
        "task_id": "medium",
        "pr_title": "Fix: update pagination logic for user listing endpoint",
        "pr_description": (
            "Updates the paginate() helper to use a simpler index calculation. "
            "Tested manually on the staging environment."
        ),
        "files": [
            {
                "filename": "pagination.py",
                "language": "python",
                "original": MEDIUM_ORIGINAL,
                "modified": MEDIUM_MODIFIED,
                "diff": MEDIUM_DIFF,
            }
        ],
        "planted_issues": [
            {
                "issue_id": "medium-1",
                "filename": "pagination.py",
                "line_start": 3,
                "line_end": 3,
                "severity": "error",
                "category": "logic",
                "description": (
                    "Off-by-one bug: start index uses 'page * size' instead of "
                    "'(page - 1) * size', causing page 1 to skip the first 'size' items"
                ),
                "fix_hint": "Change 'start = page * size' back to 'start = (page - 1) * size'",
            },
        ],
        "max_steps": 5,
    },
    "hard": {
        "task_id": "hard",
        "pr_title": "Perf: simplify auth query and speed up password hashing",
        "pr_description": (
            "Simplifies the database query by inlining the username directly "
            "and switches to MD5 for faster password hashing in high-traffic scenarios."
        ),
        "files": [
            {
                "filename": "auth.py",
                "language": "python",
                "original": HARD_ORIGINAL,
                "modified": HARD_MODIFIED,
                "diff": HARD_DIFF,
            }
        ],
        "planted_issues": [
            {
                "issue_id": "hard-1",
                "filename": "auth.py",
                "line_start": 9,
                "line_end": 10,
                "severity": "critical",
                "category": "security",
                "description": (
                    "SQL injection vulnerability: username is interpolated directly "
                    "into the query string via an f-string. An attacker can manipulate "
                    "the query to bypass authentication or exfiltrate data."
                ),
                "fix_hint": "Use parameterized queries: cursor.execute('... WHERE username = ?', (username,))",
            },
            {
                "issue_id": "hard-2",
                "filename": "auth.py",
                "line_start": 19,
                "line_end": 19,
                "severity": "critical",
                "category": "security",
                "description": (
                    "MD5 is cryptographically broken and must not be used for password hashing. "
                    "It is vulnerable to collision attacks and rainbow table attacks."
                ),
                "fix_hint": "Use bcrypt, argon2, or at minimum hashlib.sha256 with a salt",
            },
        ],
        "max_steps": 6,
    },
}


def get_task(task_id: str) -> dict:
    if task_id not in TASKS:
        raise KeyError(f"Unknown task_id: {task_id!r}. Valid: {list(TASKS)}")
    return deepcopy(TASKS[task_id])


#  EXPERT task 
_EXPERT_STORAGE_ORIGINAL = """\
import os, shutil
from validator import is_safe_filename
UPLOAD_DIR = "/var/uploads"
def save_upload(filename, tmp_path):
    if not is_safe_filename(filename):
        raise ValueError(f"Unsafe filename: {filename}")
    dest = os.path.join(UPLOAD_DIR, filename)
    shutil.move(tmp_path, dest)
    return dest
"""
_EXPERT_STORAGE_MODIFIED = """\
import os, shutil
from validator import is_safe_filename
UPLOAD_DIR = "/var/uploads"
def save_upload(filename, tmp_path):
    if not is_safe_filename(filename):
        raise ValueError(f"Unsafe filename: {filename}")
    dest = os.path.realpath(os.path.join(UPLOAD_DIR, filename))
    shutil.move(tmp_path, dest)
    return dest
"""
_EXPERT_STORAGE_DIFF = "--- a/storage.py\n+++ b/storage.py\n@@ -7 +7 @@\n-    dest = os.path.join(UPLOAD_DIR, filename)\n+    dest = os.path.realpath(os.path.join(UPLOAD_DIR, filename))\n"
_EXPERT_VALIDATOR_ORIGINAL = """\
import os, re
ALLOWED_EXTENSIONS = {".jpg",".jpeg",".png",".gif",".pdf"}
def is_safe_filename(filename):
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        return False
    if re.search(r"[/\\\x00]", filename):
        return False
    return True
"""
_EXPERT_VALIDATOR_DIFF = "--- a/validator.py\n+++ b/validator.py\n  (no changes)\n"

#  ADVERSARIAL task 
_ADV_API_ORIGINAL = """\
from flask import Flask, jsonify, request, abort
from functools import wraps
import time
app = Flask(__name__)
_rate_store = {}
def rate_limit(n=60):
    def d(f):
        @wraps(f)
        def w(*a,**k):
            key=request.remote_addr; now=__import__("time").time()
            hits=[t for t in _rate_store.get(key,[]) if now-t<60]
            if len(hits)>=n: abort(429)
            _rate_store[key]=hits+[now]; return f(*a,**k)
        return w
    return d
def get_document(doc_id, db):
    return db.query("SELECT * FROM documents WHERE id = ?", (doc_id,))
@app.route("/api/documents/<int:doc_id>")
@rate_limit(30)
def document_handler(doc_id):
    user_id=request.headers.get("X-User-Id")
    doc=get_document(doc_id,app.db)
    if doc is None: abort(404)
    if str(doc["owner_id"])!=str(user_id): abort(403)
    return jsonify(doc)
"""
_ADV_API_MODIFIED = """\
from flask import Flask, jsonify, request, abort
app = Flask(__name__)
def get_document(doc_id, db):
    return db.query("SELECT * FROM documents WHERE id = ?", (doc_id,))
@app.route("/api/documents/<int:doc_id>")
def document_handler(doc_id):
    doc=get_document(doc_id,app.db)
    if doc is None: abort(404)
    return jsonify(doc)
"""
_ADV_API_DIFF = "--- a/api.py\n+++ b/api.py\n@@ removed rate_limit and ownership check @@\n"
_ADV_MODELS_ORIGINAL = """\
from dataclasses import dataclass
@dataclass
class Document:
    id: int; owner_id: int; title: str; content: str; is_public: bool = False
"""
_ADV_MODELS_DIFF = "--- a/models.py\n+++ b/models.py\n  (no changes)\n"

CANNED_ANSWERS = {
    "easy": {"default": "Utility module, no external callers depend on the function name yet."},
    "medium": {"default": "Pages are 1-indexed. Page 1 returns items 0 through size-1."},
    "hard": {"default": "Auth module used in production with real user credentials."},
    "expert": {
        "default": "Upload directory is world-readable, served directly via nginx.",
        "symlink": "Linux server. Symlinks in the upload directory are followed by nginx.",
    },
    "adversarial": {
        "default": "Private documents should only be accessible to their owner.",
        "rate": "This endpoint is publicly accessible without authentication.",
    },
}

TASKS["expert"] = {
    "task_id": "expert",
    "pr_title": "Fix: resolve symlinks before writing uploaded files",
    "pr_description": "Adds os.path.realpath() to resolve symlinks. Prevents symlink traversal. Validator unchanged.",
    "files": [
        {"filename": "storage.py", "language": "python", "original": _EXPERT_STORAGE_ORIGINAL, "modified": _EXPERT_STORAGE_MODIFIED, "diff": _EXPERT_STORAGE_DIFF},
        {"filename": "validator.py", "language": "python", "original": _EXPERT_VALIDATOR_ORIGINAL, "modified": _EXPERT_VALIDATOR_ORIGINAL, "diff": _EXPERT_VALIDATOR_DIFF},
    ],
    "planted_issues": [
        {"issue_id": "expert-1", "filename": "storage.py", "line_start": 7, "line_end": 9, "severity": "critical", "category": "security",
         "description": "TOCTOU race condition: is_safe_filename() checks original filename but realpath resolves after the check. Attacker can swap file with symlink between check and write (CWE-367).",
         "fix_hint": "Resolve realpath first, then verify it starts with UPLOAD_DIR using os.path.commonpath."},
        {"issue_id": "expert-2", "filename": "validator.py", "line_start": 1, "line_end": 9, "severity": "warning", "category": "security",
         "description": "Validator checks filename extension but not resolved path. A safe-looking filename can be a symlink pointing outside UPLOAD_DIR.",
         "fix_hint": "Validate os.path.realpath(filename) is within UPLOAD_DIR after resolution."},
    ],
    "false_positive_targets": [],
    "priority_issue_ids": ["expert-1"],
    "max_steps": 7,
}

TASKS["adversarial"] = {
    "task_id": "adversarial",
    "pr_title": "Refactor: simplify document handler, remove redundant checks",
    "pr_description": "Removes rate limiter (replaced by nginx) and ownership check (handled by DB view layer). Reduces boilerplate.",
    "files": [
        {"filename": "api.py", "language": "python", "original": _ADV_API_ORIGINAL, "modified": _ADV_API_MODIFIED, "diff": _ADV_API_DIFF},
        {"filename": "models.py", "language": "python", "original": _ADV_MODELS_ORIGINAL, "modified": _ADV_MODELS_ORIGINAL, "diff": _ADV_MODELS_DIFF},
    ],
    "planted_issues": [
        {"issue_id": "adv-1", "filename": "api.py", "line_start": 7, "line_end": 9, "severity": "critical", "category": "security",
         "description": "IDOR vulnerability: ownership check removed. Any user can read any document by guessing its ID. PR description falsely claims DB view layer handles this.",
         "fix_hint": "Restore: if str(doc['owner_id']) != str(user_id): abort(403)"},
        {"issue_id": "adv-2", "filename": "api.py", "line_start": 6, "line_end": 6, "severity": "error", "category": "security",
         "description": "Rate limiting removed from sensitive public endpoint. No evidence nginx handles this. Enables enumeration and brute-force attacks.",
         "fix_hint": "Restore @rate_limit(30) decorator or confirm nginx config in a separate PR."},
    ],
    "false_positive_targets": [
        {"filename": "api.py", "line_start": 1, "line_end": 2, "description": "Import statements are not issues"},
    ],
    "priority_issue_ids": ["adv-1", "adv-2"],
    "max_steps": 8,
}


def get_canned_answer(task_id: str, question: str) -> str:
    """Return a deterministic canned answer for a clarifying question."""
    answers = CANNED_ANSWERS.get(task_id, {})
    q_lower = question.lower()
    for keyword, answer in answers.items():
        if keyword != "default" and keyword in q_lower:
            return answer
    return answers.get("default", "No additional context available for this PR.")


# ──────────────────────────────────────────────────────────────────────────────
# JWT_BYPASS — alg:none attack + weak secret
# A JWT middleware is refactored to "support multiple algorithms" but now
# accepts alg:none (unsigned tokens). The secret is also hardcoded.
# ──────────────────────────────────────────────────────────────────────────────
_JWT_MIDDLEWARE_ORIGINAL = """\
import jwt
SECRET = os.environ.get("JWT_SECRET", "")
def verify_token(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"])
"""
_JWT_MIDDLEWARE_MODIFIED = """\
import jwt
SECRET = "supersecret123"
def verify_token(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "HS256")
    if alg == "none":
        return jwt.decode(token, options={"verify_signature": False})
    return jwt.decode(token, SECRET, algorithms=[alg])
"""
_JWT_MIDDLEWARE_DIFF = """\
--- a/middleware.py
+++ b/middleware.py
@@ -1,4 +1,8 @@
 import jwt
-SECRET = os.environ.get("JWT_SECRET", "")
-def verify_token(token: str) -> dict:
-    return jwt.decode(token, SECRET, algorithms=["HS256"])
+SECRET = "supersecret123"
+def verify_token(token: str) -> dict:
+    header = jwt.get_unverified_header(token)
+    alg = header.get("alg", "HS256")
+    if alg == "none":
+        return jwt.decode(token, options={"verify_signature": False})
+    return jwt.decode(token, SECRET, algorithms=[alg])
"""

TASKS["jwt_bypass"] = {
    "task_id": "jwt_bypass",
    "pr_title": "Feat: support flexible JWT algorithm negotiation",
    "pr_description": "Updates JWT verification to support multiple signing algorithms based on the token header. Also inlines the secret for easier local dev.",
    "files": [
        {"filename": "middleware.py", "language": "python",
         "original": _JWT_MIDDLEWARE_ORIGINAL, "modified": _JWT_MIDDLEWARE_MODIFIED, "diff": _JWT_MIDDLEWARE_DIFF},
    ],
    "planted_issues": [
        {"issue_id": "jwt-1", "filename": "middleware.py", "line_start": 5, "line_end": 7,
         "severity": "critical", "category": "security",
         "description": "JWT alg:none attack: accepting algorithm from token header allows attacker to forge unsigned tokens and bypass authentication entirely (CVE-2015-9235).",
         "fix_hint": "Never trust the alg field from the token. Always specify allowed algorithms explicitly: jwt.decode(token, SECRET, algorithms=['HS256'])"},
        {"issue_id": "jwt-2", "filename": "middleware.py", "line_start": 2, "line_end": 2,
         "severity": "critical", "category": "security",
         "description": "Hardcoded JWT secret in source code. Anyone with repo access can forge valid tokens. Secret must come from environment variables.",
         "fix_hint": "Use os.environ.get('JWT_SECRET') and raise an error if not set."},
    ],
    "false_positive_targets": [],
    "priority_issue_ids": ["jwt-1"],
    "max_steps": 6,
}

CANNED_ANSWERS["jwt_bypass"] = {
    "default": "This service is used for user authentication across all microservices.",
    "algorithm": "Tokens are generated by a third-party identity provider.",
}

# ──────────────────────────────────────────────────────────────────────────────
# PATH_TRAVERSAL — directory traversal via unsanitized filename
# A file download endpoint uses user-supplied filename directly in os.path.join,
# allowing traversal outside the intended directory.
# ──────────────────────────────────────────────────────────────────────────────
_PATH_ORIGINAL = """\
import os
from flask import Flask, send_file, abort
app = Flask(__name__)
FILES_DIR = "/var/app/files"

@app.route("/download/<path:filename>")
def download(filename):
    safe_path = os.path.join(FILES_DIR, filename)
    if not os.path.exists(safe_path):
        abort(404)
    return send_file(safe_path)
"""
_PATH_MODIFIED = """\
import os
from flask import Flask, send_file, abort, request
app = Flask(__name__)
FILES_DIR = "/var/app/files"

@app.route("/download")
def download():
    filename = request.args.get("file", "")
    safe_path = os.path.join(FILES_DIR, filename)
    if not os.path.exists(safe_path):
        abort(404)
    return send_file(safe_path)
"""
_PATH_DIFF = """\
--- a/download.py
+++ b/download.py
@@ -5,7 +5,8 @@
-@app.route("/download/<path:filename>")
-def download(filename):
-    safe_path = os.path.join(FILES_DIR, filename)
+@app.route("/download")
+def download():
+    filename = request.args.get("file", "")
+    safe_path = os.path.join(FILES_DIR, filename)
     if not os.path.exists(safe_path):
         abort(404)
     return send_file(safe_path)
"""

TASKS["path_traversal"] = {
    "task_id": "path_traversal",
    "pr_title": "Refactor: move filename to query param for flexibility",
    "pr_description": "Changes the download endpoint to accept filename as a query parameter instead of a path segment. Cleaner URL structure.",
    "files": [
        {"filename": "download.py", "language": "python",
         "original": _PATH_ORIGINAL, "modified": _PATH_MODIFIED, "diff": _PATH_DIFF},
    ],
    "planted_issues": [
        {"issue_id": "path-1", "filename": "download.py", "line_start": 8, "line_end": 9,
         "severity": "critical", "category": "security",
         "description": "Path traversal vulnerability: user-supplied filename is joined directly with FILES_DIR without sanitization. Attacker can use ../../etc/passwd to read arbitrary files.",
         "fix_hint": "Use os.path.realpath and verify the result starts with FILES_DIR: assert os.path.commonpath([real, FILES_DIR]) == FILES_DIR"},
    ],
    "false_positive_targets": [],
    "priority_issue_ids": ["path-1"],
    "max_steps": 5,
}

CANNED_ANSWERS["path_traversal"] = {
    "default": "The server runs as root for legacy reasons. FILES_DIR contains only public assets.",
    "traversal": "No WAF or reverse proxy is in front of this endpoint.",
}

# ──────────────────────────────────────────────────────────────────────────────
# CRYPTO_FAIL — ECB mode encryption + static IV
# A data encryption module switches from AES-GCM to AES-ECB "for simplicity"
# and uses a hardcoded static IV in another function.
# ──────────────────────────────────────────────────────────────────────────────
_CRYPTO_ORIGINAL = """\
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import base64

KEY = get_random_bytes(32)

def encrypt(data: bytes) -> str:
    iv = get_random_bytes(16)
    cipher = AES.new(KEY, AES.MODE_GCM, nonce=iv)
    ciphertext, tag = cipher.encrypt_and_digest(data)
    return base64.b64encode(iv + tag + ciphertext).decode()

def decrypt(token: str) -> bytes:
    raw = base64.b64decode(token)
    iv, tag, ciphertext = raw[:16], raw[16:32], raw[32:]
    cipher = AES.new(KEY, AES.MODE_GCM, nonce=iv)
    return cipher.decrypt_and_verify(ciphertext, tag)
"""
_CRYPTO_MODIFIED = """\
from Crypto.Cipher import AES
import base64

KEY = b"hardcoded_key_32"

def encrypt(data: bytes) -> str:
    padded = data + b" " * (16 - len(data) % 16)
    cipher = AES.new(KEY, AES.MODE_ECB)
    return base64.b64encode(cipher.encrypt(padded)).decode()

def decrypt(token: str) -> bytes:
    cipher = AES.new(KEY, AES.MODE_ECB)
    return cipher.decrypt(base64.b64decode(token)).rstrip(b" ")
"""
_CRYPTO_DIFF = """\
--- a/crypto.py
+++ b/crypto.py
@@ -1,17 +1,11 @@
 from Crypto.Cipher import AES
-from Crypto.Random import get_random_bytes
 import base64
-KEY = get_random_bytes(32)
-def encrypt(data: bytes) -> str:
-    iv = get_random_bytes(16)
-    cipher = AES.new(KEY, AES.MODE_GCM, nonce=iv)
-    ciphertext, tag = cipher.encrypt_and_digest(data)
-    return base64.b64encode(iv + tag + ciphertext).decode()
-def decrypt(token: str) -> bytes:
-    raw = base64.b64decode(token)
-    iv, tag, ciphertext = raw[:16], raw[16:32], raw[32:]
-    cipher = AES.new(KEY, AES.MODE_GCM, nonce=iv)
-    return cipher.decrypt_and_verify(ciphertext, tag)
+KEY = b"hardcoded_key_32"
+def encrypt(data: bytes) -> str:
+    padded = data + b" " * (16 - len(data) % 16)
+    cipher = AES.new(KEY, AES.MODE_ECB)
+    return base64.b64encode(cipher.encrypt(padded)).decode()
+def decrypt(token: str) -> bytes:
+    cipher = AES.new(KEY, AES.MODE_ECB)
+    return cipher.decrypt(base64.b64decode(token)).rstrip(b" ")
"""

TASKS["crypto_fail"] = {
    "task_id": "crypto_fail",
    "pr_title": "Perf: simplify encryption module, remove GCM overhead",
    "pr_description": "Switches from AES-GCM to AES-ECB for faster encryption. GCM overhead was causing latency in bulk operations. Also inlines the key for easier testing.",
    "files": [
        {"filename": "crypto.py", "language": "python",
         "original": _CRYPTO_ORIGINAL, "modified": _CRYPTO_MODIFIED, "diff": _CRYPTO_DIFF},
    ],
    "planted_issues": [
        {"issue_id": "crypto-1", "filename": "crypto.py", "line_start": 7, "line_end": 9,
         "severity": "critical", "category": "security",
         "description": "AES-ECB mode is insecure: identical plaintext blocks produce identical ciphertext blocks, leaking data patterns. ECB must never be used for sensitive data encryption.",
         "fix_hint": "Use AES-GCM or AES-CBC with a random IV. GCM also provides authentication."},
        {"issue_id": "crypto-2", "filename": "crypto.py", "line_start": 4, "line_end": 4,
         "severity": "critical", "category": "security",
         "description": "Hardcoded encryption key in source code. Key is static and exposed to anyone with repo access. Rotating the key requires a code change and redeploy.",
         "fix_hint": "Load key from environment: KEY = base64.b64decode(os.environ['ENCRYPTION_KEY'])"},
    ],
    "false_positive_targets": [],
    "priority_issue_ids": ["crypto-1"],
    "max_steps": 6,
}

CANNED_ANSWERS["crypto_fail"] = {
    "default": "This module encrypts PII including SSNs and credit card numbers before storing in the database.",
    "ecb": "The data being encrypted includes user profile photos and structured JSON records.",
}

# ──────────────────────────────────────────────────────────────────────────────
# SSRF — Server-Side Request Forgery via unvalidated URL fetch
# An internal webhook handler fetches a user-supplied URL without validation,
# allowing attackers to probe internal services and cloud metadata endpoints.
# ──────────────────────────────────────────────────────────────────────────────
_SSRF_ORIGINAL = """\
import requests
from flask import Flask, request, jsonify
app = Flask(__name__)
ALLOWED_DOMAINS = ["api.github.com", "hooks.slack.com"]

def fetch_webhook_payload(url: str) -> dict:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.hostname not in ALLOWED_DOMAINS:
        raise ValueError(f"Domain not allowed: {parsed.hostname}")
    resp = requests.get(url, timeout=5)
    return resp.json()

@app.route("/webhook/register", methods=["POST"])
def register_webhook():
    url = request.json.get("callback_url")
    data = fetch_webhook_payload(url)
    return jsonify({"status": "registered", "data": data})
"""
_SSRF_MODIFIED = """\
import requests
from flask import Flask, request, jsonify
app = Flask(__name__)

def fetch_webhook_payload(url: str) -> dict:
    resp = requests.get(url, timeout=10)
    return resp.json()

@app.route("/webhook/register", methods=["POST"])
def register_webhook():
    url = request.json.get("callback_url")
    if not url:
        return jsonify({"error": "callback_url required"}), 400
    data = fetch_webhook_payload(url)
    return jsonify({"status": "registered", "data": data})
"""
_SSRF_DIFF = """\
--- a/webhook.py
+++ b/webhook.py
@@ -1,16 +1,14 @@
 import requests
 from flask import Flask, request, jsonify
 app = Flask(__name__)
-ALLOWED_DOMAINS = ["api.github.com", "hooks.slack.com"]
-def fetch_webhook_payload(url: str) -> dict:
-    from urllib.parse import urlparse
-    parsed = urlparse(url)
-    if parsed.hostname not in ALLOWED_DOMAINS:
-        raise ValueError(f"Domain not allowed: {parsed.hostname}")
-    resp = requests.get(url, timeout=5)
-    return resp.json()
+def fetch_webhook_payload(url: str) -> dict:
+    resp = requests.get(url, timeout=10)
+    return resp.json()
 @app.route("/webhook/register", methods=["POST"])
 def register_webhook():
     url = request.json.get("callback_url")
+    if not url:
+        return jsonify({"error": "callback_url required"}), 400
     data = fetch_webhook_payload(url)
     return jsonify({"status": "registered", "data": data})
"""

TASKS["ssrf"] = {
    "task_id": "ssrf",
    "pr_title": "Refactor: simplify webhook registration, remove domain whitelist",
    "pr_description": "Removes the domain allowlist from webhook registration — it was blocking legitimate third-party integrations. Added null check for callback_url instead.",
    "files": [
        {"filename": "webhook.py", "language": "python",
         "original": _SSRF_ORIGINAL, "modified": _SSRF_MODIFIED, "diff": _SSRF_DIFF},
    ],
    "planted_issues": [
        {"issue_id": "ssrf-1", "filename": "webhook.py", "line_start": 5, "line_end": 7,
         "severity": "critical", "category": "security",
         "description": "SSRF vulnerability: domain allowlist removed. Attacker can supply http://169.254.169.254/latest/meta-data/ to access AWS instance metadata, internal services, or localhost endpoints.",
         "fix_hint": "Restore domain allowlist or use a DNS rebinding-safe HTTP client that blocks private IP ranges (10.x, 172.16.x, 192.168.x, 169.254.x)."},
    ],
    "false_positive_targets": [
        {"filename": "webhook.py", "line_start": 11, "line_end": 13, "description": "Null check is a valid improvement, not an issue"},
    ],
    "priority_issue_ids": ["ssrf-1"],
    "max_steps": 5,
}

CANNED_ANSWERS["ssrf"] = {
    "default": "This service runs on AWS EC2. The webhook endpoint is publicly accessible.",
    "internal": "There are internal microservices on the 10.0.0.0/8 subnet accessible from this host.",
    "metadata": "The instance metadata service is enabled and not restricted by IMDSv2.",
}

# ──────────────────────────────────────────────────────────────────────────────
# DESERIALIZATION — Insecure pickle deserialization + command injection
# A caching layer switches from JSON to pickle for "performance", and a
# subprocess call uses shell=True with user input.
# ──────────────────────────────────────────────────────────────────────────────
_DESER_ORIGINAL = """\
import json
import subprocess
import redis

cache = redis.Redis()

def get_cached(key: str):
    raw = cache.get(key)
    if raw is None:
        return None
    return json.loads(raw)

def set_cached(key: str, value) -> None:
    cache.set(key, json.dumps(value), ex=3600)

def run_report(report_name: str) -> str:
    allowed = ["daily", "weekly", "monthly"]
    if report_name not in allowed:
        raise ValueError("Invalid report name")
    result = subprocess.run(["python", "reports/" + report_name + ".py"],
                            capture_output=True, text=True)
    return result.stdout
"""
_DESER_MODIFIED = """\
import pickle
import subprocess
import redis

cache = redis.Redis()

def get_cached(key: str):
    raw = cache.get(key)
    if raw is None:
        return None
    return pickle.loads(raw)

def set_cached(key: str, value) -> None:
    cache.set(key, pickle.dumps(value), ex=3600)

def run_report(report_name: str) -> str:
    result = subprocess.run(f"python reports/{report_name}.py",
                            shell=True, capture_output=True, text=True)
    return result.stdout
"""
_DESER_DIFF = """\
--- a/cache.py
+++ b/cache.py
@@ -1,20 +1,16 @@
-import json
+import pickle
 import subprocess
 import redis
 cache = redis.Redis()
 def get_cached(key: str):
     raw = cache.get(key)
     if raw is None:
         return None
-    return json.loads(raw)
+    return pickle.loads(raw)
 def set_cached(key: str, value) -> None:
-    cache.set(key, json.dumps(value), ex=3600)
+    cache.set(key, pickle.dumps(value), ex=3600)
 def run_report(report_name: str) -> str:
-    allowed = ["daily", "weekly", "monthly"]
-    if report_name not in allowed:
-        raise ValueError("Invalid report name")
-    result = subprocess.run(["python", "reports/" + report_name + ".py"],
-                            capture_output=True, text=True)
+    result = subprocess.run(f"python reports/{report_name}.py",
+                            shell=True, capture_output=True, text=True)
     return result.stdout
"""

TASKS["deserialization"] = {
    "task_id": "deserialization",
    "pr_title": "Perf: switch cache serialization to pickle, simplify report runner",
    "pr_description": "Replaces JSON with pickle for faster cache serialization. Also simplifies the report runner by removing the allowlist — reports are internal only.",
    "files": [
        {"filename": "cache.py", "language": "python",
         "original": _DESER_ORIGINAL, "modified": _DESER_MODIFIED, "diff": _DESER_DIFF},
    ],
    "planted_issues": [
        {"issue_id": "deser-1", "filename": "cache.py", "line_start": 11, "line_end": 11,
         "severity": "critical", "category": "security",
         "description": "Insecure deserialization: pickle.loads on data from Redis allows remote code execution if an attacker can write to the cache. Pickle can execute arbitrary Python during deserialization.",
         "fix_hint": "Use json.loads instead of pickle.loads. If complex objects are needed, use a safe serialization library like msgpack or orjson."},
        {"issue_id": "deser-2", "filename": "cache.py", "line_start": 16, "line_end": 17,
         "severity": "critical", "category": "security",
         "description": "Command injection via shell=True with unsanitized report_name. Attacker can pass 'daily; rm -rf /' as report_name. The allowlist was removed in this PR.",
         "fix_hint": "Remove shell=True and pass arguments as a list. Restore the allowlist: if report_name not in ['daily','weekly','monthly']: raise ValueError"},
    ],
    "false_positive_targets": [],
    "priority_issue_ids": ["deser-1", "deser-2"],
    "max_steps": 7,
}

CANNED_ANSWERS["deserialization"] = {
    "default": "Redis is shared between multiple services and is accessible from the internal network.",
    "pickle": "The cache stores user session objects and query result sets.",
    "shell": "The report_name parameter comes from a user-facing API endpoint.",
}
