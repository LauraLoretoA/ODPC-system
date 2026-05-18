import sqlite3
from datetime import datetime

# Connect to the database
conn = sqlite3.connect("odpc.db")
cursor = conn.cursor()

current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Insert enquiry
cursor.execute("""
INSERT INTO enquiries (enquirer_name, enquirer_email, subject, description, date_received, status)
VALUES (?, ?, ?, ?, ?, ?)
""", ("ABC Limited", "abcltd@gmail.com", "REGISTRATION", "Asking for registration procedure as a data processor", current_datetime, "New"))


cursor.execute("""
INSERT INTO enquiries (enquirer_name, enquirer_email, subject, description, date_received, status)
VALUES (?, ?, ?, ?, ?, ?)
""", ("Kenya beauty", "kenyabeauty@gmail.com", "SME Query", "SME Query", current_datetime, "New"))


conn.commit()
conn.close()

print("Two new enquiries have been inserted into the database.")