from ..db.session import engine
from .base_class import Base


def init_db() -> None:
    # Create all tables
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database tables created successfully!")
