"""Browsing, searching and moderating notes on the redesigned pages."""
import io
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from core.models import Note, NoteFile, Notification, Rating, Subject
from core.tests.test_security import SecurityTestCase, pdf_upload


def image_upload(name, exif_rotated=False):
    """A real 40x30 JPEG; with exif_rotated it carries the "rotate 90°" flag phone cameras use."""
    buffer = io.BytesIO()
    exif = Image.Exif()
    if exif_rotated:
        exif[0x0112] = 6
    Image.new('RGB', (40, 30), 'white').save(buffer, 'JPEG', exif=exif)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')


class BrowseTests(SecurityTestCase):
    def test_subject_list_counts_published_notes(self):
        response = self.client_for(None).get(reverse('subject_list'))
        subject = response.context['page'][0]
        self.assertEqual(subject.note_count, 1)

    def test_course_filters_use_the_notes_university_and_clear_link(self):
        chemistry = Subject.objects.create(name='Chemistry')
        Note.objects.create(subject=chemistry, provider=self.provider, note_type='pdf', caption='c', year=2, semester=1,
                            university='NSU', name='Acids', is_verified=True, file=pdf_upload('acids.pdf'))
        response = self.client_for(None).get(reverse('subject_list'), {'university': 'NSU'})
        self.assertEqual([s.name for s in response.context['page']], ['Chemistry'])
        self.assertEqual(response.context['page'][0].universities, ['NSU'])
        self.assertIn(('NSU', 'North South University (NSU)'), response.context['universities'])
        self.assertContains(response, 'Clear filters')

    def test_course_page_filters_by_university_and_finds_course_codes(self):
        Note.objects.create(subject=self.subject, provider=self.provider, note_type='pdf', caption='c', year=2,
                            semester=4, university='NSU', course_code='PHY 201', name='Lenses', is_verified=True,
                            file=pdf_upload('lenses.pdf'))
        url = reverse('subject_detail', args=[self.subject.id])
        self.assertEqual([n.name for n in self.client_for(None).get(url, {'university': 'NSU'}).context['page']], ['Lenses'])
        self.assertContains(self.client_for(None).get(url), 'NSU · PHY 201 · Year 2, Sem 4')
        found = self.client_for(None).get(reverse('search'), {'q': 'phy 201'}).context['page']
        self.assertEqual([n.name for n in found], ['Lenses'])

    def test_subject_list_is_paginated(self):
        for i in range(13):
            Subject.objects.create(name=f'Subject {i:02}', year=1, semester=1, university='Test U')
        response = self.client_for(None).get(reverse('subject_list'), {'page': 2})
        self.assertEqual(len(response.context['page']), 2)  # 14 subjects, 12 per page
        self.assertContains(response, 'aria-current="page">2<')

    def test_subject_page_lists_only_published_notes_best_first(self):
        better = Note.objects.create(
            subject=self.subject, provider=self.other_provider, note_type='pdf', caption='c', year=1, semester=1,
            university='Test U', name='Better note', is_verified=True, file=pdf_upload('better.pdf'),
        )
        Rating.objects.create(note=better, user=self.basic, score=5)
        notes = list(self.client_for(None).get(reverse('subject_detail', args=[self.subject.id])).context['page'])
        self.assertEqual(notes, [better, self.verified_note])

    def test_subject_page_filters_by_provider_name_and_sorts_newest(self):
        url = reverse('subject_detail', args=[self.subject.id])
        self.assertContains(self.client_for(None).get(url, {'q': 'nobody'}), 'Nothing matches')
        newer = Note.objects.create(
            subject=self.subject, provider=self.provider, note_type='pdf', caption='c', year=1, semester=1,
            university='Test U', name='Newer note', is_verified=True, file=pdf_upload('newer.pdf'),
        )
        self.assertEqual(list(self.client_for(None).get(url, {'sort': 'newest'}).context['page'])[0], newer)

    def test_old_topic_links_go_to_the_subject(self):
        target = reverse('subject_detail', args=[self.subject.id])
        for old in (f'/subject/{self.subject.id}/topics/', f'/topic/{self.topic.id}/notes/'):
            response = self.client_for(None).get(old)
            self.assertRedirects(response, target, status_code=301)

    def test_a_note_belongs_to_its_topics_subject_when_saved_the_old_way(self):
        note = Note.objects.create(topic=self.topic, provider=self.provider, note_type='pdf', caption='c', year=1,
                                   semester=1, university='Test U', name='Old way', file=pdf_upload('old.pdf'))
        self.assertEqual(note.subject, self.subject)


