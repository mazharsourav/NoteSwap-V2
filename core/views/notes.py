"""Courses (the Subject model) and notes: browsing, uploading, editing, verifying, rating, commenting.

Notes belong straight to a subject (topics were dropped from the site in 2026-10; old topic links redirect)."""
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .. import terms
from ..forms import NoteCommentForm, NoteFilesForm, NoteRatingForm, NoteUploadForm, SubjectForm
from ..logs import audit
from ..models import CustomUser, Follow, Note, NoteComment, NoteFile, Rating, Subject, Topic  # Topic: old links
from ..notifications import publish_notes, reject_notes
from ..permissions import can_view_note, moderator_required, provider_required
from ..universities import NAMES as UNIVERSITY_NAMES, full_name, label as university_label
from ..validators import note_type_for
from ._helpers import image_size, published_notes, readable_extra_files, rejection_reason, safe_next

SUBJECTS_PAGE_SIZE = 12
NOTES_PAGE_SIZE = 15
BEST_FIRST = (F('avg_rating').desc(nulls_last=True), '-rating_count', '-id')


FILTER_KEYS = ('university', 'term', 'year', 'semester')  # year= and semester= are from older links


def _note_filters(params, prefix=''):
    """A Q for ?university=UAP&term=2-1 on notes (prefix='notes__' to use it from a course)."""
    match = Q()
    university = params.get('university', '').strip()
    if university:
        match &= Q(**{prefix + 'university': university})
    picked = terms.parse(params.get('term'))
    if picked:
        match &= Q(**{prefix + 'year': picked[0], prefix + 'semester': picked[1]})
    else:
        for key in ('year', 'semester'):
            value = params.get(key, '').strip()
            if value.isdigit():
                match &= Q(**{prefix + key: value})
    return match


def _filters(request, notes):
    """What the search + university + semester filter needs, for `notes` (the published notes in view):
    the universities they're from (as (value, label) pairs) and the semester chips. A chip is greyed out when no note is for it at the chosen university."""
    university = request.GET.get('university', '').strip()
    picked = terms.parse(request.GET.get('term'))
    rows = list(notes.order_by().values_list('university', 'year', 'semester').annotate(n=Count('id', distinct=True)))
    codes = sorted({u for u, _, _, _ in rows if u} | ({university} if university else set()),
                   key=lambda u: full_name(u).lower())
    counts = {}
    for u, year, semester, n in rows:
        if not university or u == university:
            counts[(year, semester)] = counts.get((year, semester), 0) + n
    chips = [{'value': terms.label(*pair), 'count': counts.get(pair, 0), 'active': pair == picked}
             for pair in terms.chip_terms((year, semester) for _, year, semester, _ in rows)]
    chosen_term = terms.label(*picked) if picked else ''
    carry = [(key, value) for key, value in (('university', university), ('term', chosen_term)) if value]
    return {
        'universities': [(u, university_label(u) if u in UNIVERSITY_NAMES else u) for u in codes],
        'chosen_university': university,
        'chosen_term': chosen_term,
        'term_chips': chips,
        'carry': '?' + urlencode(carry) if carry else '',  # keeps the filter when a course is opened
    }


def _with_universities(subjects):
    """Give each course `.universities`: the universities its published notes are from, most notes first."""
    by_subject = {subject.id: [] for subject in subjects}
    rows = (Note.objects.filter(is_verified=True, subject_id__in=by_subject).exclude(university='')
            .values('subject_id', 'university').annotate(n=Count('id')).order_by('-n', 'university'))
    for row in rows:
        by_subject[row['subject_id']].append(row['university'])
    for subject in subjects:
        subject.universities = by_subject[subject.id]
    return subjects


def _subject_picker():
    """Courses for the picker on the upload and edit forms, plus the "add a course" pop-up's form."""
    return {
        'subjects': Subject.objects.order_by('name'),
        'new_subject_form': SubjectForm(auto_id='new-subject-%s'),
    }


