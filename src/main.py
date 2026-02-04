import sys
import os
import click
import boto3

# --- 1. תיקון נתיבים ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- 2. אימפורטים מהקבצים שיצרנו ---
from src.resources.s3_manager import create_s3_bucket, list_created_buckets
from src.resources.ec2_manager import create_instance, list_created_instances
from src.resources.route53_manager import create_hosted_zone, create_dns_record


@click.group()
def cli():
    """AWS Resource Provisioning Tool - The Final Version"""
    pass


# ================= S3 COMMANDS =================
@cli.command()
@click.option('--name', required=True, help='Unique bucket name')
@click.option('--public', is_flag=True, help='Set public access')
def create_s3(name, public):
    """Creates a new S3 bucket"""
    click.echo(f"🔄 Deploying S3 Bucket: {name}...")
    try:
        success, message = create_s3_bucket(name, public)
        color = 'green' if success else 'red'
        click.echo(click.style(f"{'✅' if success else '❌'} {message}", fg=color))
    except Exception as e:
        click.echo(click.style(f"❌ Error: {e}", fg='red'))


@cli.command()
def list_s3():
    """Lists project buckets"""
    try:
        buckets = list_created_buckets()
        if buckets:
            click.echo(click.style(f"✅ Found {len(buckets)} buckets:", fg='green'))
            for b in buckets: click.echo(f" - {b}")
        else:
            click.echo(click.style("⚠️ No buckets found.", fg='yellow'))
    except Exception as e:
        click.echo(click.style(f"❌ Error: {e}", fg='red'))


# ================= EC2 COMMANDS =================
@cli.command()
@click.option('--name', required=True, help='Name tag for the server')
def create_ec2(name):
    """Launches a t2.micro instance"""
    click.echo(f"🚀 Launching EC2 Instance: {name}...")
    try:
        success, message = create_instance(name)
        color = 'green' if success else 'red'
        click.echo(click.style(f"{'✅' if success else '❌'} {message}", fg=color))
    except Exception as e:
        click.echo(click.style(f"❌ Error: {e}", fg='red'))


@cli.command()
def list_ec2():
    """Lists project instances"""
    try:
        instances = list_created_instances()
        if instances:
            click.echo(click.style(f"✅ Found {len(instances)} instances:", fg='green'))
            for i in instances: click.echo(f" - {i}")
        else:
            click.echo(click.style("⚠️ No instances found.", fg='yellow'))
    except Exception as e:
        click.echo(click.style(f"❌ Error: {e}", fg='red'))


# ================= ROUTE 53 COMMANDS (החדש!) =================
@cli.command()
@click.option('--domain', required=True, help='Domain name (e.g., my-app.com)')
@click.option('--instance-name', required=True, help='The EC2 instance name to connect to')
def setup_dns(domain, instance_name):
    """Connects a Domain to an EC2 Instance"""
    click.echo(f"🔌 Connecting {domain} to instance '{instance_name}'...")

    try:
        # שלב 1: מציאת ה-IP של השרת באופן אוטומטי
        ec2 = boto3.client('ec2')
        response = ec2.describe_instances(
            Filters=[
                {'Name': 'tag:Name', 'Values': [instance_name]},
                {'Name': 'instance-state-name', 'Values': ['running']}
            ]
        )

        public_ip = None
        for r in response['Reservations']:
            for i in r['Instances']:
                public_ip = i.get('PublicIpAddress')

        if not public_ip:
            click.echo(click.style(f"❌ Could not find running instance named '{instance_name}' or it has no public IP.",
                                   fg='red'))
            return

        click.echo(f"   found IP: {public_ip}")

        # שלב 2: יצירת ה-Hosted Zone
        success, result = create_hosted_zone(domain)
        if not success:
            click.echo(click.style(f"❌ Failed to create zone: {result}", fg='red'))
            return

        zone_id = result
        click.echo(f"   Created Zone ID: {zone_id}")

        # שלב 3: יצירת הרשומה (Record)
        rec_success, rec_msg = create_dns_record(zone_id, f"www.{domain}", public_ip)

        if rec_success:
            click.echo(click.style(f"✅ SUCCESS! {rec_msg}", fg='green'))
        else:
            click.echo(click.style(f"❌ Failed to create record: {rec_msg}", fg='red'))

    except Exception as e:
        click.echo(click.style(f"❌ Unexpected Error: {e}", fg='red'))


if __name__ == '__main__':
    cli()