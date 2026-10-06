"""Provider listing and profiles, and the provider application workflow."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..forms import ProviderRequestForm
from ..logs import audit
from ..models import CustomUser, Follow, ProviderRequest, Rating, Subject
from ..universities import full_name
from ..permissions import is_premium, moderator_required
from ._helpers import provider_cards, published_notes, rejection_reason

PROVIDER_SORTS = {
    'notes': lambda item: (-item['note_count'], -item['follower_count']),
    'followers': lambda item: (-item['follower_count'], -item['note_count']),
    'name': lambda item: (item['provider'].get_full_name() or item['provider'].username).lower(),
}


def _followed_ids(user):
    if not user.is_authenticated:
        return set()
    return set(Follow.objects.filter(follower=user).values_list('provider_id', flat=True))


def providers(request):
    q = request.GET.get('q', '').strip().lower()
    sort = request.GET.get('sort', '')
    provider_data = provider_cards(with_followers=True)
    if q:
        provider_data = [
            item for item in provider_data
            if q in ' '.join([item['provider'].username, item['provider'].get_full_name(),
                              item['provider'].university, full_name(item['provider'].university)]).lower()
        ]
    provider_data.sort(key=PROVIDER_SORTS.get(sort, PROVIDER_SORTS['notes']))
    return render(request, 'providers/provider_list.html', {
        'provider_data': provider_data,
        'followed_ids': _followed_ids(request.user),
    })


def provider_profile(request, provider_id):
    provider = get_object_or_404(CustomUser, id=provider_id, user_type='provider')
    all_notes = published_notes().filter(provider=provider)
    notes = all_notes
    subject_id = request.GET.get('subject', '')
    if subject_id.isdigit():
        notes = notes.filter(subject_id=subject_id)
    if request.GET.get('sort') == 'newest':
        notes = notes.order_by('-uploaded_at', '-id')
    else:
        notes = notes.order_by(F('avg_rating').desc(nulls_last=True), '-rating_count', '-id')

    return render(request, 'providers/provider_detail.html', {
        'provider': provider,
        'notes': notes,
        'note_count': all_notes.count(),
        'subjects': Subject.objects.filter(notes__in=all_notes).distinct().order_by('name'),
        'average_rating': Rating.objects.filter(note__in=all_notes).aggregate(avg=Avg('score'))['avg'],
        'follower_count': Follow.objects.filter(provider=provider).count(),
        'is_following': provider.id in _followed_ids(request.user),
        'can_ask': request.user != provider and is_premium(request.user),
        'tab': 'about' if request.GET.get('tab') == 'about' else 'notes',
    })


@login_required
def become_provider(request):
    application = ProviderRequest.objects.filter(user=request.user).first()
    Status = ProviderRequest.Status

    if request.user.user_type == 'provider' or (application and application.status == Status.ACCEPTED):
        state = 'accepted'
    elif application and application.status == Status.PENDING:
        state = 'pending'
    elif application and application.status == Status.REJECTED and not application.can_reapply:
        state = 'cooldown'
    else:
        state = 'open'  # never applied, or a rejection whose cooldown has passed

    form = None
    if state == 'open':
        # A reapplication updates the user's existing application (one per user).
        # A first application starts from the profile (name, email, university, department, gender).
        profile = {} if application else {
            'first_name': request.user.first_name, 'last_name': request.user.last_name, 'email': request.user.email,
            'university': request.user.university, 'department': request.user.department, 'gender': request.user.gender,
        }
        form = ProviderRequestForm(request.POST or None, instance=application, initial=profile)
        if request.method == 'POST' and form.is_valid():
            reapplying = application is not None
            application = form.save(commit=False)
            application.user = request.user
            application.status = Status.PENDING
            application.rejection_reason = ''
            application.reviewed_at = None
            application.save()
            audit('provider.reapplied' if reapplying else 'provider.applied', application=application.id,
                  user=request.user.username)
            messages.success(request, 'Your application was submitted. A moderator will review it soon.')
            return redirect('become_provider')

    elif request.method == 'POST':
        # Only reachable by posting by hand (the page shows no form): pending, already a provider, or the
        # 30-day wait after a rejection.
        audit('provider.apply_refused', user=request.user.username, why=state)

    return render(request, 'providers/apply.html', {'form': form, 'state': state, 'application': application})


@moderator_required
def provider_requests(request):
    requests = (ProviderRequest.objects.filter(status=ProviderRequest.Status.PENDING)
                .select_related('user').order_by('submitted_at'))
    reviewed = (ProviderRequest.objects.exclude(status=ProviderRequest.Status.PENDING)
                .select_related('user').order_by('-reviewed_at', '-id')[:10])
    return render(request, 'providers/application_list.html', {'requests': requests, 'reviewed': reviewed})


@moderator_required
def provider_request_detail(request, request_id):
    req = get_object_or_404(ProviderRequest, id=request_id)
    return render(request, 'providers/application_detail.html', {'req': req})


@moderator_required
@require_POST
def provider_request_action(request, request_id, action):
    provider_request = get_object_or_404(ProviderRequest, id=request_id, status=ProviderRequest.Status.PENDING)
    user = provider_request.user

    if action == 'accept':
        provider_request.status = ProviderRequest.Status.ACCEPTED
        provider_request.reviewed_at = timezone.now()
        provider_request.save()
        user.user_type = 'provider'
        user.save()
        audit('provider.accepted', application=provider_request.id, user=user.username, by=request.user.username)
        messages.success(request, f"{user.username} is now a provider.")

    elif action == 'reject':
        reason = rejection_reason(request)
        if not reason:
            messages.error(request, "Please give a reason. The applicant will see it.")
            return redirect('provider_request_detail', request_id=provider_request.id)
        provider_request.status = ProviderRequest.Status.REJECTED
        provider_request.rejection_reason = reason
        provider_request.reviewed_at = timezone.now()
        provider_request.save()
        audit('provider.rejected', application=provider_request.id, user=user.username, by=request.user.username,
              reason=reason)
        messages.warning(request, f"Application from {user.username} was rejected. They can reapply in 30 days.")

    return redirect('provider_requests')
