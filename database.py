import sqlite3

def create_tables():
    conn = sqlite3.connect("odpc.db")
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()


    # USERS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)

    # ENQUIRERS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS enquirers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        enquirer_type TEXT NOT NULL,

        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,

        pobox TEXT,
        location TEXT,
        county TEXT,
        kra_pin TEXT,

        id_number TEXT,

        admin_verified INTEGER DEFAULT 0,
        admin_rejection_reason TEXT
    )
    """)


    # ENQUIRIES TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS enquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        enquirer_name TEXT NOT NULL,
        enquirer_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        description TEXT NOT NULL,
        date_received TEXT,
        status TEXT DEFAULT 'New',
        assigned_dpo_id INTEGER,
        enquirer_id INTEGER,
        FOREIGN KEY (assigned_dpo_id) REFERENCES users(id),
        FOREIGN KEY (enquirer_id) REFERENCES enquirers(id)
    )
    """)

    # ADVISORIES TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS advisories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        enquiry_id INTEGER NOT NULL,
        dpo_id INTEGER NOT NULL,
        draft_content TEXT,
        final_content TEXT,
        date_submitted TEXT,
        review_status TEXT DEFAULT 'Pending',
        review_comment TEXT,
        FOREIGN KEY (enquiry_id) REFERENCES enquiries(id),
        FOREIGN KEY (dpo_id) REFERENCES users(id)
    )
    """)

    # ACTIVITY LOGS TABLE 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        timestamp TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # Add new columns if they don't exist (SQLite doesn't support IF NOT EXISTS for ALTER)
    try:
        cursor.execute("ALTER TABLE advisories ADD COLUMN file_path TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cursor.execute("ALTER TABLE advisories ADD COLUMN advisory_title TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Enquirers enrichment columns
    try:
        cursor.execute("ALTER TABLE enquirers ADD COLUMN enquirer_type TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cursor.execute("ALTER TABLE enquirers ADD COLUMN pobox TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE enquirers ADD COLUMN location TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE enquirers ADD COLUMN county TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE enquirers ADD COLUMN kra_pin TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE enquirers ADD COLUMN id_number TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE enquirers ADD COLUMN admin_rejection_reason TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN enquirer_id INTEGER")
    except sqlite3.OperationalError:
        pass  # Column already exists


    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_tables()
    print("All tables created successfully.")

