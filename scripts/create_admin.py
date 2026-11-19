"""Create an admin user.  Usage: python -m scripts.create_admin admin@company.com"""

import argparse
import getpass

from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.schemas.user import UserCreate
from app.services.user_service import UserService


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("email")
    parser.add_argument("--name", default="Administrator")
    args = parser.parse_args()
    password = getpass.getpass("Password: ")
    with SessionLocal() as db:
        user = UserService(db).create(
            UserCreate(email=args.email, full_name=args.name, password=password, role=UserRole.ADMIN)
        )
    print(f"Created admin {user.email} (id={user.id})")


if __name__ == "__main__":
    main()
