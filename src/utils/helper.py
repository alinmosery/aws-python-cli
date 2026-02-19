# src/utils/helper.py

#יגיד לנו מהנוצר תחת הטאג שלנו
PROJECT_TAG = {'Key': 'CreatedBy', 'Value': 'Alin-DevOps-CLI'}

def get_standard_tags():
    """
    מחזיר את רשימת הטאגים שחובה להצמיד לכל משאב (EC2, S3, וכו').
    """
    return [PROJECT_TAG]
