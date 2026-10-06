"""
Accounts created before email verification existed keep working.

Each existing user's email is registered with allauth as their verified, primary
address, so they can still sign in. An address can only be verified on one
account; when several accounts share one, it goes to a superuser if there is
one, otherwise to the account that signed in most recently. The other accounts
(and accounts with no email) are asked to verify an address when they sign in.

New sign-ups are not affected: they always verify by email.
"""
from collections import defaultdict

from django.db import migrations


def register_existing_emails(apps, schema_editor):
    User = apps.get_model('core', 'CustomUser')
    EmailAddress = apps.get_model('account', 'EmailAddress')

    by_email = defaultdict(list)
    for user in User.objects.exclude(email='').only('id', 'email', 'is_superuser', 'last_login'):
        by_email[user.email.strip().lower()].append(user)

    addresses = []
    for email, users in by_email.items():
        users.sort(key=lambda u: (not u.is_superuser, -(u.last_login.timestamp() if u.last_login else 0), u.id))
        owner = users[0]
        if not EmailAddress.objects.filter(email__iexact=email, verified=True).exists():
            addresses.append(EmailAddress(user_id=owner.id, email=email, verified=True, primary=True))
    EmailAddress.objects.bulk_create(addresses, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_remove_friendrequest'),
        ('account', '0009_emailaddress_unique_primary_email'),
    ]

    operations = [
        migrations.RunPython(register_existing_emails, migrations.RunPython.noop),
    ]
