"""
Audit log (core.audit): one line per important action, saying who did what.
Logs L3: Premium orders, approvals, rejections, reminders, packages, and admin-site edits.
L4–L6 (moderation, accounts and security, content) are in test_audit_activity.py.
"""
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.admin.sites import site
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from core.models import CustomUser, PremiumPackage, PremiumPurchase
from core.notifications import send_premium_reminders

from .test_security import SecurityTestCase, make_user


class AuditTestCase(SecurityTestCase):
    def audit_lines(self, action, level='INFO', logger='core.audit', starting=''):
        """Run `action` and return the lines it wrote (message only), optionally only the
        ones starting with `starting`."""
        with self.assertLogs(logger, level) as logs:
            with self.captureOnCommitCallbacks(execute=True):
                action()
        return [record.getMessage() for record in logs.records if record.getMessage().startswith(starting)]

    def security_lines(self, action, starting=''):
        return self.audit_lines(action, logger='core.security', starting=starting)

    def assertNoAudit(self, action):
        with self.assertNoLogs('core.audit'):
            action()

    def post(self, user, name, *args, data=None):
        return lambda: self.client_for(user).post(reverse(name, args=args), data or {})


class PremiumOrderAuditTests(AuditTestCase):
    def test_order_placed(self):
        buyer = make_user('buyer')
        lines = self.audit_lines(lambda: self.client_for(buyer).post(
            reverse('purchase_premium_package', args=[self.package.id])))
        order = PremiumPurchase.objects.get(user=buyer)
        self.assertEqual(lines, [f'premium.ordered order={order.id} user=buyer package=Monthly amount=100.00 months=1'])

    def test_second_order_while_one_waits_is_refused(self):
        lines = self.audit_lines(lambda: self.client_for(self.basic).post(
            reverse('purchase_premium_package', args=[self.package.id])))
        self.assertEqual(lines, [f'premium.order_refused user=basic package={self.package.id} '
                                 f'why="order already waiting"'])

    def test_approved_with_reviewer_and_paid_period(self):
        lines = self.audit_lines(lambda: self.client_for(self.superuser).post(
            reverse('approve_purchase', args=[self.purchase.id])))
        self.purchase.refresh_from_db()
        day = timezone.localtime(self.purchase.ends_at).strftime('%Y-%m-%d')
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith(f'premium.approved order={self.purchase.id} user=basic by=root '
                                            f'amount=100.00 months=1 starts='))
        self.assertTrue(lines[0].endswith(f'ends={day}'))

    def test_reviewing_an_order_twice_is_a_warning(self):
        admin = self.client_for(self.superuser)
        admin.post(reverse('approve_purchase', args=[self.purchase.id]))
        with self.assertLogs('core.audit', 'WARNING') as logs:
            admin.post(reverse('reject_purchase', args=[self.purchase.id]), {'reason': 'late'})
        self.assertEqual(logs.output, [f'WARNING:core.audit:premium.already_handled order={self.purchase.id} '
                                       f'by=root tried=reject'])

    def test_rejected_with_the_reason_on_one_line(self):
        lines = self.audit_lines(lambda: self.client_for(self.superuser).post(
            reverse('reject_purchase', args=[self.purchase.id]), {'reason': 'TrxID not found.\nPay again.'}))
        self.assertEqual(lines, [f'premium.rejected order={self.purchase.id} user=basic by=root '
                                 f'reason="TrxID not found. Pay again."'])

    def test_rejecting_without_a_reason_logs_nothing(self):
        self.assertNoAudit(lambda: self.client_for(self.superuser).post(
            reverse('reject_purchase', args=[self.purchase.id]), {'reason': ' '}))

    def test_admin_bulk_approve_is_logged_the_same_way(self):
        lines = self.audit_lines(lambda: self.client_for(self.superuser).post(
            reverse('admin:core_premiumpurchase_changelist'),
            {'action': 'approve_purchases', '_selected_action': [self.purchase.id]}))
        self.assertTrue(lines[0].startswith(f'premium.approved order={self.purchase.id} user=basic by=root '))


class PremiumReminderAuditTests(AuditTestCase):
    def test_reminded_and_ended(self):
        ending = make_user('ending')
        self.make_premium(ending, days=3)
        self.make_premium(self.basic, days=-1)
        lines = self.audit_lines(send_premium_reminders)
        ending.refresh_from_db()
        self.basic.refresh_from_db()
        self.assertEqual(lines, [
            f"premium.reminded user=ending ends={timezone.localtime(ending.premium_until):%Y-%m-%d}",
            f"premium.ended user=basic ended={timezone.localtime(self.basic.premium_until):%Y-%m-%d}",
        ])
        self.assertNoAudit(send_premium_reminders)  # nothing new the second time


