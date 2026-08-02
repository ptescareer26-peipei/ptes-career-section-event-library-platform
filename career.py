import io
import re
import calendar
import smtplib
import urllib.parse
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
from PIL import Image
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# Google API Client & OAuth Credentials
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ==========================================
# 1. PAGE CONFIGURATION & GLOBAL CONSTANTS
# ==========================================
st.set_page_config(page_title="PTES Career Section Portal", layout="wide")

# Google Drive Target Folder ID
GDRIVE_FOLDER_ID = "1yFdDBqKb73uM3lcCWmvl9AJr5ETVnrWc"

# Default Admin WhatsApp Contact Number
ADMIN_WA_NUMBER = "6737318186"

# Database Columns Schema (Strictly Columns A through K)
DB_COLUMNS = [
    "Event ID", 
    "Date", 
    "Time", 
    "Title", 
    "Venue", 
    "Target Audience", 
    "Organization Body", 
    "Facilitator Name", 
    "Contact Number", 
    "Materials_Link", 
    "Status"
]

# ==========================================
# 2. STYLING (CUSTOM GLOBAL CSS)
# ==========================================
custom_css = """
<style>
    .stApp, .stAppViewContainer, [data-testid="stHeader"] {
        background-color: #E5C2F5 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #FAE48F !important;
    }
    .header-container {
        background-color: #D4FA8F;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 15px;
        text-align: center;
        border: 4px solid #45DB24;
    }
    .header-container h1 {
        color: #111111 !important;
        font-weight: 800;
        margin-bottom: 5px;
    }
    div[data-testid="stForm"] {
        background-color: #FDE7FE !important;
        padding: 20px !important;
        border-radius: 12px !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FABBFC !important;
        border-radius: 12px !important;
        padding: 10px !important;
    }
    div[data-testid="stWidgetLabel"] p {
        font-size: 12pt !important;
        font-weight: bold !important;
        color: #111111 !important;
    }
    button[data-baseweb="tab"],
    button[data-baseweb="tab"] *,
    [data-testid="stTab"],
    [data-testid="stTab"] * {
        font-weight: 900 !important;
        font-size: 13pt !important;
    }
    button[data-baseweb="tab"] {
        background-color: rgba(255, 255, 255, 0.4) !important;
        border-radius: 8px 8px 0px 0px !important;
        padding: 8px 16px !important;
        margin-right: 4px !important;
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ==========================================
# 3. HELPER FUNCTIONS & CONNECTIONS
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

def get_drive_service():
    """Builds and returns Google Drive API service client using User OAuth credentials."""
    if "gcp_oauth" not in st.secrets:
        return None
    creds = Credentials(
        token=None,
        refresh_token=st.secrets["gcp_oauth"]["refresh_token"],
        client_id=st.secrets["gcp_oauth"]["client_id"],
        client_secret=st.secrets["gcp_oauth"]["client_secret"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

def list_drive_files_from_folder():
    """Fetches list of all files directly inside the Google Drive target folder."""
    try:
        service = get_drive_service()
        if not service:
            return []
        
        query = f"'{GDRIVE_FOLDER_ID}' in parents and trashed = false"
        results = service.files().list(
            q=query,
            fields="files(id, name, webViewLink, createdTime)",
            orderBy="createdTime desc"
        ).execute()
        
        return results.get("files", [])
    except Exception as e:
        st.error(f"Error fetching files from Google Drive: {e}")
        return []

def delete_single_drive_file(file_id):
    """Deletes a single file directly from Google Drive by File ID."""
    try:
        service = get_drive_service()
        if not service:
            return False, "Missing Google Drive API credentials."
        
        service.files().delete(fileId=file_id).execute()
        return True, "File permanently deleted from Google Drive."
    except Exception as e:
        return False, f"Error deleting file from Google Drive: {e}"

def upload_multiple_pdfs_to_drive(uploaded_file_list, generated_event_id):
    """Uploads PDF files to Google Drive folder using OAuth credentials."""
    if not uploaded_file_list:
        return "0 File(s)"

    uploaded_links = []
    try:
        service = get_drive_service()
        if not service:
            st.error("⚠️ Streamlit secrets missing [gcp_oauth] key!")
            return "0 File(s) [Error: Missing Secrets]"

        for index, pdf_file in enumerate(uploaded_file_list, start=1):
            renamed_title = f"{generated_event_id}_Doc{index}.pdf"

            file_metadata = {
                "name": renamed_title,
                "parents": [GDRIVE_FOLDER_ID]
            }

            media = MediaIoBaseUpload(
                io.BytesIO(pdf_file.getvalue()),
                mimetype="application/pdf",
                resumable=True
            )

            drive_file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, webViewLink"
            ).execute()

            file_id = drive_file.get("id")

            permission = {"type": "anyone", "role": "reader"}
            service.permissions().create(
                fileId=file_id, 
                body=permission
            ).execute()

            uploaded_links.append(drive_file.get("webViewLink"))

        return ", ".join(uploaded_links)
    except Exception as e:
        st.error(f"Error uploading PDF documents to Google Drive: {e}")
        return "0 File(s) [Upload Failed]"

def delete_files_from_drive(materials_link_str):
    """Extracts Drive File IDs from links and permanently deletes them from Google Drive."""
    if not materials_link_str or "0 File(s)" in materials_link_str:
        return 0, "No attached files to delete."

    try:
        service = get_drive_service()
        if not service:
            return 0, "Missing Drive API credentials."

        urls = [link.strip() for link in str(materials_link_str).split(",") if link.strip().startswith("http")]
        deleted_count = 0

        for url in urls:
            match = re.search(r'/d/([a-zA-Z0-9_-]+)', url) or re.search(r'id=([a-zA-Z0-9_-]+)', url)
            if match:
                file_id = match.group(1)
                try:
                    service.files().delete(fileId=file_id).execute()
                    deleted_count += 1
                except Exception as file_err:
                    st.warning(f"Could not delete Drive file ID {file_id}: {file_err}")

        return deleted_count, f"Successfully deleted {deleted_count} file(s) from Google Drive."
    except Exception as e:
        return 0, f"Error deleting files from Google Drive: {e}"

def send_admin_email(details):
    """Sends an automated HTML notification email to the admin Outlook address."""
    try:
        sender_email = st.secrets["SENDER_EMAIL"]
        sender_password = st.secrets["SENDER_PASSWORD"]
        receiver_email = st.secrets["ADMIN_RECEIVER_EMAIL"]

        subject = f"🔔 New External Career Event Request: {details['Org']}"
        body = f"""
        <html>
            <body>
                <h2>📌 New Career Event Request ({details['Event_ID']})</h2>
                <ul>
                    <li><b>Event ID:</b> {details['Event_ID']}</li>
                    <li><b>Organization:</b> {details['Org']}</li>
                    <li><b>Facilitator:</b> {details['Facilitator']} ({details['Contact']})</li>
                    <li><b>Requested Date:</b> {details['Date']}</li>
                    <li><b>Requested Venue:</b> {details['Venue']}</li>
                    <li><b>Target Audience:</b> {details['Audience']}</li>
                    <li><b>Proposal Details:</b> {details['Details']}</li>
                    <li><b>Materials Link / Files:</b> {details['Materials']}</li>
                </ul>
            </body>
        </html>
        """
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = receiver_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.warning(f"Request saved, but automated email alert failed: {e}")
        return False

# Read Data safely from Google Sheets
try:
    master_data = conn.read(ttl=0)
    if master_data is None or master_data.empty:
        master_data = pd.DataFrame(columns=DB_COLUMNS)
    else:
        master_data = master_data.dropna(how="all").reindex(columns=DB_COLUMNS)
except Exception:
    master_data = pd.DataFrame(columns=DB_COLUMNS)

# Retrieve Admin Password safely from Streamlit secrets
try:
    target_password = st.secrets.get("admin_password", "admin123")
except Exception:
    target_password = "admin123"

# ==========================================
# 4. HEADER SECTION
# ==========================================
st.markdown("""
    <div class="header-container">
        <h1>PUSAT TINGKATAN ENAM SENGKURONG</h1>
        <p style="font-size: 18px; font-weight: bold; color: #111;">🎓 PTES Career Section Portal 🎓</p>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# 5. SIDEBAR: ADMIN MANAGEMENT
