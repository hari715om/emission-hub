"""
Management command: seed_demo
Creates a demo tenant, superuser, site mappings, and loads unit/emission fixtures.
Run once after migrations on a fresh database.

Usage:
    python manage.py seed_demo
    python manage.py seed_demo --admin-password mypassword
"""
# pyrefly: ignore [missing-import]
from django.core.management.base import BaseCommand
# pyrefly: ignore [missing-import]
from django.contrib.auth import get_user_model
# pyrefly: ignore [missing-import]
from django.core.management import call_command

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds demo tenant, superuser, and reference data for the prototype'

    def add_arguments(self, parser):
        parser.add_argument('--admin-password', default='breathe123', type=str)
        parser.add_argument('--admin-username', default='admin', type=str)
        parser.add_argument('--admin-email', default='admin@breatheesg.demo', type=str)

    def handle(self, *args, **options):
        # 1. Load fixtures (unit mappings + emission factors)
        self.stdout.write('Loading fixtures...')
        call_command('loaddata', 'ingestion/fixtures/initial_data.json', verbosity=0)
        self.stdout.write(self.style.SUCCESS('  [OK] Fixtures loaded'))

        # 2. Create demo tenant
        from tenants.models import Tenant, SiteMapping
        tenant, created = Tenant.objects.get_or_create(
            slug='acme-corp',
            defaults={
                'name': 'Acme Corporation (Demo)',
                'country': 'United Kingdom',
                'industry': 'Manufacturing',
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  [OK] Tenant created: {tenant.name}'))
        else:
            self.stdout.write(f'  [OK] Tenant already exists: {tenant.name}')

        # 3. Seed site mappings — SAP WERKS codes for Acme
        site_data = [
            ('1000', 'London HQ', 'United Kingdom', 'England', 'SAP'),
            ('2000', 'Manchester Plant', 'United Kingdom', 'England', 'SAP'),
            ('3000', 'Birmingham Depot', 'United Kingdom', 'England', 'SAP'),
            ('4000', 'Glasgow Office', 'United Kingdom', 'Scotland', 'SAP'),
            ('MPAN-001', 'London HQ — Main Meter', 'United Kingdom', 'England', 'UTILITY'),
            ('MPAN-002', 'Manchester Plant — Meter A', 'United Kingdom', 'England', 'UTILITY'),
            ('MPAN-003', 'Birmingham Depot — Meter', 'United Kingdom', 'England', 'UTILITY'),
        ]
        created_count = 0
        for code, name, country, region, src_type in site_data:
            _, c = SiteMapping.objects.get_or_create(
                tenant=tenant,
                source_code=code,
                source_type=src_type,
                defaults={'site_name': name, 'country': country, 'region': region}
            )
            if c:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(f'  [OK] {created_count} site mappings created'))

        # 4. Create superuser
        username = options['admin_username']
        password = options['admin_password']
        email = options['admin_email']

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f'  [OK] Superuser created: {username} / {password}'))
        else:
            self.stdout.write(f'  [OK] Superuser already exists: {username}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('[DONE] Demo seed complete.'))
        self.stdout.write(f'   Tenant ID: {tenant.id}')
        self.stdout.write(f'   Admin login: {username} / {password}')
        self.stdout.write('   Upload the sample CSVs from sample_data/ to test ingestion.')
