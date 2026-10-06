"""Log out, profiles and user search. Sign up, sign in, email verification and
password reset are handled by django-allauth (/accounts/, templates/account/)."""
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import UserProfileForm
from ..logs import audit
from ..models import CustomUser, Follow, Note, Notification, ProviderRequest
from ._helpers import published_notes

SEARCH_PAGE_SIZE = 12


def logout_view(request):
    # Logging out changes state, so only a POST (the navbar link submits one) logs out.
    if request.method == 'POST':
        logout(request)
    return redirect('home')


@login_required
def profile_view(request):
    user = request.user
    followed = CustomUser.objects.filter(followers__follower=user).annotate(
        note_count=Count('note', filter=Q(note__is_verified=True), distinct=True),
    ).order_by('first_name', 'username')
    context = {
        'following_count': followed.count(),
        'following_preview': followed[:3],
        'follower_count': Follow.objects.filter(provider=user).count(),
        'recent_notifications': Notification.objects.filter(recipient=user).select_related('actor', 'note', 'purchase')[:3],
        'application': ProviderRequest.objects.filter(user=user).first(),
    }
    if user.user_type == 'provider' or user.is_superuser:
        own = Note.objects.filter(provider=user)
        context.update({
            'my_notes': own.select_related('subject').order_by('-uploaded_at', '-id')[:6],
            'published_count': own.filter(is_verified=True).count(),
            'pending_count': own.awaiting_review().count(),
            'rejected_count': own.filter(rejected_at__isnull=False).count(),
        })
    return render(request, 'accounts/profile.html', context)


@login_required
def user_profile(request, user_id):
    user_obj = get_object_or_404(CustomUser, id=user_id)
    is_provider = user_obj.user_type == 'provider'

    return render(request, 'accounts/user_detail.html', {
        'user_obj': user_obj,
        'notes': published_notes().filter(provider=user_obj).order_by('-uploaded_at', '-id') if is_provider else [],
        'follower_count': Follow.objects.filter(provider=user_obj).count() if is_provider else 0,
        'is_following': Follow.objects.filter(follower=request.user, provider=user_obj).exists(),
    })


@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            if form.changed_data:  # names of the fields only, never what was typed
                audit('profile.edited', user=request.user.username, fields=','.join(form.changed_data))
            messages.success(request, 'Profile updated.')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, 'accounts/profile_edit.html', {'form': form})


@login_required
def search_users(request):
    query = request.GET.get('q', '').strip()
    results = None
    if query:
        matches = CustomUser.objects.filter(
            Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query)
        ).exclude(id=request.user.id).order_by('first_name', 'username')
        results = Paginator(matches, SEARCH_PAGE_SIZE).get_page(request.GET.get('page'))
    return render(request, 'accounts/user_search.html', {'results': results, 'query': query})