# ==========================================
with st.sidebar:
    try:
        logo = Image.open('ptes_logo.PNG')
        st.image(logo, width='stretch')
    except Exception:
        st.info("Logo image optional.")

    st.header("⚙️ Admin Management")
    admin_password = st.text_input("Enter Admin Password", type="password", key="sidebar_password")

    if target_password and admin_password == target_password:
        st.success("✅ Admin Access Active")
        st.divider()

        if "delete_success_msg" in st.session_state:
            st.warning(st.session_state.delete_success_msg)
            del st.session_state.delete_success_msg

        st.subheader("🗑️ Delete / Cancel Event")
        
        if not master_data.empty:
            event_options = {}
            for idx, row in master_data.iterrows():
                label = f"[{row['Event ID']}] {row['Title']} ({row['Date']})"
                event_options[label] = idx

            selected_event_label = st.selectbox("Select Event to Cancel", list(event_options.keys()))
            cancel_reason = st.text_area("Reason for Cancellation")

            if st.button("Delete Event & Files", type="primary"):
                target_idx = event_options[selected_event_label]
                deleted_id = master_data.loc[target_idx, 'Event ID']
                deleted_title = master_data.loc[target_idx, 'Title']
                materials_link_val = master_data.loc[target_idx, 'Materials_Link']

                with st.spinner(f"Deleting files from Google Drive and removing Event [{deleted_id}]... Please wait."):
                    count_deleted, drive_msg = delete_files_from_drive(materials_link_val)
                    
                    updated_df = master_data.drop(index=target_idx).reset_index(drop=True).reindex(columns=DB_COLUMNS)
                    conn.update(data=updated_df)
                    st.cache_data.clear()

                st.session_state.delete_success_msg = (
                    f"🗑️ **DELETED!** Event ID **[{deleted_id}] - {deleted_title}** has been removed.\n\n"
                    f"📄 **Drive Cleanup:** {drive_msg}"
                )

                st.rerun()
        else:
            st.info("No events in database to delete.")
    else:
        st.caption("🔒 Enter valid admin credentials to unlock management tools.")

