import boto3
from botocore.exceptions import ClientError
from src.utils.helper import get_standard_tags, PROJECT_TAG

# --- קבועים למגבלות (לפי דרישות המרצה) ---
ALLOWED_TYPES = ['t3.micro', 't2.small']
ALLOWED_OS = ['amazon_linux', 'ubuntu']
MAX_INSTANCES = 2

def get_latest_ami(ec2_client, os_type='amazon_linux'):
    """
    Finds the latest AMI ID based on the OS choice.
    Supports: 'amazon_linux' (AL2023) and 'ubuntu' (24.04 LTS).
    """
    ssm = boto3.client('ssm')
    
    try:
        if os_type == 'amazon_linux':
            # שימוש ב-SSM עבור Amazon Linux (הכי מהיר ומדויק)
            response = ssm.get_parameter(
                Name='/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64',
                WithDecryption=False
            )
            return response['Parameter']['Value']

        elif os_type == 'ubuntu':
            # חיפוש הגרסה הכי חדשה של Ubuntu 24.04
            response = ec2_client.describe_images(
                Filters=[
                    {'Name': 'name', 'Values': ['ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*']},
                    {'Name': 'owner-id', 'Values': ['099720109477']}, # הקוד הרשמי של Canonical
                    {'Name': 'state', 'Values': ['available']},
                    {'Name': 'architecture', 'Values': ['x86_64']}
                ],
                Owners=['099720109477']
            )
            # מיון לפי תאריך יצירה (מהחדש לישן) ולקיחת הראשון
            images = sorted(response['Images'], key=lambda x: x['CreationDate'], reverse=True)
            if not images:
                raise Exception("No Ubuntu AMI found.")
            return images[0]['ImageId']
            
        else:
            raise Exception(f"Unsupported OS type: {os_type}")

    except Exception as e:
        # גיבוי למקרה שמשהו משתבש בחיפוש הדינמי
        print(f"Warning: Failed to resolve dynamic AMI ({e}). Using fallback.")
        if os_type == 'ubuntu':
            return "ami-04b70fa74e45c3917" # Ubuntu 24.04 (us-east-1)
        return "ami-0c7217cdde317cfec"     # Amazon Linux 2023 (us-east-1)

def check_limit(ec2_client):
    """
    השוטר: בודק כמה שרתים יצרנו
    """
    project_value = PROJECT_TAG['Value']

    response = ec2_client.describe_instances(
        Filters=[
            {'Name': 'tag:CreatedBy', 'Values': [project_value]},
            {'Name': 'instance-state-name', 'Values': ['running', 'pending', 'stopped']}
        ]
    )

    count = 0
    for reservation in response['Reservations']:
        count += len(reservation['Instances'])

    if count >= MAX_INSTANCES:
        return False, f"Limit reached! You have {count}/{MAX_INSTANCES} instances."

    return True, "Limit check passed."

def create_instance(name, instance_type='t3.micro', os_type='amazon_linux'):
    """
    Creates a new EC2 instance with validation for Type and OS.
    """
    ec2_client = boto3.client('ec2')

    # 1. Validation - בדיקה שהמשתמש בחר רק מה שמותר
    if instance_type not in ALLOWED_TYPES:
        return False, f"Error: Invalid type '{instance_type}'. Allowed: {ALLOWED_TYPES}"
    
    if os_type not in ALLOWED_OS:
        return False, f"Error: Invalid OS '{os_type}'. Allowed: {ALLOWED_OS}"

    # 2. בדיקת כמות (Hard Cap)
    allowed, msg = check_limit(ec2_client)
    if not allowed:
        return False, msg

    try:
        print(f"DEBUG: Finding latest AMI for {os_type}...")
        ami_id = get_latest_ami(ec2_client, os_type)

        # 3. הכנת הטאגים
        tags = get_standard_tags()
        tags.append({'Key': 'Name', 'Value': name})
        tags.append({'Key': 'OS', 'Value': os_type}) # תגית לזיהוי המערכת

        print(f"DEBUG: Launching {os_type} instance '{name}' ({instance_type})...")

        # 4. יצירת השרת
        ec2_client.run_instances(
            ImageId=ami_id,
            InstanceType=instance_type,
            MinCount=1,
            MaxCount=1,
            TagSpecifications=[
                {'ResourceType': 'instance', 'Tags': tags},
                {'ResourceType': 'volume', 'Tags': tags}
            ]
        )

        return True, f"Success! Created {os_type} server '{name}' ({instance_type})"

    except ClientError as e:
        return False, f"AWS Error: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def stop_instance(instance_id):
    ec2_client = boto3.client('ec2')
    project_value = PROJECT_TAG['Value']

    try:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        if not response['Reservations']: return False, "Instance not found."
             
        tags = response['Reservations'][0]['Instances'][0].get('Tags', [])
        if not any(t['Key'] == 'CreatedBy' and t['Value'] == project_value for t in tags):
             return False, "Security Alert: Permission denied."

        ec2_client.stop_instances(InstanceIds=[instance_id])
        return True, f"Stopping instance {instance_id}..."

    except ClientError as e:
        return False, f"AWS Error: {e}"

def start_instance(instance_id):
    ec2_client = boto3.client('ec2')
    project_value = PROJECT_TAG['Value']

    try:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        if not response['Reservations']: return False, "Instance not found."

        tags = response['Reservations'][0]['Instances'][0].get('Tags', [])
        if not any(t['Key'] == 'CreatedBy' and t['Value'] == project_value for t in tags):
             return False, "Security Alert: Permission denied."

        ec2_client.start_instances(InstanceIds=[instance_id])
        return True, f"Starting instance {instance_id}..."

    except ClientError as e:
        return False, f"AWS Error: {e}"

def list_created_instances():
    ec2_client = boto3.client('ec2')
    project_value = PROJECT_TAG['Value'] 

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
                inst_type = instance.get('InstanceType', 'Unknown')
                
                name = "Unknown"
                if 'Tags' in instance:
                    for tag in instance['Tags']:
                        if tag['Key'] == 'Name': name = tag['Value']

                instances.append(f"{name} ({instance_id}) | Type: {inst_type} | State: {state} | IP: {public_ip}")

        return instances

    except Exception as e:
        print(f"Error listing instances: {e}")
        return []
