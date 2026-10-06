"""The Manage dashboard and the inbox, for moderators and superusers."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..logs import audit
from ..models import InboxMessage, Note, NoteFile, PremiumPackage, PremiumPurchase, ProviderRequest
from ..permissions import moderator_required, superuser_required
from ._helpers import safe_next

INBOX_PAGE_SIZE = 20


@moderator_required
def manage_dash_view(request):
    counts = {
        'pending_notes': Note.objects.awaiting_review().count(),
        'pending_files': NoteFile.objects.filter(is_verified=False).count(),
        'pending_applications': ProviderRequest.objects.filter(status=ProviderRequest.Status.PENDING).count(),
        'open_messages': InboxMessage.objects.filter(is_resolved=False).count(),
    }
    if request.user.is_superuser:
        counts['pending_purchases'] = PremiumPurchase.objects.filter(status=PremiumPurchase.Status.PENDING).count()
        counts['packages'] = PremiumPackage.objects.count()
    waiting = Note.objects.awaiting_review().select_related('provider', 'subject')
    oldest = waiting.order_by('uploaded_at').values_list('uploaded_at', flat=True).first()
    return render(request, 'dashboard/manage.html', {
        'counts': counts,
        'waiting_notes': waiting.order_by('uploaded_at')[:8],
        'oldest_waiting': oldest,
    })


@superuser_required
def manage_premium(request):
    """Superusers: approve or reject Premium purchases, and edit the packages on sale."""
    return render(request, 'dashboard/premium.html', {
        'pending_purchases': PremiumPurchase.objects.filter(status=PremiumPurchase.Status.PENDING)
                             .select_related('user').order_by('timestamp'),
        'recent_purchases': PremiumPurchase.objects.exclude(status=PremiumPurchase.Status.PENDING)
                            .select_related('user', 'reviewed_by').order_by('-reviewed_at', '-id')[:10],
        'packages': PremiumPackage.objects.annotate(order_count=Count('purchases'))
                    .order_by('-is_active', 'duration_in_months', 'price'),
    })


@moderator_required
def inbox(request):
    status = request.GET.get('status', 'open')
    kind = request.GET.get('kind', '')

    inbox_messages = InboxMessage.objects.select_related('user')
    if status == 'open':
        inbox_messages = inbox_messages.filter(is_resolved=False)
    elif status == 'resolved':
        inbox_messages = inbox_messages.filter(is_resolved=True)
    else:
        status = 'all'
    if kind in InboxMessage.Kind.values:
        inbox_messages = inbox_messages.filter(kind=kind)
    else:
        kind = ''

    page = Paginator(inbox_messages, INBOX_PAGE_SIZE).get_page(request.GET.get('page'))
    return render(request, 'dashboard/inbox.html', {
        'page': page,
        'status': status,
        'kind': kind,
        'kinds': InboxMessage.Kind.choices,
        'open_count': InboxMessage.objects.filter(is_resolved=False).count(),
    })


@moderator_required
@require_POST
def inbox_toggle(request, message_id):
    """Mark a message resolved, or reopen a resolved one."""
    message = get_object_or_404(InboxMessage, id=message_id)
    message.is_resolved = not message.is_resolved
    message.save(update_fields=['is_resolved'])
    audit('inbox.resolved' if message.is_resolved else 'inbox.reopened', messages=message.id,
          by=request.user.username)
    if message.is_resolved:
        messages.success(request, f"Message from {message.name} marked as resolved.")
    else:
        messages.info(request, f"Message from {message.name} reopened.")
    return redirect(safe_next(request, 'inbox'))