# ==========================================
# 6. TAB NAVIGATION
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📅 Event Calendar", 
    "🔍 Information Preview & File Manager", 
    "📤 Pending Approvals & Venues", 
    "✉️ New Request"
])

# ==========================================
# TAB 1: CALENDAR & EVENT STATUS BY DATE
# ==========================================
with tab1:
    st.subheader("📅 Career Events Calendar & Status")

    with st.container(border=True):
        col_m, col_y = st.columns(2)
        with col_m:
            month_names = list(calendar.month_name)[1:]
            selected_month_str = st.selectbox("Select Month", month_names, index=datetime.today().month - 1)
            selected_month = month_names.index(selected_month_str) + 1
        with col_y:
            selected_year = st.number_input("Select Year", min_value=2024, max_value=2030, value=datetime.today().year)

        if 'selected_calendar_day' not in st.session_state:
            st.session_state.selected_calendar_day = datetime.today().day

        if not master_data.empty:
            temp_dates = pd.to_datetime(master_data['Date'], format='%d/%m/%Y', errors='coerce')
            month_events = master_data[
                (temp_dates.dt.month == selected_month) &
                (temp_dates.dt.year == selected_year)
            ]
        else:
            month_events = pd.DataFrame()

        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdayscalendar(selected_year, selected_month)
        days_header = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        
        cols = st.columns(7)
        for i, h in enumerate(days_header):
            cols[i].markdown(f"**{h}**")

        st.divider()

        for week in month_days:
            grid_cols = st.columns(7)
            for i, day in enumerate(week):
                with grid_cols[i]:
                    if day != 0:
                        day_str = f"{day:02d}/{selected_month:02d}/{selected_year}"
                        day_has_events = not month_events.empty and not month_events[month_events['Date'] == day_str].empty
                        
                        btn_label = f"🔴 {day:02d}" if day_has_events else f"⚪ {day:02d}"
                        
                        if st.button(btn_label, key=f"cal_btn_{day}_{selected_month}_{selected_year}", width='stretch'):
                            st.session_state.selected_calendar_day = day

    active_day = st.session_state.selected_calendar_day
    max_days = calendar.monthrange(selected_year, selected_month)[1]
    if active_day > max_days:
        active_day = max_days

    selected_date_str = f"{active_day:02d}/{selected_month:02d}/{selected_year}"
    st.markdown(f"### 🔍 Scheduled Events & Requests for **{selected_date_str}**")

    if not month_events.empty:
        day_details = month_events[month_events['Date'] == selected_date_str]
        if not day_details.empty:
            for _, row in day_details.iterrows():
                status_color = "🟢" if row['Status'] == "Officially Confirmed" else "🟡"
                
                with st.expander(f"{status_color} [{row['Event ID']}] {row['Title']} ({row['Time']}) - Status: {row['Status']}", expanded=True):
                    st.write(f"**Event ID:** `{row['Event ID']}`")
                    st.write(f"**Status:** `{row['Status']}`")
                    st.write(f"**Venue:** {row['Venue']}")
                    st.write(f"**Target Audience:** {row['Target Audience']}")
                    st.write(f"**Organization:** {row['Organization Body']}")
                    st.write(f"**Facilitator:** {row['Facilitator Name']} ({row['Contact Number']})")
                    
                    mat_val = str(row['Materials_Link']) if pd.notnull(row['Materials_Link']) and str(row['Materials_Link']).strip() else "0 File(s)"
                    st.write(f"**Materials Attached:** {mat_val}")
        else:
            st.info("No events scheduled or requested for this date.")
    else:
        st.info("No events scheduled for this month.")

