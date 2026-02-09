import boto3
import time
from botocore.exceptions import ClientError
from src.utils.helper import get_standard_tags


def create_hosted_zone(domain_name):
    # יוצר 'אזור ניהול' (Hosted Zone) לדומיין ב-Route53.
    client = boto3.client('route53')
    #AWS דורש איידי לכל בקשה ליצירת זון
    # כדי שלא ייצא מצב שנריץ את אותו הסקריפט פעמיים ויווצרו שניים שונים (ונאלץ לשלם כפול)
    # אז אם נשלח בקשה עם אותו מספר סידורי, נבין שזו אותה בקשה ולא יהיו כפילויות
    # אנחנו משתמשים בשעון (Timestamp) כדי לייצר מספר שתמיד משתנה.
    timestamp_ref = str(int(time.time()))
    caller_ref = f"{domain_name}-{timestamp_ref}"

    try:
        print(f"DEBUG: Creating Hosted Zone for {domain_name}...")

        # 1. יצירת האזור
        response = client.create_hosted_zone(
            Name=domain_name,
            CallerReference=caller_ref,
            HostedZoneConfig={
                'Comment': 'Created by Alin-DevOps-CLI', # הערה שתופיע בקונסול
                'PrivateZone': False  # False = דומיין ציבורי שחשוף לאינטרנט (כמו google.com)
            }
        )

        # AWS מחזיר מזהה ארוך ומכוער כמו '/hostedzone/Z042345...'
        full_zone_id = response['HostedZone']['Id']

        # נצטרך רק את האיידי כדי לעבוד איתתו בהמשך
        clean_zone_id = full_zone_id.split('/')[-1]

        #ניצור פקודה חדשה להוספת טאגים
        # לא קיימת אפשרות להוספת טאגים create_hosted_zone.
        # לכן, חייבים לקרוא לפקודה נפרדת: change_tags_for_resource.
        print(f"DEBUG: Adding tags to zone {clean_zone_id}...")
        
        tags = get_standard_tags() # מביא את הטאג CreatedBy: 
        client.change_tags_for_resource(
            ResourceType='hostedzone',
            ResourceId=clean_zone_id,
            AddTags=tags
        )

        return True, clean_zone_id

    except ClientError as e:
        # טיפול במקרה שהדומיין כבר קיים
        if e.response['Error']['Code'] == 'HostedZoneAlreadyExists':
            return False, f"Error: The hosted zone '{domain_name}' already exists."
        return False, f"AWS Error: {e}"


def create_dns_record(zone_id, record_name, target_ip):
    
   # יוצר רשומת A (חיבור בין שם ל-IP).
   # הפונקציה מקבלת:
   # 1. zone_id המזהה של הדומיין 
   # 2. record_name - השם המלא (למשל www.mysite.com)
   # 3. target_ip - הכתובת של השרת שיצרנו (למשל 54.21.10.1)
    
    client = boto3.client('route53')

    try:
        print(f"DEBUG: Pointing {record_name} -> {target_ip}...")

        # הפקודה הזו היא אחת המורכבות ב-Boto3 כי המבנה שלה (JSON) מאוד עמוק.
        response = client.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={
                'Comment': 'Created via CLI',
                'Changes': [
                    {
                        # --- הסבר על UPSERT ---
                        # Action יכול להיות: CREATE, DELETE, UPSERT.
                        # אנחנו בוחרים UPSERT (שילוב של Update + Insert).
                        # אם הרשומה לא קיימת -> הוא יוצר אותה.
                        # אם הרשומה כבר קיימת -> הוא מעדכן אותה ל-IP החדש.
                        # זה מונע שגיאות של "Record already exists".
                        'Action': 'UPSERT', 
                        'ResourceRecordSet': {
                            'Name': record_name,
                            'Type': 'A',  # סוג הרשומה: A = Address (כתובת IP)
                            
                            # TTL (Time To Live):
                            # כמה זמן (בשניות) ה-DNS בעולם יזכור את הכתובת הזו לפני שיבדוק שוב.
                            # שמנו 300 שניות (5 דקות) - זה זמן טוב לפיתוח.
                            'TTL': 300,
                            'ResourceRecords': [{'Value': target_ip}]
                        }
                    }
                ]
            }
        )
        return True, f"DNS Record created: http://{record_name}"

    except ClientError as e:
        return False, f"Error creating record: {e}"
