import sys
import os
import click  # ספרייה ליצירת ממשק שורת פקודה (CLI) נוח ויפה
import boto3  # הספרייה הרשמית של AWS לפייתון  דרכה אנחנו מדברים עם הענן


# כשאנחנו מריצים סקריפט מתוך תיקייה פנימית, פייתון לפעמים לא מוצא את התיקיות האחרות.
# השורות האלה מוודאות שפייתון מכיר את התיקייה הראשית של הפרויקט, כדי שנוכל לייבא קבצים מ-src.
current_dir = os.path.dirname(os.path.abspath(__file__))  # איפה הקובץ הזה נמצא עכשיו
project_root = os.path.dirname(current_dir)             # התיקייה אליה הקובץ שייך 
if project_root not in sys.path:
    sys.path.insert(0, project_root)                    # הוספת התיקייה הראשית לנתיב החיפוש של פייתון


# אנחנו מייבאים רק את הפונקציות הספציפיות שאנחנו צריכים מכל קובץ.
# זה שומר על הקוד נקי ומסודר.
from src.resources.s3_manager import create_s3_bucket, list_created_buckets
from src.resources.ec2_manager import create_instance, list_created_instances
from src.resources.route53_manager import create_hosted_zone, create_dns_record


# יצירת קבוצת הפקודות הראשית
# @click.group הופך את הפונקציה cli ל"אבא" של כל הפקודות האחרות.
# זה מאפשר לנו להריץ: python main.py [command]
@click.group()
def cli():
    """AWS Resource Provisioning Tool - The Final Version"""
    pass  # הפונקציה הזו לא עושה כלום בעצמה, היא רק מאגדת את הפקודות


#  S3 COMMANDS (פקודות לאחסון) 

@cli.command()  # מגדיר שזו פקודה תחת ה-CLI שלנו
@click.option('--name', required=True, help='Unique bucket name')  # פרמטר חובה: שם הבאקט
@click.option('--public', is_flag=True, help='Set public access')  # דגל האם הבאקט ציבורי?
def create_s3(name, public):
    """Creates a new S3 bucket"""
    
    # הדפסה למשתמש 
    click.echo(f" Deploying S3 Bucket: {name}...")
    
    try:
        # קריאה לפונקציה מתוך s3_manager.py שמבצעת את העבודה מול AWS
        success, message = create_s3_bucket(name, public)
        
        # צביעת ההודעה בירוק אם הצליח, אדום אם נכשל
        color = 'green' if success else 'red'
        
        
        # click.style מאפשר לנו להדפיס בצבעים לטרמינל
        click.echo(click.style(f" {message}", fg=color))
        
    except Exception as e:
        # תפיסת שגיאות בלתי צפויות (כדי שהתוכנית לא תקרוס )
        click.echo(click.style(f" Error: {e}", fg='red'))


@cli.command()
def list_s3():
    """Lists project buckets"""
    try:
        # שליפת רשימת הבאקטים (רק אלו שנוצרו ע"י הכלי שלנו)
        buckets = list_created_buckets()
        
        if buckets:
            click.echo(click.style(f" Found {len(buckets)} buckets:", fg='green'))
            # מעבר על הרשימה והדפסת כל באקט
            for b in buckets: 
                click.echo(f" - {b}")
        else:
            # אם הרשימה ריקה
            click.echo(click.style(" No buckets found.", fg='yellow'))
            # אם משום מה זה לא רץ
    except Exception as e:
        click.echo(click.style(f" Error: {e}", fg='red'))


#EC2 COMMANDS פקודות לשרתים

@cli.command()
@click.option('--name', required=True, help='Name tag for the server')
def create_ec2(name):
    """Launches a t2.micro instance"""
    click.echo(f"🚀 Launching EC2 Instance: {name}...")
    try:
        # קריאה לפונקציה ב-ec2_manager.
        #  לא מעבירים סוג שרת כי זה כבר מוגדר קבוע בפונקציה של המנהלה
       
        success, message = create_instance(name)
        
        color = 'green' if success else 'red'
        click.echo(click.style(f"{message}", fg=color))
        
    except Exception as e:
        click.echo(click.style(f" Error: {e}", fg='red'))


@cli.command()
def list_ec2():
    """Lists project instances"""
    try:
        # מקבלים רשימה של שרתים שנוצרו ע"י הכלי
        instances = list_created_instances()
        
        if instances:
            click.echo(click.style(f" Found {len(instances)} instances:", fg='green'))
            for i in instances: 
                click.echo(f" - {i}")
        else:
            click.echo(click.style(" No instances found.", fg='yellow'))
            
    except Exception as e:
        click.echo(click.style(f" Error: {e}", fg='red'))


#  ROUTE 53 COMMANDS (ניהול דומיינים) 
# זו הפקודה המורכבת ביותר, שמחברת בין השרת לדומיין

@cli.command()
@click.option('--domain', required=True, help='Domain name (e.g., my-app.com)')
@click.option('--instance-name', required=True, help='The EC2 instance name to connect to')
def setup_dns(domain, instance_name):
    """Connects a Domain to an EC2 Instance"""
    click.echo(f" Connecting {domain} to instance '{instance_name}'...")

    try:
        # מציאת האייפי של השרת באפון אוטומטי
        # אנחנו צריכים את האייפי הציבורי של השרת כדי לחבר אותו לדומיין.
        # במקום לבקש מהמשתמש להעתיק-להדביק אייפי, אנחנו מוצאים אותו לבד לפי השם.
        
        ec2 = boto3.client('ec2')
        response = ec2.describe_instances(
            Filters=[
                {'Name': 'tag:Name', 'Values': [instance_name]},  # מחפשים לפי תגית השם
                {'Name': 'instance-state-name', 'Values': ['running']} # מוודאים שהוא רץ
            ]
        )

        public_ip = None
        # לולאה שעוברת על כל התצאות מאמזון ומחפשת את האייפי
        for r in response['Reservations']:
            for i in r['Instances']:
                public_ip = i.get('PublicIpAddress')

        # אם לא מצאנו אייפי (אולי השרת כבוי או לא קיים)
        if not public_ip:
            click.echo(click.style(f" Could not find running instance named '{instance_name}' or it has no public IP.",
                                   fg='red'))
            return

        click.echo(f"   found IP: {public_ip}")

        #  יצירת ה hosted zone  ב route53  
        # אנחנו יוצרים אזור ניהול חדש לדומיין הזה
        success, result = create_hosted_zone(domain)
        if not success:
            click.echo(click.style(f" Failed to create zone: {result}", fg='red'))
            return

        zone_id = result  # שומרים את ה-איידי של האזור שנוצר
        click.echo(f"   Created Zone ID: {zone_id}")

        # יצירת הרשומה (A Record)
        #מחברים את הכתובת דומיין לאייפי שמצאנו  
        rec_success, rec_msg = create_dns_record(zone_id, f"www.{domain}", public_ip)

        if rec_success:
            click.echo(click.style(f" SUCCESS! {rec_msg}", fg='green'))
        else:
            click.echo(click.style(f" Failed to create record: {rec_msg}", fg='red'))

    except Exception as e:
        click.echo(click.style(f" Unexpected Error: {e}", fg='red'))


# נקודת הכניסה של הסקריפט
# זה אומר: "אם מריצים את הקובץ הזה ישירות (ולא מייבאים אותו), תפעיל את ה-CLI".
if __name__ == '__main__':
    cli()
