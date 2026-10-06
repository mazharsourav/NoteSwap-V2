"""
Premium that runs out: approval adds paid months (stacking on renewals), rejection keeps
the order with a reason, one premium check everywhere, and what happens after it ends.
"""
from datetime import datetime, timezone as dt_timezone

from django.urls import reverse
from django.utils import timezone

from core.models import NoteSolveRequest, PremiumPurchase, add_months

from .test_security import SecurityTestCase, make_user


def messages_of(response):
    return [str(message) for message in response.context['messages']]


class AddMonthsTests(SecurityTestCase):
    def test_whole_calendar_months_clamped_to_the_month_end(self):
        def utc(*args):
            return datetime(*args, tzinfo=dt_timezone.utc)
        self.assertEqual(add_months(utc(2026, 3, 10, 6), 1).date().isoformat(), '2026-04-10')
        self.assertEqual(add_months(utc(2026, 1, 31, 6), 1).date().isoformat(), '2026-02-28')
        self.assertEqual(add_months(utc(2028, 1, 31, 6), 1).date().isoformat(), '2028-02-29')
        self.assertEqual(add_months(utc(2026, 11, 30, 6), 3).date().isoformat(), '2027-02-28')
        self.assertEqual(add_months(utc(2026, 5, 15, 6), 12).date().isoformat(), '2027-05-15')


class ApproveTests(SecurityTestCase):
    def approve(self, purchase):
        return self.client_for(self.superuser).post(reverse('approve_purchase', args=[purchase.id]), follow=True)

    def order(self, months=1):
        return PremiumPurchase.objects.create(user=self.basic, package_name='P', amount=1, duration_in_months=months)

    def test_approving_starts_premium_now_for_the_package_length(self):
        before = timezone.now()
        response = self.approve(self.purchase)
        self.purchase.refresh_from_db()
        self.basic.refresh_from_db()
        self.assertEqual(self.purchase.status, PremiumPurchase.Status.APPROVED)
        self.assertGreaterEqual(self.purchase.starts_at, before)
        self.assertEqual(self.purchase.ends_at, add_months(self.purchase.starts_at, 1))
        self.assertEqual(self.basic.premium_until, self.purchase.ends_at)
        self.assertTrue(self.basic.is_premium)
        self.assertIsNotNone(self.purchase.reviewed_at)
        self.assertIn('has Premium until', messages_of(response)[0])

    def test_a_renewal_is_added_after_the_current_premium_ends(self):
        self.make_premium(self.basic, days=10)
        current_end = type(self.basic).objects.get(id=self.basic.id).premium_until
        self.approve(self.purchase)
        self.purchase.refresh_from_db()
        self.basic.refresh_from_db()
        self.assertEqual(self.purchase.starts_at, current_end)
        self.assertEqual(self.basic.premium_until, add_months(current_end, 1))

    def test_after_premium_ended_a_new_order_starts_from_today_not_the_old_end(self):
        self.make_premium(self.basic, days=-40)
        before = timezone.now()
        self.approve(self.purchase)
        self.purchase.refresh_from_db()
        self.assertGreaterEqual(self.purchase.starts_at, before)

    def test_approving_twice_adds_the_months_once(self):
        self.approve(self.purchase)
        self.basic.refresh_from_db()
        first_end = self.basic.premium_until
        response = self.approve(self.purchase)
        self.basic.refresh_from_db()
        self.assertEqual(self.basic.premium_until, first_end)
        self.assertIn('already approved or rejected', messages_of(response)[0])

    def test_the_length_comes_from_the_order_not_the_package_now(self):
        self.package.duration_in_months = 12
        self.package.save()
        self.approve(self.purchase)  # ordered as 1 month
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.ends_at, add_months(self.purchase.starts_at, 1))

    def test_ordering_copies_the_package_length(self):
        self.purchase.delete()
        self.client_for(self.basic).post(reverse('purchase_premium_package', args=[self.package.id]))
        order = PremiumPurchase.objects.get(user=self.basic)
        self.assertEqual((order.duration_in_months, order.status), (1, PremiumPurchase.Status.PENDING))

    def test_admin_action_adds_months_and_skips_reviewed_orders(self):
        rejected = self.order(months=6)
        rejected.reject('no payment')
        self.client_for(self.superuser).post(reverse('admin:core_premiumpurchase_changelist'), {
            'action': 'approve_purchases', '_selected_action': [self.purchase.id, rejected.id],
        })
        self.basic.refresh_from_db()
        rejected.refresh_from_db()
        self.assertTrue(self.basic.is_premium)
        self.assertEqual(rejected.status, PremiumPurchase.Status.REJECTED)
        self.assertEqual(self.basic.premium_until, PremiumPurchase.objects.get(id=self.purchase.id).ends_at)