class SemesterFilterTests(SecurityTestCase):
    """The course list and course page filter by university and a "2-1" semester chip."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.chemistry = Subject.objects.create(name='Chemistry')
        for name, university, year, semester in [('Acids', 'NSU', 2, 1), ('Bases', 'UAP', 2, 1), ('Salts', 'UAP', 3, 2),
                                                 ('Old style', 'UAP', 1, 6)]:
            Note.objects.create(subject=cls.chemistry, provider=cls.provider, note_type='pdf', caption='c', year=year,
                                semester=semester, university=university, name=name, is_verified=True,
                                file=pdf_upload(f'{name}.pdf'))

    def courses(self, **params):
        response = self.client_for(None).get(reverse('subject_list'), params)
        return response, {s.name: s.note_count for s in response.context['page'] if s.note_count}

    def test_university_and_semester_combine(self):
        self.assertEqual(self.courses(term='2-1')[1], {'Chemistry': 2})  # every university's 2-1
        self.assertEqual(self.courses(university='UAP')[1], {'Chemistry': 3})  # all of UAP's semesters
        self.assertEqual(self.courses(university='UAP', term='2-1')[1], {'Chemistry': 1})
        self.assertEqual(self.courses(university='NSU', term='3-2')[1], {})
        self.assertEqual(self.courses(term='nonsense')[1], {'Chemistry': 4, 'Physics': 1})  # ignored

    def test_courses_with_most_notes_come_first(self):
        self.assertEqual(list(self.courses()[1]), ['Chemistry', 'Physics'])

    def test_chips_grey_out_semesters_without_notes(self):
        response, _ = self.courses(university='NSU')
        chips = {chip['value']: chip['count'] for chip in response.context['term_chips']}
        self.assertEqual(list(chips), ['1-1', '1-2', '2-1', '2-2', '3-1', '3-2', '4-1', '4-2'])
        self.assertEqual((chips['2-1'], chips['3-2']), (1, 0))
        self.assertContains(response, 'aria-disabled="true" title="No notes for 3-2 yet"')
        self.assertContains(response, 'href="?university=NSU&amp;term=2-1"')

    def test_extra_chips_appear_only_when_a_note_needs_them(self):
        Note.objects.filter(name='Salts').update(year=5, semester=3)
        values = [chip['value'] for chip in self.courses()[0].context['term_chips']]
        self.assertEqual(values[-1], '5-3')
        self.assertNotIn('1-3', values)

    def test_the_filter_carries_into_the_course_and_shows_there(self):
        response, _ = self.courses(university='UAP', term='2-1')
        url = reverse('subject_detail', args=[self.chemistry.id])
        self.assertContains(response, f'href="{url}?university=UAP&amp;term=2-1"')
        page = self.client_for(None).get(url, {'university': 'UAP', 'term': '2-1'})
        self.assertEqual([n.name for n in page.context['page']], ['Bases'])
        self.assertContains(page, 'Showing <strong>UAP · 2-1</strong> notes')
        self.assertContains(page, 'UAP · 2-1</span>')  # the note row
        self.assertContains(self.client_for(None).get(url), 'UAP · Year 1, Sem 6')  # an older note that doesn't fit

    def test_empty_result_offers_all_semesters(self):
        response, _ = self.courses(university='NSU', term='4-2')
        self.assertContains(response, 'No NSU notes for 4-2 yet')
        self.assertContains(response, 'Show all semesters')

    def test_university_list_is_only_universities_with_notes(self):
        response, _ = self.courses()
        self.assertEqual([code for code, _ in response.context['universities']], ['NSU', 'Test U', 'UAP'])
        self.assertNotContains(response, '<optgroup')

    def test_older_year_and_semester_links_still_filter(self):
        self.assertEqual(self.courses(year='3', semester='2')[1], {'Chemistry': 1})


class SearchTests(SecurityTestCase):
    def test_finds_subjects_notes_and_providers(self):
        response = self.client_for(None).get(reverse('search'), {'q': 'physi'})
        self.assertEqual(list(response.context['page']), [self.verified_note])  # matched through its subject
        self.assertNotIn('topics', response.context)
        self.assertEqual(list(self.client_for(None).get(reverse('search'), {'q': 'phys'}).context['subjects']),
                         [self.subject])
        self.assertEqual(list(self.client_for(None).get(reverse('search'), {'q': 'other_prov'}).context['providers']),
                         [self.other_provider])

    def test_pending_notes_are_never_found(self):
        response = self.client_for(None).get(reverse('search'), {'q': 'Pending'})
        self.assertNotIn(self.unverified_note, list(response.context['page']))

    def test_empty_query_shows_the_prompt(self):
        self.assertContains(self.client_for(None).get(reverse('search')), 'What are you looking for?')


class NotePageTests(SecurityTestCase):
    def test_owner_sees_edit_tools_and_review_notice(self):
        response = self.client_for(self.provider).get(reverse('note_detail', args=[self.unverified_note.id]))
        self.assertContains(response, 'Waiting for review.')
        self.assertContains(response, reverse('edit_note', args=[self.unverified_note.id]))

    def test_readers_get_viewer_download_and_follow(self):
        response = self.client_for(self.basic).get(reverse('note_detail', args=[self.verified_note.id]))
        self.assertContains(response, 'id="reader-files"')
        self.assertContains(response, 'vendor/pdfjs/pdf.worker.min.mjs')
        self.assertContains(response, 'download>')
        self.assertContains(response, reverse('follow_provider', args=[self.provider.id]))
        self.assertNotContains(response, reverse('edit_note', args=[self.verified_note.id]))

    def test_upload_page_preselects_the_subject_and_its_details(self):
        response = self.client_for(self.provider).get(reverse('upload_note'), {'subject': self.subject.id, 'term': '2-1'})
        self.assertContains(response, f'<option value="{self.subject.id}" selected>')
        self.assertEqual(response.context['form'].initial['university'], 'Test U')  # the provider's own university
        self.assertContains(response, '<option value="2-1" selected>')
        self.assertNotContains(response, 'Topic')

    def test_semester_is_one_choice_saved_as_year_and_semester(self):
        response = self.client_for(self.provider).post(reverse('upload_note'), {
            'name': 'Two three', 'caption': 'c', 'term': '2-3', 'university': 'Test U', 'subject': self.subject.id,
            'file': pdf_upload('two.pdf')})
        self.assertEqual(response.status_code, 302)
        note = Note.objects.get(name='Two three')
        self.assertEqual((note.year, note.semester, note.term), (2, 3, '2-3'))
        edit = self.client_for(self.provider).get(reverse('edit_note', args=[note.id]))
        self.assertContains(edit, '<option value="2-3" selected>')

    def test_an_older_note_picks_its_semester_again_when_edited(self):
        Note.objects.filter(id=self.unverified_note.id).update(year=1, semester=6)
        edit = self.client_for(self.provider).get(reverse('edit_note', args=[self.unverified_note.id]))
        self.assertContains(edit, '<option value="" selected>Choose the semester</option>')

    def test_add_subject_returns_to_the_upload_form_with_it_picked(self):
        response = self.client_for(self.provider).post(
            reverse('add_subject'), {'name': 'Chemistry', 'year': 1, 'semester': 2, 'university': 'Test U', 'next': '/upload/'},
        )
        subject = Subject.objects.get(name='Chemistry')
        self.assertRedirects(response, f'/upload/?subject={subject.id}', fetch_redirect_response=False)
        page = self.client_for(self.provider).get(response['Location'])
        self.assertContains(page, f'<option value="{subject.id}" selected>')

    def test_upload_page_has_the_add_subject_popup(self):
        response = self.client_for(self.provider).get(reverse('upload_note'))
        self.assertContains(response, 'id="add-subject-dialog"')
        self.assertContains(response, 'id="new-subject-name"')  # own ids, no clash with the note form
        self.assertNotContains(response, 'add-topic-dialog')

    def test_popup_saves_with_json(self):
        client = self.client_for(self.provider)
        response = client.post(reverse('add_subject'), {'name': 'Chemistry'}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 201)
        subject = Subject.objects.get(name='Chemistry')
        self.assertEqual(response.json(), {'id': subject.id, 'name': 'Chemistry'})

        response = client.post(reverse('add_subject'), {'name': 'physics', 'year': 1, 'semester': 1, 'university': 'U'},
                               HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['errors']['name'][0]['message'], '“Physics” is already in the list. Pick it from the courses.')

    def test_students_cannot_add_subjects(self):
        response = self.client_for(self.basic).post(reverse('add_subject'),
                                                    {'name': 'Waves', 'year': 1, 'semester': 1, 'university': 'U'},
                                                    HTTP_ACCEPT='application/json')
        self.assertNotEqual(response.status_code, 201)
        self.assertFalse(Subject.objects.filter(name='Waves').exists())


class NoteReaderTests(SecurityTestCase):
    """The note page shows the main file and the additional files as one document."""

    def setUp(self):
        self.published_extra = NoteFile.objects.create(note=self.verified_note, file=image_upload('page2.jpg', exif_rotated=True),
                                                       is_verified=True)

    def reader_files(self, user):
        return self.client_for(user).get(reverse('note_detail', args=[self.verified_note.id])).context['reader_files']

    def test_readers_get_the_main_file_then_published_extras(self):
        files = self.reader_files(self.basic)
        self.assertEqual([f['url'] for f in files], [
            reverse('note_file', args=[self.verified_note.id]), reverse('note_extra_file', args=[self.published_extra.id]),
        ])
        self.assertEqual(files[0]['type'], 'pdf')
        # A phone photo stored sideways (EXIF "rotate 90"): reported the way browsers show it
        self.assertEqual((files[1]['type'], files[1]['width'], files[1]['height']), ('image', 30, 40))

    def test_owner_also_sees_extras_waiting_for_review(self):
        files = self.reader_files(self.provider)
        self.assertEqual([f['pending'] for f in files], [False, True, False])  # unverified_extra came first

    def test_zip_has_every_readable_file_in_order(self):
        response = self.client_for(self.basic).get(reverse('note_zip', args=[self.verified_note.id]))
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="published-note.zip"')
        with zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content))) as bundle:
            names = bundle.namelist()
        self.assertEqual(len(names), 2)
        self.assertTrue(names[0].startswith('01 published') and names[1].startswith('02 page2'))

    def test_zip_of_a_pending_note_is_hidden_from_readers(self):
        response = self.client_for(self.basic).get(reverse('note_zip', args=[self.unverified_note.id]))
        self.assertEqual(response.status_code, 404)

    def test_download_menu_only_when_there_are_extra_files(self):
        response = self.client_for(self.basic).get(reverse('note_detail', args=[self.verified_note.id]))
        self.assertContains(response, reverse('note_zip', args=[self.verified_note.id]))
        self.published_extra.delete()
        response = self.client_for(self.basic).get(reverse('note_detail', args=[self.verified_note.id]))
        self.assertNotContains(response, reverse('note_zip', args=[self.verified_note.id]))


class NoteFilesTests(SecurityTestCase):
    """The owner's Files page: add several files at once, delete single ones."""

    def test_adds_several_files_at_once(self):
        response = self.client_for(self.provider).post(reverse('note_files', args=[self.verified_note.id]),
                                                       {'files': [pdf_upload('a.pdf'), image_upload('b.jpg')]})
        self.assertRedirects(response, reverse('note_files', args=[self.verified_note.id]), fetch_redirect_response=False)
        added = self.verified_note.files.filter(is_verified=False).exclude(id=self.unverified_extra.id)
        self.assertEqual(added.count(), 2)

    def test_one_bad_file_adds_none_and_names_it(self):
        fake = SimpleUploadedFile('fake.pdf', b'not a pdf at all', content_type='application/pdf')
        response = self.client_for(self.provider).post(reverse('note_files', args=[self.verified_note.id]),
                                                       {'files': [pdf_upload('good.pdf'), fake]})
        self.assertContains(response, 'fake.pdf: ')
        self.assertEqual(self.verified_note.files.count(), 1)

    def test_owner_deletes_one_file_and_it_leaves_storage(self):
        wrong = NoteFile.objects.create(note=self.verified_note, file=pdf_upload('wrong.pdf'))
        storage, name = wrong.file.storage, wrong.file.name
        url = reverse('delete_note_file', args=[self.verified_note.id, wrong.id])
        self.assertEqual(self.client_for(self.provider).get(url).status_code, 405)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client_for(self.provider).post(url)
        self.assertRedirects(response, reverse('note_files', args=[self.verified_note.id]), fetch_redirect_response=False)
        self.assertEqual(list(self.verified_note.files.all()), [self.unverified_extra])
        self.assertFalse(storage.exists(name))
        self.assertTrue(Note.objects.filter(id=self.verified_note.id).exists())

    def test_others_cannot_delete_files(self):
        url = reverse('delete_note_file', args=[self.verified_note.id, self.unverified_extra.id])
        for user in (self.other_provider, self.basic, self.moderator):
            self.assertEqual(self.client_for(user).post(url).status_code, 403)
        self.assertTrue(NoteFile.objects.filter(id=self.unverified_extra.id).exists())

    def test_file_must_belong_to_the_note_in_the_url(self):
        url = reverse('delete_note_file', args=[self.unverified_note.id, self.unverified_extra.id])
        self.assertEqual(self.client_for(self.provider).post(url).status_code, 404)

    def test_files_page_lists_them_in_reading_order_with_delete_buttons(self):
        response = self.client_for(self.provider).get(reverse('note_files', args=[self.verified_note.id]))
        self.assertContains(response, 'Main file')
        self.assertContains(response, reverse('delete_note_file', args=[self.verified_note.id, self.unverified_extra.id]))


