import logging
import os
import struct

from django.core.exceptions import ValidationError
from PIL import Image

from .logs import audit

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB

# extension -> detected content kind
ALLOWED_EXTENSIONS = {
    'pdf': 'pdf',
    'jpg': 'jpeg',
    'jpeg': 'jpeg',
    'png': 'png',
    'webp': 'webp',
}
UPLOAD_ACCEPT = '.pdf,.jpg,.jpeg,.png,.webp'

# What Pillow raises for a damaged, fake or far too large image: the user's file, not our bug.
BAD_IMAGE_ERRORS = (OSError, ValueError, SyntaxError, struct.error, Image.DecompressionBombError)


def log_if_unexpected(error, what):
    """The user is told their image is bad either way; anything Pillow doesn't normally raise is
    logged with its traceback, so a real bug doesn't hide behind "this image is damaged"."""
    if not isinstance(error, BAD_IMAGE_ERRORS):
        logger.warning('Unexpected error while reading %s', what, exc_info=error)


def refused(upload, why):
    """Log a refused upload (INFO): many in a row point at abuse or a broken check. The file name
    is what the user's computer called it; the contents are never logged."""
    audit('upload.refused', file=upload.name, size_kb=upload.size // 1024, why=why)


def detect_file_kind(f):
    """Identify a file by its leading bytes rather than its name."""
    f.seek(0)
    head = f.read(12)
    f.seek(0)
    if head.startswith(b'%PDF-'):
        return 'pdf'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if head.startswith(b'\xff\xd8\xff'):
        return 'jpeg'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'webp'
    return None


def validate_upload(value):
    """Accept only real PDF/JPG/PNG/WEBP files up to MAX_UPLOAD_SIZE."""
    if getattr(value, '_committed', False):
        return  # already stored; only newly uploaded files are checked

    if value.size > MAX_UPLOAD_SIZE:
        refused(value, 'too large')
        raise ValidationError(
            'File is too large (%(size).1f MB). The maximum is 20 MB.',
            params={'size': value.size / (1024 * 1024)},
        )

    ext = os.path.splitext(value.name)[1].lower().lstrip('.')
    if ext not in ALLOWED_EXTENSIONS:
        refused(value, 'file type')
        raise ValidationError('Unsupported file type. Upload a PDF, JPG, PNG or WEBP file.')

    kind = detect_file_kind(value)
    if kind != ALLOWED_EXTENSIONS[ext]:
        refused(value, 'contents do not match the name')
        raise ValidationError("The file's contents don't match its .%(ext)s extension.", params={'ext': ext})

    if kind != 'pdf':
        try:
            with Image.open(value) as image:
                image.verify()
        except Exception as error:
            log_if_unexpected(error, f'the uploaded image {value.name!r}')
            refused(value, 'damaged image')
            raise ValidationError('The image file is damaged or not a valid image.')
        finally:
            value.seek(0)


def note_type_for(filename):
    """Note.note_type for a stored file: 'pdf' for PDFs, otherwise 'image'."""
    return 'pdf' if filename.lower().endswith('.pdf') else 'image'
