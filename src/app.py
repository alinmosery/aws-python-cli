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

# 3.  כותרת
st.set_page_config(page_title="AWS Manager", layout="wide")
st.title("AWS Resource Management System")
st.markdown("Internal tool for managing EC2, S3, and Route53 resources.")

# 4. תפריט צד 
menu_options = ["EC2 Instances", "S3 Storage", "Route53 DNS"]
selected_service = st.sidebar.radio("Select Service", menu_options)

# ec2
if selected_service == "EC2 Instances":
    st.header("EC2 Instance Management")
    
    # שימוש בטאבים לחלוקה לוגית
    tab_create, tab_manage = st.tabs(["Create Instance", "Manage Instances"])
    
    # טאב יצירה
    with tab_create:
        st.subheader("Launch New Server")
        instance_name = st.text_input("Enter Server Name")
        
        if st.button("Create Instance"):
            if instance_name:
                with st.spinner("Provisioning instance..."):
                    # קריאה לפונקציה מה-Manager
                    success, message = create_instance(instance_name)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
            else:
                st.warning("Server name is required.")

    # טאב רשימה, כיבוי, הדלקה
    with tab_manage:
        st.subheader("Current Inventory")
        if st.button("Refresh List"):
            instances = list_created_instances()
            if instances:
                st.write(instances)
            else:
                st.info("No instances found.")
        
        st.markdown("---")
        
        # חלוקה לשתי עמודות לכיבוי והדלקה
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

# S3 
elif selected_service == "S3 Storage":
    st.header("S3 Bucket Management")
    
    tab_create, tab_upload, tab_list = st.tabs(["Create Bucket", "Upload File", "List Buckets"])
    
    # טאב יצירת באקט
    with tab_create:
        bucket_name = st.text_input("Bucket Name (Unique)")
        is_public = st.checkbox("Enable Public Access")
        
        # אזהרת אבטחה אם נבחר ציבורי
        if is_public:
            st.warning("Security Warning: This bucket will be public.")
            confirm_public = st.checkbox("I acknowledge the risk")
        else:
            confirm_public = True
            
        if st.button("Create Bucket"):
            if bucket_name:
                #  ניקוי רווחים מיותרים מהשם כדי לא לקבל שגיאה 
                clean_name = bucket_name.strip()
                
                if is_public and not confirm_public:
                    st.error("Please confirm public access.")
                else:
                    success, msg = create_s3_bucket(clean_name, is_public)
                    if success: st.success(msg)
                    else: st.error(msg)
            else:
                st.warning("Bucket name is required.")

    # טאב העלאת קבצים
    with tab_upload:
        target_bucket = st.text_input("Target Bucket Name")
        file_obj = st.file_uploader("Select File")
        
        if st.button("Upload File"):
            if target_bucket and file_obj:
                # שמירה זמנית של הקובץ
                with open(file_obj.name, "wb") as f:
                    f.write(file_obj.getbuffer())
                
                # קריאה לפונקציה
                clean_bucket = target_bucket.strip()
                success, msg = upload_file_to_bucket(clean_bucket, file_obj.name)
                
                if success: st.success(msg)
                else: st.error(msg)
                
                # מחיקת הקובץ הזמני
                os.remove(file_obj.name)
            else:
                st.error("Bucket name and file are required.")

    # טאב רשימה
    with tab_list:
        if st.button("List My Buckets"):
            buckets = list_created_buckets()
            if buckets:
                st.write(buckets)
            else:
                st.info("No buckets found.")

# ROUTE53
elif selected_service == "Route53 DNS":
    st.header("DNS Management")
    
    tab_setup, tab_list = st.tabs(["Configure DNS", "List Zones"])
    
    with tab_setup:
        st.subheader("Map Domain to Server")
        domain_name = st.text_input("Domain Name (e.g., example.com)")
        server_tag_name = st.text_input("Server Name (Tag)")
        
        if st.button("Create DNS Record"):
            if domain_name and server_tag_name:
                with st.spinner("Processing..."):
                    # 1. חיפוש ה-IP של השרת
                    ec2 = boto3.client('ec2')
                    try:
                        response = ec2.describe_instances(
                            Filters=[
                                {'Name': 'tag:Name', 'Values': [server_tag_name]},
                                {'Name': 'instance-state-name', 'Values': ['running']}
                            ]
                        )
                        
                        public_ip = None
                        if response['Reservations']:
                            for r in response['Reservations']:
                                for i in r['Instances']:
                                    public_ip = i.get('PublicIpAddress')
                        
                        if public_ip:
                            st.info(f"Server IP found: {public_ip}")
                            
                            # 2. יצירת Zone
                            zone_success, zone_id = create_hosted_zone(domain_name)
                            
                            if zone_success:
                                # 3. יצירת רשומה
                                rec_success, rec_msg = create_dns_record(zone_id, f"www.{domain_name}", public_ip)
                                if rec_success:
                                    st.success(f"DNS Configured: {rec_msg}")
                                else:
                                    st.error(rec_msg)
                            else:
                                st.error(f"Zone Error: {zone_id}")
                        else:
                            st.error("Server not found or has no Public IP.")
                            
                    except Exception as e:
                        st.error(f"System Error: {e}")
            else:
                st.warning("All fields are required.")

    with tab_list:
        if st.button("List Hosted Zones"):
            zones = list_hosted_zones()
            if zones:
                st.write(zones)
            else:
                st.info("No hosted zones found.")