# ==========================================
# TAB 2: EXTRACT MATERIALS & DIRECT DRIVE FILE MANAGER
# ==========================================
with tab2:
    st.subheader("🔍 Extract Documents & Google Drive File Manager")

    # Persistent alert message display
    if "drive_tab_msg" in st.session_state:
        st.success(st.session_state.drive_tab_msg)
        del st.session_state.drive_tab_msg

    mode = st.radio(
        "Choose Search Method:", 
        ["1. Lookup by Event ID (Google Sheets)", "2. Browse Google Drive Folder directly (by Date / Event ID)"],
        horizontal=True
    )

    st.divider()

    if mode.startswith("1."):
        search_id = st.text_input("Enter Event ID (e.g., CS-26-08-01):", placeholder="CS-26-08-01").strip()

        if search_id and not master_data.empty:
            matched_event = master_data[master_data['Event ID'].astype(str).str.contains(search_id, case=False, na=False)]

            if not matched_event.empty:
                for idx, row in matched_event.iterrows():
                    st.markdown(f"### 📌 Event: **{row['Title']}** (`{row['Event ID']}`)")
                    
                    if row['Status'] == "Officially Confirmed":
                        st.success(f"✅ Status: **{row['Status']}**")
                    else:
                        st.warning(f"⏳ Status: **{row['Status']}** (Awaiting PTES Admin Confirmation)")

                    raw_link_val = str(row['Materials_Link']) if pd.notnull(row['Materials_Link']) else ""
                    
                    if raw_link_val and "0 File(s)" not in raw_link_val:
                        doc_links = [link.strip() for link in raw_link_val.split(",") if link.strip().startswith("http")]
                    else:
                        doc_links = []

                    if doc_links:
                        st.write(f"📎 Found **{len(doc_links)}** document(s) attached:")

                        doc_options = [f"Document {i+1}: {doc_links[i][:50]}..." for i in range(len(doc_links))]
                        selected_doc_label = st.radio("Select a document to preview:", doc_options)
                        selected_index = doc_options.index(selected_doc_label)
                        active_url = doc_links[selected_index]

                        col_prev, col_btn = st.columns([3, 1])

                        with col_prev:
                            st.markdown("**📄 On-Screen Preview:**")
                            if "drive.google.com" in active_url and "/view" in active_url:
                                preview_url = active_url.replace("/view", "/preview")
                            else:
                                preview_url = active_url
                            
                            st.components.v1.iframe(preview_url, height=500, scrolling=True)

                        with col_btn:
                            st.markdown("**💾 Save / Hard Copy:**")
                            st.markdown(f'<a href="{active_url}" target="_blank"><button style="background-color:#10B981; color:white; padding:10px 20px; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">⬇️ DOWNLOAD / OPEN</button></a>', unsafe_allow_html=True)
                    else:
                        st.info(f"ℹ️ No documents uploaded for Event ID `{row['Event ID']}` (Count: 0).")
            else:
                st.error(f"No event found matching Event ID '{search_id}'.")
        elif search_id:
            st.info("Database is empty.")

    else:
        st.markdown("### 📁 Direct Google Drive File Browser")
        st.caption("Browse and manage PDF files stored in Google Drive, even if event records were removed from Google Sheets.")

        # Step 1: Select Date Filter
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            selected_drive_date = st.date_input("🗓️ 1. Select Date Filter", datetime.today())
            filter_formatted_date = selected_drive_date.strftime("%d/%m/%Y")
            yy_mm_str = f"{selected_drive_date.strftime('%y')}-{selected_drive_date.strftime('%m')}"

        with st.spinner("Fetching files directly from Google Drive folder..."):
            all_drive_files = list_drive_files_from_folder()

        if all_drive_files:
            # Match files created on that date or matching the CS-YY-MM prefix
            matching_files = [
                f for f in all_drive_files 
                if yy_mm_str in f['name'] or 
                datetime.strptime(f['createdTime'][:10], '%Y-%m-%d').date() == selected_drive_date
            ]

            st.write(f"Found **{len(matching_files)}** file(s) for date **{filter_formatted_date}** (or Event pattern `CS-{yy_mm_str}`):")

            if matching_files:
                with col_d2:
                    # Step 2: Select Event / File
                    file_options = {f"{f['name']} (Uploaded: {f['createdTime'][:10]})": f for f in matching_files}
                    selected_file_label = st.selectbox("📄 2. Select Document to View / Delete", list(file_options.keys()))

                chosen_file = file_options[selected_file_label]
                chosen_file_id = chosen_file['id']
                chosen_file_name = chosen_file['name']
                file_web_link = chosen_file.get('webViewLink', '')

                st.divider()
                st.markdown(f"#### 📄 Document Preview: `{chosen_file_name}`")

                col_preview, col_actions = st.columns([3, 2])

                with col_preview:
                    if "drive.google.com" in file_web_link and "/view" in file_web_link:
                        embed_preview_url = file_web_link.replace("/view", "/preview")
                    elif f"https://drive.google.com/file/d/{chosen_file_id}" not in file_web_link:
                        embed_preview_url = f"https://drive.google.com/file/d/{chosen_file_id}/preview"
                    else:
                        embed_preview_url = file_web_link

                    st.components.v1.iframe(embed_preview_url, height=500, scrolling=True)

                with col_actions:
                    st.markdown("### ⚙️ File Actions")
                    st.markdown(f'<a href="{file_web_link}" target="_blank"><button style="background-color:#10B981; color:white; padding:10px 20px; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">⬇️ OPEN IN DRIVE</button></a>', unsafe_allow_html=True)
                    
                    st.divider()
                    st.markdown("🔒 **Admin File Clean-Up**")
                    pwd_input_file = st.text_input("Enter Admin Password to delete this file:", type="password", key="drive_file_pwd")

                    if pwd_input_file == target_password:
                        if st.button(f"🗑️ Delete `{chosen_file_name}` from Google Drive", type="primary"):
                            with st.spinner("Deleting file permanently from Google Drive..."):
                                success, del_msg = delete_single_drive_file(chosen_file_id)
                            
                            if success:
                                st.session_state.drive_tab_msg = f"🗑️ **SUCCESS!** `{chosen_file_name}` was permanently removed from Google Drive."
                                st.rerun()
                            else:
                                st.error(del_msg)
                    elif pwd_input_file != "":
                        st.error("❌ Incorrect Admin Password.")
            else:
                st.info(f"No PDF files found matching Date/Event pattern for **{filter_formatted_date}**. Try selecting a different date above.")
        else:
            st.info("No files currently found in your Google Drive target folder.")

