import boto3
import time
from botocore.exceptions import ClientError


def create_hosted_zone(domain_name):
    """
    Creates a new Route 53 Hosted Zone (Domain 'bucket').
    """
    client = boto3.client('route53')

    # AWS דורש "מספר סימוכין" ייחודי לכל בקשה כדי למנוע כפילויות
    # אנחנו נשתמש בשעון (Timestamp) כדי לייצר מספר שלא חוזר על עצמו
    timestamp_ref = str(int(time.time()))
    caller_ref = f"{domain_name}-{timestamp_ref}"

    try:
        print(f"DEBUG: Creating Hosted Zone for {domain_name}...")

        response = client.create_hosted_zone(
            Name=domain_name,
            CallerReference=caller_ref,
            HostedZoneConfig={
                'Comment': 'Created by Alin-DevOps-CLI',
                'PrivateZone': False  # אנחנו יוצרים אזור ציבורי לתרגיל
            }
        )

        # AWS מחזיר מזהה ארוך כמו '/hostedzone/Z042345...'
        zone_id = response['HostedZone']['Id']
        # אנחנו צריכים רק את הסוף (ה-ID נטו)
        clean_zone_id = zone_id.split('/')[-1]

        return True, clean_zone_id

    except ClientError as e:
        return False, f"AWS Error: {e}"


def create_dns_record(zone_id, record_name, target_ip):
    """
    Creates an 'A Record' linking a name (record_name) to an IP (target_ip).
    """
    client = boto3.client('route53')

    try:
        print(f"DEBUG: Pointing {record_name} -> {target_ip}...")

        response = client.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={
                'Comment': 'Created via CLI',
                'Changes': [
                    {
                        'Action': 'UPSERT',  # Create or Update (דרוס אם קיים)
                        'ResourceRecordSet': {
                            'Name': record_name,
                            'Type': 'A',  # סוג הרשומה: A = Address (כתובת)
                            'TTL': 300,  # זמן חיים במטמון (5 דקות)
                            'ResourceRecords': [{'Value': target_ip}]
                        }
                    }
                ]
            }
        )
        return True, f"DNS Record created: http://{record_name}"

    except ClientError as e:
        return False, f"Error creating record: {e}"