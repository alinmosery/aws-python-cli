import boto3
from botocore.exceptions import ClientError
from src.utils.helper import get_standard_tags, PROJECT_TAG


def create_s3_bucket(bucket_name, is_public=False):
    # Creates an S3 bucket with specific tags and access settings.
    # חיבור ל aws
    s3_client = boto3.client('s3')

    try:
          #  יצירת הבאקט עצמו
          #בניגוד לאיסי2 באס3 אי אפשר להוסיף טאקים בתוך פקודת היצירה
        # לכן קודם יוצרים ואז מתייגים.
        s3_client.create_bucket(Bucket=bucket_name)
        print(f"DEBUG: Bucket '{bucket_name}' created.")

        #  הוספת הטאגים (Post-Creation Tagging)
        tags = get_standard_tags() # שליפת הטאגים הקבועים מההלפר
        
        s3_client.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={'TagSet': tags} # AWS דורש את המבנה הזה בדיוק
        )
        print(f"DEBUG: Tags added to '{bucket_name}'.")

        #  ניהול אבטחה Security Guardrails
        # AWS נועלת באקטים באופן ברירת מחדל (Block Public Access).
        # אנחנו צריכים להחליט אם לפתוח או לנעול חזק יותר.
        
        if is_public:
            # אם המשתמש ביקש ציבורי: חייבים להסיר את המנעולים של AWS.
            # זה לא הופך את הבאקט לציבורי מייד (צריך גם Policy), אבל זה מאפשר לו להיות ציבורי.
            print(f"DEBUG:  Setting bucket {bucket_name} to PUBLIC (Removing Blocks)...")
            s3_client.delete_public_access_block(Bucket=bucket_name)
            access_msg = "PUBLIC access enabled (Blocks removed) "
        
        else:
            # אם המשתמש ביקש פרטי: אנחנו מפעילים את כל 4 המנעולים של AWS.
            print(f"DEBUG:  Locking bucket {bucket_name}...")
            s3_client.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    'BlockPublicAcls': True,      # חוסם רשימות גישה ציבוריות
                    'IgnorePublicAcls': True,     # מתעלם אם מישהו ניסה להגדיר כזה
                    'BlockPublicPolicy': True,    # חוסם מדיניות (Policy) ציבורית
                    'RestrictPublicBuckets': True # נועל את הבאקט לגישה חיצונית
                }
            )
            access_msg = "Private access secured "

        return True, f"Bucket created successfully. {access_msg}"

    except ClientError as e:
        # תופס שגיאות כמו: שם באקט תפוס, אין הרשאות ועוד
        if e.response['Error']['Code'] == 'BucketAlreadyExists':
            return False, "Error: Bucket name already taken globally. Try a different name."
        return False, f"AWS Error: {e}"
        #לכל שאר השגיאות
    except Exception as e:
        return False, f"Unexpected Error: {e}"


def list_created_buckets():
  
    # Lists only buckets that contain the specific project tag.
   # פונקציה הסורקת
    
    s3_client = boto3.client('s3')
    project_value = PROJECT_TAG['Value'] # שימוש במשתנה המיובא

    try:
        # 1. קבלת רשימת כל הבאקטים בחשבון 
        response = s3_client.list_buckets()
        all_buckets = response.get('Buckets', [])

        my_buckets = []
        print(f"DEBUG: Scanning {len(all_buckets)} buckets for tag: {project_value}...")

        # 2. מעבר על כל באקט ובדיקה האם הוא בעל הטאג שלנו'
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
                # תפסתי שגיאה כי אם לא הקוד יקרוס
                if e.response['Error']['Code'] == 'NoSuchTagSet':
                    continue # אין טאגים, אז זה לא הבאקט שלנו
                else:
                    print(f"Warning: Could not check tags for bucket {name}: {e}")
                    continue

        return my_buckets

    except Exception as e:
        print(f"Error listing buckets: {e}")
        return []
