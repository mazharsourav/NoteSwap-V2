"""The redesigned home page and the site header around it."""
from django.urls import reverse

from core.models import Follow, Note, Rating, Review
from core.tests.test_security import SecurityTestCase, make_user, pdf_upload


class HomePageTests(SecurityTestCase):
    def test_signed_out_visitors_get_the_intro_and_sign_up_links(self):
        response = self.client_for(None).get(reverse('home'))
        self.assertContains(response, 'Notes from students who already aced the course.')
        self.assertContains(response, f'href="{reverse("account_signup")}"')
        self.assertContains(response, 'Apply to be a provider')
        self.assertContains(response, 'See Premium plans')
        self.assertNotContains(response, 'New from providers you follow')

    def test_signed_in_students_are_welcomed_by_name(self):
        response = self.client_for(self.basic).get(reverse('home'))
        self.assertContains(response, f'Welcome back, {self.basic.username}')

    def test_notes_from_followed_providers_get_their_own_row(self):
        client = self.client_for(self.basic)
        self.assertNotContains(client.get(reverse('home')), 'New from providers you follow')
        Follow.objects.create(follower=self.basic, provider=self.provider)
        response = client.get(reverse('home'))
        self.assertContains(response, 'New from providers you follow')
        self.assertEqual(list(response.context['following_notes']), [self.verified_note])

    def test_top_rated_puts_rated_notes_before_unrated_ones(self):
        rated = Note.objects.create(
            topic=self.topic, provider=self.other_provider, note_type='pdf', caption='c', year=1, semester=1,
            university='Test U', name='Rated note', is_verified=True, file=pdf_upload('rated.pdf'),
        )
        Rating.objects.create(note=rated, user=self.basic, score=3)
        notes = list(self.client_for(None).get(reverse('home')).context['top_rated_notes'])
        self.assertEqual(notes[0], rated)
        self.assertEqual(notes[0].rating_count, 1)
        self.assertNotIn(self.unverified_note, notes)

    def test_subjects_show_published_note_counts(self):
        subject = self.client_for(None).get(reverse('home')).context['subjects'][0]
        self.assertEqual(subject.note_count, 1)  # the pending note doesn't count

    def test_posting_a_review(self):
        client = self.client_for(self.basic)
        response = client.post(reverse('home'), {'comment': 'Great notes!'}, follow=True)
        self.assertRedirects(response, reverse('home'))
        self.assertContains(response, 'Thanks for your review!')
        self.assertContains(response, 'Great notes!')
        self.assertTrue(Review.objects.filter(user=self.basic, comment='Great notes!').exists())

    def test_an_empty_review_reopens_the_dialog_with_the_error(self):
        response = self.client_for(self.basic).post(reverse('home'), {'comment': ''})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="review-dialog" aria-labelledby="review-dialog-title" data-open')
        self.assertContains(response, 'class="field-error"')

    def test_signed_out_review_post_goes_to_sign_in(self):
        response = self.client_for(None).post(reverse('home'), {'comment': 'Hi'})
        self.assertRedirects(response, f"{reverse('account_login')}?next=/", fetch_redirect_response=False)
        self.assertFalse(Review.objects.exists())


class HeaderTests(SecurityTestCase):
    def header_for(self, user):
        return self.client_for(user).get(reverse('home')).content.decode()

    def test_links_depend_on_the_role(self):
        upload, manage = f'href="{reverse("upload_note")}"', f'href="{reverse("Manage")}"'
        premium, inbox = f'href="{reverse("premium_packages")}"', f'href="{reverse("provider_solved_requests")}"'

        basic = self.header_for(self.basic)
        self.assertIn(premium, basic)
        self.assertNotIn(upload, basic)
        self.assertNotIn(manage, basic)

        provider = self.header_for(self.provider)
        self.assertIn(upload, provider)
        self.assertIn(inbox, provider)
        self.assertNotIn(manage, provider)

        self.assertIn(manage, self.header_for(self.moderator))

    def test_premium_students_get_notesolve_and_the_badge(self):
        self.make_premium(self.basic)
        html = self.header_for(self.basic)
        self.assertIn(f'href="{reverse("notesolve_dashboard")}"', html)
        self.assertIn('premium-chip', html)

    def test_profile_picture_or_initials(self):
        nadia = make_user('nadia', first_name='Nadia', last_name='Islam')
        self.assertIn('>NI</span>', self.header_for(nadia))

    def test_current_section_is_highlighted(self):
        client = self.client_for(self.basic)
        self.assertEqual(client.get(reverse('subject_list')).context['nav_section'], 'notes')
        self.assertEqual(client.get(reverse('providers')).context['nav_section'], 'providers')
        self.assertEqual(client.get(reverse('home')).context['nav_section'], '')
