import streamlit as st
import boto3
import time
import os
import sys

# הוספת התיקייה הראשית לנתיב כדי שהאימפורטים יעבדו
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ייבוא הפונקציות שבנינו
from src.resources.ec2_manager import create_instance, list_created_instances, stop_instance, start_instance
from src.resources.s3_manager import create_s3_bucket, list_created_buckets, upload_file_to_bucket
from src.resources.route53_manager import create_hosted_zone, create_dns_record, list_hosted_zones

# --- הגדרות דף ---
st.set_page_config(page_title="AWS Automation Tool", page_icon="☁️", layout="wide")

st.title("☁️ AWS Platform Engineering Console")
st.markdown("### Self-Service Infrastructure for Developers")

# --- תפריט צד ---
menu = ["EC2 (Servers)", "S3 (Storage)", "Route53 (Domains)"]
choice = st.sidebar.selectbox("Select Service", menu)

# ==================== EC2 SCREEN ====================
if choice == "EC2 (Servers)":
    st.header("🖥️ EC2 Server Management")
    
    # טאבים לנוחות
    tab1, tab2 = st.tabs(["Create Server", "Manage Servers"])
    
    with tab1:
        st.subheader("Launch New Instance")
        name = st.text_input("Server Name (e.g., web-server-1)")
        
        if st.button("🚀 Launch Instance"):
            if name:
                with st.spinner("Launching server... please wait"):
                    success, msg = create_instance(name)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
            else:
                st.warning("Please enter a server name.")

    with tab2:
        st.subheader("Existing Servers")
        if st.button("🔄 Refresh List"):
            instances = list_created_instances()
            if instances:
                st.success(f"Found {len(instances)} instances")
                for i in instances:
                    st.code(i)
            else:
                st.info("No instances found created by this tool.")
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            stop_id = st.text_input("Instance ID to STOP")
            if st.button("🛑 Stop Server"):
                success, msg = stop_instance(stop_id)
                if success: st.success(msg)
                else: st.error(msg)
        
        with col2:
            start_id = st.text_input("Instance ID to START")
            if st.button("🟢 Start Server"):
                success, msg = start_instance(start_id)
                if success: st.success(msg)
                else: st.error(msg)

# ==================== S3 SCREEN ====================
elif choice == "S3 (Storage)":
    st.header("🪣 S3 Bucket Management")
    
    tab1, tab2, tab3 = st.tabs(["Create Bucket", "Upload File", "List Buckets"])
    
    with tab1:
        st.subheader("Create New Bucket")
        bucket_name = st.text_input("Bucket Name (Must be globally unique!)")
        is_public = st.checkbox("Make Public? (⚠️ Dangerous)")
        
        # מנגנון הגנה ויזואלי
        if is_public:
            st.warning("⚠️ Warning: You are about to create a PUBLIC bucket.")
            confirm = st.checkbox("I confirm that I want this bucket to be public")
        else:
            confirm = True
            
        if st.button("🛠️ Create Bucket"):
            if bucket_name:
                if is_public and not confirm:
                    st.error("Please confirm public access.")
                else:
                    with st.spinner("Creating bucket..."):
                        success, msg = create_s3_bucket(bucket_name, is_public)
                        if success: st.success(msg)
                        else: st.error(msg)
            else:
                st.warning("Please enter a bucket name.")

    with tab2:
        st.subheader("Upload File")
        target_bucket = st.text_input("Target Bucket Name")
        uploaded_file = st.file_uploader("Choose a file")
        
        if st.button("📤 Upload"):
            if target_bucket and uploaded_file:
                # שמירת הקובץ זמנית כדי להעלות אותו
                with open(uploaded_file.name, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                with st.spinner("Uploading..."):
                    success, msg = upload_file_to_bucket(target_bucket, uploaded_file.name)
                    if success: st.success(msg)
                    else: st.error(msg)
                
                # ניקוי הקובץ הזמני
                os.remove(uploaded_file.name)
            else:
                st.error("Please provide both bucket name and a file.")

    with tab3:
        if st.button("🔄 Refresh Buckets"):
            buckets = list_created_buckets()
            if buckets:
                for b in buckets:
                    st.text(f"📦 {b}")
            else:
                st.info("No buckets found.")

# ==================== ROUTE53 SCREEN ====================
elif choice == "Route53 (Domains)":
    st.header("🌐 Route53 DNS Manager")
    
    tab1, tab2 = st.tabs(["Setup DNS", "List Zones"])
    
    with tab1:
        st.subheader("Connect Domain to EC2")
        st.info("This wizard will find your server IP and create a DNS record automatically.")
        
        domain = st.text_input("Domain Name (e.g., myapp.com)")
        server_name = st.text_input("Target Server Name (Tag: Name)")
        
        if st.button("🔗 Connect Domain"):
            if domain and server_name:
                with st.spinner("Finding server IP and creating records..."):
                    # 1. לוגיקה למציאת IP (כמו שעשינו ב-main.py)
                    ec2 = boto3.client('ec2')
                    try:
                        response = ec2.describe_instances(
                            Filters=[
                                {'Name': 'tag:Name', 'Values': [server_name]},
                                {'Name': 'instance-state-name', 'Values': ['running']}
                            ]
                        )
                        public_ip = None
                        for r in response['Reservations']:
                            for i in r['Instances']:
                                public_ip = i.get('PublicIpAddress')
                        
                        if public_ip:
                            st.success(f"✅ Found Server IP: {public_ip}")
                            
                            # 2. יצירת Zone
                            s1, r1 = create_hosted_zone(domain)
                            if s1:
                                st.info(f"Zone Created/Found ID: {r1}")
                                # 3. יצירת רשומה
                                s2, r2 = create_dns_record(r1, f"www.{domain}", public_ip)
                                if s2:
                                    st.success(f"🎉 SUCCESS! {r2}")
                                else:
                                    st.error(f"Failed to create record: {r2}")
                            else:
                                st.error(f"Failed to create zone: {r1}")
                        else:
                            st.error(f"Could not find running server named '{server_name}' with public IP.")
                            
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.warning("Please fill all fields.")

    with tab2:
        if st.button("🔄 Refresh Zones"):
            zones = list_hosted_zones()
            if zones:
                for z in zones:
                    st.code(z)
            else:
                st.info("No hosted zones found.")

# --- Footer ---
st.markdown("---")
st.caption("🔒 Secured by AWS IAM | Created with Python & Streamlit")
