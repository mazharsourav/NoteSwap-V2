from django.db import migrations, models


class Migration(migrations.Migration):
    """One rating per user per note. Runs after 0018 removed existing duplicates."""

    dependencies = [
        ('core', '0018_phase3_data_cleanup'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='rating',
            constraint=models.UniqueConstraint(fields=('note', 'user'), name='unique_rating_per_user_and_note'),
        ),
    ]
