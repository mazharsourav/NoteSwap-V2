"""NoteSolve: premium students ask providers to solve problems."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..forms import NoteSolveFileForm, NoteSolveRequestForm, SolutionRatingForm, SolveForm
from ..logs import audit, security
from ..models import CustomUser, NoteSolveFile, NoteSolveRequest, NoteSolveSolution
from ..permissions import PREMIUM_NEEDED, is_premium, premium_required
from ._helpers import rejection_reason


@login_required
def notesolve_dashboard(request):
    # Premium students ask questions here. Once Premium ends they can still read and rate past answers.
    can_ask = is_premium(request.user)
    if not can_ask and not NoteSolveRequest.objects.filter(user=request.user).exists():
        security('access.denied', user=request.user.username, path=request.path, needs='premium')
        messages.error(request, PREMIUM_NEEDED)
        return redirect('home')

    # 📩 Blank forms
    request_form = NoteSolveRequestForm(initial={'university': request.user.university,
                                                 'department': request.user.department})
    file_form = NoteSolveFileForm()

    # 🧑‍🏫 All providers (excluding current user)
    providers = CustomUser.objects.filter(user_type='provider').exclude(id=request.user.id)

    # 🔍 Search filtering
    q = request.GET.get('q')
    if q:
        providers = providers.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(username__icontains=q)
        )

    # ⭐ Annotate with average provider rating
    providers = providers.annotate(avg_rating=Avg('notesolvesolution__rating'))

    # 🎯 Prioritize providers from same university and department
    same_uni_dept = providers.filter(
        university=request.user.university,
        department=request.user.department
    )
    others = providers.exclude(id__in=same_uni_dept)
    sorted_providers = list(same_uni_dept) + list(others)

    # 📨 Handle form submissions
    if request.method == 'POST':
        # ⭐ Rating a solution
        if 'rate_solution_id' in request.POST:
            solution = get_object_or_404(
                NoteSolveSolution,
                id=request.POST['rate_solution_id'],
                solve_request__user=request.user
            )
            form = SolutionRatingForm(request.POST, instance=solution)
            if form.is_valid():
                form.save()
                messages.success(request, "Thanks for rating the solution!")
                return redirect('notesolve_dashboard')
            else:
                messages.error(request, "Choose a rating from 1 to 5 stars.")

        # 📝 Submitting a new request
        elif not can_ask:
            security('access.denied', user=request.user.username, path=request.path, needs='premium')
            messages.error(request, PREMIUM_NEEDED)
            return redirect('notesolve_dashboard')
        else:
            request_form = NoteSolveRequestForm(request.POST)
            file_form = NoteSolveFileForm(request.POST, request.FILES)
            provider_id = request.POST.get("provider_id")

            has_file = 'file' in request.FILES
            if request_form.is_valid() and provider_id and (not has_file or file_form.is_valid()):
                provider = get_object_or_404(CustomUser, id=provider_id, user_type='provider')
                with transaction.atomic():
                    note_request = request_form.save(commit=False)
                    note_request.user = request.user
                    note_request.requested_to = provider
                    note_request.created_at = timezone.now()
                    note_request.save()

                    if has_file:
                        attachment = file_form.save(commit=False)
                        attachment.solve_request = note_request
                        attachment.save()

                    audit('notesolve.sent', request=note_request.id, user=request.user.username,
                          to=provider.username, files=int(has_file))
                    messages.success(request, f"Your NoteSolve request was sent to {provider.get_full_name() or provider.username}.")
                    return redirect('notesolve_dashboard')
            elif has_file and file_form.errors:
                messages.error(request, ' '.join(file_form.errors.get('file', [])))
            else:
                messages.error(request, "Please fill out all required fields and select a provider.")

    # 📜 Requests by this user
    my_requests = NoteSolveRequest.objects.filter(user=request.user) \
        .select_related('requested_to').order_by('-created_at')

    # 📎 Attachments for all of the user's requests in one query
    file_dict = {}
    for attachment in NoteSolveFile.objects.filter(solve_request__in=my_requests).order_by('id'):
        file_dict.setdefault(attachment.solve_request_id, []).append(attachment)

    solved_dict = {
        sol.solve_request_id: sol
        for sol in NoteSolveSolution.objects.filter(solve_request__in=my_requests)
    }

    selected = request.POST.get('provider_id') or request.GET.get('provider') or ''
    return render(request, 'notesolve/dashboard.html', {
        'can_ask': can_ask,
        'selected_provider': selected if selected.isdigit() else '',
        'suggested_ids': {p.id for p in same_uni_dept},
        'status_counts': {
            'pending': sum(1 for r in my_requests if r.status == NoteSolveRequest.Status.PENDING),
            'solved': sum(1 for r in my_requests if r.status == NoteSolveRequest.Status.SOLVED),
        },
        'all_providers': CustomUser.objects.filter(user_type='provider').exclude(id=request.user.id).order_by('username'),
        'form': request_form,
        'file_form': file_form,
        'providers': sorted_providers,
        'my_requests': my_requests,
        'request_files': file_dict,
        'solved': solved_dict,
        'rating_form': SolutionRatingForm()
    })


@premium_required
def request_to_provider(request, provider_id):
    if request.method == 'POST':
        provider = get_object_or_404(CustomUser, id=provider_id, user_type='provider')

        form = NoteSolveRequestForm(request.POST, request.FILES)
        file_form = NoteSolveFileForm(request.POST, request.FILES)

        if form.is_valid() and 'file' in request.FILES and file_form.is_valid():
            with transaction.atomic():
                note_request = form.save(commit=False)
                note_request.user = request.user
                note_request.requested_to = provider
                note_request.save()

                attachment = file_form.save(commit=False)
                attachment.solve_request = note_request
                attachment.save()

                audit('notesolve.sent', request=note_request.id, user=request.user.username,
                      to=provider.username, files=1)
                messages.success(request, f"Request sent to {provider.get_full_name() or provider.username}.")
                return redirect('home')  # or 'notesolve_dashboard' if preferred
        else:
            messages.error(request, "Please fill out all fields and upload a file.")
            return redirect('notesolve_dashboard')

    messages.error(request, "Invalid request method.")
    return redirect('notesolve_dashboard')


@premium_required
@require_POST
def resend_solve_request(request, request_id):
    solve_request = get_object_or_404(
        NoteSolveRequest, id=request_id, user=request.user, status=NoteSolveRequest.Status.REJECTED
    )
    provider = CustomUser.objects.filter(id=request.POST.get('provider_id'), user_type='provider').first()
    if provider is None or provider.id in (solve_request.requested_to_id, request.user.id):
        messages.error(request, "Please choose a different provider.")
        return redirect('notesolve_dashboard')
    solve_request.requested_to = provider
    solve_request.status = NoteSolveRequest.Status.PENDING
    solve_request.rejection_reason = ''
    solve_request.save()
    audit('notesolve.resent', request=solve_request.id, user=request.user.username, to=provider.username)
    messages.success(request, f"Your request was sent to {provider.get_full_name() or provider.username}.")
    return redirect('notesolve_dashboard')


@login_required
def provider_solved_requests(request):
    if request.user.user_type != 'provider' and not request.user.is_superuser:
        security('access.denied', user=request.user.username, path=request.path, needs='provider')
        messages.error(request, "You are not authorized to view this page.")
        return redirect('home')

    # ✅ Subquery: Check if a solution exists for a given request
    solved_subquery = NoteSolveSolution.objects.filter(
        solve_request=OuterRef('pk'),
        provider=request.user
    )

    # 📬 Requests waiting for this provider (not yet solved or rejected)
    received_requests = NoteSolveRequest.objects.filter(
        requested_to=request.user, status=NoteSolveRequest.Status.PENDING
    ).annotate(
        already_solved=Exists(solved_subquery)
    ).filter(
        already_solved=False
    ).select_related('user').order_by('-created_at')

    # ✅ Requests already solved by this provider
    solved_requests = NoteSolveSolution.objects.select_related(
        'solve_request__user'
    ).filter(
        provider=request.user
    ).order_by('-submitted_at')

    return render(request, 'notesolve/provider_inbox.html', {
        'received_requests': received_requests,
        'solved_requests': solved_requests
    })


@login_required
def solve_request_view(request, request_id):
    # ✅ Ensure only providers or superusers
    if request.user.user_type != 'provider' and not request.user.is_superuser:
        security('access.denied', user=request.user.username, path=request.path, needs='provider')
        messages.error(request, "You do not have permission to solve this request.")
        return redirect('home')

    # 🔍 Only the provider the request was sent to may see or answer it
    solve_request = get_object_or_404(NoteSolveRequest, id=request_id, requested_to=request.user)

    # 🔒 Only pending requests can be answered or rejected
    if solve_request.status != NoteSolveRequest.Status.PENDING:
        messages.warning(request, "This request was already answered or rejected.")
        return redirect('provider_solved_requests')

    # 📂 Fetch any uploaded files
    attached_files = NoteSolveFile.objects.filter(solve_request=solve_request)

    # 📨 Handle POST
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'reject':
            reason = rejection_reason(request)
            if not reason:
                messages.error(request, "Please give a reason. The student will see it.")
                return redirect('solve_request', request_id=solve_request.id)
            solve_request.status = NoteSolveRequest.Status.REJECTED
            solve_request.rejection_reason = reason
            solve_request.save()
            audit('notesolve.rejected', request=solve_request.id, student=solve_request.user.username,
                  by=request.user.username, reason=reason)
            messages.info(request, "Request rejected. The student can send it to another provider.")
            return redirect('provider_solved_requests')

        form = SolveForm(request.POST, request.FILES)
        if form.is_valid():
            solution = form.save(commit=False)
            solution.solve_request = solve_request
            solution.provider = request.user
            solution.submitted_at = timezone.now()
            with transaction.atomic():
                solution.save()
                solve_request.status = NoteSolveRequest.Status.SOLVED
                solve_request.save(update_fields=['status'])
            audit('notesolve.solved', request=solve_request.id, solution=solution.id,
                  student=solve_request.user.username, by=request.user.username, files=int(bool(solution.file)))

            messages.success(request, "Solution submitted successfully.")
            return redirect('provider_solved_requests')
        else:
            messages.error(request, "Please check your input and try again.")
    else:
        form = SolveForm()

    return render(request, 'notesolve/solve_form.html', {
        'solve_request': solve_request,
        'form': form,
        'attached_files': attached_files,
    })
