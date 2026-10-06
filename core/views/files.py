"""
Protected file downloads.

Uploaded notes and NoteSolve files are served through these views instead of
public /media/ URLs, so every request is checked against the viewer's access.
"""
import logging
import mimetypes
import os
import shutil
import tempfile
import zipfile

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.views.decorators.clickjacking import xframe_options_sameorigin

from ..logs import audit
from ..models import Note, NoteFile, NoteSolveFile, NoteSolveSolution
from ..permissions import can_manage_note, can_view_note
from ._helpers import readable_extra_files


INLINE_CONTENT_TYPES = {'application/pdf', 'image/jpeg', 'image/png', 'image/webp', 'image/gif'}

logger = logging.getLogger(__name__)


def _log_missing(field_file):
    # The database points at a file that isn't in storage any more: lost data, so an ERROR
    # (emailed to ADMINS). The reader gets a 404 or a zip without that file.
    owner = field_file.instance
    logger.error('%s #%s: file missing from storage: %s', type(owner).__name__, owner.pk, field_file.name)


def _serve_file(field_file):
    if not field_file:
        raise Http404
    try:
        handle = field_file.open('rb')
    except FileNotFoundError:
        _log_missing(field_file)
        raise Http404
    name = os.path.basename(field_file.name)
    content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
    # Anything that isn't a plain PDF/image is forced to download, never rendered.
    return FileResponse(
        handle,
        as_attachment=content_type not in INLINE_CONTENT_TYPES,
        filename=name,
        content_type=content_type,
    )


@login_required
@xframe_options_sameorigin
def note_file(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    if not can_view_note(request.user, note):
        raise Http404
    return _serve_file(note.file)


@login_required
def note_zip(request, note_id):
    """The whole note, main file and every additional file the user may see, as one zip,
    numbered in reading order. Built in a temporary file, so big notes don't fill the memory."""
    note = get_object_or_404(Note, id=note_id)
    if not can_view_note(request.user, note):
        raise Http404
    files = [note.file] + [extra.file for extra in readable_extra_files(request.user, note)]

    archive = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_STORED) as bundle:  # PDFs and photos are compressed already
        for number, field_file in enumerate(files, start=1):
            try:
                with field_file.open('rb') as source,                         bundle.open(f'{number:02d} {os.path.basename(field_file.name)}', 'w') as target:
                    shutil.copyfileobj(source, target)
            except FileNotFoundError:
                _log_missing(field_file)
                continue
    archive.seek(0)
    audit('download.zip', note=note.id, files=len(files), user=request.user.username)
    name = slugify(note.name) or f'note-{note.id}'
    return FileResponse(archive, as_attachment=True, filename=f'{name}.zip', content_type='application/zip')


@login_required
@xframe_options_sameorigin
def note_extra_file(request, file_id):
    extra = get_object_or_404(NoteFile.objects.select_related('note'), id=file_id)
    published = extra.is_verified and extra.note.is_verified
    if not (published or can_manage_note(request.user, extra.note)):
        raise Http404
    return _serve_file(extra.file)


@login_required
@xframe_options_sameorigin
def notesolve_file(request, file_id):
    attachment = get_object_or_404(NoteSolveFile.objects.select_related('solve_request'), id=file_id)
    solve_request = attachment.solve_request
    allowed = {solve_request.user_id, solve_request.requested_to_id}
    if request.user.id not in allowed and not request.user.is_superuser:
        raise Http404
    return _serve_file(attachment.file)


@login_required
@xframe_options_sameorigin
def notesolve_solution_file(request, solution_id):
    solution = get_object_or_404(NoteSolveSolution.objects.select_related('solve_request'), id=solution_id)
    allowed = {solution.solve_request.user_id, solution.provider_id}
    if request.user.id not in allowed and not request.user.is_superuser:
        raise Http404
    return _serve_file(solution.file)
