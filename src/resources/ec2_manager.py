import boto3
from botocore.exceptions import ClientError
# אנחנו מייבאים גם את הפונקציה וגם את המשתנה הקבוע
from src.utils.helper import get_standard_tags, PROJECT_TAG

# הגדרות קבועות
INSTANCE_TYPE = 't2.micro'
MAX_INSTANCES = 2

def get_latest_ami(ec2_client):
   
    # מוצא את האיידי של מערכת ההפעלה הכי חדשה (Amazon Linux 2023).
    try:
        response = ec2_client.describe_images(
            Owners=['amazon'],
            Filters=[
                {'Name': 'name', 'Values': ['al2023-ami-2023.*-x86_64']},
                {'Name': 'state', 'Values': ['available']},
                {'Name': 'architecture', 'Values': ['x86_64']}
            ]
        )
        images = sorted(response['Images'], key=lambda x: x['CreationDate'], reverse=True)
        if not images:
            raise Exception("No AMIs found.")
        return images[0]['ImageId']
    except Exception as e:
        raise Exception(f"Error finding AMI: {str(e)}")


def check_limit(ec2_client):
   
   # ה'שוטר': בודק כמה שרתים פעילים יש תחת התגית שלנו.

    #שליפת הערך מתוך ההלפר
    project_value = PROJECT_TAG['Value']

    response = ec2_client.describe_instances(
        Filters=[
            # שימוש במשתנה המיובא
            #כך שאם נרצה לשנות שם פרויקט לא תהיה בעיה וזה יסתנכרן לבד
            {'Name': 'tag:CreatedBy', 'Values': [project_value]},
            {'Name': 'instance-state-name', 'Values': ['running', 'pending', 'stopped']}
        ]
    )

    count = 0
    for reservation in response['Reservations']:
        count += len(reservation['Instances'])

    print(f"DEBUG: Found {count} instances with tag {project_value}.")

    if count >= MAX_INSTANCES:
        return False, f" Limit reached! You have {count}/{MAX_INSTANCES} instances."

    return True, "Limit check passed."


def create_instance(name):
     # הפונקציה הראשית שיוצרת את השרת
 
    ec2_client = boto3.client('ec2')

    # 1. בדיקה
    allowed, msg = check_limit(ec2_client)
    if not allowed:
        return False, msg

    try:
        print(f"DEBUG: Finding latest AMI...")
        ami_id = get_latest_ami(ec2_client)

        # 2. הכנת הטאגים
        tags = get_standard_tags()
        tags.append({'Key': 'Name', 'Value': name})

        print(f"DEBUG: Launching instance {name}...")

        # 3. יצירת השרת
        ec2_client.run_instances(
            ImageId=ami_id,
            InstanceType=INSTANCE_TYPE,
            MinCount=1,
            MaxCount=1,
            TagSpecifications=[
                {'ResourceType': 'instance', 'Tags': tags},
                {'ResourceType': 'volume', 'Tags': tags}
            ]
        )

        return True, f"Instance '{name}' launched successfully!"

    except ClientError as e:
        return False, f"AWS Error: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def stop_instance(instance_id):
    
    # Stops an EC2 instance only if it has our project tag.
  
    ec2_client = boto3.client('ec2')
    project_value = PROJECT_TAG['Value']

    try:
        # 1. בדיקת בעלות
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        tags = response['Reservations'][0]['Instances'][0].get('Tags', [])
        
        is_ours = False
        for tag in tags:
            if tag['Key'] == 'CreatedBy' and tag['Value'] == project_value:
                is_ours = True
                break
        
        if not is_ours:
            return False, f" Security Alert: You cannot stop instance {instance_id} because it was not created by this CLI."

        # 2. ביצוע העצירה
        ec2_client.stop_instances(InstanceIds=[instance_id])
        return True, f"Stopping instance {instance_id}..."

    except ClientError as e:
        return False, f"AWS Error: {e}"


def start_instance(instance_id):
   
   #  Starts an EC2 instance only if it has our tag
  
    ec2_client = boto3.client('ec2')
    project_value = PROJECT_TAG['Value']

    try:
        # 1. בדיקת בעלות
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        tags = response['Reservations'][0]['Instances'][0].get('Tags', [])
        
        is_ours = False
        for tag in tags:
            if tag['Key'] == 'CreatedBy' and tag['Value'] == project_value:
                is_ours = True
                break
        
        if not is_ours:
            return False, f" Security Alert: You cannot start instance {instance_id} because it was not created by this CLI."

        # 2. ביצוע ההפעלה
        ec2_client.start_instances(InstanceIds=[instance_id])
        return True, f"Starting instance {instance_id}..."

    except ClientError as e:
        return False, f"AWS Error: {e}"
def list_created_instances():
   
   # רשימת השרתים
   
    ec2_client = boto3.client('ec2')
    project_value = PROJECT_TAG['Value'] # שימוש באותו משתנה מההלפר

    try:
        response = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:CreatedBy', 'Values': [project_value]},
                {'Name': 'instance-state-name', 'Values': ['running', 'pending', 'stopped']}
            ]
        )

        instances = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                state = instance['State']['Name']
                public_ip = instance.get('PublicIpAddress', 'No IP')
                
                name = "Unknown"
                if 'Tags' in instance:
                    for tag in instance['Tags']:
                        if tag['Key'] == 'Name':
                            name = tag['Value']
                            break

                instances.append(f"{name} ({instance_id}) - [{state}] - IP: {public_ip}")

        return instances

    except Exception as e:
        print(f"Error listing instances: {e}")
        return []
