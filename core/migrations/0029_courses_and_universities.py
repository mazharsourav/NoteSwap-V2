"""Courses: a subject is just a name now; each note gets an optional course code.
Universities: stored values are tidied to the codes in core/universities.py ("Uap" -> "UAP");
names that aren't in the list are kept as typed. Reversing leaves the tidied values.
"""
import django.core.validators
from django.db import migrations, models

from core.universities import normalize

MODELS_WITH_A_UNIVERSITY = ['CustomUser', 'Subject', 'Topic', 'Note', 'ProviderRequest', 'NoteSolveRequest']


def tidy_universities(apps, schema_editor):
    for model_name in MODELS_WITH_A_UNIVERSITY:
        Model = apps.get_model('core', model_name)
        for value in Model.objects.order_by().values_list('university', flat=True).distinct():
            clean = normalize(value)
            if clean != value:
                Model.objects.filter(university=value).update(university=clean)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_note_subject'),
    ]

    operations = [
        migrations.AddField(
            model_name='note',
            name='course_code',
            field=models.CharField(blank=True, help_text='The course code at this university, e.g. "CSE 301".', max_length=30, verbose_name='course code'),
        ),
        migrations.AlterField(
            model_name='subject',
            name='semester',
            field=models.IntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1, 'Use a semester from 1 to 12.'), django.core.validators.MaxValueValidator(12, 'Use a semester from 1 to 12.')]),
        ),
        migrations.AlterField(
            model_name='subject',
            name='university',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='subject',
            name='year',
            field=models.IntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1, 'Use a year of study from 1 to 5.'), django.core.validators.MaxValueValidator(5, 'Use a year of study from 1 to 5.')]),
        ),
        migrations.RunPython(tidy_universities, noop),
    ]
