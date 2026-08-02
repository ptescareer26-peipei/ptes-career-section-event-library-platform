import streamlit as st
import pandas as pd
from PIL import Image
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import calendar
import urllib.parse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# PAGE CONFIGURATION & STYLING
# ==========================================
st.set_page_config(page_title="PTES Career Section Portal", layout="wide")

custom_css = """
<style>
    /* Main Background & Sidebar Styling */
    .stApp, .stAppViewContainer, [data-testid="stHeader"] {
        background-color: #E5C2F5 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #FAE48F !important;
    }

    /* Header Container Styling */
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

    /* Form Container & Block Styling */
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

    /* -------------------------------------------------- */
    /* TAB TITLE STYLING: BOLD FONT                       */
    /* -------------------------------------------------- */
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
# DATABASE SCHEMA & CONNECTION
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

ADMIN_WA_NUMBER = "6737318186"
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

def send_admin_email(details):
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
                    <li><b>Materials Link:</b> {details['Materials']}</li>
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

# Read Data safely
try:
    master_data = conn.read(ttl=10)
    if master_data.empty:
        master_data = pd.DataFrame(columns=DB_COLUMNS)
    else:
        master_data = master_data.reindex(columns=DB_COLUMNS)
except Exception:
    master_data = pd.DataFrame(columns=DB_COLUMNS)

# ==========================================
# HEADER SECTION
# ==========================================
st.markdown("""
    <div class="header-container">
        <h1>PUSAT TINGKATAN ENAM SENGKURONG</h1>
        <p style="font-size: 18px; font-weight: bold; color: #111;">🎓 PTES Career Section Portal 🎓</p>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# SIDEBAR: ADMIN MANAGEMENT
# ==========================================
with st.sidebar:
    try:
        logo = Image.open('ptes_logo.PNG')
        st.image(logo, use_container_width=True)
    except Exception:
        st.info("Logo image 'ptes_logo.PNG' optional.")

    st.header("⚙️ Admin Management")
    admin_password = st.text_input("Enter Admin Password", type="password")

    try:
        target_password = st.secrets["admin_password"]
    except KeyError:
        target_password = None

    if target_password and admin_password == target_password:
        st.subheader("✅ Approve Pending Requests")
        if not master_data.empty:
            pending_events = master_data[master_data['Status'] == "Pending Approval"]
            
            if not pending_events.empty:
                pending_options = [
                    f"[{row['Event ID']}] {row['Title']} ({row['Date']})" 
                    for _, row in pending_events.iterrows()
                ]
                selected_pending = st.selectbox("Select Pending Request", pending_options)
                
                if st.button("Approve Request", type="primary"):
                    selected_id = selected_pending.split("]")[0].replace("[", "")
                    master_data.loc[master_data['Event ID'] == selected_id, 'Status'] = "Officially Confirmed"
                    conn.update(data=master_data)
                    st.cache_data.clear()
                    st.success(f"Event `{selected_id}` has been Officially Confirmed!")
                    st.rerun()
            else:
                st.info("No pending requests to approve.")

        st.divider()
        st.subheader("🗑️ Delete / Cancel Event")
        if not master_data.empty:
            event_options = [
                f"[{row['Event ID']}] {row['Title']} ({row['Date']})" 
                for _, row in master_data.iterrows()
            ]
            selected_event_label = st.selectbox("Select Event to Cancel", event_options)
            cancel_reason = st.text_area("Reason for Cancellation")

            if st.button("Delete Event"):
                selected_id = selected_event_label.split("]")[0].replace("[", "")
                updated_df = master_data[master_data['Event ID'] != selected_id].reindex(columns=DB_COLUMNS)
                conn.update(data=updated_df)
                st.cache_data.clear()
                st.success(f"Event `{selected_id}` cancelled successfully. Reason: {cancel_reason}")
                st.rerun()
    else:
        st.caption("🔒 Enter valid admin credentials to unlock management tools.")

