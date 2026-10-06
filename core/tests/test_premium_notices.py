"""
Premium notices and package rules: bell notifications for every Premium event, email only
for the important ones, the daily reminder job, who reviewed an order, and packages that
can be taken off sale but not deleted once they have orders.
"""
from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from core.models import CustomUser, Notification, PremiumPackage, PremiumPurchase
from core.notifications import send_premium_reminders

from .test_security import SecurityTestCase, make_user

Kind = Notification.Kind


class PremiumNoticeTestCase(SecurityTestCase):
    def setUp(self):
        CustomUser.objects.filter(id=self.basic.id).update(email='student@example.com')
        CustomUser.objects.filter(id=self.superuser.id).update(email='admin@example.com')
        self.basic.refresh_from_db()
        self.superuser.refresh_from_db()

    def notices(self, user, kind):
        return Notification.objects.filter(recipient=user, kind=kind)


class OrderNoticeTests(PremiumNoticeTestCase):
    def test_a_new_order_tells_every_admin_by_bell_and_email(self):
        second_admin = make_user('root2', is_superuser=True, is_staff=True, email='admin2@example.com')
        self.purchase.delete()
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.basic).post(reverse('purchase_premium_package', args=[self.package.id]))
        order = PremiumPurchase.objects.get(user=self.basic)
        self.assertEqual(order.package, self.package)
        for admin in (self.superuser, second_admin):
            self.assertEqual(self.notices(admin, Kind.PREMIUM_ORDER).get().purchase, order)
        self.assertFalse(self.notices(self.moderator, Kind.PREMIUM_ORDER).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(sorted(mail.outbox[0].to), ['admin2@example.com', 'admin@example.com'])
        self.assertIn('Monthly', mail.outbox[0].body)
        self.assertIn(reverse('manage_premium'), mail.outbox[0].body)

    def test_approving_tells_the_student_and_records_the_reviewer(self):
        Notification.objects.create(recipient=self.superuser, kind=Kind.PREMIUM_ORDER, purchase=self.purchase)
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.superuser).post(reverse('approve_purchase', args=[self.purchase.id]))
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.reviewed_by, self.superuser)
        notice = self.notices(self.basic, Kind.PREMIUM_APPROVED).get()
        self.assertIn('Premium runs until', notice.text)
        self.assertEqual(notice.url, reverse('premium_packages'))
        self.assertTrue(self.notices(self.superuser, Kind.PREMIUM_ORDER).get().is_read)  # handled
        self.assertEqual([m.to for m in mail.outbox], [['student@example.com']])
        self.assertIn('Premium is active until', mail.outbox[0].body)

    def test_rejecting_tells_the_student_the_reason(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.superuser).post(reverse('reject_purchase', args=[self.purchase.id]),
                                                 {'reason': 'No payment with that number.'})
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.reviewed_by, self.superuser)
        self.assertTrue(self.notices(self.basic, Kind.PREMIUM_REJECTED).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('No payment with that number.', mail.outbox[0].body)

    def test_reviewing_twice_sends_nothing_more(self):
        with self.captureOnCommitCallbacks(execute=True):
            for _ in range(2):
                self.client_for(self.superuser).post(reverse('approve_purchase', args=[self.purchase.id]))
        self.assertEqual(self.notices(self.basic, Kind.PREMIUM_APPROVED).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_students_without_an_email_still_get_the_bell(self):
        CustomUser.objects.filter(id=self.basic.id).update(email='')
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.superuser).post(reverse('approve_purchase', args=[self.purchase.id]))
        self.assertTrue(self.notices(self.basic, Kind.PREMIUM_APPROVED).exists())
        self.assertEqual(mail.outbox, [])

    def test_admin_bulk_approve_also_tells_the_student(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.superuser).post(reverse('admin:core_premiumpurchase_changelist'), {
                'action': 'approve_purchases', '_selected_action': [self.purchase.id],
            })
        self.assertTrue(self.notices(self.basic, Kind.PREMIUM_APPROVED).exists())
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.reviewed_by, self.superuser)

    def test_notification_pages_show_premium_notices(self):
        self.purchase.approve(self.superuser)
        Notification.objects.create(recipient=self.basic, kind=Kind.PREMIUM_APPROVED, purchase=self.purchase)
        Notification.objects.create(recipient=self.basic, kind=Kind.PREMIUM_ENDING)
        Notification.objects.create(recipient=self.superuser, kind=Kind.PREMIUM_ORDER, actor=self.basic,
                                    purchase=self.purchase)
        page = self.client_for(self.basic).get(reverse('notifications'))
        self.assertContains(page, 'Your Monthly order was approved.')
        self.assertContains(page, 'Your Premium ends in less than a week.')
        self.assertEqual(self.client_for(self.basic).get(reverse('profile')).status_code, 200)
        self.assertContains(self.client_for(self.superuser).get(reverse('notifications')),
                            'ordered Monthly (৳ 100). Check the payment.')

    def test_manage_page_shows_who_reviewed(self):
        self.purchase.approve(self.superuser)
        self.assertContains(self.client_for(self.superuser).get(reverse('manage_premium')), 'by root')


