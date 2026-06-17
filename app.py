# Imports used for dates and deadline calculations.
# datetime gives the current date/time; timedelta helps add days
from datetime import datetime, timedelta
# Imports Python's built-in web server classes.
# BaseHTTPRequestHandler lets us define how GET and POST requests are handled.
# HTTPServer starts and keeps the web application running.
from http.server import BaseHTTPRequestHandler, HTTPServer
# Imports sqlite3 so the system can connect to the local SQLite database file odpc.db.
import sqlite3
# Imports URL/form parsing tools used to read submitted form data and query strings.
import urllib.parse
# Imports operating-system utilities used for folders, filenames, and file paths.
import os
# Imports mimetypes to detect the correct content type when downloading files.
import mimetypes
import hashlib
import secrets
import re


# Imports a helper function from another file to identify the logged-in enquirer from cookies.
from Extras.auth import get_logged_in_enquirer_id

# Records important user actions in the activity_logs table.
def log_activity(user_id, action):

    conn = sqlite3.connect("odpc.db")
    cursor = conn.cursor()  #executes sql commands

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO activity_logs (
            user_id,
            action,
            timestamp
        )
        VALUES (?, ?, ?)
    """, (
        user_id,
        action,
        timestamp
    ))

    conn.commit()
    conn.close()
    
#Activity logs but for enquirers
def log_enquirer_activity(enquirer_id, action):

    conn = sqlite3.connect("odpc.db")
    cursor = conn.cursor()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO activity_logs (
            enquirer_id,
            action,
            timestamp
        )
        VALUES (?, ?, ?)
    """, (
        enquirer_id,
        action,
        timestamp
    ))

    conn.commit()
    conn.close()
    
# Creates a notification for a specific user
def create_notification(user_id, message):

    conn = sqlite3.connect("odpc.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO notifications (
            user_id,
            message,
            created_at
        )
        VALUES (?, ?, ?)
    """, (
        user_id,
        message,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

# Checks whether an unread notification with the same message already exists.
# This prevents duplicate deadline alert notifications from being created repeatedly
def notification_exists(user_id, message):

    conn = sqlite3.connect("odpc.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM notifications
        WHERE user_id = ?
        AND message = ?
        AND is_read = 0
    """, (user_id, message))

    exists = cursor.fetchone()

    conn.close()

    return exists is not None

# Reads the user_id from the browser cookie.
# Enforces session management
SESSION_TIMEOUT_MINUTES = 20
def get_logged_in_user_id(handler):
    cookie = handler.headers.get("Cookie")
    if not cookie:
        return None

    user_id = None
    last_active = None

    parts = cookie.split(";")

    for part in parts:
        part = part.strip()

        if part.startswith("user_id="):
            user_id = part.split("=", 1)[1]

        if part.startswith("last_active="):
            last_active = part.split("=", 1)[1]

    if not user_id or not last_active:
        return None

    try:
        last_active_time = datetime.fromtimestamp(float(last_active))

        if datetime.now() - last_active_time > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            return None

    except Exception:
        return None

    return user_id



def hash_password(password):
    # Creates a random salt so that even identical passwords produce different hashes.
    salt = secrets.token_hex(16)

    # Hashes the password 
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    ).hex()

    # Stores the method, salt, and hash together.
    return f"pbkdf2_sha256${salt}${password_hash}"


def verify_password(stored_password, entered_password):
    # Checks hashed passwords
    if stored_password.startswith("pbkdf2_sha256$"):
        _, salt, saved_hash = stored_password.split("$", 2)

        entered_hash = hashlib.pbkdf2_hmac(
            "sha256",
            entered_password.encode("utf-8"),
            salt.encode("utf-8"),
            100000
        ).hex()

        return secrets.compare_digest(saved_hash, entered_hash)

    # This allows old accounts to still log in before their passwords are updated.
    return stored_password == entered_password


def is_strong_password(password):
    # Password must be at least 8 characters.
    if len(password) < 8:
        return False

    # Must contain uppercase, lowercase, number, and special character.
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[^A-Za-z0-9]", password):
        return False

    return True
#input validation functions for enquirer registration form
def is_valid_email(email):
    return re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email) is not None


def is_valid_kra_pin(kra_pin):
    return re.match(r"^[A-Z][0-9]{9}[A-Z]$", kra_pin) is not None


def is_valid_id_number(id_number):
    return id_number.isdigit() and len(id_number) in [7, 8]

# It separates normal form fields into data and uploaded files into files.
def parse_multipart(post_data, content_type):
    
    boundary_marker = "boundary="
    b_idx = content_type.find(boundary_marker)
    if b_idx == -1:
        return {}, {}
    boundary = content_type[b_idx + len(boundary_marker):]
    if ";" in boundary:
        boundary = boundary.split(";")[0]
    boundary = boundary.strip().strip('"')

    boundary_bytes = ("--" + boundary).encode()
    parts = post_data.split(boundary_bytes)

    data = {}
    files = {}
       
    for part in parts:
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue

        header_body_split = b"\r\n\r\n"
        idx = part.find(header_body_split)
        if idx == -1:
            continue

        headers = part[:idx].decode("utf-8", errors="replace")
        body = part[idx + len(header_body_split):]

        if body.endswith(b"\r\n"):
            body = body[:-2]
        if body.endswith(b"--"):
            body = body[:-2]

        name = None
        filename = None
        for line in headers.split("\r\n"):
            if line.lower().startswith("content-disposition"):
                name_start = line.find('name="')
                if name_start != -1:
                    name_start += 6
                    name_end = line.find('"', name_start)
                    name = line[name_start:name_end]

                fn_start = line.find('filename="')
                if fn_start != -1:
                    fn_start += 10
                    fn_end = line.find('"', fn_start)
                    filename = line[fn_start:fn_end]

        if name is None:
            continue

        if filename is not None:
            files[name] = {"filename": filename, "data": body}
        else:
            data[name] = body.decode("utf-8", errors="replace")

    return data, files



# Ensures the uploads folder exists before any files are saved.
os.makedirs("uploads", exist_ok=True)


# Defines the port number where the local web server will run.
PORT = 8000



