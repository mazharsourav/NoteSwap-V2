"""
Premium that runs out: orders get a status (pending / approved / rejected) and the paid
time they add; users get `premium_until`.

Existing approved orders are replayed in order per user, starting at the order time and
stacking, so `premium_until` is what it would have been if expiry had always existed.
"""
import calendar

import django.core.validators
from django.db import migrations, models
from django.utils import timezone


def add_months(moment, months):
    local = timezone.localtime(moment)
    month_index = local.month - 1 + months
    year, month = local.year + month_index // 12, month_index % 12 + 1
    return local.replace(year=year, month=month, day=min(local.day, calendar.monthrange(year, month)[1]))


def fill_premium_time(apps, schema_editor):
    PremiumPurchase = apps.get_model('core', 'PremiumPurchase')
    PremiumPackage = apps.get_model('core', 'PremiumPackage')
    CustomUser = apps.get_model('core', 'CustomUser')
    months_by_name = dict(PremiumPackage.objects.values_list('name', 'duration_in_months'))

    premium_until = {}
    for order in PremiumPurchase.objects.order_by('timestamp', 'id'):
        order.duration_in_months = months_by_name.get(order.package_name, 1)
        if order.is_approved:
            current = premium_until.get(order.user_id)
            order.status = 'approved'
            order.reviewed_at = order.timestamp
            order.starts_at = max(order.timestamp, current) if current else order.timestamp
            order.ends_at = add_months(order.starts_at, order.duration_in_months)
            premium_until[order.user_id] = order.ends_at
        else:
            order.status = 'pending'
        order.save()
    for user_id, until in premium_until.items():
        CustomUser.objects.filter(id=user_id).update(premium_until=until)


def restore_is_approved(apps, schema_editor):
    PremiumPurchase = apps.get_model('core', 'PremiumPurchase')
    PremiumPurchase.objects.filter(status='approved').update(is_approved=True)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_value_ranges'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='premium_until',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='premiumpurchase',
            name='duration_in_months',
            field=models.PositiveSmallIntegerField(default=1, validators=[
                django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(36),
            ]),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='premiumpurchase',
            name='status',
            field=models.CharField(choices=[('pending', 'Waiting for approval'), ('approved', 'Approved'),
                                            ('rejected', 'Rejected')], default='pending', max_length=10),
        ),
        migrations.AddField(
            model_name='premiumpurchase',
            name='rejection_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='premiumpurchase',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='premiumpurchase',
            name='starts_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='premiumpurchase',
            name='ends_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(fill_premium_time, restore_is_approved),
        migrations.RemoveField(
            model_name='premiumpurchase',
            name='is_approved',
        ),
    ]