class ReminderTests(PremiumNoticeTestCase):
    def run_job(self, now=None):
        with self.captureOnCommitCallbacks(execute=True):
            return send_premium_reminders(now)

    def test_a_week_before_the_end_bell_and_email_once(self):
        self.make_premium(self.basic, days=3)
        self.assertEqual(self.run_job(), (1, 0))
        self.assertEqual(self.run_job(), (0, 0))  # running again doesn't repeat it
        self.assertEqual(self.notices(self.basic, Kind.PREMIUM_ENDING).count(), 1)
        self.assertEqual([m.to for m in mail.outbox], [['student@example.com']])
        self.assertIn('Your Premium ends on', mail.outbox[0].body)

    def test_not_reminded_while_more_than_a_week_is_left(self):
        self.make_premium(self.basic, days=20)
        self.assertEqual(self.run_job(), (0, 0))

    def test_a_renewal_gets_its_own_reminder(self):
        self.make_premium(self.basic, days=3)
        self.run_job()
        self.make_premium(self.basic, days=33)  # renewed: ends a month later
        later = timezone.now() + timedelta(days=30)
        self.assertEqual(self.run_job(now=later), (1, 0))

    def test_when_it_ends_bell_only(self):
        self.make_premium(self.basic, days=-1)
        self.assertEqual(self.run_job(), (0, 1))
        self.assertEqual(self.run_job(), (0, 0))
        notice = self.notices(self.basic, Kind.PREMIUM_ENDED).get()
        self.assertEqual(notice.url, reverse('notesolve_dashboard'))
        self.assertEqual(mail.outbox, [])

    def test_long_ago_endings_are_not_announced(self):
        self.make_premium(self.basic, days=-30)
        self.assertEqual(self.run_job(), (0, 0))

    def test_management_command(self):
        self.make_premium(self.basic, days=2)
        out = StringIO()
        call_command('send_premium_reminders', stdout=out)
        self.assertIn('1 ending soon, 0 ended', out.getvalue())


class PackageRulesTests(PremiumNoticeTestCase):
    def test_off_sale_packages_are_hidden_and_cannot_be_bought(self):
        self.client_for(self.superuser).post(reverse('toggle_premium_package', args=[self.package.id]))
        self.package.refresh_from_db()
        self.assertFalse(self.package.is_active)
        self.assertNotContains(self.client_for(None).get(reverse('premium_packages')), 'id="package-')
        student = self.client_for(self.basic)
        self.assertEqual(student.get(reverse('purchase_premium_package', args=[self.package.id])).status_code, 404)
        self.client_for(self.superuser).post(reverse('toggle_premium_package', args=[self.package.id]))
        self.package.refresh_from_db()
        self.assertTrue(self.package.is_active)

    def test_only_superusers_can_toggle_and_only_by_post(self):
        url = reverse('toggle_premium_package', args=[self.package.id])
        self.assertEqual(self.client_for(self.moderator).post(url).status_code, 403)
        self.assertEqual(self.client_for(self.superuser).get(url).status_code, 405)
        self.package.refresh_from_db()
        self.assertTrue(self.package.is_active)

    def test_a_package_with_orders_cannot_be_deleted(self):
        PremiumPurchase.objects.filter(id=self.purchase.id).update(package=self.package)
        response = self.client_for(self.superuser).post(
            reverse('delete_premium_package', args=[self.package.id]), follow=True)
        self.assertTrue(PremiumPackage.objects.filter(id=self.package.id).exists())
        self.assertContains(response, 'Take it off sale instead.')
        self.assertContains(response, 'can’t be deleted, only taken off sale')

    def test_a_package_without_orders_can_be_deleted(self):
        spare = PremiumPackage.objects.create(name='Spare', description='d', price=50, duration_in_months=1)
        self.client_for(self.superuser).post(reverse('delete_premium_package', args=[spare.id]))
        self.assertFalse(PremiumPackage.objects.filter(id=spare.id).exists())
