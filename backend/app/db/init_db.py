import logging
from app.db.session import engine, Base
# Import models to register them
from app.db import models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully!")

if __name__ == "__main__":
    init_database()
