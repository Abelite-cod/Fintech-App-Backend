from app.database import SessionLocal
from app import models, security

db = SessionLocal()

# Create admin user
admin_email = "admin@example.com"
admin_password = "supersecurepassword"

hashed_password = security.hash_password(admin_password)

admin_user = models.User(
    email=admin_email,
    hashed_password=hashed_password,
    username="Admin",
    role="admin"
)

# Check if admin already exists
existing = db.query(models.User).filter(models.User.email == admin_email).first()
if existing:
    print("Admin already exists ✅")
else:
    db.add(admin_user)
    db.commit()
    print("Admin created ✅")

db.close()
