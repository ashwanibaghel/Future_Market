import logging
from sqlalchemy import text
from app.db.session import engine, Base
from app.db import models

logger = logging.getLogger(__name__)

def check_and_add_column(connection, table_name, column_name, column_type):
    """
    Checks if a column exists in a table, and if not, adds it.
    """
    try:
        # SQLite specific PRAGMA to check column info
        result = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        column_names = [row[1] for row in result]
        
        if column_name not in column_names:
            logger.info(f"Adding column '{column_name}' to table '{table_name}'...")
            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
            logger.info(f"Column '{column_name}' added successfully.")
        else:
            logger.debug(f"Column '{column_name}' already exists in table '{table_name}'.")
    except Exception as e:
        logger.error(f"Error checking/adding column {column_name} in table {table_name}: {str(e)}")

def run_migrations():
    logger.info("Starting database migrations...")
    
    # Connect and add columns
    with engine.begin() as connection:
        tables_to_update = ["option_chain_strikes", "aggregated_5m_strikes", "aggregated_15m_strikes"]
        greeks_columns = [
            ("call_delta", "FLOAT DEFAULT 0.0"),
            ("call_gamma", "FLOAT DEFAULT 0.0"),
            ("call_theta", "FLOAT DEFAULT 0.0"),
            ("call_vega", "FLOAT DEFAULT 0.0"),
            ("put_delta", "FLOAT DEFAULT 0.0"),
            ("put_gamma", "FLOAT DEFAULT 0.0"),
            ("put_theta", "FLOAT DEFAULT 0.0"),
            ("put_vega", "FLOAT DEFAULT 0.0"),
        ]
        
        for table in tables_to_update:
            # Check if table exists before adding columns
            # In SQLite, sqlite_master is queried
            result = connection.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")).fetchone()
            if result:
                for col_name, col_type in greeks_columns:
                    check_and_add_column(connection, table, col_name, col_type)
            else:
                logger.info(f"Table '{table}' does not exist yet. It will be created by metadata.create_all.")

        # V2 signal engine migrations
        signal_table = "trading_signals"
        signal_v2_columns = [
            ("bullish_score", "FLOAT DEFAULT 0.0"),
            ("bearish_score", "FLOAT DEFAULT 0.0"),
            ("decision_margin", "FLOAT DEFAULT 0.0"),
            ("confidence_ratio", "FLOAT DEFAULT 0.0"),
            ("dynamic_threshold", "FLOAT DEFAULT 70.0"),
            ("raw_signal", "VARCHAR(20) DEFAULT 'NO_TRADE'"),
            ("volume_z_score", "FLOAT DEFAULT 0.0"),
            ("feature_version", "VARCHAR(10) DEFAULT 'v2.0'"),
            ("data_quality_score", "INTEGER DEFAULT 100"),
            ("top_contributors", "TEXT"),
            ("lifecycle_state", "VARCHAR(20) DEFAULT 'CREATED'"),
        ]
        result = connection.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{signal_table}'")).fetchone()
        if result:
            for col_name, col_type in signal_v2_columns:
                check_and_add_column(connection, signal_table, col_name, col_type)
        else:
            logger.info(f"Table '{signal_table}' does not exist yet.")

    # Create any missing tables (like manual_trader_decisions and observation_logs)
    logger.info("Creating any missing tables from metadata...")
    Base.metadata.create_all(bind=engine)
    logger.info("Migrations completed successfully.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migrations()
