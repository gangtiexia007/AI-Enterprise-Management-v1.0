"""Initialize database and create default admin user."""
import sys
sys.path.insert(0, ".")

from app.core.database import Database
from app.core.config import get_config

cfg = get_config()
cfg.setup_logging()

db = Database.get_instance(cfg.db_path)
applied = db.run_migrations()
print(f"Migrations applied: {applied}")

tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print(f"Total tables: {len(tables)}")
for t in tables:
    print(f"  - {t['name']}")

existing = db.query("dashboard_users", {"username": "admin"}, limit=1)
if not existing:
    import bcrypt
    from app.core.database import new_id
    password_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
    db.insert("dashboard_users", {
        "id": new_id(),
        "username": "admin",
        "password_hash": password_hash,
        "tier": "T1",
        "display_name": "系统管理员",
    })
    print("Default admin user created (admin / admin123)")
else:
    print("Admin user already exists")

print("Database initialization complete!")
