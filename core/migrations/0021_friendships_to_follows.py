"""
Friends are replaced by following providers.

Every accepted friendship with a provider becomes a follow of that provider
(both ways if both are providers). Pending requests and friendships between
two non-providers have no equivalent and are dropped with the friend table
in the next migration.
"""
from django.db import migrations


def friendships_to_follows(apps, schema_editor):
    FriendRequest = apps.get_model('core', 'FriendRequest')
    Follow = apps.get_model('core', 'Follow')

    pairs = set()
    for friendship in FriendRequest.objects.filter(status='accepted').select_related('from_user', 'to_user'):
        a, b = friendship.from_user, friendship.to_user
        if a.id == b.id:
            continue
        if b.user_type == 'provider':
            pairs.add((a.id, b.id))
        if a.user_type == 'provider':
            pairs.add((b.id, a.id))

    Follow.objects.bulk_create(
        [Follow(follower_id=follower, provider_id=provider) for follower, provider in sorted(pairs)],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_follow_and_notification'),
    ]

    operations = [
        migrations.RunPython(friendships_to_follows, migrations.RunPython.noop),
    ]