# ==========================================
# TAB 3: PENDING EVENTS DASHBOARD & ADMIN APPROVAL
# ==========================================
with tab3:
    st.subheader("📤 Pending Events Dashboard & Authorizations")
    st.markdown("This dashboard lists all events requiring attention that are currently in **Pending Approval** status.")

    if not master_data.empty:
        pending_events_df = master_data[master_data['Status'] == "Pending Approval"]
    else:
        pending_events_df = pd.DataFrame()

    if pending_events_df.empty:
        st.success("🎉 No pending events require attention at the moment!")
    else:
        st.info(f"There are currently **{len(pending_events_df)}** event(s) awaiting review.")
        for _, row in pending_events_df.iterrows():
            with st.expander(f"🟡 [{row['Event ID']}] {row['Title']} ({row['Date']} - {row['Time']})", expanded=True):
                st.write(f"**Organization Body:** {row['Organization Body']}")
                st.write(f"**Facilitator:** {row['Facilitator Name']} ({row['Contact Number']})")
                st.write(f"**Requested Venue:** {row['Venue']}")
                st.write(f"**Target Audience:** {row['Target Audience']}")
                
                mat_val = str(row['Materials_Link']) if pd.notnull(row['Materials_Link']) and str(row['Materials_Link']).strip() else "0 File(s)"
                st.write(f"**Materials / Files:** {mat_val}")

    st.divider()

    st.markdown("### 🔐 Admin Authorization Panel")
    st.caption("Enter the admin password below and press Enter to unlock status changing capabilities.")
    
    tab3_password_input = st.text_input("Enter Password for Approval Actions", type="password", key="tab3_pwd")

    is_authorized = (
        (tab3_password_input != "" and tab3_password_input == target_password) or 
        (admin_password != "" and admin_password == target_password)
    )

    if is_authorized:
        st.success("🔓 Admin Authorization Granted!")

        if "approval_success_msg" in st.session_state:
            st.success(st.session_state.approval_success_msg)
            del st.session_state.approval_success_msg

        st.warning("""
        **⚠️ IMPORTANT REMINDER FOR ADMIN:**  
        Before approving any event below, please ensure you **book the venue using the FM portal** (available from the FM Admin) and verify there are **NO CLASHES** of date and time with existing venue usage!
        """)

        if not pending_events_df.empty:
            pending_options = {}
            for idx, row in pending_events_df.iterrows():
                label = f"[{row['Event ID']}] {row['Title']} ({row['Date']} at {row['Venue']})"
                pending_options[label] = idx

            selected_to_approve = st.selectbox("Select Pending Event to Authorize", list(pending_options.keys()))

            if st.button("✅ Approve & Change Status to Officially Confirmed", type="primary"):
                target_idx = pending_options[selected_to_approve]
                
                approved_event_id = master_data.loc[target_idx, 'Event ID']
                approved_event_title = master_data.loc[target_idx, 'Title']

                with st.spinner(f"Updating status for Event ID [{approved_event_id}]... Please wait."):
                    master_data.loc[target_idx, 'Status'] = "Officially Confirmed"
                    
                    clean_df = master_data.reindex(columns=DB_COLUMNS)
                    conn.update(data=clean_df)
                    st.cache_data.clear()

                st.session_state.approval_success_msg = f"👍 **SUCCESS!** Event ID **[{approved_event_id}] - {approved_event_title}** has been officially confirmed and updated in Google Sheets!"
                
                st.balloons()
                st.rerun()
        else:
            st.info("No pending events available to authorize.")
    elif tab3_password_input != "":
        st.error("❌ Incorrect password. Please check your credentials.")
    else:
        st.info("🔒 Enter password above and press Enter to access venue confirmation and status change tools.")

