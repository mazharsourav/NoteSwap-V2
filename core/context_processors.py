from django.conf import settings

from .models import InboxMessage, Note, NoteFile, Notification, PremiumPurchase, ProviderRequest
from .permissions import is_premium


def premium_status(request):
    """`is_premium_user` for the navbar and home page (no query: it's a field on the user)."""
    return {'is_premium_user': is_premium(request.user)}


def notifications(request):
    """`unread_notifications` for the navbar bell (one query per request when logged in)."""
    if not request.user.is_authenticated:
        return {'unread_notifications': 0}
    return {'unread_notifications': Notification.objects.filter(recipient=request.user, is_read=False).count()}


def site_credits(request):
    """Footer developer credit, from NOTESWAP_DEVELOPER_NAME / _URL (hidden while the name is empty)."""
    return {'developer_name': settings.DEVELOPER_NAME, 'developer_url': settings.DEVELOPER_URL}


def sign_in_options(request):
    """`google_login_enabled`: show "Continue with Google" only once its keys are configured."""
    return {'google_login_enabled': bool(settings.GOOGLE_CLIENT_ID)}


# url name -> main navigation section, for the header's active link
NAV_SECTIONS = {
    'notes': {'subject_list', 'search', 'subject_detail', 'note_detail', 'upload_note', 'edit_note',
              'note_files', 'delete_note', 'add_subject'},
    'providers': {'providers', 'provider_profile', 'become_provider'},
    'notesolve': {'notesolve_dashboard', 'request_to_provider', 'solve_request', 'provider_solved_requests'},
    'premium': {'premium_packages', 'purchase_premium_package', 'checkout_pending'},
    'manage': {'Manage', 'inbox', 'verify_notes', 'provider_requests', 'provider_request_detail',
               'manage_premium', 'add_premium_package', 'edit_premium_package'},
    'about': {'about'},
    'help': {'help_center', 'help_article', 'ask_question', 'send_feedback', 'contact', 'terms_of_use'},
}


def navigation(request):
    """`nav_section`: which main navigation link to highlight on this page."""
    match = getattr(request, 'resolver_match', None)
    name = match.url_name if match else None
    section = next((key for key, names in NAV_SECTIONS.items() if name in names), '')
    context = {'nav_section': section, 'manage_url_name': name}
    user = request.user
    if section == 'manage' and user.is_authenticated and (user.is_superuser or user.user_type == 'moderator'):
        context['manage_counts'] = _manage_counts(user)
    return context


def _manage_counts(user):
    """Waiting items for the Manage sidebar (only computed on Manage pages)."""
    counts = {
        'review': Note.objects.awaiting_review().count() + NoteFile.objects.filter(is_verified=False).count(),
        'applications': ProviderRequest.objects.filter(status=ProviderRequest.Status.PENDING).count(),
        'inbox': InboxMessage.objects.filter(is_resolved=False).count(),
    }
    if user.is_superuser:
        counts['purchases'] = PremiumPurchase.objects.filter(status=PremiumPurchase.Status.PENDING).count()
    return counts
