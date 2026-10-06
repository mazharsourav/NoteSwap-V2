from django.db import migrations


def clean_ratings(apps, schema_editor):
    """Enforce the new rating rules on existing data before the unique constraint (0019)."""
    Rating = apps.get_model('core', 'Rating')
    # scores outside 1-5, and providers rating their own notes
    Rating.objects.exclude(score__gte=1, score__lte=5).delete()
    for rating in Rating.objects.select_related('note'):
        if rating.user_id == rating.note.provider_id:
            rating.delete()
    # one rating per user per note: keep each user's latest
    seen = set()
    for rating in Rating.objects.order_by('-id'):
        key = (rating.note_id, rating.user_id)
        if key in seen:
            rating.delete()
        else:
            seen.add(key)


def normalise_provider_statuses(apps, schema_editor):
    """'Pending'/'pending', 'Accepted'/'approved', 'Rejected' -> pending / accepted / rejected."""
    ProviderRequest = apps.get_model('core', 'ProviderRequest')
    mapping = {'pending': 'pending', 'accepted': 'accepted', 'approved': 'accepted', 'rejected': 'rejected'}
    for application in ProviderRequest.objects.all():
        status = mapping.get(application.status.lower(), 'pending')
        if status != application.status:
            application.status = status
            application.save(update_fields=['status'])


def mark_answered_requests_solved(apps, schema_editor):
    NoteSolveRequest = apps.get_model('core', 'NoteSolveRequest')
    NoteSolveRequest.objects.filter(solutions__isnull=False).update(status='solved')


def set_note_types_from_files(apps, schema_editor):
    Note = apps.get_model('core', 'Note')
    for note in Note.objects.all():
        note_type = 'pdf' if note.file.name.lower().endswith('.pdf') else 'image'
        if note.note_type != note_type:
            note.note_type = note_type
            note.save(update_fields=['note_type'])


class Migration(migrations.Migration):
    """Bring existing data in line with the Phase 3 rules. Not reversible (removed
    duplicate ratings can't be restored); use the phase snapshot to roll back."""

    dependencies = [
        ('core', '0017_phase3_status_inbox_ratings'),
    ]

    operations = [
        migrations.RunPython(clean_ratings, migrations.RunPython.noop),
        migrations.RunPython(normalise_provider_statuses, migrations.RunPython.noop),
        migrations.RunPython(mark_answered_requests_solved, migrations.RunPython.noop),
        migrations.RunPython(set_note_types_from_files, migrations.RunPython.noop),
    ]
