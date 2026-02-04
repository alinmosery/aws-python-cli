import boto3
from botocore.exceptions import ClientError
from src.utils.helper import get_standard_tags


def create_s3_bucket(bucket_name, is_public=False):
    """
    Creates an S3 bucket with specific tags.
    """
    # שלב 1: יצירת קליינט
    s3_client = boto3.client('s3')

    try:
        # שלב 2: הבאת הטאגים
        tags = get_standard_tags()

        # שלב 3: יצירה + תיוג
        s3_client.create_bucket(Bucket=bucket_name)

        s3_client.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={'TagSet': tags}
        )

        print(f"DEBUG: Created bucket {bucket_name} with tags.")

        # --- שלב 4: הגדרת גישה (Public vs Private) ---
        if is_public:
            # אם המשתמש ביקש ציבורי: אנחנו מסירים את חסימות הגישה
            print(f"DEBUG: Setting bucket {bucket_name} to PUBLIC...")
            s3_client.delete_public_access_block(Bucket=bucket_name)

            # (אופציונלי: אפשר להוסיף כאן גם Bucket Policy לקריאה בלבד, אבל זה בדרך כלל מספיק לתרגיל)
            access_msg = "PUBLIC access enabled ⚠️"
        else:
            # אם המשתמש ביקש פרטי (או לא ביקש כלום): אנחנו נועלים הכל
            print(f"DEBUG: Setting bucket {bucket_name} to PRIVATE (Secured)...")
            s3_client.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    'BlockPublicAcls': True,
                    'IgnorePublicAcls': True,
                    'BlockPublicPolicy': True,
                    'RestrictPublicBuckets': True
                }
            )
            access_msg = "Private access secured 🔒"

        return True, f"Bucket {bucket_name} created successfully. ({access_msg})"

    except ClientError as e:
        return False, f"Error creating bucket: {e}"
    except ClientError as e:
        return False, f"Error creating bucket: {e}"


def list_created_buckets():
    """
    Lists only buckets that contain the specific project tag.
    """
    s3_client = boto3.client('s3')

    # 1. קבלת רשימת כל הבאקטים בחשבון
    response = s3_client.list_buckets()
    all_buckets = response.get('Buckets', [])

    my_buckets = []
    print(f"DEBUG: Scanning {len(all_buckets)} buckets for our tag...")

    # 2. מעבר על כל באקט ובדיקה האם הוא 'שלנו'
    for bucket in all_buckets:
        name = bucket['Name']
        try:
            # S3 לא נותן טאגים ברשימה הראשית, צריך לבקש אותם במיוחד לכל באקט
            tags_response = s3_client.get_bucket_tagging(Bucket=name)
            tag_set = tags_response.get('TagSet', [])

            # בדיקה: האם הטאג שלנו נמצא ברשימה?
            # אנחנו מחפשים אם יש טאג שהמפתח שלו הוא 'CreatedBy' והערך 'Alin-DevOps-CLI'
            for tag in tag_set:
                if tag['Key'] == 'CreatedBy' and tag['Value'] == 'Alin-DevOps-CLI':
                    my_buckets.append(name)
                    break

        except ClientError:
            # אם לבאקט אין טאגים בכלל, AWS מחזיר שגיאה - וזה בסדר, פשוט מדלגים עליו
            continue

    return my_buckets