def _wants_json(request):
    """The upload form's pop-up sends fetch() requests that ask for JSON instead of a page."""
    return request.headers.get('Accept', '').startswith('application/json')


def _place_json(place, status=201):
    return JsonResponse({'id': place.id, 'name': place.name}, status=status)


def _with_param(url, key, value):
    """`url` with ?key=value added (or replaced), e.g. to preselect a new course on the upload form."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != key] + [(key, str(value))]
    return urlunsplit(parts._replace(query=urlencode(query)))


@provider_required
def upload_note(request):
    if request.method == 'POST':
        form = NoteUploadForm(request.POST, request.FILES)
        if form.is_valid():
            note = form.save(commit=False)
            note.provider = request.user
            note.note_type = note_type_for(note.file.name)
            note.is_verified = False
            note.save()
            audit('note.uploaded', note=note.id, name=note.name, course=note.subject_id, type=note.note_type,
                  by=request.user.username)
            messages.success(request, 'Note submitted for verification.')
            return redirect('home')
    else:
        # Start from the provider's own university, and the course and semester from ?subject=<id>&term=2-1
        # (a course page's link)
        subject_id = request.GET.get('subject', '')
        picked = terms.parse(request.GET.get('term'))
        form = NoteUploadForm(initial={
            'university': request.user.university,
            'subject': subject_id if subject_id.isdigit() else None,
            'term': terms.label(*picked) if picked else '',
        })

    return render(request, 'notes/note_upload.html', {'form': form, **_subject_picker()})


@moderator_required
def verify_notes(request):
    if request.method == 'POST':
        verify_type = request.POST.get('verify_type')
        action = request.POST.get('action')

        if verify_type == 'main':
            pending = Note.objects.filter(id__in=request.POST.getlist('note_ids')).awaiting_review()
            if action == 'reject':
                reason = rejection_reason(request)
                if not reason:
                    messages.error(request, 'Write a reason. The provider sees it and can fix the note.')
                elif rejected := reject_notes(pending, reason, by=request.user):
                    messages.success(request, f'{rejected} note(s) rejected. The providers were told why.')
            else:
                published = publish_notes(pending, by=request.user)
                if published:
                    messages.success(request, f'{published} note(s) published. Followers of their providers were notified.')

        elif verify_type == 'extra':
            files = NoteFile.objects.filter(id__in=[i for i in request.POST.getlist('file_ids') if i.isdigit()])
            ids = ','.join(str(i) for i in files.order_by('id').values_list('id', flat=True))
            if action == 'verify' and ids:
                files.update(is_verified=True)
                audit('note.files_approved', files=ids, by=request.user.username)
            elif action == 'reject' and ids:
                files.delete()
                audit('note.files_removed', files=ids, by=request.user.username)

        return redirect('verify_notes')  # Refresh

    unverified_notes = (Note.objects.awaiting_review()
                        .select_related('provider', 'subject').order_by('uploaded_at'))
    unverified_files = (NoteFile.objects.filter(is_verified=False)
                        .select_related('note__provider').order_by('uploaded_at'))

    return render(request, 'notes/verify_queue.html', {
        'unverified_notes': unverified_notes,
        'unverified_files': unverified_files,
    })


def subject_list(request):
    """All courses, most notes first. The university and semester ("2-1") filters keep the courses that
    have notes for them, and the counts then count only those notes."""
    match = _note_filters(request.GET, prefix='notes__')
    published = Q(notes__is_verified=True) & match
    subjects = Subject.objects.all()
    if match:
        subjects = subjects.filter(published).distinct()
    q = request.GET.get('q', '').strip()
    if q:
        subjects = subjects.filter(name__icontains=q)
    subjects = subjects.annotate(note_count=Count('notes', filter=published, distinct=True)).order_by(
        '-note_count', 'name')
    page = Paginator(subjects, SUBJECTS_PAGE_SIZE).get_page(request.GET.get('page'))
    _with_universities(page.object_list)
    return render(request, 'notes/subject_list.html', {
        'page': page,
        'filtering': any(request.GET.get(k) for k in ('q',) + FILTER_KEYS),
        **_filters(request, Note.objects.filter(is_verified=True)),
    })


def subject_detail(request, subject_id):
    """A course's page: its published notes from every university, best first (or newest), filtered by
    title, code or provider and by university and semester ("2-1")."""
    subject = get_object_or_404(Subject, id=subject_id)
    all_notes = published_notes().filter(subject=subject)
    notes = all_notes.filter(_note_filters(request.GET))
    q = request.GET.get('q', '').strip()
    if q:
        notes = notes.filter(
            Q(provider__username__icontains=q) | Q(provider__first_name__icontains=q)
            | Q(provider__last_name__icontains=q) | Q(name__icontains=q) | Q(course_code__icontains=q)
        )
    sort = request.GET.get('sort', '')
    notes = notes.order_by('-uploaded_at', '-id') if sort == 'newest' else notes.order_by(*BEST_FIRST)
    return render(request, 'notes/subject_detail.html', {
        'subject': subject,
        'page': Paginator(notes, NOTES_PAGE_SIZE).get_page(request.GET.get('page')),
        'total': all_notes.count(),
        'filtering': any(request.GET.get(k) for k in ('q',) + FILTER_KEYS),
        'newest_notes': all_notes.order_by('-uploaded_at', '-id')[:5],
        **_filters(request, all_notes),
    })


def old_subject_topics(request, subject_id):
    """/subject/<id>/topics/ from before topics were dropped: the subject's page now lists its notes."""
    return redirect('subject_detail', subject_id=subject_id, permanent=True)


