import sqlite3
import pandas as pd
import os

DB_NAME = 'database/nutrient_log.db'
CSV_PATH = 'data/ABBREV.csv'

def initialize_database():
    """Initializes the SQLite database and creates necessary tables."""
    # Ensure the database directory exists
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Create the User Profile Table (for personalized goals and metrics)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        name TEXT,
        weight_kg REAL,
        height_cm REAL,
        age INTEGER,
        gender TEXT,
        daily_calorie_goal INTEGER,
        target_protein_g REAL,
        target_iron_mg REAL
    );
    """)

    # 2. Create the Food Log Table (for historical data used in RNN prediction)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS food_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        log_date TEXT,
        food_name TEXT,
        quantity_g REAL,
        calories_consumed INTEGER,
        protein_g REAL,
        iron_mg REAL,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """)

    # 3. Load the ABBREV.csv into a lookup table
    try:
        df = pd.read_csv(CSV_PATH)
        df.to_sql('nutrient_data', conn, if_exists='replace', index=False)
        print("✅ Nutrient lookup table loaded successfully.")
    except Exception as e:
        print(f"❌ Error loading nutrient data: {e}")

    # Insert a dummy user for testing
    try:
        cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                       ('user_123', 'Final Year Student', 75.0, 175.0, 22, 'Male', 2500, 150.0, 18.0))
        print("✅ Dummy user created.")
    except sqlite3.IntegrityError:
        pass # User already exists

    conn.commit()
    conn.close()
    print(f"Database setup complete at {DB_NAME}.")

if __name__ == '__main__':
    initialize_database()

# NOTE: To run this file, open your VS Code terminal and execute: python database_setup.py