# Main request handler class for the whole web application.
# It inherits from BaseHTTPRequestHandler so it can respond to browser requests.
class MyHandler(BaseHTTPRequestHandler):

    # Handles all GET requests.

    def do_GET(self):

        # Route for serving the ODPC logo image to the browser.
        # Serve logo image
        if self.path in ["/logo%20odpc.png", "/logo odpc.png", "/logo.png"]:
            try:
                with open("logo odpc.png", "rb") as img:
                    img_data = img.read()
                self.send_response(200)
                self.send_header("Content-type", "image/png")
                self.send_header("Content-Length", str(len(img_data)))
                self.end_headers()
                self.wfile.write(img_data)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
            return

        # Route for downloading or viewing uploaded advisory files from the uploads folder.
        # Serve uploaded files
        if self.path.startswith("/download/"):
            filename = os.path.basename(self.path[len("/download/"):])
            filepath = os.path.join("uploads", filename)
            if os.path.exists(filepath):
                with open(filepath, "rb") as f:
                    data = f.read()
                self.send_response(200)
                content_type, _ = mimetypes.guess_type(filepath)
                if not content_type:
                    content_type = "application/octet-stream"
                self.send_header("Content-type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"File not found")
            return

        # Serves the main CSS file so pages can load styling.
        if self.path == "/style.css":
            try:
                with open("Static/style.css", "rb") as css:
                    css_data = css.read()
                self.send_response(200)
                self.send_header("Content-type", "text/css")
                self.send_header("Content-Length", str(len(css_data)))
                self.end_headers()
                self.wfile.write(css_data)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
            return
        # Serves the main JavaScript file used by the front-end pages.
        if self.path == "/main.js":
            try:
                with open("Static/main.js", "rb") as js:
                    js_data = js.read()

                self.send_response(200)
                self.send_header("Content-type", "application/javascript")
                self.send_header("Content-Length", str(len(js_data)))
                self.end_headers()
                self.wfile.write(js_data)

            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()

            return
        # Displays the internal user login page.
        # Login page
        if self.path == "/" or self.path == "/login":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            with open("Pages/login.html", "r") as file:
                self.wfile.write(file.read().encode())


        # Admin dashboard route.
        
        elif self.path.startswith("/admin"):
            user_id = get_logged_in_user_id(self)

            if not user_id:
                self.send_response(303)
                self.send_header("Location", "/login")
                self.end_headers()
                return

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id,
                       enquirer_type,
                       name,
                       email,
                       pobox,
                       location,
                       county,
                       kra_pin,
                       id_number,
                       admin_verified,
                       admin_rejection_reason
                FROM enquirers
                WHERE admin_verified = 0
                AND admin_rejection_reason IS NULL
                ORDER BY id DESC
            """)

            pending_enquirers = cursor.fetchall()
            cursor.execute("""
                SELECT id, name, email, role
                FROM users
                ORDER BY role, name
                """)
            users = cursor.fetchall()
            cursor.execute("""
                SELECT message, created_at
                FROM notifications
                WHERE user_id = ? AND is_read = 0
                ORDER BY id DESC
                LIMIT 5
            """, (get_logged_in_user_id(self),))

            notifications = cursor.fetchall()
            print(f"DEBUG ADMIN: Found {len(pending_enquirers)} pending enquirers: {pending_enquirers}")
            notifications_html = ""

            if notifications:
                for note in notifications:
                    notifications_html += f"""
                    <article class="hod-workload-card">
                        <p><strong>{note[0]}</strong></p>
                        <p class="hod-small-text">{note[1]}</p>
                    </article>
                    """
            else:
                notifications_html = '<div class="hod-empty-state">No unread notifications.</div>'
            
            conn.close()

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            # Load base HTML
            with open("Pages/admin_dashboard.html", "r") as file:
                html = file.read()
            print(f"DEBUG ADMIN: Original HTML length: {len(html)}")

            # Generate pending_html
            pending_html = "<h2>Pending Enquirers (Need Verification)</h2>\n"
            if pending_enquirers:
                for enq in pending_enquirers:
                    # columns:
                    # 0=id,1=enquirer_type,2=name,3=email,4=pobox,5=location,6=county,7=kra_pin,8=id_number,9=admin_verified,10=admin_rejection_reason
                    enq_id, enquirer_type, name, email, pobox, location, county, kra_pin, id_number, verified, admin_rejection_reason = enq

                    id_display = id_number if enquirer_type == 'individual' else '—'

                    pending_html += f"""
                <article class='item-card'>    
                    <p><strong>ID:</strong> {enq_id}</p>    
                    <p><strong>Type:</strong> {enquirer_type.title()}</p>
                    <p><strong>Name:</strong> {name}</p>    
                    <p><strong>Email:</strong> {email}</p>   

                    <p><strong>P.O. Box:</strong> {pobox or '—'}</p>
                    <p><strong>Location:</strong> {location or '—'}</p>
                    <p><strong>County:</strong> {county or '—'}</p>

                    <p><strong>KRA PIN:</strong> {kra_pin or '—'}</p>
                    <p><strong>ID Number:</strong> {id_display or '—'}</p>

                    <p><strong>Status:</strong> <span style='color:orange;'>Pending Verification</span></p>   
                    <div class='item-actions'>        
                        <form method="POST" action="/verify_enquirer" style="display:inline;">           
                            <input type="hidden" name="enq_id" value="{enq_id}">            
                            <button type="submit" onclick="return confirm('Are you sure you would like to approve this profile?')">Verify & Approve</button>        
                        </form> 
                        <form method="POST" action="/reject_enquirer" style="display:inline;">
                            <input type="hidden" name="enq_id" value="{enq_id}">
                            <textarea name="rejection_reason" placeholder="Enter rejection reason" required rows="2" style="width:220px; vertical-align:middle;"></textarea>
                            <button type="submit" style="background-color:red;" onclick="return confirm('Are you sure you would like to reject this profile?')">Reject</button>
                        </form>  
                    </div>
                </article>
                """

            else:
                pending_html += "<p>No pending enquirers needing verification.</p>"

            print(f"DEBUG ADMIN: Generated pending_html length: {len(pending_html)}")
            print(f"DEBUG ADMIN: pending_html preview: {pending_html[:200]}...")

            users_html = ""

            if users:
                users_html += """
                <div class="hod-table-wrap">
                    <table class="hod-table">
                   <thead>
                       <tr>
                           <th>ID</th>
                           <th>Name</th>
                           <th>Email</th>
                           <th>Role</th>
                           <th>Action</th>
                       </tr>
                   </thead>
                   <tbody>
                """

                for user in users:
                    user_id, name, email, role = user
                    users_html += f"""
                        <tr>
                            <td>{user_id}</td>
                            <td>{name}</td>
                            <td>{email}</td>
                            <td>{role}</td>
                            <td>
                                <form method="POST" action="/delete_user" onsubmit="return confirm('Are you sure you want to delete this user?');">
                                    <input type="hidden" name="user_id" value="{user_id}">
                                    <button type="submit" style="background:red;">Delete</button>
                                </form>
                            </td>
                        </tr>
                    """

                users_html += """
                        </tbody>
                    </table>
                </div>
                """
            else:
                users_html = "<p>No internal users found.</p>"

            html = html.replace('<div id="pending-enquirers-list"></div>', pending_html)
            html = html.replace('<div id="users-list"></div>', users_html)
            html = html.replace('<div id="admin-notifications-list"></div>', notifications_html)
    
            print(f"DEBUG ADMIN: Final HTML length: {len(html)}")

            self.wfile.write(html.encode())




        # Logs out the internal users by clearing the user_id cookie and redirecting to login.
        elif self.path == "/hod_logout":
            self.send_response(303)
            self.send_header(
                "Set-Cookie",
                "user_id=; expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/"
            )
            self.send_header(
                "Set-Cookie",
                "last_active=; expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/"
            )
            self.send_header("Location", "/login")
            self.end_headers()
            return
        #Download reports 
        elif self.path == "/download_reports":
            user_id = get_logged_in_user_id(self)

            if not user_id:
                self.send_response(303)
                self.send_header("Location", "/login")
                self.end_headers()
                return

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, enquirer_name, enquirer_email, subject, date_received, status, assigned_dpo_id
                FROM enquiries
                ORDER BY id DESC
            """)

            reports = cursor.fetchall()
            conn.close()

            csv_data = "ID,Enquirer Name,Email,Subject,Date Received,Status,Assigned DPO ID\n"

            for report in reports:
              csv_data += f"{report[0]},{report[1]},{report[2]},{report[3]},{report[4]},{report[5]},{report[6]}\n"

            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", "attachment; filename=odpc_reports.csv")
            self.end_headers()
            self.wfile.write(csv_data.encode())

        # HOD dashboard route.
        # Loads enquiry statistics, DPO workloads, deadline reports, notifications, and HOD profile data.
        elif self.path.startswith("/hod"):
            user_id = get_logged_in_user_id(self)
            if not user_id:
                self.send_response(303)
                self.send_header("Location", "/login")
                self.end_headers()
                return

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()
            cursor.execute("SELECT role, name, email FROM users WHERE id=?", (user_id,))
            user_row = cursor.fetchone()
            if not user_row or user_row[0] != "HOD":
                conn.close()
                self.send_response(303)
                self.send_header("Location", "/login")
                self.end_headers()
                return

            hod_profile = {
                "name": user_row[1] or "",
                "email": user_row[2] or ""
            }

            cursor.execute("SELECT COUNT(*) FROM enquiries WHERE status='New'")
            new_enquiries = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM enquiries WHERE status='Assigned'")
            assigned_enquiries = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM enquiries WHERE status='Completed'")
            completed_enquiries = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM enquiries WHERE status!='Completed'")
            total_active = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT e.id,
                       e.enquirer_name,
                       e.enquirer_email,
                       e.subject,
                       e.description,
                       e.date_received,
                       e.status,
                       e.assigned_dpo_id,
                       u.name as dpo_name
                FROM enquiries e
                LEFT JOIN users u ON e.assigned_dpo_id = u.id
                ORDER BY e.id DESC
            """)
            enquiries = cursor.fetchall()

            cursor.execute("SELECT id, name, email FROM users WHERE role='DPO'")
            dpo_rows = cursor.fetchall()
            
            #empty lsts filled with data
            dpo_workloads = []
            available_dpos = []
            dpo_performance = []
            for dpo in dpo_rows:
                dpo_id, dpo_name, dpo_email = dpo
                cursor.execute("""
                    SELECT id, subject, status
                    FROM enquiries
                    WHERE assigned_dpo_id = ?
                    ORDER BY id DESC
                """, (dpo_id,))
                assigned_rows = cursor.fetchall()
                
                #Workload
                active_count = len([row for row in assigned_rows if row[2] != 'Completed'])
                assigned_titles = [row[1] or f"Enquiry {row[0]}" for row in assigned_rows]
                assigned_enquiry_ids = [str(row[0]) for row in assigned_rows]
                completed_count = len([row for row in assigned_rows if row[2] == 'Completed'])
                pending_count = len([row for row in assigned_rows if row[2] != 'Completed'])
                status_badge = "Available" if active_count < 3 else "Full"
                badge_style = "hod-status-available" if active_count < 3 else "hod-status-full"
                
                # Store available dpos
                if active_count < 3:
                    available_dpos.append({
                        "id": dpo_id,
                        "name": dpo_name,
                        "email": dpo_email,
                        "activeCount": active_count
                    })

                dpo_workloads.append({
                    "id": dpo_id,
                    "name": dpo_name,
                    "email": dpo_email,
                    "activeCount": active_count,
                    "assignedTitles": assigned_titles,
                    "assignedEnquiryIds": assigned_enquiry_ids,
                    "statusBadgeText": status_badge,
                    "statusBadgeClass": badge_style
                })
                dpo_performance.append({
                    "name": dpo_name,
                    "email": dpo_email,
                    "assigned": len(assigned_rows),
                    "completed": completed_count,
                    "pending": pending_count
                })
            cursor.execute("""
                SELECT message, created_at
                FROM notifications
                WHERE user_id = ? AND is_read = 0
                ORDER BY id DESC
                LIMIT 5
            """, (user_id,))

            notifications = cursor.fetchall()
            conn.close()

            deadline_report = []
            approaching_deadline_count = 0
            overdue_count = 0
            # Check enquiries to calculate deadlines
            enquiries_list = []
            for enq in enquiries:
                enq_id, enq_name, enq_email, subject, description, date_received, status, assigned_dpo_id, dpo_name = enq
                deadline_label = "—"
                days_remaining_value = "N/A"
                deadline_status = "No date recorded"
                received_dt = None

                if date_received:
                    try:
                        received_dt = datetime.strptime(
                            date_received,
                            "%Y-%m-%d %H:%M:%S"
                        )
                    except ValueError:

                        try:
                            received_dt = datetime.strptime(
                                date_received,
                                "%Y-%m-%d"
                            )
                        except Exception:
                            received_dt = None
                            
                if status == "Completed":
                    deadline_label = "Completed"
                    deadline_status = "Completed"
                
                elif received_dt:
                    deadline_dt = received_dt + timedelta(days=10)
                    days_remaining = (deadline_dt - datetime.today()).days

                    days_remaining_value = days_remaining

                    if days_remaining < 0:
                        deadline_label = "OVERDUE"
                        deadline_status = "Overdue"
                        overdue_count += 1
                    #affects notifications too
                    elif days_remaining <= 10:
                          deadline_label = f"{days_remaining} days left"
                          deadline_status = "Approaching Deadline"
                          approaching_deadline_count += 1

                    else:
                        deadline_label = f"{days_remaining} days left"
                        deadline_status = "Safe"

                enquiries_list.append({
                    "id": enq_id,
                    "enquirer_name": enq_name,
                    "enquirer_email": enq_email,
                    "title": subject,
                    "description": description,
                    "deadline": deadline_label,
                    "status": status,
                    "assigned_dpo_id": assigned_dpo_id,
                    "assigned_dpo_name": dpo_name,
                }) 
                
                #Alerts
                if deadline_status in ["Approaching Deadline", "Overdue"]:
                    hod_message = f"Deadline alert: Enquiry #{enq_id} is {deadline_status.lower()}"
                     #duplication fix 
                    if not notification_exists(user_id, hod_message):
                        create_notification(user_id, hod_message)
                    #also notifies dpo
                    if assigned_dpo_id:
                        dpo_message = f"Deadline alert: Enquiry #{enq_id} is {deadline_status.lower()}"

                        if not notification_exists(assigned_dpo_id, dpo_message):
                            create_notification(assigned_dpo_id, dpo_message)
                            
                deadline_report.append({
                    "id": enq_id,
                    "subject": subject,
                    "assignedDpo": dpo_name if dpo_name else "Unassigned",
                    "daysRemaining": days_remaining_value,
                    "deadlineStatus": deadline_status
                })
                #convert notifs to dictionaries 
            notifications_list = []

            for note in notifications:
                notifications_list.append({
                    "message": note[0],
                    "createdAt": note[1]
                })
                
                #combines all hod data
            hod_state = {
                "stats": {
                    "new": new_enquiries,
                    "assigned": assigned_enquiries,
                    "completed": completed_enquiries,
                    "totalActive": total_active
                },
                "enquiries": enquiries_list,
                "dpoWorkloads": dpo_workloads,
                "availableDpos": available_dpos,
                "reports": {
                    "totalEnquiries": len(enquiries),
                    "completedAdvisories": completed_enquiries,
                    "approachingDeadline": approaching_deadline_count,
                    "overdueEnquiries": overdue_count,
                    "dpoPerformance": dpo_performance,
                    "deadlines": deadline_report
                },
                "notifications": notifications_list,
                "profile": hod_profile
            }

            with open("Pages/hod_dashboard.html", "r", encoding="utf-8") as f:
                html = f.read()

            import json
            state_json = json.dumps(hod_state).replace('</', '<\\/')
            state_script = f'\n    <script>window.__HOD_STATE__ = {state_json};</script>\n'
            html = html.replace("</head>", state_script + "</head>", 1)

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Set-Cookie", f"last_active={datetime.now().timestamp()}; Path=/; HttpOnly; SameSite=Lax")
            self.end_headers()
            self.wfile.write(html.encode())


        # DPO dashboard route.
    
        elif self.path.startswith("/dpo"):

            user_id = get_logged_in_user_id(self)

            if not user_id:
                self.send_response(303)
                self.send_header("Location", "/login")
                self.end_headers()
                return

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, email FROM users WHERE id=?",
                (user_id,)
            )
            #fetch dpo notifications
            profile = cursor.fetchone()
            cursor.execute("""
                SELECT message, created_at
                FROM notifications
                WHERE user_id = ? AND is_read = 0
                ORDER BY id DESC
                LIMIT 5
            """, (user_id,))

            notifications = cursor.fetchall()
            
            
            cursor.execute("""
                SELECT
                    enquiries.id,
                    enquiries.enquirer_name,
                    enquiries.enquirer_email,
                    enquiries.subject,
                    enquiries.description,
                    enquiries.date_received,
                    enquiries.status,
                    advisories.review_status,
                    advisories.review_comment,
                    advisories.advisory_title,
                    advisories.file_path,
                    advisories.draft_content
                FROM enquiries
                LEFT JOIN advisories
                ON enquiries.id = advisories.enquiry_id
                WHERE enquiries.assigned_dpo_id = ?
            """, (user_id,))
            
        
            enquiries = cursor.fetchall()
            notifications_html = ""

            if notifications:
                for note in notifications:
                    notifications_html += f"""
                    <article class="hod-workload-card">
                        <p><strong>{note[0]}</strong></p>
                        <p class="hod-small-text">{note[1]}</p>
                    </article>
                    """
            else:
                notifications_html = '<div class="hod-empty-state">No unread notifications.</div>'
            
            conn.close()

            today = datetime.today()
            dpo_enquiries_html = ""

            if enquiries:
                for enquiry in enquiries:
                    review_status = enquiry[7]
                    review_comment = enquiry[8]
                    advisory_title = enquiry[9]
                    file_path = enquiry[10]
                    date_received_str = enquiry[5]

                    if review_status == "Approved":
                       deadline_status = "N/A"

                    elif date_received_str:
                        try:
                            date_received = datetime.strptime(date_received_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            date_received = datetime.strptime(date_received_str, "%Y-%m-%d")

                        deadline = date_received + timedelta(days=10)
                        days_remaining = (deadline - today).days

                        if days_remaining < 0:
                            deadline_status = "<span style='color:red;'>OVERDUE</span>"
                        elif days_remaining == 0:
                            deadline_status = "<span style='color:orange;'>Due today</span>"
                        else:
                            deadline_status = f"{days_remaining} days remaining"

                    else:
                        deadline_status = "No date recorded"
                        
                    card_status = review_status if review_status else enquiry[6]
                    #Enquiry card
                    dpo_enquiries_html += f"""
                    <article class='hod-workload-card' data-status="{card_status}">
                        <div class='hod-workload-card-header'>
                            <div>
                                <h3>{enquiry[3]}</h3>
                                <p class='hod-small-text'>Enquiry #{enquiry[0]}</p>
                            </div>
                            <span class='hod-badge hod-status-available'>{enquiry[6]}</span>
                        </div>

                        <p><strong>Enquirer:</strong> {enquiry[1]} ({enquiry[2]})</p>
                        <p><strong>Description:</strong> {enquiry[4]}</p>
                        <p><strong>Date Received:</strong> {enquiry[5]}</p>
                        <p><strong>Deadline:</strong> {deadline_status}</p>
                        <p><strong>Review Status:</strong> {review_status if review_status else enquiry[6]}</p>
                        <p><strong>Comment:</strong> {review_comment if review_comment else "None"}</p>
                    """

                    if advisory_title:
                        dpo_enquiries_html += f"<p><strong>Advisory Title:</strong> {advisory_title}</p>"

                    if file_path:
                        dpo_enquiries_html += f"<p><strong>Attachment:</strong> <a href='/download/{file_path}' target='_blank'>{file_path}</a></p>"

                    if not review_status or review_status == "Needs Revision":
                        dpo_enquiries_html += f"""
                        <div class='item-actions'>
                            <form method="GET" action="/draft_advisory">
                                <input type="hidden" name="enquiry_id" value="{enquiry[0]}">
                                <button type="submit">Draft / Redraft Advisory</button>
                            </form>
                        </div>
                        """
                    elif review_status == "Approved":
                        dpo_enquiries_html += "<p style='color:green;'><strong>Approved</strong></p>"

                    dpo_enquiries_html += "</article>"
            else:
                dpo_enquiries_html = "<div class='hod-empty-state'>No assigned enquiries.</div>"
            
            profile_name = profile[0] if profile else ""
            profile_email = profile[1] if profile else ""

            with open("Pages/dpo_dashboard.html", "r", encoding="utf-8") as file:
                html = file.read()

            html = html.replace("{{dpo_enquiries}}", dpo_enquiries_html)
            html = html.replace("{{dpo_notifications}}", notifications_html)

            html = html.replace(
                "Loading...</span>",
                f"{profile_name}</span>",
                1
            )

            html = html.replace(
                "Loading...</span>",
                f"{profile_email}</span>",
                1
            )

            html = html.replace(
                'id="dpo-name"',
                f'id="dpo-name" value="{profile_name}"'
            )

            html = html.replace(
                'id="dpo-email"',
                 f'id="dpo-email" value="{profile_email}"'
            )

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Set-Cookie", f"last_active={datetime.now().timestamp()}; Path=/; HttpOnly; SameSite=Lax")
            self.end_headers()
            self.wfile.write(html.encode())


        # Draft advisory page route.
        elif self.path.startswith("/draft_advisory"):

            user_id = get_logged_in_user_id(self)
            if not user_id:
                self.send_response(303)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            #checks query
            query = urllib.parse.urlparse(self.path).query
            #converts query
            params = urllib.parse.parse_qs(query)

            enquiry_id = params.get("enquiry_id", [None])[0]
            if not enquiry_id:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing enquiry_id")
                return

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM enquiries WHERE id=?", (enquiry_id,))
            enquiry = cursor.fetchone()

            cursor.execute("""
                SELECT id, draft_content, file_path, advisory_title
                FROM advisories WHERE enquiry_id = ?
            """, (enquiry_id,))
            existing = cursor.fetchone()
            conn.close()

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            with open("Pages/draft_advisory.html", "r") as file:
                html = file.read()

            html = html.replace("{{subject}}", enquiry[3] if enquiry else "")
            html = html.replace("{{description}}", enquiry[4] if enquiry else "")
            html = html.replace("{{enquiry_id}}", str(enquiry_id))
            html = html.replace("{{dpo_id}}", str(user_id))

            if existing:
                html = html.replace("{{advisory_title}}", existing[3] if existing[3] else "")
                html = html.replace("{{draft_content}}", existing[1] if existing[1] else "")
                if existing[2]:
                    existing_file_html = f"<p>Current attachment: <a href='/download/{existing[2]}' target='_blank'>{existing[2]}</a><br><em>Upload a new file below to replace it.</em></p>"
                else:
                    existing_file_html = ""
                html = html.replace("{{existing_file}}", existing_file_html)
            else:
                html = html.replace("{{advisory_title}}", "")
                html = html.replace("{{draft_content}}", "")
                html = html.replace("{{existing_file}}", "")

            self.wfile.write(html.encode())


        # DDC dashboard route.
        elif self.path.startswith("/ddc"):
            user_id = get_logged_in_user_id(self)

            if not user_id:
                self.send_response(303)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            
            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()
            user_id = get_logged_in_user_id(self)

            cursor.execute(
                "SELECT name, email FROM users WHERE id=?",
                (user_id,)
            )
            profile = cursor.fetchone()
            
            cursor.execute("""
                SELECT message, created_at
                FROM notifications
                WHERE user_id = ? AND is_read = 0
                ORDER BY id DESC
                LIMIT 5
            """, (user_id,))

            notifications = cursor.fetchall()
            
            #Fetch advisories pending review
            cursor.execute("""
                SELECT
                    advisories.id,
                    enquiries.subject,
                    enquiries.description,
                    advisories.draft_content,
                    advisories.final_content,
                    advisories.review_status,
                    advisories.review_comment,
                    advisories.advisory_title,
                    advisories.file_path
                FROM advisories
                JOIN enquiries ON advisories.enquiry_id = enquiries.id
                WHERE advisories.review_status != 'Approved'
            """)

            advisories = cursor.fetchall()
            cursor.execute("""
                SELECT
                    advisories.id,
                    enquiries.subject,
                    enquiries.description,
                    advisories.final_content,
                    advisories.review_comment,
                    advisories.advisory_title,
                    advisories.file_path
                FROM advisories
                JOIN enquiries ON advisories.enquiry_id = enquiries.id
                WHERE advisories.review_status = 'Approved'
                ORDER BY advisories.id DESC
            """)

            completed_advisories = cursor.fetchall()

            notifications_html = ""

            if notifications:
                for note in notifications:
                    notifications_html += f"""
                    <article class="hod-workload-card">
                        <p><strong>{note[0]}</strong></p>
                        <p class="hod-small-text">{note[1]}</p>
                    </article>
                    """
            else:
                notifications_html = '<div class="hod-empty-state">No unread notifications.</div>'
            conn.close()

            ddc_advisories_html = ""
            
            completed_advisories_html = ""

            if completed_advisories:
                for adv in completed_advisories:
                    file_link = ""
                    if adv[6]:
                       file_link = f"<p><strong>Attachment:</strong> <a href='/download/{adv[6]}' target='_blank'>{adv[6]}</a></p>"

                    completed_advisories_html += f"""
                    <article class='hod-workload-card'>
                        <div class='hod-workload-card-header'>
                            <div>
                                <h3>{adv[5] if adv[5] else adv[1]}</h3>
                                <p class='hod-small-text'>Advisory #{adv[0]}</p>
                            </div>
                            <span class='hod-badge hod-status-available'>Approved</span>
                        </div>

                        <p><strong>Subject:</strong> {adv[1]}</p>
                        <p><strong>Description:</strong> {adv[2]}</p>
                        <p><strong>Final Advisory:</strong><br>{adv[3] if adv[3] else "No written response"}</p>
                        {file_link}
                        <p><strong>Review Comment:</strong> {adv[4] if adv[4] else "None"}</p>
                    </article>
                    """
            else:
                completed_advisories_html = "<div class='hod-empty-state'>No completed advisories yet.</div>"
            

            if advisories:
                for adv in advisories:
                    file_link = ""
                    if adv[8]:
                        file_link = f"<p><strong>Attachment:</strong> <a href='/download/{adv[8]}' target='_blank'>{adv[8]}</a></p>"

                    title_display = f"<p><strong>Advisory Title:</strong> {adv[7]}</p>" if adv[7] else ""

                    ddc_advisories_html += f"""
                    <article class='hod-workload-card'>
                        <div class='hod-workload-card-header'>
                            <div>
                                <h3>{adv[1]}</h3>
                                <p class='hod-small-text'>Advisory #{adv[0]}</p>
                            </div>
                            <span class='hod-badge hod-status-available'>{adv[5] if adv[5] else "Pending"}</span>
                        </div>

                        {title_display}
                        <p><strong>Description:</strong> {adv[2]}</p>
                        <p><strong>Draft:</strong><br>{adv[3]}</p>
                        <p><strong>Final:</strong><br>{adv[4] if adv[4] else "Not approved yet"}</p>
                        {file_link}
                        <p><strong>Comment:</strong> {adv[6] if adv[6] else "None"}</p>

                        <div class='item-actions'>
                            <form method="POST" action="/review_advisory">
                                <input type="hidden" name="advisory_id" value="{adv[0]}">
                                <textarea name="comment" placeholder="Enter review comment"></textarea>
                                <div class='item-actions'>
                                <button name="action" value="approve">Approve</button>
                                <button name="action" value="revise">Send Back</button>
                        </div>
                    </form>
                </div>
            </article>
            """
            else:
                ddc_advisories_html = "<div class='hod-empty-state'>No advisories pending review.</div>"
            profile_name = profile[0] if profile else ""
            profile_email = profile[1] if profile else ""

            with open("Pages/ddc_dashboard.html", "r", encoding="utf-8") as file:
                html = file.read()

            html = html.replace("{{ddc_advisories}}", ddc_advisories_html)
            html = html.replace("{{completed_advisories}}", completed_advisories_html)
            html = html.replace("{{ddc_notifications}}", notifications_html)
            html = html.replace("Loading...</span>", f"{profile_name}</span>", 1)
            html = html.replace("Loading...</span>", f"{profile_email}</span>", 1)

            html = html.replace(
                'id="ddc-name"',
                f'id="ddc-name" value="{profile_name}"'
            )

            html = html.replace(
                'id="ddc-email"',
                f'id="ddc-email" value="{profile_email}"'
            )

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Set-Cookie", f"last_active={datetime.now().timestamp()}; Path=/; HttpOnly; SameSite=Lax")
            self.end_headers()
            self.wfile.write(html.encode())


        # Displays the enquirer registration page.
        elif self.path.startswith("/enquirer_register"):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open("Pages/enquirer_register.html", "r") as file:
                self.wfile.write(file.read().encode())

        # Displays the enquirer login page.
        elif self.path.startswith("/enquirer_login"):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open("Pages/enquirer_login.html", "r") as file:
                self.wfile.write(file.read().encode())

        # Processes an enquiry submitted by a logged-in enquirer.
        elif self.path == "/submit_enquiry":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open("Pages/submit_enquiry.html", "r") as file:
                self.wfile.write(file.read().encode())
                
         

        # Enquirer dashboard route.
        elif self.path.startswith("/enquirer_dashboard"):
            enquirer_id = get_logged_in_enquirer_id(self)

            if not enquirer_id:
                self.send_response(303)
                self.send_header("Location", "/enquirer_login")
                self.end_headers()
                return

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute("""
                SELECT e.id, e.subject, e.description, e.date_received, e.status,
                       a.final_content, a.advisory_title, a.file_path
                FROM enquiries e
                LEFT JOIN advisories a ON e.id = a.enquiry_id
                WHERE e.enquirer_id = ?
                ORDER BY e.id DESC
            """, (enquirer_id,))

            enquiries = cursor.fetchall()
            conn.close()

            total_enquiries = len(enquiries)
            new_enquiries = len([e for e in enquiries if e[4] == "New"])
            assigned_enquiries = len([e for e in enquiries if e[4] == "Assigned"])
            completed_enquiries = len([e for e in enquiries if e[4] == "Completed"])

            enquiries_rows = ""
            advisories_list = ""

            today = datetime.today()

            if enquiries:
                for enquiry in enquiries:
                    enq_id, subject, desc, date_str, status, final_content, advisory_title, file_path = enquiry

                    if status == "Completed":
                        deadline_status = "N/A"

                    elif date_str:
                        try:
                            date_received = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            date_received = datetime.strptime(date_str, "%Y-%m-%d")

                        deadline = date_received + timedelta(days=10)
                        days_remaining = (deadline - today).days

                        if days_remaining < 0:
                            deadline_status = "<span style='color:red;'>OVERDUE</span>"
                        elif days_remaining == 0:
                            deadline_status = "<span style='color:orange;'>Due today</span>"
                        else:
                            deadline_status = f"{days_remaining} days remaining"
                    else:
                        deadline_status = "No date recorded"

                    enquiries_rows += f"""
                    <tr>
                        <td>{enq_id}</td>
                        <td>{subject}</td>
                        <td>{status}</td>
                        <td>{date_str or 'N/A'}</td>
                        <td>{deadline_status}</td>
                    </tr>
                    """

                    if status == "Completed" and (final_content or file_path):
                        file_link = ""

                        if file_path:
                            file_link = f"""
                            <p>
                                <strong>Attachment:</strong>
                                <a href='/download/{file_path}' target='_blank'>
                                    {file_path}
                                </a>
                            </p>
                            """
                        advisories_list += f"""
                        <article class="hod-workload-card">
                            <div class="hod-workload-card-header">
                                <div>
                                    <h3>{advisory_title if advisory_title else subject}</h3>
                                    <p class="hod-small-text">Enquiry #{enq_id}</p>
                                </div>
                                <span class="hod-badge hod-status-available">Issued</span>
                            </div>

                            <p><strong>Subject:</strong> {subject}</p>
                            <p><strong>Advisory Response:</strong><br>{final_content if final_content else "See attached advisory document."}</p>{file_link}
                        </article>
                        """
            else:
                enquiries_rows = """
                <tr>
                    <td colspan="5" class="hod-empty-state">
                        No enquiries submitted yet.
                    </td>
                </tr>
                """

            if not advisories_list:
                advisories_list = """
                <div class="hod-empty-state">
                    No advisories have been issued yet.
                </div>
                """

            with open("Pages/enquirer_dashboard.html", "r", encoding="utf-8") as file:
                html = file.read()

            html = html.replace("{{total_enquiries}}", str(total_enquiries))
            html = html.replace("{{new_enquiries}}", str(new_enquiries))
            html = html.replace("{{assigned_enquiries}}", str(assigned_enquiries))
            html = html.replace("{{completed_enquiries}}", str(completed_enquiries))
            html = html.replace("{{enquiries_rows}}", enquiries_rows)
            html = html.replace("{{advisories_list}}", advisories_list)

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())
        elif self.path == "/enquirer_logout":
            enquirer_id = get_logged_in_enquirer_id(self)

            if enquirer_id:

                log_enquirer_activity(
                    enquirer_id,
                    "Logged out of the enquirer portal"
                )
            self.send_response(303)
            self.send_header(
                "Set-Cookie",
                "enquirer_id=; expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/"
            )
            self.send_header("Location", "/enquirer_login")
            self.end_headers()
            return
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Page not found")


    # Handles all POST requests.

    def do_POST(self):

        
        # LOGIN LOGIC
        if self.path == "/" or self.path.startswith("/login"):

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            email = data.get("email")[0]
            password = data.get("password")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute(
                 "SELECT id, role, password FROM users WHERE email=?",
                 (email,)
            )

            user = cursor.fetchone()

            if user and verify_password(user[2], password):
                user_id = user[0]
                role = user[1]

            #convert to a hashed password after login.
                if not user[2].startswith("pbkdf2_sha256$"):
                    cursor.execute(
                        "UPDATE users SET password=? WHERE id=?",
                        (hash_password(password), user_id)
                )
                conn.commit()

                conn.close()
                #activity log 
                log_activity(
                    user_id,
                    f"Logged into the system as {role}"
                )   
                #store session cookies
                self.send_response(303)
                self.send_header("Set-Cookie", f"user_id={user_id}; Path=/; HttpOnly; SameSite=Lax")
                self.send_header("Set-Cookie", f"last_active={datetime.now().timestamp()}; Path=/; HttpOnly; SameSite=Lax")

                if role == "Admin":
                    self.send_header("Location", "/admin?success=Login successful")
                elif role == "HOD":
                    self.send_header("Location", "/hod?success=Login successful")
                elif role == "DPO":
                    self.send_header("Location", "/dpo?success=Login successful")
                elif role == "DDC":
                    self.send_header("Location", "/ddc?success=Login successful")
                self.end_headers()

            else:
                conn.close()
                self.send_response(303)
                self.send_header("Location", "/login?error=Invalid email or password")
                self.end_headers()
                

        
        # CREATE USER LOGIC (ADMIN)
        elif self.path == "/create_user":

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            name = data.get("name")[0]
            email = data.get("email")[0]
            password = data.get("password")[0]
            role = data.get("role")[0]
            #Checks for password policy
            if not is_strong_password(password):
                self.send_response(303)
                self.send_header(
                    "Location",
                    "/admin?error=Password must have at least 8 characters, uppercase, lowercase, number and special character"
                )
                self.end_headers()
                return

            password = hash_password(password)

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO users (name, email, password, role)
                VALUES (?, ?, ?, ?)
            """, (name, email, password, role))

            conn.commit()
            admin_id = get_logged_in_user_id(self)

            log_activity(
                admin_id,
                f"Created {role} account for {name}"
            )
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/admin?success=User created successfully")
            self.end_headers()

        # Allows Admin to delete an internal user account.
        #DELETE USER LOGIC (ADMIN)
        elif self.path == "/delete_user":

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            user_id = data.get("user_id")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, role FROM users WHERE id=?",
                (user_id,)
            )

            deleted_user = cursor.fetchone()
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

            conn.commit()
            admin_id = get_logged_in_user_id(self)

            if deleted_user:
                log_activity(
                    admin_id,
                    f"Deleted {deleted_user[1]} account: {deleted_user[0]}"
                )
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/admin?success=User deleted successfully")
            self.end_headers()   

        # Allows Admin to approve a pending enquirer profile.
        # VERIFY ENQUIRER (ADMIN)
        elif self.path == "/verify_enquirer":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            enq_id = data.get("enq_id")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE enquirers SET admin_verified = 1, admin_rejection_reason = NULL WHERE id = ?",
                (enq_id,)
            )
            conn.commit()
            admin_id = get_logged_in_user_id(self)

            log_activity(
                admin_id,
                f"Approved enquirer profile #{enq_id}"
            )
            conn.close()

            # Feedback
            self.send_response(303)
            self.send_header("Location", "/admin?success=Approval successful")
            self.end_headers()
            return
        
        
        # REJECT ENQUIRER (ADMIN)
        elif self.path == "/reject_enquirer":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            enq_id = data.get("enq_id")[0]
            rejection_reason = data.get("rejection_reason", [""])[0].strip()

            if not rejection_reason:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Rejection reason is required")
                return

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE enquirers
                SET admin_verified = 0,
                    admin_rejection_reason = ?
                WHERE id = ?
                """,
                (rejection_reason, enq_id)
            )

            conn.commit()
            admin_id = get_logged_in_user_id(self)

            log_activity(
                admin_id,
                f"Rejected enquirer profile #{enq_id}"
            )
            conn.close()

            # Simple feedback
            self.send_response(303)
            self.send_header("Location", "/admin?success=Profile rejected successfully")
            self.end_headers()
            return

        
        
        # ASSIGN DPO LOGIC (HOD)
        elif self.path == "/assign_dpo":

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())
            #Extract form values
            enquiry_id = data.get("enquiry_id")[0]
            dpo_id = data.get("dpo_id")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM enquiries WHERE assigned_dpo_id = ? AND status != 'Completed'", (dpo_id,))
            active_count = cursor.fetchone()[0] or 0
            if active_count >= 3:
                conn.close()
                self.send_response(303)
                self.send_header("Location", "/hod?error=This DPO already has maximum active enquiries")
                self.end_headers()
                return
                

            cursor.execute("""
                UPDATE enquiries
                SET assigned_dpo_id = ?, status = 'Assigned'
                WHERE id = ?
            """, (dpo_id, enquiry_id))

            conn.commit()
            create_notification(
                dpo_id,
                f"You have been assigned enquiry #{enquiry_id}"
            )


            hod_id = get_logged_in_user_id(self)

            log_activity(
                hod_id,
                f"Assigned enquiry #{enquiry_id} to DPO #{dpo_id}"
            )
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/hod?success=DPO assigned successfully")
            self.end_headers()


        # Updates the HOD profile name and email.
        elif self.path == "/hod_update_profile":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            hod_user_id = get_logged_in_user_id(self)
            if not hod_user_id:
                self.send_response(303)
                self.send_header("Location", "/login")
                self.end_headers()
                return

            name = data.get("name", [""])[0].strip()
            email = data.get("email", [""])[0].strip()
            if not name or not email:
                self.send_response(303)
                self.end_headers()
                self.wfile.write(b"Name and email are required.")
                return

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET name = ?, email = ? WHERE id = ? AND role = 'HOD'", (name, email, hod_user_id))
            conn.commit()
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/hod?success=Profile updated successfully")
            self.end_headers()


        # Allows the HOD to change password after confirming the old password.
        elif self.path == "/hod_change_password":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            hod_user_id = get_logged_in_user_id(self)
            if not hod_user_id:
                self.send_response(303)
                self.send_header("Location", "/login")
                self.end_headers()
                return

            old_password = data.get("old_password", [""])[0]
            new_password = data.get("new_password", [""])[0]
            confirm_password = data.get("confirm_password", [""])[0]

            if not old_password or not new_password or not confirm_password:
                self.send_response(400)
                self.send_header("Location", "/hod?error=All password fields are required")
                self.end_headers()
                
                return

            if new_password != confirm_password:
                self.send_response(400)
                self.send_header("Location", "/hod?error=Passwords do not match")
                self.end_headers()
                
                return
            #Check if current password is correct
            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE id = ? AND password = ? AND role = 'HOD'", (hod_user_id, old_password))
            if not cursor.fetchone():
                conn.close()
                self.send_response(303)
                self.send_header("Location", "/hod?error=Current password is incorrect")
                self.end_headers()
                
                return
            #Update new password in DB
            cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, hod_user_id))
            conn.commit()
            log_activity(
                hod_user_id,
                "Changed password"
            )
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/hod?success=Password changed successfully")
            self.end_headers()

        
        # SUBMIT ADVISORY LOGIC (DPO)
        elif self.path == "/submit_advisory":

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            content_type = self.headers.get('Content-Type', '')

            data, files = parse_multipart(post_data, content_type)

            enquiry_id = data.get("enquiry_id")
            draft_content = data.get("draft_content", "").strip()
            advisory_title = data.get("advisory_title", "").strip()

            if not enquiry_id or not draft_content:
                self.send_response(303)
                self.end_headers()
                self.wfile.write(b"Missing enquiry_id or draft_content")
                return

            dpo_id = get_logged_in_user_id(self)
            if not dpo_id:
                self.send_response(303)
                self.send_header("Location", "/login")
                self.end_headers()
                return

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            # Check if advisory already exists
            cursor.execute("""
                SELECT id, file_path FROM advisories WHERE enquiry_id = ?
            """, (enquiry_id,))
            existing = cursor.fetchone()

            # Handle file upload
            file_path = None
            if "advisory_file" in files and files["advisory_file"]["filename"]:
                upload_dir = "uploads"
                os.makedirs(upload_dir, exist_ok=True)
                original_name = os.path.basename(files["advisory_file"]["filename"])
                unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{original_name}"
                filepath = os.path.join(upload_dir, unique_name)
                with open(filepath, "wb") as f:
                    f.write(files["advisory_file"]["data"])
                file_path = unique_name
            elif existing:
                file_path = existing[1]

            if existing:
                # UPDATE existing advisory
                cursor.execute("""
                    UPDATE advisories
                    SET draft_content = ?, review_status = 'Pending', review_comment = NULL,
                        advisory_title = ?, file_path = ?, dpo_id = ?
                    WHERE enquiry_id = ?
                """, (draft_content, advisory_title, file_path, dpo_id, enquiry_id))
            else:
                # INSERT new advisory
                cursor.execute("""
                    INSERT INTO advisories (enquiry_id, dpo_id, draft_content, review_status, advisory_title, file_path)
                    VALUES (?, ?, ?, 'Pending', ?, ?)
                """, (enquiry_id, dpo_id, draft_content, advisory_title, file_path))

            conn.commit()
            cursor.execute(
                "SELECT id FROM users WHERE role='DDC'"
            )

            ddc = cursor.fetchone()

            if ddc:
                create_notification(
                    ddc[0],
                    f"Advisory submitted for enquiry #{enquiry_id}"
                )
            
            log_activity(
                dpo_id,
                f"Submitted advisory for enquiry #{enquiry_id}"
            )
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/dpo?success=Advisory submitted successfully")
            self.end_headers()


        # Allows the DDC to approve an advisory or return it to the DPO for revision.
        elif self.path == "/review_advisory":

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            advisory_id = data.get("advisory_id")[0]
            action = data.get("action")[0]
            comment = data.get("comment", [""])[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            if action == "approve":

                # Get draft content
                cursor.execute("""
                    SELECT draft_content, enquiry_id
                    FROM advisories
                    WHERE id = ?
                """, (advisory_id,))
                result = cursor.fetchone()

                draft_content = result[0]
                enquiry_id = result[1]

                # Move draft to final content table
                cursor.execute("""
                    UPDATE advisories
                    SET review_status = 'Approved',
                        final_content = ?,
                        review_comment = ?
                    WHERE id = ?
                """, (draft_content, comment, advisory_id))

                # Update enquiry status
                cursor.execute("""
                    UPDATE enquiries
                    SET status = 'Completed'
                    WHERE id = ?
                """, (enquiry_id,))

            # advisory that needs revision
            else:
                cursor.execute("""
                     UPDATE advisories
                     SET review_status = 'Needs Revision',
                         review_comment = ?
                     WHERE id = ?
                """, (comment, advisory_id))

            conn.commit()
            ddc_id = get_logged_in_user_id(self)

            log_activity(
                ddc_id,
                f"Returned advisory #{advisory_id} for revision"
            )
            conn.close()

            self.send_response(303)
            if action == "approve":
                self.send_header("Location", "/ddc?success=Advisory approved successfully")
            else:
                self.send_header("Location", "/ddc?success=Advisory returned for revision")
            self.end_headers()


        # Processes new enquirer registration and keeps the profile pending until Admin approval.
        elif self.path == "/enquirer_register":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            # Required common fields
            enquirer_type = data.get("enquirer_type", [""])[0]
            name = data.get("name", [""])[0].strip()
            email = data.get("email", [""])[0].strip()
            password = data.get("password", [""])[0]
            confirm_password = data.get("confirm_password", [""])[0]

            pobox = data.get("pobox", [""])[0].strip()
            location = data.get("location", [""])[0].strip()
            county = data.get("county", [""])[0].strip()
            kra_pin = data.get("kra_pin", [""])[0].strip()

            # Individual-only
            id_number = data.get("id_number", [""])[0].strip()

            # Basic validation
            if enquirer_type not in ["company", "individual"]:
                self.send_response(303)
                self.end_headers()
                self.wfile.write(b"Invalid enquirer type")
                return

            if not name or not email or not password or not pobox or not location or not county or not kra_pin:
                self.send_response(303)
                self.end_headers()
                self.wfile.write(b"Missing required fields")
                return
            
            #input validation
            if not is_valid_email(email):
                self.send_response(303)
                self.send_header("Location", "/enquirer_register?error=Invalid email format")
                self.end_headers()
                return

            if not is_valid_kra_pin(kra_pin):
                self.send_response(303)
                self.send_header("Location", "/enquirer_register?error=Invalid KRA PIN format")
                self.end_headers()
                return

            if enquirer_type == "individual" and not is_valid_id_number(id_number):
                self.send_response(303)
                self.send_header("Location", "/enquirer_register?error=Invalid ID number format")
                self.end_headers()
                return
            
            if password != confirm_password:
                self.send_response(303)
                self.send_header("Location", "/enquirer_register?error=Passwords do not match")
                self.end_headers()
                return
            
            if not is_strong_password(password):
                self.send_response(303)
                self.send_header(
                    "Location",
                    "/enquirer_register?error=Password must have at least 8 characters, uppercase, lowercase, number and special character"
                )
                self.end_headers()
                return    

            if enquirer_type == "individual" and not id_number:
                self.send_response(303)
                self.send_header("Location", "/enquirer_register?error=Missing ID number")
                self.end_headers()
                return

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            # Duplicate detection: email
            cursor.execute("SELECT id FROM enquirers WHERE email = ?", (email,))
            if cursor.fetchone():
                conn.close()
                self.send_response(303)
                self.send_header("Location", "/enquirer_register?error=Account already exists")
                self.end_headers()
                return
            

            # Duplicate detection: KRA PIN
            cursor.execute("SELECT id FROM enquirers WHERE kra_pin = ?", (kra_pin,))
            if cursor.fetchone():
                conn.close()
                self.send_response(303)
                self.send_header("Location", "/enquirer_register?error=Account already exists")
                self.end_headers()
                return
                

            # Individual duplicate detection: ID number
            if enquirer_type == "individual":
                cursor.execute("SELECT id FROM enquirers WHERE id_number = ?", (id_number,))
                if cursor.fetchone():
                    conn.close()
                    self.send_response(303)
                    self.send_header("Location", "/enquirer_register?error=Account already exists")
                    self.end_headers()
                    return

            # Insert new pending enquirer
            cursor.execute("""
                INSERT INTO enquirers (
                    enquirer_type, name, email, password,
                    pobox, location, county, kra_pin, id_number,
                    admin_verified
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (enquirer_type, name, email, hash_password(password), pobox, location, county, kra_pin, id_number))

            conn.commit()
            cursor.execute(
                "SELECT id FROM users WHERE role='Admin'"
            )

            admin = cursor.fetchone()

            if admin:
                create_notification(
                    admin[0],
                    f"New enquirer registration awaiting approval"
               )
                
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/enquirer_login?success=Registration successful. Await admin approval.")
            self.end_headers()



        # Processes enquirer login only if the account has been approved by Admin.
        elif self.path == "/enquirer_login":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            email = data.get("email")[0]
            password = data.get("password")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, password FROM enquirers WHERE email=? AND admin_verified=1",
                (email,)
            )

            enquirer = cursor.fetchone()

            if enquirer and verify_password(enquirer[1], password):

              # convert  to a hashed password.
                if not enquirer[1].startswith("pbkdf2_sha256$"):
                    cursor.execute(
                        "UPDATE enquirers SET password=? WHERE id=?",
                        (hash_password(password), enquirer[0])
                   )
                conn.commit()

                conn.close()

            if enquirer:
                log_enquirer_activity(
                    enquirer[0],
                    "Logged into the enquirer portal"
                )
                self.send_response(303)
                self.send_header("Set-Cookie", f"enquirer_id={enquirer[0]}; Path=/")
                self.send_header("Location", "/enquirer_dashboard?success=Login successful")
                self.end_headers()
            else:
                conn.close()
                self.send_response(303)
                self.send_header("Location", "/enquirer_login?error=Invalid credentials or account not approved")
                self.end_headers()


        # Processes an enquiry submitted by a logged-in enquirer.
        elif self.path == "/submit_enquiry":
            enquirer_id = get_logged_in_enquirer_id(self)
            if not enquirer_id:
                self.send_response(303)
                self.send_header("Location", "/enquirer_login")
                self.end_headers()
                return

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            subject = data.get("subject")[0]
            description = data.get("description")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute("SELECT name, email FROM enquirers WHERE id=?", (enquirer_id,))
            enquirer = cursor.fetchone()
            date_received = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO enquiries (enquirer_name, enquirer_email, subject, description, date_received, status, enquirer_id)
                VALUES (?, ?, ?, ?, ?, 'New', ?)
            """, (enquirer[0], enquirer[1], subject, description, date_received, enquirer_id))
            conn.commit()
            log_enquirer_activity(
                enquirer_id,
                f"Submitted enquiry: {subject}"
            )
            cursor.execute(
                "SELECT id FROM users WHERE role='HOD'"
            )

            hod = cursor.fetchone()

            if hod:
                create_notification(
                    hod[0],
                    f"New enquiry submitted: {subject}"
                )
            conn.close() 

            self.send_response(303)
            self.send_header("Location", "/enquirer_dashboard")
            self.end_headers()


        # Logs out the enquirer by clearing the enquirer_id cookie.
        elif self.path == "/enquirer_logout":
            self.send_response(303)
            self.send_header("Set-Cookie", "enquirer_id=; expires=Thu, 01 Jan 1970 00:00:00 GMT")
            self.send_header("Location", "/")
            self.end_headers()

        # Updates the DPO profile name and email.
        elif self.path == "/dpo_update_profile":

            content_length = int(
                self.headers['Content-Length']
            )

            post_data = self.rfile.read(content_length)

            data = urllib.parse.parse_qs(
                post_data.decode()
            )

            user_id = get_logged_in_user_id(self)

            name = data.get("name")[0]
            email = data.get("email")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE users
                SET name=?, email=?
                WHERE id=?
                """,
                (name, email, user_id)
            )

            conn.commit()
            log_activity(
                user_id,
                "Updated profile information"
            )
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/dpo?success=Profile updated successfully")
            self.end_headers()

        # Allows the DPO to change password after checking the old password.
        elif self.path == "/dpo_change_password":

            content_length = int(
                self.headers['Content-Length']
            )

            post_data = self.rfile.read(content_length)

            data = urllib.parse.parse_qs(
                post_data.decode()
            )

            user_id = get_logged_in_user_id(self)

            old_password = data.get(
                "old_password"
            )[0]

            new_password = data.get(
                "new_password"
            )[0]

            confirm_password = data.get(
                "confirm_password"
            )[0]

            if new_password != confirm_password:

                self.send_response(200)
                self.send_header("Location", "/dpo?error=New password and confirmation do not match")
                self.end_headers()

                return

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT password
                FROM users
                WHERE id=?
                """,
                (user_id,)
            )

            result = cursor.fetchone()

            if not result or result[0] != old_password:

                conn.close()

                self.send_response(303)
                self.send_header("Location", "/dpo?error=Current password is incorrect")
                self.end_headers()
                return
               
            cursor.execute(
                """
                UPDATE users
                SET password=?
                WHERE id=?
                """,
                (new_password, user_id)
            )

            conn.commit()
            log_activity(
                user_id,
                "Changed password"
            )
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/dpo?success=Password changed successfully")
            self.end_headers()

        # Updates the DDC profile name and email.
        elif self.path == "/ddc_update_profile":

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            user_id = get_logged_in_user_id(self)
            name = data.get("name")[0]
            email = data.get("email")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE users
                SET name=?, email=?
                WHERE id=?
                """,
                (name, email, user_id)
            )

            conn.commit()
            log_activity(
                user_id,
                "Updated profile information"
            )
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/ddc?success=Profile updated successfully")
            self.end_headers()


        # Allows the DDC to change password after checking the old password.
        elif self.path == "/ddc_change_password":

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            user_id = get_logged_in_user_id(self)

            old_password = data.get("old_password")[0]
            new_password = data.get("new_password")[0]
            confirm_password = data.get("confirm_password")[0]

            if new_password != confirm_password:
                self.send_response(303)
                self.send_header("Location", "/ddc?error=New password and confirmation do not match")
                self.end_headers()
                
                return

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT password
                FROM users
                WHERE id=?
                """,
                (user_id,)
            )

            result = cursor.fetchone()

            if not result or result[0] != old_password:
                conn.close()
                self.send_response(303)
                self.send_header("Location", "/ddc?error=Current password is incorrect")
                self.end_headers()
                
                return

            cursor.execute(
                """
                UPDATE users
                SET password=?
                WHERE id=?
                """,
                (new_password, user_id)
            )

            conn.commit()
            log_activity(
                user_id,
                "Changed password"
            )
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/ddc?success=Password changed successfully")
            self.end_headers()

# Starts the HTTP server on localhost using the defined PORT and MyHandler class.
def run():
    server = HTTPServer(("localhost", PORT), MyHandler)
    print(f"Server running on http://localhost:{PORT}")
    server.serve_forever()



# Ensures the server only starts when this file is run directly, not when imported by another file.
if __name__ == "__main__":
    run()

