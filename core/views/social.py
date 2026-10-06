"""Following providers, and the notifications page."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..models import CustomUser, Follow, Notification
from ..notifications import notify_new_follower, withdraw_new_follower
from ._helpers import safe_next

FOLLOWING_PAGE_SIZE = 12
NOTIFICATIONS_PAGE_SIZE = 20


@login_required
def following(request):
    providers = CustomUser.objects.filter(followers__follower=request.user).annotate(
        note_count=Count('note', filter=Q(note__is_verified=True), distinct=True),
    ).order_by('first_name', 'username')
    page = Paginator(providers, FOLLOWING_PAGE_SIZE).get_page(request.GET.get('page'))
    return render(request, 'social/following.html', {'page': page})


@login_required
@require_POST
def follow_provider(request, provider_id):
    provider = get_object_or_404(CustomUser, id=provider_id, user_type='provider')
    name = provider.get_full_name() or provider.username
    if provider == request.user:
        messages.error(request, "You can't follow yourself.")
    else:
        follow, created = Follow.objects.get_or_create(follower=request.user, provider=provider)
        if created:
            notify_new_follower(follow)
        messages.success(request, f"You're following {name}. You'll be notified when they publish a new note.")
    return redirect(safe_next(request, reverse('provider_profile', args=[provider.id])))


@login_required
@require_POST
def unfollow_provider(request, provider_id):
    provider = get_object_or_404(CustomUser, id=provider_id)
    if Follow.objects.filter(follower=request.user, provider=provider).delete()[0]:
        withdraw_new_follower(request.user, provider)
        messages.info(request, f"You unfollowed {provider.get_full_name() or provider.username}.")
    return redirect(safe_next(request, 'following'))


@login_required
def notifications(request):
    items = Notification.objects.filter(recipient=request.user).select_related('actor', 'note', 'purchase')
    page = Paginator(items, NOTIFICATIONS_PAGE_SIZE).get_page(request.GET.get('page'))
    # Evaluate the page now so it still shows which items were unread, then mark them read.
    page.object_list = list(page.object_list)
    unread = [item.id for item in page.object_list if not item.is_read]
    if unread:
        Notification.objects.filter(id__in=unread).update(is_read=True)
    return render(request, 'social/notifications.html', {'page': page})
