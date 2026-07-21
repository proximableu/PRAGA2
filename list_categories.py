"""
Script to list all available RAG categories (collections) in the PostgreSQL database.
Usage: python list_categories.py
"""
import os
import psycopg
from dotenv import load_dotenv

# Load environment variables from .env file [3]
load_dotenv()


def list_categories(db_uri: str) -> None:
    """
    Queries the parent_sections table to retrieve a distinct list of all
    ingested collection names (categories).
    """
    conn = psycopg.connect(db_uri)
    cursor = conn.cursor()

    try:
        # Fetch unique collection names ordered alphabetically [3]
        cursor.execute("SELECT DISTINCT collection_name FROM parent_sections ORDER BY collection_name;")
        categories = cursor.fetchall()

        if not categories:
            print("No categories found in the database.")
        else:
            print(f"Found {len(categories)} RAG category(ies):")
            for cat in categories:
                print(f"- {cat[0]}")

    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    # Retrieve DB URI from environment variables [3]
    db_uri = os.getenv("POSTGRES_DB_URI")
    if not db_uri:
        raise ValueError("POSTGRES_DB_URI environment variable is not set.")

    list_categories(db_uri)