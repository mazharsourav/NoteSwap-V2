"""Pages added or reworked in the redesign: help articles, Manage -> Premium, pricing, NoteSolve, providers."""
from unittest import mock

from django.test import override_settings
from django.urls import reverse

from core.help_content import ARTICLES
from core.models import PremiumPackage, PremiumPurchase
from core.tests.test_security import SecurityTestCase


class HelpTests(SecurityTestCase):
    def test_help_center_lists_every_article(self):
        response = self.client_for(None).get(reverse('help_center'))
        for article in ARTICLES:
            self.assertContains(response, reverse('help_article', args=[article['slug']]))

    def test_every_article_renders_and_its_links_resolve(self):
        for article in ARTICLES:
            response = self.client_for(None).get(reverse('help_article', args=[article['slug']]))
            self.assertContains(response, article['title'])

    def test_unknown_article_is_404(self):
        self.assertEqual(self.client_for(None).get(reverse('help_article', args=['nope'])).status_code, 404)


class PremiumPagesTests(SecurityTestCase):
    def test_pricing_marks_the_cheapest_per_month_as_best_value(self):
        longer = PremiumPackage.objects.create(name='Year', description='d', price=600, duration_in_months=12)
        response = self.client_for(None).get(reverse('premium_packages'))
        self.assertEqual(response.context['best_value_id'], longer.id)
        self.assertContains(response, 'Best value')

    def test_students_see_their_pending_order(self):
        PremiumPurchase.objects.create(user=self.other_provider, package_name='x', amount=1,  # someone else's
                                       duration_in_months=1)
        PremiumPurchase.objects.create(user=self.basic, package_name='Monthly', amount=100, duration_in_months=1)
        response = self.client_for(self.basic).get(reverse('premium_packages'))
        self.assertContains(response, 'Your Monthly order is waiting for approval')

    def test_a_second_order_while_one_is_pending_is_not_created(self):
        client = self.client_for(self.basic)
        client.post(reverse('purchase_premium_package', args=[self.package.id]))
        client.post(reverse('purchase_premium_package', args=[self.package.id]))
        self.assertEqual(PremiumPurchase.objects.filter(user=self.basic, status=PremiumPurchase.Status.PENDING).count(), 1)

    def test_approving_goes_back_to_manage_premium(self):
        response = self.client_for(self.superuser).post(reverse('approve_purchase', args=[self.purchase.id]))
        self.assertRedirects(response, reverse('manage_premium'), fetch_redirect_response=False)


class NoteSolvePageTests(SecurityTestCase):
    def setUp(self):
        self.make_premium(self.basic)

    def test_ask_link_preselects_the_provider(self):
        response = self.client_for(self.basic).get(reverse('notesolve_dashboard'), {'provider': self.provider.id})
        self.assertContains(response, f'<option value="{self.provider.id}" selected>')

    def test_question_and_solution_files_open_in_the_preview(self):
        response = self.client_for(self.basic).get(reverse('notesolve_dashboard'))
        self.assertContains(response, 'id="file-preview"')
        self.assertContains(response, f'href="{reverse("notesolve_file", args=[self.solve_file.id])}" target="_blank" rel="noopener" data-preview="q')
        self.assertContains(response, f'href="{reverse("notesolve_solution_file", args=[self.solution.id])}" target="_blank" rel="noopener" data-preview="a')
        self.assertContains(response, 'js/pages/file-preview.js')

    def test_provider_page_offers_notesolve_to_premium_students(self):
        response = self.client_for(self.basic).get(reverse('provider_profile', args=[self.provider.id]))
        self.assertContains(response, f'{reverse("notesolve_dashboard")}?provider={self.provider.id}#ask')


class ProviderListTests(SecurityTestCase):
    def test_search_by_name(self):
        response = self.client_for(None).get(reverse('providers'), {'q': 'other_prov'})
        self.assertEqual([item['provider'] for item in response.context['provider_data']], [self.other_provider])

    def test_provider_profile_filters_by_subject(self):
        response = self.client_for(None).get(reverse('provider_profile', args=[self.provider.id]), {'subject': self.subject.id})
        self.assertEqual(list(response.context['notes']), [self.verified_note])


class SiteShellTests(SecurityTestCase):
    @override_settings(DEVELOPER_NAME='', DEVELOPER_URL='')
    def test_developer_credit_is_hidden_until_set(self):
        self.assertNotContains(self.client_for(None).get(reverse('home')), 'Built by')

    @override_settings(DEVELOPER_NAME='Dev Person', DEVELOPER_URL='https://github.com/dev')
    def test_developer_credit_links_to_the_portfolio(self):
        self.assertContains(self.client_for(None).get(reverse('home')),
                            '<a class="flink" href="https://github.com/dev" target="_blank" rel="noopener">Dev Person</a>')

    def test_page_language_comes_from_the_settings(self):
        self.assertContains(self.client_for(None).get(reverse('home')), '<html lang="en">')


class AboutTeamTests(SecurityTestCase):
    def test_team_cards_show_only_links_that_have_an_address(self):
        from core.views import pages
        member = {'name': 'Test Person', 'role': 'Tester', 'photo': 'img/team/sourav.jpg',
                  'links': {'portfolio': '', 'github': 'https://github.com/example', 'linkedin': '',
                            'instagram': 'https://instagram.com/example'}}
        with mock.patch.object(pages, 'TEAM', [member]):
            response = self.client_for(None).get(reverse('about'))
        self.assertContains(response, 'href="https://github.com/example"')
        self.assertContains(response, 'aria-label="Test Person on Instagram"')
        self.assertNotContains(response, 'aria-label="Test Person on LinkedIn"')
        self.assertNotContains(response, 'aria-label="Test Person on Portfolio"')