# ==========================================
# TAB 4: EXTERNAL REQUESTS WITH PDF UPLOADS
# ==========================================
with tab4:
    st.subheader("✉️ External Organization Event Request Form")

    col_req1, col_req2 = st.columns(2)
    
    with col_req1:
        title_req = st.text_input("Proposed Event Title")
        org_name = st.text_input("Organization / Company Name")
        facilitator_req = st.text_input("Facilitator Name")
        contact_no_req = st.text_input("Contact Phone Number")
        contact_email = st.text_input("Contact Email")

    with col_req2:
        proposed_date = st.date_input("Proposed Event Date", min_value=datetime.today())
        time_slot_req = st.selectbox("Preferred Time Slot", ["08:00 - 10:00", "10:30 - 12:30", "14:00 - 16:30", "Whole Day"])
        venue_req = st.selectbox("Preferred Venue", [
            "Lecture Theatre 2 [100 - Level 3]",
            "Lecture Theatre 1 [100 pax- Level 2]",
            "Multi-Media Theatre [200 pax - Level 2]",
            "MPH Multi-Purpose Hall [750 pax-A building]"
        ])
        target_aud_req = st.multiselect("Target Audience", [
            "Lower 6th",
            "Upper 6th",
            "PTES Staff",
            "PIBG or Parents",
            "other Association (Public)"
        ])

    uploaded_pdfs = st.file_uploader(
        "Upload Proposal & Supporting Documents (PDF Format Only)",
        type=["pdf"],
        accept_multiple_files=True,
        help="If your document is an image, please convert it to PDF before uploading."
    )

    if uploaded_pdfs:
        st.info(f"📎 {len(uploaded_pdfs)} PDF file(s) attached and ready for upload.")

    event_proposal = st.text_area("Event Purpose & Proposal Details")
    notify_method = st.radio("Send Notification to Admin via:", ["WhatsApp Link", "Automated Email", "Both"], horizontal=True)

    if st.button("Submit Event Request", type="primary"):
        if org_name and contact_email and title_req and facilitator_req and contact_no_req:
            formatted_prop_date = proposed_date.strftime("%d/%m/%Y")
            
            yy = proposed_date.strftime("%y")
            mm = proposed_date.strftime("%m")
            
            total_existing_rows = len(master_data) if not master_data.empty else 0
            seq_num = f"{(total_existing_rows + 1):02d}"
            generated_event_id = f"CS-{yy}-{mm}-{seq_num}"

            if uploaded_pdfs:
                with st.spinner("Uploading PDF documents to Google Drive..."):
                    materials_link_req = upload_multiple_pdfs_to_drive(uploaded_pdfs, generated_event_id)
            else:
                materials_link_req = "0 File(s)"

            audience_str = ", ".join(target_aud_req)

            new_request_row = pd.DataFrame([{
                "Event ID": generated_event_id,
                "Date": formatted_prop_date,
                "Time": time_slot_req,
                "Title": title_req,
                "Venue": venue_req,
                "Target Audience": audience_str,
                "Organization Body": org_name,
                "Facilitator Name": facilitator_req,
                "Contact Number": contact_no_req,
                "Materials_Link": materials_link_req,
                "Status": "Pending Approval"
            }])[DB_COLUMNS]

            updated_master = pd.concat([master_data, new_request_row], ignore_index=True).reindex(columns=DB_COLUMNS)
            
            conn.update(data=updated_master)
            st.cache_data.clear()

            st.success(f"✅ Request submitted successfully! Your unique Event ID is **{generated_event_id}**. Use this ID in Tab 2 to check approval status.")

            payload = {
                "Event_ID": generated_event_id,
                "Org": org_name,
                "Email": contact_email,
                "Facilitator": facilitator_req,
                "Contact": contact_no_req,
                "Date": formatted_prop_date,
                "Venue": venue_req,
                "Audience": audience_str,
                "Details": event_proposal,
                "Materials": materials_link_req
            }

            if notify_method in ["WhatsApp Link", "Both"]:
                wa_message = (
                    f"📌 *NEW CAREER EVENT REQUEST [{generated_event_id}]*\n\n"
                    f"🏢 *Organization:* {org_name}\n"
                    f"👤 *Facilitator:* {facilitator_req} ({contact_no_req})\n"
                    f"📅 *Date:* {formatted_prop_date}\n"
                    f"📍 *Venue:* {venue_req}\n"
                    f"👥 *Target Audience:* {audience_str}\n"
                    f"📄 *Materials / Files:* {materials_link_req}\n"
                    f"📝 *Details:* {event_proposal}"
                )
                encoded_wa = urllib.parse.quote(wa_message)
                wa_url = f"https://wa.me/{ADMIN_WA_NUMBER}?text={encoded_wa}"
                st.link_button("📲 Click here to notify Admin via WhatsApp", wa_url)

            if notify_method in ["Automated Email", "Both"]:
                if send_admin_email(payload):
                    st.info("✉️ Admin notified via automated email alert.")
        else:
            st.error("Please fill in all required request details.")