# ==========================================
# TAB NAVIGATION
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📅 Event Calendar", 
    "🔍 Information Preview", 
    "📤 Information Upload", 
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
            master_data['datetime_obj'] = pd.to_datetime(master_data['Date'], format='%d/%m/%Y', errors='coerce')
            month_events = master_data[
                (master_data['datetime_obj'].dt.month == selected_month) &
                (master_data['datetime_obj'].dt.year == selected_year)
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
                        
                        if st.button(btn_label, key=f"cal_btn_{day}_{selected_month}_{selected_year}", use_container_width=True):
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
                    if pd.notnull(row['Materials_Link']) and str(row['Materials_Link']).strip():
                        st.write(f"**Materials Link:** {row['Materials_Link']}")
        else:
            st.info("No events scheduled or requested for this date.")
    else:
        st.info("No events scheduled for this month.")

# ==========================================
# TAB 2: EXTRACT MATERIALS & CHECK STATUS BY EVENT ID
# ==========================================
with tab2:
    st.subheader("🔍 Extract Documents & Check Confirmation Status")

    search_id = st.text_input("Enter Event ID (e.g., CS-26-08-01):", placeholder="CS-26-08-01").strip()

    if search_id and not master_data.empty:
        matched_event = master_data[master_data['Event ID'].astype(str).str.contains(search_id, case=False, na=False)]

        if not matched_event.empty:
            for _, row in matched_event.iterrows():
                st.markdown(f"### 📌 Event: **{row['Title']}** (`{row['Event ID']}`)")
                
                if row['Status'] == "Officially Confirmed":
                    st.success(f"✅ Status: **{row['Status']}**")
                else:
                    st.warning(f"⏳ Status: **{row['Status']}** (Awaiting PTES Admin Confirmation)")

                links_str = str(row['Materials_Link']) if pd.notnull(row['Materials_Link']) else ""
                doc_links = [link.strip() for link in links_str.split(",") if link.strip()]

                if doc_links:
                    st.write(f"Found **{len(doc_links)}** document(s) for this event:")

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
                        st.markdown("**💾 Save To Hard Drive**")
                        st.markdown(f'<a href="{active_url}" target="_blank"><button style="background-color:#10B981; color:white; padding:10px 20px; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">⬇️ DOWNLOAD / OPEN</button></a>', unsafe_allow_html=True)
                else:
                    st.info(f"No document links attached to Event ID `{row['Event ID']}` yet.")
        else:
            st.error(f"No event found matching Event ID '{search_id}'.")
    elif search_id:
        st.info("Database is empty.")

# ==========================================
# TAB 3: ADMIN DIRECT BOOKING & PUBLISH
# ==========================================
with tab3:
    st.subheader("📤 Book Venue & Publish Career Event (Direct Confirmation)")

    with st.form("upload_event_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            title = st.text_input("Event Title (e.g., UBD Admissions Talk)")
            org_body = st.text_input("Organization Body (e.g., PTES Career Section)")
            facilitator = st.text_input("Facilitator Name")
            contact_no = st.text_input("Contact Number (e.g., +673 8123456)")
            event_date = st.date_input("Event Date", min_value=datetime.today())
            time_slot = st.selectbox("Time Slot", ["08:00 - 10:00", "10:30 - 12:30", "14:00 - 16:30", "Whole Day"])

        with col2:
            venue = st.selectbox("Book Venue (Resource Room)", [
                "Lecture Theatre 2 [100 - Level 3]",
                "Lecture Theatre 1 [100 pax- Level 2]",
                "Multi-Media Theatre [200 pax - Level 2]",
                "MPH Multi-Purpose Hall [750 pax-A building]"
            ])
            
            target_audience = st.multiselect("Target Audience", [
                "Lower 6th",
                "Upper 6th",
                "PTES Staff",
                "PIBG or Parents",
                "other Association (Public)"
            ])
            
            materials_link = st.text_input("Google Drive / PDF Links (Separate multiple links with commas)")

        submit_upload = st.form_submit_button("Confirm Booking & Publish Event")

    if submit_upload:
        if title and org_body and facilitator and contact_no and venue and target_audience:
            formatted_date = event_date.strftime("%d/%m/%Y")
            
            # Check venue clash
            clash = master_data[
                (master_data['Date'] == formatted_date) & 
                (master_data['Venue'] == venue) &
                (master_data['Time'] == time_slot)
            ]
            
            if not clash.empty:
                st.error(f"❌ Venue Clash: {venue} is already booked on {formatted_date} at {time_slot}!")
            else:
                yy = event_date.strftime("%y")
                mm = event_date.strftime("%m")

                events_same_day = master_data[master_data['Date'] == formatted_date]
                count_same_day = len(events_same_day) + 1
                seq_num = f"{count_same_day:02d}"

                generated_event_id = f"CS-{yy}-{mm}-{seq_num}"
                audience_str = ", ".join(target_audience)

                new_row = pd.DataFrame([{
                    "Event ID": generated_event_id,
                    "Date": formatted_date,
                    "Time": time_slot,
                    "Title": title,
                    "Venue": venue,
                    "Target Audience": audience_str,
                    "Organization Body": org_body,
                    "Facilitator Name": facilitator,
                    "Contact Number": contact_no,
                    "Materials_Link": materials_link,
                    "Status": "Officially Confirmed"
                }])[DB_COLUMNS]

                updated_master = pd.concat([master_data, new_row], ignore_index=True)
                conn.update(data=updated_master)
                st.cache_data.clear()
                st.balloons()
                st.success(f"✅ Event Published! Assigned Event ID: **{generated_event_id}**")
        else:
            st.error("Please fill in all required form fields.")

# ==========================================
# TAB 4: EXTERNAL REQUESTS WITH DOCUMENTS & NOTIFICATION OPTIONS
# ==========================================
with tab4:
    st.subheader("✉️ External Organization Event Request Form")

    with st.form("external_request_form"):
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
            materials_link_req = st.text_input("Upload Materials Link (Google Drive / Document Link)")

        event_proposal = st.text_area("Event Purpose & Proposal Details")
        notify_method = st.radio("Send Notification to Admin via:", ["WhatsApp Link", "Automated Email", "Both"], horizontal=True)

        submit_req = st.form_submit_button("Submit Event Request")

    if submit_req:
        if org_name and contact_email and title_req and facilitator_req and contact_no_req:
            formatted_prop_date = proposed_date.strftime("%d/%m/%Y")
            
            yy = proposed_date.strftime("%y")
            mm = proposed_date.strftime("%m")
            events_same_day = master_data[master_data['Date'] == formatted_prop_date]
            seq_num = f"{(len(events_same_day) + 1):02d}"
            generated_event_id = f"CS-{yy}-{mm}-{seq_num}"

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

            updated_master = pd.concat([master_data, new_request_row], ignore_index=True)
            conn.update(data=updated_master)
            st.cache_data.clear()

            st.success(f"✅ Request submitted successfully! Your Event ID is **{generated_event_id}**. Use this ID in Tab 2 to check approval status.")

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
                    f"📄 *Materials:* {materials_link_req}\n"
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
