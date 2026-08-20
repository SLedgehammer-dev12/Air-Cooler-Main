import json
import os
import tempfile
import unittest
from pathlib import Path

from air_cooler_users import (
    generate_salt,
    hash_password,
    verify_password,
    initialize_users_db,
    authenticate_user,
    change_password,
    register_user,
    delete_user,
    update_user_role,
    list_users,
    update_last_login,
    validate_password,
    is_default_password,
    check_admin_exists,
    PBKDF2_ITERATIONS,
)


class TestUserAuth(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir, "test_users.json")

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    # ── Hashing ──

    def test_generate_salt_returns_32_char_hex(self):
        salt = generate_salt()
        self.assertEqual(len(salt), 32)
        int(salt, 16)

    def test_hash_password_returns_pbkdf2_prefixed(self):
        salt = generate_salt()
        h = hash_password("test123", salt)
        self.assertTrue(h.startswith("pbkdf2_"))
        self.assertEqual(len(h), 7 + 64)

    def test_verify_password_correct(self):
        salt = generate_salt()
        h = hash_password("test123", salt)
        self.assertTrue(verify_password("test123", salt, h))

    def test_verify_password_incorrect(self):
        salt = generate_salt()
        h = hash_password("test123", salt)
        self.assertFalse(verify_password("wrong", salt, h))

    def test_verify_password_legacy_format(self):
        salt = generate_salt()
        import hashlib
        legacy = "sha256_" + hashlib.sha256(("test123" + salt).encode()).hexdigest()
        self.assertTrue(verify_password("test123", salt, legacy))
        self.assertFalse(verify_password("wrong", salt, legacy))

    def test_verify_password_unprefixed_hash_migrated_on_load(self):
        salt = generate_salt()
        import hashlib
        raw = hashlib.sha256(("test123" + salt).encode()).hexdigest()
        self.assertFalse(verify_password("test123", salt, raw))

    # ── initialize_users_db ──

    def test_init_creates_default_users(self):
        db = initialize_users_db(self.db_path)
        self.assertIn("admin", db)
        self.assertIn("user", db)
        self.assertEqual(db["admin"]["role"], "admin")
        self.assertEqual(db["user"]["role"], "user")
        self.assertIn("email", db["admin"])
        self.assertIn("created_at", db["admin"])
        self.assertIn("last_login", db["admin"])

    def test_init_loads_existing_file(self):
        db = initialize_users_db(self.db_path)
        db2 = initialize_users_db(self.db_path)
        self.assertEqual(db["admin"]["role"], db2["admin"]["role"])

    def test_init_handles_corrupt_file(self):
        self.db_path.write_text("{{{corrupt", encoding="utf-8")
        db = initialize_users_db(self.db_path)
        self.assertIn("admin", db)

    def test_init_handles_write_error(self):
        db = initialize_users_db("/nonexistent/path/to/users.json")
        self.assertIn("admin", db)

    def test_init_migrates_legacy_hash(self):
        salt = generate_salt()
        import hashlib
        raw_hash = hashlib.sha256(("admin123" + salt).encode()).hexdigest()
        legacy = {"admin": {"salt": salt, "hash": raw_hash, "role": "admin"}}
        self.db_path.write_text(json.dumps(legacy), encoding="utf-8")
        db = initialize_users_db(self.db_path)
        self.assertTrue(db["admin"]["hash"].startswith("sha256_"))

    # ── authenticate_user ──

    def test_authenticate_success(self):
        db = initialize_users_db(self.db_path)
        ok, role = authenticate_user("admin", "admin123", db)
        self.assertTrue(ok)
        self.assertEqual(role, "admin")

    def test_authenticate_wrong_password(self):
        db = initialize_users_db(self.db_path)
        ok, role = authenticate_user("admin", "wrong", db)
        self.assertFalse(ok)
        self.assertIsNone(role)

    def test_authenticate_unknown_user(self):
        db = initialize_users_db(self.db_path)
        ok, role = authenticate_user("nobody", "pass", db)
        self.assertFalse(ok)
        self.assertIsNone(role)

    def test_authenticate_case_sensitive_username(self):
        db = initialize_users_db(self.db_path)
        ok, role = authenticate_user("Admin", "admin123", db)
        self.assertFalse(ok)

    def test_authenticate_whitespace_stripped(self):
        db = initialize_users_db(self.db_path)
        ok, role = authenticate_user("  admin  ", "admin123", db)
        self.assertTrue(ok)

    def test_authenticate_newly_registered_user(self):
        db = initialize_users_db(self.db_path)
        ok, msg = register_user("testuser", "test123", "test@test.com", db, self.db_path)
        self.assertTrue(ok)
        ok, role = authenticate_user("testuser", "test123", db)
        self.assertTrue(ok)
        self.assertEqual(role, "user")

    # ── change_password ──

    def test_change_password_success(self):
        db = initialize_users_db(self.db_path)
        ok, msg = change_password("admin", "admin123", "newadmin456", db, self.db_path)
        self.assertTrue(ok)
        ok, role = authenticate_user("admin", "newadmin456", db)
        self.assertTrue(ok)
        ok, _ = authenticate_user("admin", "admin123", db)
        self.assertFalse(ok)

    def test_change_password_wrong_old(self):
        db = initialize_users_db(self.db_path)
        ok, msg = change_password("admin", "wrong", "newpass", db, self.db_path)
        self.assertFalse(ok)

    def test_change_password_unknown_user(self):
        db = initialize_users_db(self.db_path)
        ok, msg = change_password("nobody", "pass", "newpass", db, self.db_path)
        self.assertFalse(ok)

    def test_change_password_writes_to_disk(self):
        db = initialize_users_db(self.db_path)
        change_password("admin", "admin123", "newadmin456", db, self.db_path)
        db2 = initialize_users_db(self.db_path)
        ok, _ = authenticate_user("admin", "newadmin456", db2)
        self.assertTrue(ok)

    # ── register_user ──

    def test_register_user_success(self):
        db = initialize_users_db(self.db_path)
        ok, msg = register_user("newuser", "newpass123", "new@test.com", db, self.db_path)
        self.assertTrue(ok)
        self.assertIn("newuser", db)
        self.assertEqual(db["newuser"]["role"], "user")
        self.assertEqual(db["newuser"]["email"], "new@test.com")

    def test_register_duplicate_username(self):
        db = initialize_users_db(self.db_path)
        ok, _ = register_user("admin", "pass123", "a@b.com", db, self.db_path)
        self.assertFalse(ok)

    def test_register_empty_username(self):
        db = initialize_users_db(self.db_path)
        ok, _ = register_user("  ", "pass123", "a@b.com", db, self.db_path)
        self.assertFalse(ok)

    def test_register_short_password(self):
        db = initialize_users_db(self.db_path)
        ok, msg = register_user("u", "12345", "a@b.com", db, self.db_path)
        self.assertFalse(ok)
        self.assertIn("6 karakter", msg)

    def test_register_writes_to_disk(self):
        db = initialize_users_db(self.db_path)
        register_user("diskuser", "diskpass", "d@d.com", db, self.db_path)
        db2 = initialize_users_db(self.db_path)
        self.assertIn("diskuser", db2)

    # ── delete_user ──

    def test_delete_user_success(self):
        db = initialize_users_db(self.db_path)
        register_user("todelete", "pass123", "d@d.com", db, self.db_path)
        ok, msg = delete_user("todelete", db, self.db_path)
        self.assertTrue(ok)
        self.assertNotIn("todelete", db)

    def test_delete_unknown_user(self):
        db = initialize_users_db(self.db_path)
        ok, msg = delete_user("nobody", db, self.db_path)
        self.assertFalse(ok)

    def test_delete_admin_protected(self):
        db = initialize_users_db(self.db_path)
        ok, msg = delete_user("admin", db, self.db_path)
        self.assertFalse(ok)
        self.assertIn("silinemez", msg)

    def test_delete_writes_to_disk(self):
        db = initialize_users_db(self.db_path)
        register_user("todelete2", "pass", "d@d.com", db, self.db_path)
        delete_user("todelete2", db, self.db_path)
        db2 = initialize_users_db(self.db_path)
        self.assertNotIn("todelete2", db2)

    # ── update_user_role ──

    def test_update_role_success(self):
        db = initialize_users_db(self.db_path)
        ok, _ = register_user("roleuser", "pass123", "r@r.com", db, self.db_path)
        self.assertTrue(ok)
        ok, msg = update_user_role("roleuser", "admin", db, self.db_path)
        self.assertTrue(ok, msg)
        self.assertEqual(db["roleuser"]["role"], "admin")

    def test_update_role_invalid_role(self):
        db = initialize_users_db(self.db_path)
        ok, _ = update_user_role("admin", "superadmin", db, self.db_path)
        self.assertFalse(ok)

    def test_update_role_unknown_user(self):
        db = initialize_users_db(self.db_path)
        ok, _ = update_user_role("nobody", "admin", db, self.db_path)
        self.assertFalse(ok)

    # ── list_users ──

    def test_list_users_returns_all(self):
        db = initialize_users_db(self.db_path)
        users = list_users(db)
        self.assertGreaterEqual(len(users), 2)
        usernames = [u["username"] for u in users]
        self.assertIn("admin", usernames)
        self.assertIn("user", usernames)

    def test_list_users_sorted(self):
        db = initialize_users_db(self.db_path)
        register_user("zzzuser", "pass", "z@z.com", db, self.db_path)
        register_user("aaauser", "pass", "a@a.com", db, self.db_path)
        users = list_users(db)
        usernames = [u["username"] for u in users]
        self.assertEqual(usernames, sorted(usernames))

    def test_list_users_includes_metadata(self):
        db = initialize_users_db(self.db_path)
        users = list_users(db)
        admin_info = next(u for u in users if u["username"] == "admin")
        self.assertIn("email", admin_info)
        self.assertIn("role", admin_info)
        self.assertIn("created_at", admin_info)

    # ── update_last_login ──

    def test_update_last_login_sets_timestamp(self):
        db = initialize_users_db(self.db_path)
        self.assertIsNone(db["admin"]["last_login"])
        update_last_login("admin", db, self.db_path)
        self.assertIsNotNone(db["admin"]["last_login"])

    def test_update_last_login_ignores_unknown_user(self):
        db = initialize_users_db(self.db_path)
        update_last_login("nobody", db, self.db_path)

    # ── validate_password ──

    def test_validate_password_short(self):
        ok, msg = validate_password("12345")
        self.assertFalse(ok)

    def test_validate_password_ok(self):
        ok, msg = validate_password("123456")
        self.assertTrue(ok)

    def test_validate_password_empty(self):
        ok, msg = validate_password("")
        self.assertFalse(ok)

    # ── is_default_password ──

    def test_is_default_password_true(self):
        self.assertTrue(is_default_password("admin123"))
        self.assertTrue(is_default_password("user123"))

    def test_is_default_password_false(self):
        self.assertFalse(is_default_password("custompass"))

    # ── check_admin_exists ──

    def test_check_admin_exists_true(self):
        db = initialize_users_db(self.db_path)
        self.assertTrue(check_admin_exists(db))

    def test_check_admin_exists_false(self):
        db = {"user1": {"role": "user"}}
        self.assertFalse(check_admin_exists(db))


if __name__ == "__main__":
    unittest.main()
