import streamlit as st
import boto3
import os
import sys

# 1. הגדרת נתיבים (כדי שפייתון ימצא את הקבצים שלנו)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.resources.ec2_manager import create_instance, list_created_instances, stop_instance, start_instance
from src.resources.s3_manager import create_s3_bucket, list_created_buckets, upload_file_to_bucket
from src.resources.route53_manager import create_hosted_zone, create_dns_record, list_hosted_zones

# 3. כותרת
st.set_page_config(page_title="AWS Manager", layout="wide")
st.title("AWS Resource Management System")
st.markdown("Internal tool for managing EC2, S3, and Route53 resources.")

# 4. תפריט צד
menu_options = ["EC2 Instances", "S3 Storage", "Route53 DNS"]
selected_service = st.sidebar.radio("Select Service", menu_options)

# ==================== EC2 SECTION ====================
if selected_service == "EC2 Instances":
    st.header("EC2 Instance Management")
    
    # שימוש בטאבים לחלוקה לוגית
    tab_create, tab_manage = st.tabs(["Create Instance", "Manage Instances"])
    
    # טאב יצירה
    with tab_create:
        st.subheader("Launch New Server")
        instance_name = st.text_input("Enter Server Name")
        
        # --- תוספת: בחירת סוג שרת ומערכת הפעלה (לפי דרישות המרצה) ---
        col_type, col_os = st.columns(2)
        
        with col_type:
            # המשתמש יכול לבחור רק מה שמותר בתמונה ששלחת
            inst_type = st.selectbox("Instance Type", ["t3.micro", "t2.small"])
            
        with col_os:
            # המשתמש בוחר שם ידידותי, אנחנו נמיר אותו לקוד עבור ה-Manager
            os_display = st.selectbox("Operating System", ["Amazon Linux 2023", "Ubuntu 24.04"])
            os_map = {"Amazon Linux 2023": "amazon_linux", "Ubuntu 24.04": "ubuntu"}
            selected_os = os_map[os_display]
        
        if st.button("Create Instance"):
            if instance_name:
                with st.spinner(f"Provisioning {os_display} instance..."):
                    # שליחת השם, הסוג ומערכת ההפעלה לפונקציה המעודכנת
                    success, message = create_instance(instance_name, inst_type, selected_os)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
            else:
                st.warning("Server name is required.")

    # טאב ניהול (רשימה, כיבוי, הדלקה)
    with tab_manage:
        st.subheader("Current Inventory")
        if st.button("Refresh List"):
            instances = list_created_instances()
            if instances:
                st.write(instances)
            else:
                st.info("No instances found.")
        
        st.markdown("---")
        
        col_stop, col_start = st.columns(2)
        
        with col_stop:
            stop_id = st.text_input("Instance ID to Stop")
            if st.button("Stop Instance"):
                success, msg = stop_instance(stop_id)
                if success: st.success(msg)
                else: st.error(msg)
        
        with col_start:
            start_id = st.text_input("Instance ID to Start")
            if st.button("Start Instance"):
                success, msg = start_instance(start_id)
                if success: st.success(msg)
                else: st.error(msg)

# ==================== S3 SECTION ====================
elif selected_service == "S3 Storage":
    st.header("S3 Bucket Management")
    
    tab_create, tab_upload, tab_list = st.tabs(["Create Bucket", "Upload File", "List Buckets"])
    
    with tab_create:
        bucket_name = st.text_input("Bucket Name (Unique)")
        is_public = st.checkbox("Enable Public Access")
        
        if is_public:
            st.warning("Security Warning: This bucket will be public.")
            confirm_public = st.checkbox("I acknowledge the risk")
        else:
            confirm_public = True
            
        if st.button("Create Bucket"):
            if bucket_name:
                clean_name = bucket_name.strip()
                if is_public and not confirm_public:
                    st.error("Please confirm public access.")
                else:
                    success, msg = create_s3_bucket(clean_name, is_public)
                    if success: st.success(msg)
                    else: st.error(msg)
            else:
                st.warning("Bucket name is required.")

    with tab_upload:
        target_bucket = st.text_input("Target Bucket Name")
        file_obj = st.file_uploader("Select File")
        
        if st.button("Upload File"):
            if target_bucket and file_obj:
                with open(file_obj.name, "wb") as f:
                    f.write(file_obj.getbuffer())
                
                clean_bucket = target_bucket.strip()
                success, msg = upload_file_to_bucket(clean_bucket, file_obj.name)
                
                if success: st.success(msg)
                else: st.error(msg)
                
                os.remove(file_obj.name)
            else:
                st.error("Bucket name and file are required.")

    with tab_list:
        if st.button("List My Buckets"):
            buckets = list_created_buckets()
            if buckets:
                st.write(buckets)
            else:
                st.info("No buckets found.")

# ==================== ROUTE53 SECTION ====================
elif selected_service == "Route53 DNS":
    st.header("DNS Management")
    
    tab_setup, tab_list = st.tabs(["Configure DNS", "List Zones"])
    
    with tab_setup:
        st.subheader("Map Domain to Server")
        domain_name = st.text_input("Domain Name (e.g., example.com)")
        server_tag_name = st.text_input("Server Name (Tag)")
