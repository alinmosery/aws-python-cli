import boto3
import os  # העברנו את זה למעלה - המקום הנכון
from botocore.exceptions import ClientError
from src.utils.helper import get_standard_tags, PROJECT_TAG


def create_s3_bucket(bucket_name, is_public=False):
    
 #   Creates an S3 bucket with specific tags and access settings.
    
    s3_client = boto3.client('s3')

    try:
        # 1. יצירת הבאקט עצמו
        # בניגוד ל-EC2, ב-S3 אי אפשר להוסיף טאגים בתוך פקודת היצירה.
        s3_client.create_bucket(Bucket=bucket_name)
        print(f"DEBUG: Bucket '{bucket_name}' created.")

        # 2. הוספת הטאגים (Post-Creation Tagging)
        tags = get_standard_tags() # שליפת הטאגים הקבועים מההלפר
        
        s3_client.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={'TagSet': tags} # AWS דורש את המבנה הזה בדיוק
        )
        print(f"DEBUG: Tags added to '{bucket_name}'.")

        # 3. ניהול אבטחה (Security Guardrails)
        if is_public:
            # אם המשתמש ביקש ציבורי: מסירים את המנעולים
            print(f"DEBUG: Setting bucket {bucket_name} to PUBLIC (Removing Blocks)...")
            s3_client.delete_public_access_block(Bucket=bucket_name)
            access_msg = "PUBLIC access enabled (Blocks removed) "
        
        else:
            # אם המשתמש ביקש פרטי: נועלים הכל
            print(f"DEBUG: Locking bucket {bucket_name}...")
            s3_client.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    'BlockPublicAcls': True,
                    'IgnorePublicAcls': True,
                    'BlockPublicPolicy': True,
                    'RestrictPublicBuckets': True
                }
            )
            access_msg = "Private access secured "

        return True, f"Bucket created successfully. {access_msg}"

    except ClientError as e:
        # תופס שגיאות כמו: שם באקט תפוס
        if e.response['Error']['Code'] == 'BucketAlreadyExists':
            return False, "Error: Bucket name already taken globally. Try a different name."
        return False, f"AWS Error: {e}"
    except Exception as e:
        return False, f"Unexpected Error: {e}"


def list_created_buckets():
    """
    Lists only buckets that contain the specific project tag.
    """
    s3_client = boto3.client('s3')
    project_value = PROJECT_TAG['Value'] # שימוש במשתנה המיובא

    try:
        # 1. קבלת רשימת כל הבאקטים בחשבון
        response = s3_client.list_buckets()
        all_buckets = response.get('Buckets', [])

        my_buckets = []
        print(f"DEBUG: Scanning {len(all_buckets)} buckets for tag: {project_value}...")

        # 2. מעבר על כל באקט ובדיקה האם הוא 'שלנו'
        for bucket in all_buckets:
            name = bucket['Name']
            try:
                # לכל באקט אנחנו שולחים בקשה נפרדת לקבל את הטאגים שלו
                tags_response = s3_client.get_bucket_tagging(Bucket=name)
                tag_set = tags_response.get('TagSet', [])

                # האם הטאג שלנו נמצא ברשימה?
                for tag in tag_set:
                    if tag['Key'] == 'CreatedBy' and tag['Value'] == project_value:
                        my_buckets.append(name)
                        break # מצאנו

            except ClientError as e:
                # באג ב-AWS: אם אין טאגים בכלל, הפקודה נכשלת
                if e.response['Error']['Code'] == 'NoSuchTagSet':
                    continue # אין טאגים, אז זה לא הבאקט שלנו
                else:
                    print(f"Warning: Could not check tags for bucket {name}: {e}")
                    continue

        return my_buckets

    except Exception as e:
        print(f"Error listing buckets: {e}")
        return []


def upload_file_to_bucket(bucket_name, file_path):
    """
    Uploads a file to an S3 bucket (only if the bucket is ours).
    """
    s3_client = boto3.client('s3')
    project_value = PROJECT_TAG['Value']

    try:
        # 1. בדיקת בעלות על הבאקט (האם יש לו את הטאג שלנו?)
        tags_response = s3_client.get_bucket_tagging(Bucket=bucket_name)
        tag_set = tags_response.get('TagSet', [])
        
        is_ours = False
        for tag in tag_set:
            if tag['Key'] == 'CreatedBy' and tag['Value'] == project_value:
                is_ours = True
                break
        
        if not is_ours:
            return False, f" Permission Denied: Bucket '{bucket_name}' is not managed by this CLI."

        # 2. העלאת הקובץ
        file_name = os.path.basename(file_path) # לוקח רק את שם הקובץ (בלי הנתיב המלא)
        s3_client.upload_file(file_path, bucket_name, file_name)
        
        return True, f"File '{file_name}' uploaded successfully to {bucket_name}!"

    except ClientError as e:
        return False, f"AWS Error: {e}"
    except FileNotFoundError:
        return False, "Error: The file you tried to upload does not exist."