class PackageAuditTests(AuditTestCase):
    def post(self, name, *args, data=None):
        return lambda: self.client_for(self.superuser).post(reverse(name, args=args), data or {})

    def package_form(self, **changes):
        return {'name': 'Monthly', 'price': '100.00', 'duration_in_months': '1', 'description': 'd', **changes}

    def test_added(self):
        lines = self.audit_lines(self.post('add_premium_package', data=self.package_form(name='Yearly', price='900')))
        package = PremiumPackage.objects.get(name='Yearly')
        self.assertEqual(lines, [f'package.added package={package.id} name=Yearly price=900.00 months=1 by=root'])

    def test_edited_names_the_changed_fields(self):
        lines = self.audit_lines(self.post('edit_premium_package', self.package.id, data=self.package_form(price='120')))
        self.assertEqual(lines, [f'package.edited package={self.package.id} name=Monthly changed=price '
                                 f'price=120.00 months=1 by=root'])

    def test_saving_without_changes_logs_nothing(self):
        self.assertNoAudit(self.post('edit_premium_package', self.package.id, data=self.package_form()))

    def test_off_sale_and_back(self):
        self.assertEqual(self.audit_lines(self.post('toggle_premium_package', self.package.id)),
                         [f'package.off_sale package={self.package.id} name=Monthly by=root'])
        self.assertEqual(self.audit_lines(self.post('toggle_premium_package', self.package.id)),
                         [f'package.on_sale package={self.package.id} name=Monthly by=root'])

    def test_deleted_and_refused(self):
        spare = PremiumPackage.objects.create(name='Spare', description='d', price=50, duration_in_months=1)
        self.assertEqual(self.audit_lines(self.post('delete_premium_package', spare.id)),
                         [f'package.deleted package={spare.id} name=Spare by=root'])
        PremiumPurchase.objects.filter(id=self.purchase.id).update(package=self.package)
        self.assertEqual(self.audit_lines(self.post('delete_premium_package', self.package.id)),
                         [f'package.delete_refused package={self.package.id} name=Monthly why="has orders" by=root'])

    def test_students_cannot_trigger_package_logs(self):
        self.assertNoAudit(lambda: self.client_for(self.basic).post(
            reverse('toggle_premium_package', args=[self.package.id])))


class AdminSiteAuditTests(AuditTestCase):
    def admin_post(self, url, data):
        return lambda: self.client_for(self.superuser).post(url, data)

    def test_package_edited_in_the_admin(self):
        url = reverse('admin:core_premiumpackage_change', args=[self.package.id])
        data = {'name': 'Monthly', 'description': 'd', 'price': '150', 'duration_in_months': '1', 'is_active': 'on'}
        lines = self.audit_lines(self.admin_post(url, data))
        self.assertEqual(lines, [f'admin.changed model=premiumpackage id={self.package.id} fields=Price by=root'])

    def test_package_added_and_deleted_in_the_admin(self):
        data = {'name': 'Weekly', 'description': 'd', 'price': '30', 'duration_in_months': '1', 'is_active': 'on'}
        lines = self.audit_lines(self.admin_post(reverse('admin:core_premiumpackage_add'), data))
        weekly = PremiumPackage.objects.get(name='Weekly')
        self.assertEqual(lines, [f'admin.added model=premiumpackage id={weekly.id} by=root'])

        lines = self.audit_lines(self.admin_post(reverse('admin:core_premiumpackage_changelist'), {
            'action': 'delete_selected', '_selected_action': [weekly.id], 'post': 'yes'}))
        self.assertEqual(lines, [f'admin.deleted model=premiumpackage count=1 ids={weekly.id} by=root'])

    def test_premium_end_date_changed_by_hand_stands_out(self):
        request = RequestFactory().post('/')
        request.user = self.superuser
        user = CustomUser.objects.get(id=self.basic.id)
        user.premium_until = timezone.now() + timedelta(days=30)
        form = SimpleNamespace(changed_data=['premium_until'], initial={'premium_until': None})
        with self.assertLogs('core.audit', 'WARNING') as logs:
            site._registry[CustomUser].save_model(request, user, form, change=True)
        after = timezone.localtime(user.premium_until).strftime('%Y-%m-%d %H:%M')
        self.assertEqual(logs.records[0].getMessage(),
                         f'premium.changed_by_hand user=basic before=- after="{after}" by=root')
