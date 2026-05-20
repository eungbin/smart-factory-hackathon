from sqlalchemy import select

from app.db.models import Factory
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal


def seed_if_empty() -> None:
    with SessionLocal() as session:
        has_factory = session.execute(select(Factory.id).limit(1)).first() is not None

    if has_factory:
        print("Seed skipped because database already has data.")
        return

    seed_demo_data()
    print("Seeded demo data because database was empty.")


if __name__ == "__main__":
    seed_if_empty()