class FileCleanupTests(SecurityTestCase):
    """core/file_cleanup.py: stored files go when nothing uses them any more.
    Each test makes its own files: the uploads folder is shared by all tests."""

    def setUp(self):
        self.note = Note.objects.create(topic=self.topic, provider=self.provider, note_type='pdf', caption='c',
                                        name='Own', year=1, semester=1, university='Test U', file=pdf_upload('own.pdf'))
        self.extra = NoteFile.objects.create(note=self.note, file=pdf_upload('own-extra.pdf'))

    def exists(self, field_file):
        return field_file.storage.exists(field_file.name)

    def test_deleting_a_note_removes_its_main_and_extra_files(self):
        main_file, extra_file = self.note.file, self.extra.file
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.provider).post(reverse('delete_note', args=[self.note.id]))
        self.assertFalse(self.exists(main_file))
        self.assertFalse(self.exists(extra_file))

    def test_rejecting_extra_files_removes_them(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.moderator).post(reverse('verify_notes'), {
                'verify_type': 'extra', 'action': 'reject', 'file_ids': [self.extra.id],
            })
        self.assertFalse(self.exists(self.extra.file))

    def test_replacing_the_main_file_removes_the_old_one(self):
        old = self.note.file
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.provider).post(reverse('edit_note', args=[self.note.id]), {
                'name': 'Own', 'caption': 'c', 'year': 1, 'semester': 1, 'university': 'Test U',
                'subject': self.subject.id, 'file': pdf_upload('new.pdf'),
            })
        self.note.refresh_from_db()
        self.assertNotEqual(self.note.file.name, old.name)
        self.assertFalse(self.exists(old))
        self.assertTrue(self.exists(self.note.file))

    def test_a_file_still_used_by_another_row_is_kept(self):
        twin = NoteFile.objects.create(note=self.note, file=self.extra.file.name)
        with self.captureOnCommitCallbacks(execute=True):
            twin.delete()
        self.assertTrue(self.exists(self.extra.file))

    def test_saves_that_do_not_touch_the_file_keep_it(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.note.name = 'Renamed'
            self.note.save()
            self.note.save(update_fields=['name'])
        self.assertTrue(self.exists(self.note.file))


class VerifyQueueTests(SecurityTestCase):
    def reject(self, reason='The scan is too blurry.'):
        return self.client_for(self.moderator).post(reverse('verify_notes'), {
            'verify_type': 'main', 'action': 'reject', 'note_ids': [self.unverified_note.id], 'reason': reason,
        })

    def test_reject_keeps_the_note_with_a_reason_and_tells_the_provider(self):
        self.reject()
        self.unverified_note.refresh_from_db()
        self.assertTrue(self.unverified_note.is_rejected)
        self.assertFalse(self.unverified_note.is_verified)
        self.assertEqual(self.unverified_note.rejection_reason, 'The scan is too blurry.')
        notification = Notification.objects.get(recipient=self.provider, kind=Notification.Kind.NOTE_REJECTED)
        self.assertEqual(notification.url, reverse('note_detail', args=[self.unverified_note.id]))

    def test_reject_needs_a_reason(self):
        self.reject(reason='  ')
        self.unverified_note.refresh_from_db()
        self.assertFalse(self.unverified_note.is_rejected)

    def test_rejected_notes_leave_the_queue_and_the_counts(self):
        self.reject()
        response = self.client_for(self.moderator).get(reverse('verify_notes'))
        self.assertNotIn(self.unverified_note, response.context['unverified_notes'])
        self.assertEqual(response.context['manage_counts']['review'], 1)  # only the extra file is left

    def test_owner_sees_the_reason_and_can_resend(self):
        self.reject()
        page = self.client_for(self.provider).get(reverse('note_detail', args=[self.unverified_note.id]))
        self.assertContains(page, 'The scan is too blurry.')
        self.assertContains(page, reverse('resubmit_note', args=[self.unverified_note.id]))
        self.assertEqual(self.client_for(self.basic).get(page.request['PATH_INFO']).status_code, 404)

        self.client_for(self.provider).post(reverse('resubmit_note', args=[self.unverified_note.id]))
        self.unverified_note.refresh_from_db()
        self.assertFalse(self.unverified_note.is_rejected)
        self.assertIn(self.unverified_note, Note.objects.awaiting_review())

    def test_saving_the_edit_form_resends_a_rejected_note(self):
        self.reject()
        self.client_for(self.provider).post(reverse('edit_note', args=[self.unverified_note.id]), {
            'name': 'Clearer scan', 'caption': 'c', 'year': 1, 'semester': 1, 'university': 'Test U',
            'subject': self.subject.id,
        })
        self.unverified_note.refresh_from_db()
        self.assertEqual((self.unverified_note.name, self.unverified_note.is_rejected), ('Clearer scan', False))

    def test_only_the_owner_can_resend(self):
        self.reject()
        url = reverse('resubmit_note', args=[self.unverified_note.id])
        self.assertEqual(self.client_for(self.other_provider).post(url).status_code, 403)
        self.unverified_note.refresh_from_db()
        self.assertTrue(self.unverified_note.is_rejected)

    def test_verify_publishes_main_notes(self):
        client = self.client_for(self.moderator)
        client.post(reverse('verify_notes'), {'verify_type': 'main', 'action': 'verify',
                                              'note_ids': [self.unverified_note.id]})
        self.unverified_note.refresh_from_db()
        self.assertTrue(self.unverified_note.is_verified)
