import sys
import os
import click  # ספרייה ליצירת ממשק שורת פקודה (CLI) נוח ויפה
import boto3  # הספרייה הרשמית של AWS לפייתון


# השורות האלה מוודאות שפייתון מכיר את התיקייה הראשית של הפרויקט.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.resources.s3_manager import create_s3_bucket, list_created_buckets, upload_file_to_bucket
from src.resources.ec2_manager import create_instance, list_created_instances, stop_instance, start_instance
from src.resources.route53_manager import create_hosted_zone, create_dns_record, list_hosted_zones


@click.group()
def cli():
    """AWS Resource Provisioning Tool - Final Edition"""
    pass


#  S3 COMMANDS 
@cli.command()
@click.option('--name', required=True, help='Unique bucket name')
@click.option('--public', is_flag=True, help='Set public access')
def create_s3(name, public):
    """Creates a new S3 bucket"""
    
    #   האישור 
    # אם המשתמש ביקש באקט ציבורי, אנחנו עוצרים ושואלים 
    if public:
        click.echo(click.style("  WARNING: You are about to create a PUBLIC bucket.", fg='yellow', bold=True))
        if not click.confirm('Are you sure you want to proceed?'):
            click.echo("Aborted.")
            return

    click.echo(f"🔄 Deploying S3 Bucket: {name}...")
    try:
        success, message = create_s3_bucket(name, public)
        color = 'green' if success else 'red'
        click.echo(click.style(f" {message}", fg=color))
    except Exception as e:
        click.echo(click.style(f" Error: {e}", fg='red'))


@cli.command()
@click.option('--bucket', required=True, help='Target bucket name')
@click.option('--file', required=True, help='Local file path to upload')
def upload_s3(bucket, file):
    """Uploads a file to a CLI-created bucket"""
    click.echo(f"📤 Uploading {file} to {bucket}...")
    try:
        # קריאה לפונקציה החדשה ב-S3 Manager
        success, message = upload_file_to_bucket(bucket, file)
        color = 'green' if success else 'red'
        click.echo(click.style(f" {message}", fg=color))
    except Exception as e:
        click.echo(click.style(f" Error: {e}", fg='red'))


@cli.command()
def list_s3():
    """Lists project buckets"""
    try:
        buckets = list_created_buckets()
        if buckets:
            click.echo(click.style(f" Found {len(buckets)} buckets:", fg='green'))
            for b in buckets: click.echo(f" - {b}")
        else:
            click.echo(click.style(" No buckets found.", fg='yellow'))
    except Exception as e:
        click.echo(click.style(f" Error: {e}", fg='red'))


# ================= EC2 COMMANDS (שרתים) =================
@cli.command()
@click.option('--name', required=True, help='Name tag for the server')
def create_ec2(name):
    """Launches a t2.micro instance"""
    click.echo(f" Launching EC2 Instance: {name}...")
    try:
        success, message = create_instance(name)
        color = 'green' if success else 'red'
        click.echo(click.style(f" {message}", fg=color))
    except Exception as e:
        click.echo(click.style(f" Error: {e}", fg='red'))


@cli.command()
@click.option('--id', required=True, help='Instance ID to stop')
def stop_ec2(id):
    """Stops a running instance"""
    click.echo(f" Stopping instance {id}...")
    try:
        # קריאה לפונקציה החדשה ב-EC2 Manager
        success, message = stop_instance(id)
        color = 'green' if success else 'red'
        click.echo(click.style(f" {message}", fg=color))
    except Exception as e:
        click.echo(click.style(f" Error: {e}", fg='red'))


@cli.command()
@click.option('--id', required=True, help='Instance ID to start')
def start_ec2(id):
    """Starts a stopped instance"""
    click.echo(f" Starting instance {id}...")
    try:
        # קריאה לפונקציה החדשה ב-EC2 Manager
        success, message = start_instance(id)
        color = 'green' if success else 'red'
        click.echo(click.style(f" {message}", fg=color))
    except Exception as e:
        click.echo(click.style(f" Error: {e}", fg='red'))


@cli.command()
def list_ec2():
    """Lists project instances"""
    try:
        instances = list_created_instances()
        if instances:
            click.echo(click.style(f" Found {len(instances)} instances:", fg='green'))
            for i in instances: click.echo(f" - {i}")
        else:
            click.echo(click.style(" No instances found.", fg='yellow'))
    except Exception as e:
        click.echo(click.style(f" Error: {e}", fg='red'))


#  ROUTE 53 COMMANDS 
@cli.command()
@click.option('--domain', required=True, help='Domain name')
@click.option('--instance-name', required=True, help='EC2 Instance Name')
def setup_dns(domain, instance_name):
    """Connects a Domain to an EC2 Instance"""
    click.echo(f"🔌 Connecting {domain} to instance '{instance_name}'...")
    try:
        # 1. מציאת ה-IP של השרת
        ec2 = boto3.client('ec2')
        response = ec2.describe_instances(
            Filters=[{'Name': 'tag:Name', 'Values': [instance_name]}, 
                     {'Name': 'instance-state-name', 'Values': ['running']}]
        )
        public_ip = None
        for r in response['Reservations']:
            for i in r['Instances']:
                public_ip = i.get('PublicIpAddress')

        if not public_ip:
            click.echo(click.style(f" Instance '{instance_name}' not found or no IP.", fg='red'))
            return

        click.echo(f"   Found IP: {public_ip}")

        # 2. יצירת Hosted Zone
        success, result = create_hosted_zone(domain)
        if not success:
            click.echo(click.style(f" Failed to create zone: {result}", fg='red'))
            return

        # 3. יצירת רשומת DNS
        rec_success, rec_msg = create_dns_record(result, f"www.{domain}", public_ip)
        color = 'green' if rec_success else 'red'
        click.echo(click.style(f" {rec_msg}", fg=color))

    except Exception as e:
        click.echo(click.style(f" Error: {e}", fg='red'))


@cli.command()
def list_route53():
    """Lists project hosted zones"""
    try:
        zones = list_hosted_zones()
        if zones:
            click.echo(click.style(f" Found {len(zones)} hosted zones:", fg='green'))
            for z in zones: click.echo(f" - {z}")
        else:
            click.echo(click.style(" No hosted zones found.", fg='yellow'))
    except Exception as e:
        click.echo(click.style(f" Error: {e}", fg='red'))


if __name__ == '__main__':
    cli()
