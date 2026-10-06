"""Notes belong straight to a subject; the topic becomes optional and is no longer used on the site.

Every existing note gets the subject of its topic. Topics and the notes' links to them are kept,
so nothing is lost and the change can be undone.
"""
import django.db.models.deletion
from django.db import migrations, models


def fill_subjects(apps, schema_editor):
    Note = apps.get_model('core', 'Note')
    for note in Note.objects.select_related('topic').only('id', 'topic__subject_id').iterator():
        Note.objects.filter(pk=note.pk).update(subject_id=note.topic.subject_id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_premium_notifications_packages'),
    ]

    operations = [
        migrations.AddField(
            model_name='note',
            name='subject',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name='notes', to='core.subject'),
        ),
        migrations.RunPython(fill_subjects, noop),
        migrations.AlterField(
            model_name='note',
            name='subject',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                    related_name='notes', to='core.subject'),
        ),
        migrations.AlterField(
            model_name='note',
            name='topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    to='core.topic'),
        ),
    ]
