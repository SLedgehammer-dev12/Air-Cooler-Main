import hashlib
import json
import os
from datetime import datetime, timezone

from pathlib import Path

def _now():
    return datetime.now(timezone.utc).isoformat()

PBKDF2_ITERATIONS = 100_000
DEFAULT_PASSWORDS = {"admin123", "user123"}
LEGACY_HASH_PREFIX = "sha256_"
PBKDF2_PREFIX = "pbkdf2_"


def generate_salt():
    return os.urandom(16).hex()


def _pbkdf2_hash(password, salt):
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS)
    return PBKDF2_PREFIX + key.hex()


def _legacy_hash(password, salt):
    return LEGACY_HASH_PREFIX + hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def hash_password(password, salt):
    return _pbkdf2_hash(password, salt)


def verify_password(password, salt, stored_hash):
    if stored_hash.startswith(PBKDF2_PREFIX):
        computed = _pbkdf2_hash(password, salt)
    else:
        raw_stored = stored_hash.replace(LEGACY_HASH_PREFIX, "", 1)
        computed = _pbkdf2_hash(password, salt)
        old_style = LEGACY_HASH_PREFIX + hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
        if old_style == stored_hash:
            return True
    return computed == stored_hash


def is_default_password(password):
    return password in DEFAULT_PASSWORDS


def _default_users():
    admin_salt = generate_salt()
    user_salt = generate_salt()
    ts = _now()
    return {
        "admin": {
            "salt": admin_salt,
            "hash": hash_password("admin123", admin_salt),
            "role": "admin",
            "email": "admin@aircooler.local",
            "display_name": "Administrator",
            "created_at": ts,
            "last_login": None,
        },
        "user": {
            "salt": user_salt,
            "hash": hash_password("user123", user_salt),
            "role": "user",
            "email": "user@aircooler.local",
            "display_name": "Default User",
            "created_at": ts,
            "last_login": None,
        },
    }


def _migrate_legacy_user(entry):
    raw_hash = entry.get("hash", "")
    if raw_hash and not raw_hash.startswith(LEGACY_HASH_PREFIX) and not raw_hash.startswith(PBKDF2_PREFIX):
        entry["hash"] = LEGACY_HASH_PREFIX + raw_hash
    entry.setdefault("email", "")
    entry.setdefault("display_name", "")
    entry.setdefault("created_at", _now())
    entry.setdefault("last_login", None)
    return entry


def initialize_users_db(db_path):
    path = Path(db_path)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            users = {}
            for uname, info in raw.items():
                users[uname] = _migrate_legacy_user(info)
            return users
        except Exception:
            pass
    users = _default_users()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return users


def _save_db(users_db, db_path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(users_db, indent=2, ensure_ascii=False), encoding="utf-8")


def authenticate_user(username, password, users_db):
    user_info = users_db.get(username.strip())
    if not user_info:
        return False, None
    salt = user_info.get("salt", "")
    stored = user_info.get("hash", "")
    if verify_password(password, salt, stored):
        return True, user_info.get("role", "user")
    return False, None


def change_password(username, old_password, new_password, users_db, db_path):
    user_info = users_db.get(username.strip())
    if not user_info:
        return False, "Kullanıcı bulunamadı."
    salt = user_info.get("salt", "")
    stored = user_info.get("hash", "")
    if not verify_password(old_password, salt, stored):
        return False, "Mevcut şifre hatalı."
    new_salt = generate_salt()
    user_info["salt"] = new_salt
    user_info["hash"] = hash_password(new_password, new_salt)
    try:
        _save_db(users_db, db_path)
        return True, "Şifre başarıyla değiştirildi."
    except Exception as e:
        return False, f"Şifre kaydedilemedi: {e}"


def validate_password(password):
    if not password or len(password) < 6:
        return False, "Şifre en az 6 karakter olmalıdır."
    return True, ""


def register_user(username, password, email, users_db, db_path):
    uname = username.strip()
    if not uname:
        return False, "Kullanıcı adı boş olamaz."
    if uname in users_db:
        return False, "Bu kullanıcı adı zaten mevcut."
    valid, msg = validate_password(password)
    if not valid:
        return False, msg
    salt = generate_salt()
    ts = _now()
    users_db[uname] = {
        "salt": salt,
        "hash": hash_password(password, salt),
        "role": "user",
        "email": email.strip(),
        "display_name": uname,
        "created_at": ts,
        "last_login": None,
    }
    try:
        _save_db(users_db, db_path)
        return True, "Kullanıcı başarıyla oluşturuldu."
    except Exception as e:
        users_db.pop(uname, None)
        return False, f"Kullanıcı kaydedilemedi: {e}"


def delete_user(username, users_db, db_path):
    if username not in users_db:
        return False, "Kullanıcı bulunamadı."
    if username == "admin":
        return False, "admin kullanıcısı silinemez."
    del users_db[username]
    try:
        _save_db(users_db, db_path)
        return True, f"Kullanıcı '{username}' silindi."
    except Exception as e:
        return False, f"Kullanıcı silinemedi: {e}"


def update_user_role(username, new_role, users_db, db_path):
    if username not in users_db:
        return False, "Kullanıcı bulunamadı."
    if new_role not in ("admin", "user"):
        return False, "Geçersiz rol. admin veya user olmalı."
    users_db[username]["role"] = new_role
    try:
        _save_db(users_db, db_path)
        return True, f"'{username}' rolü '{new_role}' olarak güncellendi."
    except Exception as e:
        return False, f"Rol güncellenemedi: {e}"


def list_users(users_db):
    result = []
    for uname, info in users_db.items():
        result.append({
            "username": uname,
            "role": info.get("role", "user"),
            "email": info.get("email", ""),
            "display_name": info.get("display_name", uname),
            "created_at": info.get("created_at", ""),
            "last_login": info.get("last_login", ""),
        })
    result.sort(key=lambda x: x["username"])
    return result


def update_last_login(username, users_db, db_path):
    if username in users_db:
        users_db[username]["last_login"] = _now()
        try:
            _save_db(users_db, db_path)
        except Exception:
            pass


def check_admin_exists(users_db):
    for info in users_db.values():
        if info.get("role") == "admin":
            return True
    return False