def old_topic_notes(request, topic_id):
    """/topic/<id>/notes/ from before topics were dropped: go to that topic's subject."""
    topic = get_object_or_404(Topic, id=topic_id)
    return redirect('subject_detail', subject_id=topic.subject_id, permanent=True)


def _universities_named(text):
    """Codes of the listed universities whose full name contains `text` ("asia" -> ["UAP"])."""
    text = text.lower()
    return [code for code, name in UNIVERSITY_NAMES.items() if len(text) > 2 and text in name.lower()]


def search(request):
    """One search box for the whole catalogue: courses, notes (title, description, course code,
    university) and providers."""
    q = request.GET.get('q', '').strip()[:100]
    context = {'q': q}
    if q:
        context.update({
            'subjects': Subject.objects.filter(name__icontains=q).annotate(
                note_count=Count('notes', filter=Q(notes__is_verified=True), distinct=True),
            ).order_by('name')[:6],
            'providers': CustomUser.objects.filter(user_type='provider').filter(
                Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
            ).order_by('first_name', 'username')[:6],
            'page': Paginator(published_notes().filter(
                Q(name__icontains=q) | Q(caption__icontains=q) | Q(subject__name__icontains=q)
                | Q(course_code__icontains=q) | Q(course_code__iexact=q.replace(' ', ''))
                | Q(university__iexact=q) | Q(university__in=_universities_named(q))
            ).order_by(*BEST_FIRST), 12).get_page(request.GET.get('page')),
        })
    return render(request, 'notes/search.html', context)


