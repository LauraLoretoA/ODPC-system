from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import sqlite3
import urllib.parse
import os
import mimetypes


from Extras.auth import get_logged_in_enquirer_id

def get_logged_in_user_id(handler):
    cookie = handler.headers.get('Cookie')
    if not cookie:
        return None

    parts = cookie.split(";")
    for part in parts:
        if "user_id=" in part:
            return part.strip().split("=")[1]

    return None


def parse_multipart(post_data, content_type):
    """Simple multipart/form-data parser (no frameworks)."""
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


# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)

PORT = 8000


class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):

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

        # Login page
        if self.path == "/" or self.path == "/login":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            with open("Pages/login.html", "r") as file:
                self.wfile.write(file.read().encode())

# Admin Dashboard - Pending Enquirers for verification
        elif self.path == "/admin":
            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, email, admin_verified
                FROM enquirers 
                WHERE admin_verified = 0
                ORDER BY id DESC
            """)
            pending_enquirers = cursor.fetchall()
            print(f"DEBUG ADMIN: Found {len(pending_enquirers)} pending enquirers: {pending_enquirers}")
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
                    enq_id, name, email, verified = enq
                    pending_html += f"""
                <article class='item-card'>    
                    <p><strong>ID:</strong> {enq_id}</p>    
                    <p><strong>Name:</strong> {name}</p>    
                    <p><strong>Email:</strong> {email}</p>   
                    <p><strong>Status:</strong> <span style='color:orange;'>Pending Verification</span></p>   
                    <div class='item-actions'>        
                        <form method="POST" action="/verify_enquirer" style="display:inline;">           
                            <input type="hidden" name="enq_id" value="{enq_id}">            
                            <button type="submit">Verify & Approve</button>        
                        </form> 
                        <form method="POST" action="/reject_enquirer" style="display:inline;">
                            <input type="hidden" name="enq_id" value="{enq_id}">
                            <button type="submit" style="background-color:red;">Reject</button>
                        </form>  
                    </div>
                </article>
                """
            else:
                pending_html += "<p>No pending enquirers needing verification.</p>"

            print(f"DEBUG ADMIN: Generated pending_html length: {len(pending_html)}")
            print(f"DEBUG ADMIN: pending_html preview: {pending_html[:200]}...")

            
            html = html.replace('<div id="pending-enquirers-list"></div>', pending_html)
    
            print(f"DEBUG ADMIN: Final HTML length: {len(html)}")

            self.wfile.write(html.encode())



        # HOD Dashboard
        elif self.path.startswith("/hod"):
            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            # Get enquiries with assigned DPO name
            cursor.execute("""
                SELECT e.*, u.name as dpo_name, enq.name as enq_name, enq.email as enq_email
                FROM enquiries e
                LEFT JOIN users u ON e.assigned_dpo_id = u.id
                LEFT JOIN enquirers enq ON e.enquirer_id = enq.id
            """)
            enquiries = cursor.fetchall()

            # Get DPO users
            cursor.execute("SELECT id, name FROM users WHERE role='DPO'")
            dpos = cursor.fetchall()
            conn.close()

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            html = """
            <html lang='en'>
            <head>
              <meta charset='UTF-8'>
              <meta name='viewport' content='width=device-width, initial-scale=1.0'>
              <title>HOD Dashboard</title>
              <link rel='stylesheet' href='/style.css'>
            </head>
            <body>
              <div class='page-shell'>
                <header class='header'>
                  <img src='/logo.png' class='logo' alt='ODPC logo'>
                  <h1>HOD Dashboard</h1>
                </header>
                <main class='container'>
                  <section class='card'>
                    <h2>All Enquiries</h2>
            """

            today = datetime.today()

            for enquiry in enquiries:
                # enquiry columns: 0=id, 1=name, 2=email, 3=subject, 4=description, 5=date, 6=status, 7=assigned_dpo_id, 8=dpo_name
                assigned_dpo_id = enquiry[7]
                dpo_name = enquiry[8]

                # Build DPO options dropdown
                options = ""
                for dpo in dpos:
                    options += f"<option value='{dpo[0]}'>{dpo[1]}</option>"

                date_received_str = enquiry[5]

                if date_received_str:
                    try:
                        date_received = datetime.strptime(date_received_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        date_received = datetime.strptime(date_received_str, "%Y-%m-%d")
                    deadline = date_received + timedelta(days=10)
                    days_remaining = (deadline - today).days

                    if days_remaining < 0:
                        deadline_status = "<span style='color:red;'>OVERDUE</span>"
                    else:
                        deadline_status = f"{days_remaining} days remaining"
                else:
                    deadline_status = "No date recorded"

                html += f"""
                <article class='item-card'>
                    <p><strong>ID:</strong> {enquiry[0]}</p>
                    <p><strong>Name:</strong> {enquiry[1]}</p>
                    <p><strong>Email:</strong> {enquiry[2]}</p>
                    <p><strong>Subject:</strong> {enquiry[3]}</p>
                    <p><strong>Description:</strong> {enquiry[4]}</p>
                    <p><strong>Date Received:</strong> {enquiry[5]}</p>
                    <p><strong>Status:</strong> {enquiry[6]}</p>
                    <p><strong>Deadline Status:</strong> {deadline_status}</p>
                """

                if assigned_dpo_id:
                    html += f"""
                    <p><strong>Assigned DPO:</strong> {dpo_name if dpo_name else 'Unknown'}</p>
                    """
                else:
                    html += f"""
                    <div class='item-actions'>
                      <form method="POST" action="/assign_dpo">
                          <input type="hidden" name="enquiry_id" value="{enquiry[0]}">
                          <select name="dpo_id">
                              {options}
                          </select>
                          <button type="submit">Assign DPO</button>
                      </form>
                    </div>
                    """

                html += "</article>"

            html += "</section></main></div></body></html>"

            self.wfile.write(html.encode())

        elif self.path.startswith("/dpo"):

            user_id = get_logged_in_user_id(self)

            if not user_id:
                self.send_response(303)
                self.send_header("Location", "/login")
                self.end_headers()
                return

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

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
            conn.close()

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            html = """
            <html lang='en'>
            <head>
              <meta charset='UTF-8'>
              <meta name='viewport' content='width=device-width, initial-scale=1.0'>
              <title>DPO Dashboard</title>
              <link rel='stylesheet' href='/style.css'>
            </head>
            <body>
              <div class='page-shell'>
                <header class='header'>
                  <img src='/logo.png' class='logo' alt='ODPC logo'>
                  <h1>DPO Dashboard</h1>
                </header>
                <main class='container'>
                  <section class='card'>
                    <h2>Assigned Enquiries</h2>
            """

            today = datetime.today()

            for enquiry in enquiries:
                # 0=id, 1=name, 2=email, 3=subject, 4=description, 5=date_received, 6=status,
                # 7=review_status, 8=review_comment, 9=advisory_title, 10=file_path, 11=draft_content
                review_status = enquiry[7]
                review_comment = enquiry[8]
                advisory_title = enquiry[9]
                file_path = enquiry[10]
                date_received_str = enquiry[5]

                if date_received_str:
                    try:
                        date_received = datetime.strptime(date_received_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        date_received = datetime.strptime(date_received_str, "%Y-%m-%d")
                    deadline = date_received + timedelta(days=10)
                    days_remaining = (deadline - today).days

                    if days_remaining < 0:
                        deadline_status = "<span style='color:red;'>OVERDUE</span>"
                    else:
                        deadline_status = f"{days_remaining} days remaining"
                else:
                    deadline_status = "No date recorded"

                html += f"""
                <article class='item-card'>
                    <p><strong>ID:</strong> {enquiry[0]}</p>
                    <p><strong>Name:</strong> {enquiry[1]}</p>
                    <p><strong>Email:</strong> {enquiry[2]}</p>
                    <p><strong>Subject:</strong> {enquiry[3]}</p>
                    <p><strong>Description:</strong> {enquiry[4]}</p>
                    <p><strong>Date Received:</strong> {enquiry[5]}</p>
                    <p><strong>Status:</strong> {enquiry[6]}</p>
                    <p><strong>Deadline:</strong> {deadline_status}</p>

                    <p><strong>Review Status:</strong> {review_status if review_status else "Not reviewed"}</p>
                    <p><strong>Comment:</strong> {review_comment if review_comment else "None"}</p>
                """

                if advisory_title:
                    html += f"<p><strong>Advisory Title:</strong> {advisory_title}</p>"
                if file_path:
                    html += f"<p><strong>Attachment:</strong> <a href='/download/{file_path}' target='_blank'>{file_path}</a></p>"

                if not review_status or review_status == "Needs Revision":
                    html += f"""
                    <div class='item-actions'>
                      <form method="GET" action="/draft_advisory">
                          <input type="hidden" name="enquiry_id" value="{enquiry[0]}">
                          <button type="submit">Draft / Redraft Advisory</button>
                      </form>
                    </div>
                    """

                elif review_status == "Approved":
                    html += "<p style='color:green;'><strong>Approved</strong></p>"

                html += "</article>"

            html += "</section></main></div></body></html>"

            self.wfile.write(html.encode())

        elif self.path.startswith("/draft_advisory"):

            user_id = get_logged_in_user_id(self)
            if not user_id:
                self.send_response(303)
                self.send_header("Location", "/login")
                self.end_headers()
                return

            query = urllib.parse.urlparse(self.path).query
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

        elif self.path.startswith("/ddc"):

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

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
            conn.close()

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            html = """
            <html lang='en'>
            <head>
              <meta charset='UTF-8'>
              <meta name='viewport' content='width=device-width, initial-scale=1.0'>
              <title>DDC Dashboard</title>
              <link rel='stylesheet' href='/style.css'>
            </head>
            <body>
              <div class='page-shell'>
                <header class='header'>
                  <img src='/logo.png' class='logo' alt='ODPC logo'>
                  <h1>DDC Review Dashboard</h1>
                </header>
                <main class='container'>
                  <section class='card'>
                    <h2>Advisories for Review</h2>
            """

            for adv in advisories:
                # 0=id, 1=subject, 2=description, 3=draft, 4=final, 5=status, 6=comment, 7=title, 8=file_path

                file_link = ""
                if adv[8]:
                    file_link = f"<p><strong>Attachment:</strong> <a href='/download/{adv[8]}' target='_blank'>{adv[8]}</a></p>"

                title_display = f"<p><strong>Advisory Title:</strong> {adv[7]}</p>" if adv[7] else ""

                html += f"""
                <article class='item-card'>
                    <p><strong>Advisory ID:</strong> {adv[0]}</p>
                    {title_display}
                    <p><strong>Subject:</strong> {adv[1]}</p>
                    <p><strong>Description:</strong> {adv[2]}</p>

                    <p><strong>Draft:</strong><br>{adv[3]}</p>
                    <p><strong>Final:</strong><br>{adv[4] if adv[4] else "Not approved yet"}</p>
                    {file_link}

                    <p><strong>Status:</strong> {adv[5] if adv[5] else "Pending"}</p>
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

            html += "</section></main></div></body></html>"

            self.wfile.write(html.encode())

        elif self.path == "/enquirer_register":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open("Pages/enquirer_register.html", "r") as file:
                self.wfile.write(file.read().encode())
        elif self.path == "/enquirer_login":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open("Pages/enquirer_login.html", "r") as file:
                self.wfile.write(file.read().encode())
        elif self.path == "/submit_enquiry":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open("Pages/submit_enquiry.html", "r") as file:
                self.wfile.write(file.read().encode())
        elif self.path == "/enquirer_dashboard":
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
                       a.final_content, a.advisory_title
                FROM enquiries e
                LEFT JOIN advisories a ON e.id = a.enquiry_id
                WHERE e.enquirer_id = ?
                ORDER BY e.id DESC
            """, (enquirer_id,))
            enquiries = cursor.fetchall()
            conn.close()

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            with open("Pages/enquirer_dashboard.html", "r") as file:
                html = file.read()

            # Dynamic enquiries section
            enquiries_html = "<h3>Your Enquiries:</h3>"
            if enquiries:
                today = datetime.today()
                for enquiry in enquiries:
                    enq_id, subject, desc, date_str, status, final_content, advisory_title = enquiry
                    # Calculate deadline (10 days from received)
                    if date_str:
                        try:
                            date_received = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            date_received = datetime.strptime(date_str, "%Y-%m-%d")
                        deadline = date_received + timedelta(days=10)
                        days_remaining = max(0, (deadline - today).days)
                        if days_remaining == 0:
                            deadline_status = "<span style='color:orange;'>Today</span>"
                        elif days_remaining < 0:
                            deadline_status = "<span style='color:red;'>Overdue</span>"
                        else:
                            deadline_status = f"{days_remaining} days left"
                    else:
                        deadline_status = "N/A"

                    enquiries_html += f"""
                    <article class='item-card'>
                        <p><strong>ID:</strong> {enq_id}</p>
                        <p><strong>Subject:</strong> {subject}</p>
                        <p><strong>Status:</strong> <span style="color:{'green' if status=='Completed' else 'blue' if status=='Assigned' else 'orange'}">{status}</span></p>
                        <p><strong>Date:</strong> {date_str or 'N/A'}</p>
                        <p><strong>Deadline:</strong> {deadline_status}</p>
                        <p><strong>Description:</strong> {desc[:100]}{'...' if len(desc)>100 else ''}</p>
                        {f"<hr><p><strong>Advisory Title:</strong> {advisory_title}</p><p><strong>Final Response:</strong><br>{final_content}</p>" if status == 'Completed' and final_content else ""}
                    </article>
                    """
            else:
                enquiries_html += "<p>No enquiries yet. <a href='/submit_enquiry'>Submit your first enquiry</a></p>"
            import re
            html = re.sub(
                r'<div id="enquiries">.*?</div>',
                f'<div id="enquiries">{enquiries_html}</div>',
                html,
                flags=re.DOTALL
                )              
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Page not found")

    def do_POST(self):

        # LOGIN LOGIC
        if self.path == "/login":

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            email = data.get("email")[0]
            password = data.get("password")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute(
                 "SELECT id, role FROM users WHERE email=? AND password=?",
                 (email, password)
            )

            user = cursor.fetchone()
            conn.close()

            if user:
                user_id = user[0]
                role = user[1]

                self.send_response(303)
                self.send_header("Set-Cookie", f"user_id={user_id}")

                if role == "Admin":
                    self.send_header("Location", "/admin")
                elif role == "HOD":
                    self.send_header("Location", "/hod")
                elif role == "DPO":
                    self.send_header("Location", "/dpo")
                elif role == "DDC":
                    self.send_header("Location", "/ddc")
                self.end_headers()

            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Invalid email or password")

        # CREATE USER LOGIC (ADMIN)
        elif self.path == "/create_user":

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            name = data.get("name")[0]
            email = data.get("email")[0]
            password = data.get("password")[0]
            role = data.get("role")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO users (name, email, password, role)
                VALUES (?, ?, ?, ?)
            """, (name, email, password, role))

            conn.commit()
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/admin")
            self.end_headers()
           

        # VERIFY ENQUIRER (ADMIN)
        elif self.path == "/verify_enquirer":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            enq_id = data.get("enq_id")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE enquirers SET admin_verified = 1 WHERE id = ?", (enq_id,))
            conn.commit()
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/admin")
            self.end_headers()
            return
        
        # REJECT ENQUIRER (ADMIN)
        # REJECT ENQUIRER (ADMIN)
        elif self.path == "/reject_enquirer":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            enq_id = data.get("enq_id")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM enquirers WHERE id = ? AND admin_verified = 0", (enq_id,))
            conn.commit()
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/admin")
            self.end_headers()
            return
        
        # ASSIGN DPO LOGIC (HOD)
        elif self.path == "/assign_dpo":

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            enquiry_id = data.get("enquiry_id")[0]
            dpo_id = data.get("dpo_id")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE enquiries
                SET assigned_dpo_id = ?, status = 'Assigned'
                WHERE id = ?
            """, (dpo_id, enquiry_id))

            conn.commit()
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/hod")
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
                self.send_response(400)
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
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/dpo")
            self.end_headers()

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
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/ddc")
            self.end_headers()

        elif self.path == "/enquirer_register":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            name = data.get("name")[0]
            email = data.get("email")[0]
            password = data.get("password")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO enquirers (name, email, password)
                VALUES (?, ?, ?)
            """, (name, email, password))
            conn.commit()
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/enquirer_login")
            self.end_headers()

        elif self.path == "/enquirer_login":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode())

            email = data.get("email")[0]
            password = data.get("password")[0]

            conn = sqlite3.connect("odpc.db")
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM enquirers WHERE email=? AND password=? AND admin_verified=1", (email, password))
            enquirer = cursor.fetchone()
            conn.close()

            if enquirer:
                self.send_response(303)
                self.send_header("Set-Cookie", f"enquirer_id={enquirer[0]}; Path=/")
                self.send_header("Location", "/enquirer_dashboard")
                self.end_headers()
            else:
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
<!DOCTYPE html>
<html>
<body>
Unverified account or invalid credentials. Contact admin for approval.
<a href="/enquirer_login">Back to Login</a>
</body>
</html>
                """)

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
            conn.close()

            self.send_response(303)
            self.send_header("Location", "/enquirer_dashboard")
            self.end_headers()

        elif self.path == "/enquirer_logout":
            self.send_response(303)
            self.send_header("Set-Cookie", "enquirer_id=; expires=Thu, 01 Jan 1970 00:00:00 GMT")
            self.send_header("Location", "/")
            self.end_headers()

def run():
    server = HTTPServer(("localhost", PORT), MyHandler)
    print(f"Server running on http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()

