import boto3
from botocore.exceptions import ClientError
from src.utils.helper import get_standard_tags

# --- הגדרות קבועות (חלק מהדרישות) ---
INSTANCE_TYPE = 't2.micro'  # סוג השרת (הכי זול)
MAX_INSTANCES = 2  # המגבלה הקשיחה: מקסימום 2 שרתים


def get_latest_ami(ec2_client):
    """
    מוצא את ה-ID של מערכת ההפעלה הכי חדשה (Amazon Linux 2023).
    זה עדיף מלכתוב ID קבוע, כי IDs משתנים בין Regions.
    """
    try:
        response = ec2_client.describe_images(
            Owners=['amazon'],
            Filters=[
                {'Name': 'name', 'Values': ['al2023-ami-2023.*-x86_64']},  # פילטר ללינוקס של אמזון
                {'Name': 'state', 'Values': ['available']}
            ]
        )
        # מיון לפי תאריך יצירה, ולקיחת הראשון (הכי חדש)
        images = sorted(response['Images'], key=lambda x: x['CreationDate'], reverse=True)
        return images[0]['ImageId']
    except IndexError:
        raise Exception("Could not find a valid AMI image.")


def check_limit(ec2_client):
    """
    ה'שוטר': בודק כמה שרתים פעילים כבר יש לפרויקט הזה.
    """
    # אנחנו מחפשים רק שרתים שיש להם את הטאג שלנו
    response = ec2_client.describe_instances(
        Filters=[
            {'Name': 'tag:CreatedBy', 'Values': ['Alin-DevOps-CLI']},
            # סופרים רק שרתים חיים (לא כאלו שנמחקו)
            {'Name': 'instance-state-name', 'Values': ['running', 'pending', 'stopped']}
        ]
    )

    count = 0
    for reservation in response['Reservations']:
        count += len(reservation['Instances'])

    print(f"DEBUG: Found {count} instances created by this CLI.")

    if count >= MAX_INSTANCES:
        return False, f"Limit reached! You already have {count}/{MAX_INSTANCES} instances."

    return True, "Limit check passed."


def create_instance(name):
    """
    הפונקציה הראשית שיוצרת את השרת
    """
    ec2_client = boto3.client('ec2')

    # 1. בדיקת השוטר
    allowed, msg = check_limit(ec2_client)
    if not allowed:
        return False, msg

    try:
        print(f"DEBUG: Finding latest AMI...")
        ami_id = get_latest_ami(ec2_client)

        # 2. הכנת הטאגים
        tags = get_standard_tags()
        tags.append({'Key': 'Name', 'Value': name})  # הוספת השם לטאגים

        print(f"DEBUG: Launching instance {name} ({INSTANCE_TYPE})...")

        # 3. פקודת היצירה (שונה מ-S3, כאן הטאגים נכנסים בתוך המפרט)
        ec2_client.run_instances(
            ImageId=ami_id,
            InstanceType=INSTANCE_TYPE,
            MinCount=1,
            MaxCount=1,
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': tags
                }
            ]
        )

        return True, f"Instance {name} launched successfully!"

    except ClientError as e:
        return False, f"AWS Error: {e}"
    except Exception as e:
        return False, f"Error: {e}"


# --- פונקציה בונוס: רשימת שרתים (כמו ב-S3) ---
def list_created_instances():
    ec2_client = boto3.client('ec2')

    response = ec2_client.describe_instances(
        Filters=[
            {'Name': 'tag:CreatedBy', 'Values': ['Alin-DevOps-CLI']},
            {'Name': 'instance-state-name', 'Values': ['running', 'pending', 'stopped']}
        ]
    )

    instances = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']

            # חיפוש השם מתוך הטאגים
            name = "Unknown"
            for tag in instance.get('Tags', []):
                if tag['Key'] == 'Name':
                    name = tag['Value']

            state = instance['State']['Name']
            instances.append(f"{name} ({instance_id}) - [{state}]")

    return instances