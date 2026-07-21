"""
Script to drop a specific RAG collection from the PostgreSQL database.
Usage: python drop_collection.py --collection dev-notes
"""
import os
import argparse
import psycopg
from dotenv import load_dotenv

# Load environment variables from .env file [3]
load_dotenv()


def drop_collection(collection_name: str, db_uri: str) -> None:
    """
    Deletes a specific collection and its associated child chunks.
    Relies on ON DELETE CASCADE defined in the schema to automatically remove child_chunks [3].
    """
    conn = psycopg.connect(db_uri)
    cursor = conn.cursor()

    try:
        # Delete parent sections; child_chunks will be automatically removed via CASCADE [3]
        cursor.execute(
            "DELETE FROM parent_sections WHERE collection_name = %s",
            (collection_name,)
        )

        deleted_count = cursor.rowcount
        conn.commit()

        print(f"Successfully dropped collection '{collection_name}'.")
        print(f"Deleted {deleted_count} parent sections (and associated child chunks).")

    except Exception as e:
        conn.rollback()
        print(f"Error dropping collection: {e}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drop a specific RAG collection from the database.")
    parser.add_argument("--collection", type=str, required=True, help="Name of the collection to drop")

    args = parser.parse_args()

    # Retrieve DB URI from environment variables [3]
    db_uri = os.getenv("POSTGRES_DB_URI")
    if not db_uri:
        raise ValueError("POSTGRES_DB_URI environment variable is not set.")

    drop_collection(args.collection, db_uri)