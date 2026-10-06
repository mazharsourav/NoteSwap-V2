"""Small helpers shared by the view modules."""
import logging

from django.db.models import Avg, Count, Q
from django.utils.http import url_has_allowed_host_and_scheme
from PIL import Image

from ..models import CustomUser, Note
from ..permissions import can_manage_note

logger = logging.getLogger(__name__)


def provider_cards(with_followers=False):
    """Providers with their published-note count (and follower count), for the provider cards (one query)."""
    providers = CustomUser.objects.filter(user_type='provider').annotate(
        note_count=Count('note', filter=Q(note__is_verified=True), distinct=True),
    ).order_by('id')
    if with_followers:
        providers = providers.annotate(follower_count=Count('followers', distinct=True))
    return [
        {'provider': provider, 'note_count': provider.note_count,
         'follower_count': getattr(provider, 'follower_count', 0)}
        for provider in providers
    ]


def published_notes():
    """Published notes ready for a note card: subject and provider loaded, plus
    `avg_rating` and `rating_count`."""
    return Note.objects.filter(is_verified=True).select_related('subject', 'provider').annotate(
        avg_rating=Avg('rating__score'),
        rating_count=Count('rating', distinct=True),
    )


def readable_extra_files(user, note):
    """A note's additional files that `user` may see, in upload order: the published ones,
    plus those still waiting for review for the owner and moderators."""
    files = note.files.order_by('uploaded_at', 'id')
    if not can_manage_note(user, note):
        files = files.filter(is_verified=True)
    return list(files)


def image_size(field_file):
    """(width, height) of an uploaded image as browsers show it (phone photos are often stored
    sideways with an EXIF "rotate" flag), or None if it can't be read. Reads only the header."""
    try:
        with field_file.open('rb') as handle, Image.open(handle) as image:
            width, height = image.size
            if image.getexif().get(0x0112) in (5, 6, 7, 8):  # rotated a quarter turn
                width, height = height, width
            return width, height
    except Exception as error:  # missing or unreadable: the reader shows it at a default size
        logger.warning('Could not read the size of image %s: %r', field_file.name, error)
        return None


def rejection_reason(request):
    return request.POST.get('reason', '').strip()[:1000]


def safe_next(request, fallback):
    """Return the ?next= target if it points to this site, otherwise `fallback`."""
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return fallback
