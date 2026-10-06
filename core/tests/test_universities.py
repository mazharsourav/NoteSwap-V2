"""The university list, the picker field, and how stored universities are shown."""
from django import forms
from django.template import Context, Template
from django.test import SimpleTestCase

from core import universities
from core.forms import UniversityField


class PickerForm(forms.Form):
    university = UniversityField()


class UniversityListTests(SimpleTestCase):
    def test_codes_are_unique(self):
        codes = [code for code, _ in universities.PUBLIC + universities.PRIVATE]
        self.assertEqual(len(codes), len(set(codes)))

    def test_common_spellings_become_the_code(self):
        for written in ('UAP', 'uap', ' Uap ', 'University of Asia Pacific', 'university of asia-pacific',
                        'University of Asia Pacific (UAP)'):
            self.assertEqual(universities.normalize(written), 'UAP', written)
        self.assertEqual(universities.normalize('Brac University'), 'BRACU')
        self.assertEqual(universities.normalize('Dhaka University'), 'DU')

    def test_unknown_names_are_kept_tidied(self):
        self.assertEqual(universities.normalize('  Sylhet   Engineering College '), 'Sylhet Engineering College')
        self.assertEqual(universities.normalize(''), '')

    def test_display_filters(self):
        html = Template('{% load ui %}{{ a|uni_short }}|{{ a|uni_full }}|{{ b|uni_short }}|{{ b|uni_full }}').render(
            Context({'a': 'UAP', 'b': 'My College'}))
        self.assertEqual(html, 'UAP|University of Asia Pacific|My College|My College')


class UniversityFieldTests(SimpleTestCase):
    def clean(self, data):
        form = PickerForm(data)
        return form.cleaned_data.get('university') if form.is_valid() else form.errors['university'][0]

    def test_picking_from_the_list_stores_the_code(self):
        self.assertEqual(self.clean({'university_choice': 'NSU'}), 'NSU')

    def test_other_stores_the_typed_name_or_matches_the_list(self):
        self.assertEqual(self.clean({'university_choice': '__other__', 'university_other': 'My College'}), 'My College')
        self.assertEqual(self.clean({'university_choice': '__other__', 'university_other': 'north south university'}), 'NSU')

    def test_missing_or_unknown_choices_are_explained(self):
        self.assertEqual(self.clean({}), 'Choose your university.')
        self.assertEqual(self.clean({'university_choice': '__other__'}), 'Type the name of your university.')
        self.assertEqual(self.clean({'university_choice': 'NOPE'}), 'Choose a university from the list.')

    def test_a_plain_value_is_matched_too(self):
        self.assertEqual(self.clean({'university': 'uap'}), 'UAP')
        self.assertEqual(self.clean({'university': 'Test U'}), 'Test U')

    def test_the_widget_shows_a_stored_other_name(self):
        html = str(PickerForm(initial={'university': 'My College'})['university'])
        self.assertIn('value="__other__" selected', html)
        self.assertIn('value="My College"', html)
        self.assertNotIn('required', html.split('university_other')[1].split('>')[0])  # the text box is optional