@login_required
def note_detail(request, note_id):
    note = get_object_or_404(Note.objects.select_related('provider', 'subject'), id=note_id)
    if not can_view_note(request.user, note):
        raise Http404
    ratings = Rating.objects.filter(note=note)
    summary = ratings.aggregate(avg=Avg('score'), count=Count('id'))
    extra_files = readable_extra_files(request.user, note)

    return render(request, 'notes/note_detail.html', {
        'note': note,
        'extra_files': extra_files,
        'reader_files': _reader_files(note, extra_files),
        'is_owner': note.provider_id == request.user.id,
        'comments': NoteComment.objects.filter(note=note).select_related('user').order_by('-id'),
        'comment_form': NoteCommentForm(),
        'user_rating': ratings.filter(user=request.user).values_list('score', flat=True).first(),
        'can_rate': note.is_verified and note.provider_id != request.user.id,
        'rating_choices': RATING_CHOICES,
        'rating_count': summary['count'],
        'avg_rating': summary['avg'],
        'more_notes': published_notes().filter(provider=note.provider).exclude(id=note.id).order_by(*BEST_FIRST)[:4],
        'provider_note_count': Note.objects.filter(provider=note.provider, is_verified=True).count(),
        'is_following': Follow.objects.filter(follower=request.user, provider=note.provider).exists(),
    })


def _reader_files(note, extra_files):
    """The main file and the additional files as one list for the note reader (js/pages/note-reader.js)."""
    entries = [(reverse('note_file', args=[note.id]), note.file, False)] + [
        (reverse('note_extra_file', args=[extra.id]), extra.file, not extra.is_verified) for extra in extra_files
    ]
    files = []
    for url, field_file, pending in entries:
        entry = {'url': url, 'name': os.path.basename(field_file.name), 'type': note_type_for(field_file.name),
                 'pending': pending}
        if entry['type'] == 'image':
            size = image_size(field_file)
            if size:
                entry['width'], entry['height'] = size
        files.append(entry)
    return files


@login_required
def comment_on_note(request, note_id):
    note = get_object_or_404(Note, id=note_id, is_verified=True)
    if request.method == 'POST':
        form = NoteCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.user = request.user
            comment.note = note
            comment.save()
        elif form.has_error('comment', 'max_length'):
            messages.error(request, f'Your comment is too long. Keep it under {NoteCommentForm.MAX_LENGTH} characters.')
        else:
            messages.error(request, 'Write something before posting your comment.')
    return redirect('note_detail', note_id=note.id)


RATING_CHOICES = [(1, 'Poor'), (2, 'Fair'), (3, 'Good'), (4, 'Very good'), (5, 'Excellent')]


@login_required
@require_POST
def rate_note(request, note_id):
    note = get_object_or_404(Note, id=note_id, is_verified=True)
    if note.provider_id == request.user.id:
        messages.error(request, "You can't rate your own note.")
        return redirect('note_detail', note_id=note.id)

    existing = Rating.objects.filter(note=note, user=request.user).first()
    form = NoteRatingForm(request.POST, instance=existing)
    if form.is_valid():
        rating = form.save(commit=False)
        rating.note = note
        rating.user = request.user
        rating.save()
        messages.success(request, 'Your rating was updated.' if existing else 'Thanks for rating this note!')
    else:
        messages.error(request, 'Please choose a rating from 1 to 5.')
    return redirect('note_detail', note_id=note.id)


@provider_required
def add_subject(request):
    form = SubjectForm(request.POST or None)
    next_url = safe_next(request, reverse('subject_list'))

    if request.method == 'POST' and form.is_valid():
        subject = form.save()
        audit('course.created', course=subject.id, name=subject.name, by=request.user.username)
        if _wants_json(request):
            return _place_json(subject)
        messages.success(request, f'Subject "{subject.name}" added.')
        if next_url.startswith(reverse('upload_note')):
            next_url = _with_param(next_url, 'subject', subject.id)  # back to the form, subject picked
        return redirect(next_url)
    if request.method == 'POST' and _wants_json(request):
        return JsonResponse({'errors': form.errors.get_json_data()}, status=400)

    return render(request, 'notes/subject_add.html', {'form': form, 'next': next_url})


