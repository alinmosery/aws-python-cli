import boto3
import time
from botocore.exceptions import ClientError
from src.utils.helper import get_standard_tags, PROJECT_TAG


def create_hosted_zone(domain_name):
    
   # Creates a new Route 53 Hosted Zone (Domain 'bucket').
    
    client = boto3.client('route53')

    # AWS דורש "מספר סימוכין" ייחודי לכל בקשה כדי למנוע כפילויות
    # אנחנו משתמשים בשעון (Timestamp) כדי לייצר מספר שלא חוזר על עצמו
    timestamp_ref = str(int(time.time()))
    caller_ref = f"{domain_name}-{timestamp_ref}"

    try:
        print(f"DEBUG: Creating Hosted Zone for {domain_name}...")

        # 1. יצירת האזור
        response = client.create_hosted_zone(
            Name=domain_name,
            CallerReference=caller_ref,
            HostedZoneConfig={
                'Comment': 'Created by Alin-DevOps-CLI',
                'PrivateZone': False  # False = דומיין ציבורי
            }
        )

        # AWS מחזיר מזהה ארוך ומכוער כמו '/hostedzone/Z042345...'
        full_zone_id = response['HostedZone']['Id']

        # נצטרך רק את האיידי כדי לעבוד איתו בהמשך
        clean_zone_id = full_zone_id.split('/')[-1]

        # 2. הוספת טאגים (פעולה נפרדת ב-Route53)
        print(f"DEBUG: Adding tags to zone {clean_zone_id}...")
        
        tags = get_standard_tags() # מביא את הטאג CreatedBy
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
    """
    Creates an 'A Record' linking a name (record_name) to an IP (target_ip).
    """
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
                        'Action': 'UPSERT',  # Create or Update (דרוס אם קיים)
                        'ResourceRecordSet': {
                            'Name': record_name,
                            'Type': 'A',  # סוג הרשומה: A = Address
                            'TTL': 300,   # זמן חיים במטמון (5 דקות)
                            'ResourceRecords': [{'Value': target_ip}]
                        }
                    }
                ]
            }
        )
        return True, f"DNS Record created: http://{record_name}"

    except ClientError as e:
        return False, f"Error creating record: {e}"


def list_hosted_zones():
 
  #  Lists only hosted zones created by this CLI (filtering by tag).
   
    client = boto3.client('route53')
    project_value = PROJECT_TAG['Value']
    
    try:
        # 1. משיכת כל הזונס
        response = client.list_hosted_zones()
        all_zones = response['HostedZones']
        my_zones = []

        print(f"DEBUG: Scanning {len(all_zones)} zones for tags...")

        # 2. סינון לפי תגיות
        for zone in all_zones:
            zone_id = zone['Id'].split('/')[-1] # ניקוי ה-ID
            zone_name = zone['Name']
            
            try:
                tags_response = client.list_tags_for_resource(
                    ResourceType='hostedzone',
                    ResourceId=zone_id
                )
                
                tags = tags_response['ResourceTagSet']['Tags']
                for tag in tags:
                    if tag['Key'] == 'CreatedBy' and tag['Value'] == project_value:
                        my_zones.append(f"{zone_name} (ID: {zone_id})")
                        break
            
            except ClientError:
                continue

        return my_zones

    except ClientError as e:
        print(f"Error listing zones: {e}")
        return []