class RejectTests(SecurityTestCase):
    def reject(self, reason):
        return self.client_for(self.superuser).post(
            reverse('reject_purchase', args=[self.purchase.id]), {'reason': reason}, follow=True)

    def test_rejecting_needs_a_reason(self):
        response = self.reject('  ')
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, PremiumPurchase.Status.PENDING)
        self.assertIn('Please give a reason', messages_of(response)[0])

    def test_rejected_orders_are_kept_with_the_reason(self):
        self.reject('We could not find this payment.')
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, PremiumPurchase.Status.REJECTED)
        self.assertEqual(self.purchase.rejection_reason, 'We could not find this payment.')
        self.assertIsNotNone(self.purchase.reviewed_at)
        self.basic.refresh_from_db()
        self.assertFalse(self.basic.is_premium)

    def test_the_student_sees_the_reason_and_can_order_again(self):
        self.reject('We could not find this payment.')
        student = self.client_for(self.basic)
        for url in (reverse('premium_packages'), reverse('checkout_pending')):
            self.assertContains(student.get(url), 'We could not find this payment.')
        student.post(reverse('purchase_premium_package', args=[self.package.id]))
        self.assertEqual(PremiumPurchase.objects.filter(user=self.basic, status=PremiumPurchase.Status.PENDING).count(), 1)

    def test_an_approved_order_cannot_be_rejected(self):
        self.purchase.approve()
        self.reject('changed my mind')
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, PremiumPurchase.Status.APPROVED)

    def test_manage_page_lists_reviewed_orders(self):
        self.reject('No payment found')
        response = self.client_for(self.superuser).get(reverse('manage_premium'))
        self.assertContains(response, 'Recently reviewed')
        self.assertContains(response, 'No payment found')


class PremiumEndsTests(SecurityTestCase):
    def setUp(self):
        self.make_premium(self.basic, days=-1)  # Premium ended yesterday; basic has a solved request

    def test_ended_premium_is_not_premium(self):
        self.assertFalse(self.basic.is_premium)
        html = self.client_for(self.basic).get(reverse('home')).content.decode()
        self.assertIn(f'href="{reverse("premium_packages")}"', html)
        self.assertNotIn(f'href="{reverse("notesolve_dashboard")}"', html)

    def test_past_answers_stay_readable_and_rateable(self):
        client = self.client_for(self.basic)
        response = client.get(reverse('notesolve_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your Premium has ended')
        self.assertContains(response, 'answer')  # the solution text
        self.assertNotContains(response, 'Send question')
        client.post(reverse('notesolve_dashboard'), {'rate_solution_id': self.solution.id, 'rating': '4'})
        self.solution.refresh_from_db()
        self.assertEqual(self.solution.rating, 4)

    def test_no_new_questions_after_premium_ends(self):
        client = self.client_for(self.basic)
        before = NoteSolveRequest.objects.count()
        fields = {'university': 'U', 'department': 'CSE', 'semester': '1', 'year': '1', 'subject': 's',
                  'topic': 't', 'problem_description': 'p', 'provider_id': self.provider.id}
        client.post(reverse('notesolve_dashboard'), fields)
        client.post(reverse('request_to_provider', args=[self.provider.id]), fields)
        self.assertEqual(NoteSolveRequest.objects.count(), before)

    def test_no_resending_after_premium_ends(self):
        self.solve_request.status = NoteSolveRequest.Status.REJECTED
        self.solve_request.save()
        self.client_for(self.basic).post(
            reverse('resend_solve_request', args=[self.solve_request.id]), {'provider_id': self.other_provider.id})
        self.solve_request.refresh_from_db()
        self.assertEqual(self.solve_request.status, NoteSolveRequest.Status.REJECTED)

    def test_a_student_who_never_had_premium_is_sent_home(self):
        newcomer = make_user('newcomer')
        response = self.client_for(newcomer).get(reverse('notesolve_dashboard'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_pricing_page_shows_when_premium_ended_and_offers_buying_again(self):
        response = self.client_for(self.basic).get(reverse('premium_packages'))
        self.assertContains(response, 'Your Premium ended on')
        self.assertContains(response, 'Buy Now')
        self.assertNotContains(response, 'Extend with')


class ActivePremiumPagesTests(SecurityTestCase):
    def test_pricing_page_shows_the_end_date_and_extend_buttons(self):
        self.make_premium(self.basic, days=20)
        response = self.client_for(self.basic).get(reverse('premium_packages'))
        self.assertContains(response, 'You’re Premium until')
        self.assertContains(response, f'Extend with {self.package.name}')
        confirm = self.client_for(self.basic).get(reverse('purchase_premium_package', args=[self.package.id]))
        self.assertContains(confirm, 'Its months start when your current Premium ends')