@login_required
def edit_note(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    if request.user != note.provider:
        raise PermissionDenied

    if request.method == 'POST':
        form = NoteUploadForm(request.POST, request.FILES, instance=note)
        if form.is_valid():
            note = form.save(commit=False)
            back_to_review = ''
            if 'file' in form.changed_data:
                note.note_type = note_type_for(note.file.name)
            if 'file' in form.changed_data and note.is_verified:
                # A new file must be reviewed before it is shown publicly again.
                note.is_verified = False
                back_to_review = 'new file'
                messages.info(request, 'Your new file was sent for review. The note is hidden until a moderator approves it.')
            if note.is_rejected:
                _send_for_review_again(note)
                back_to_review = back_to_review or 'was rejected'
                messages.success(request, 'Saved and sent for review again.')
            note.save()
            if form.changed_data:
                audit('note.edited', note=note.id, fields=','.join(form.changed_data),
                      back_to_review=back_to_review or 'no', by=request.user.username)
            return redirect('note_detail', note_id=note.id)
    else:
        form = NoteUploadForm(instance=note)

    return render(request, 'notes/note_edit.html', {'form': form, 'note': note, **_subject_picker()})


def _send_for_review_again(note):
    note.rejected_at = None
    note.rejection_reason = ''


@login_required
@require_POST
def resubmit_note(request, note_id):
    """A rejected note goes back into the review queue as it is (e.g. after the provider adds files)."""
    note = get_object_or_404(Note, id=note_id)
    if request.user != note.provider:
        raise PermissionDenied
    if note.is_rejected:
        _send_for_review_again(note)
        note.save(update_fields=['rejected_at', 'rejection_reason'])
        audit('note.resubmitted', note=note.id, by=request.user.username)
        messages.success(request, 'Sent for review again. You\'ll be notified only if it\'s rejected; otherwise it simply goes live.')
    return redirect('note_detail', note_id=note.id)


@login_required
def delete_note(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    if request.user != note.provider:
        raise PermissionDenied

    if request.method == 'POST':
        subject_id = note.subject_id
        audit('note.deleted', note=note.id, name=note.name, by=request.user.username)
        note.delete()
        messages.success(request, f'"{note.name}" was deleted.')
        return redirect('subject_detail', subject_id=subject_id)

    return render(request, 'notes/note_confirm_delete.html', {'note': note})


@login_required
def note_files(request, note_id):
    """The owner's list of a note's files in reading order: add more, delete single ones."""
    note = get_object_or_404(Note, pk=note_id)
    if request.user != note.provider:
        raise PermissionDenied

    if request.method == 'POST':
        form = NoteFilesForm(request.POST, request.FILES)
        if form.is_valid():
            uploads = form.cleaned_data['files']
            NoteFile.objects.bulk_create([NoteFile(note=note, file=upload) for upload in uploads])
            audit('note.files_added', note=note.id, count=len(uploads), by=request.user.username)
            count = f'{len(uploads)} files' if len(uploads) > 1 else 'File'
            messages.success(request, f'{count} added. They show on the note once a moderator approves them.')
            return redirect('note_files', note_id=note.id)
    else:
        form = NoteFilesForm()

    return render(request, 'notes/note_files.html', {
        'form': form, 'note': note, 'extra_files': note.files.order_by('uploaded_at', 'id'),
        'files_hint': f'PDF, JPG, PNG or WEBP, up to 20 MB each. Pick up to {NoteFilesForm.MAX_FILES} at once. '
                      'They go after the files above and show once a moderator approves them.',
    })


@login_required
@require_POST
def delete_note_file(request, note_id, file_id):
    """Remove one additional file (a wrong photo or PDF) without touching the rest of the note."""
    extra = get_object_or_404(NoteFile.objects.select_related('note'), id=file_id, note_id=note_id)
    if request.user != extra.note.provider:
        raise PermissionDenied
    name = os.path.basename(extra.file.name)
    audit('note.file_deleted', note=note_id, file=extra.id, by=request.user.username)
    extra.delete()  # core/file_cleanup.py removes the stored file too, so a wrong upload is really gone
    messages.success(request, f'“{name}” was removed from the note.')
    return redirect('note_files', note_id=note_id)
