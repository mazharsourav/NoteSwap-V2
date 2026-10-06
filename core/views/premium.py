"""Premium packages and purchases. Orders are logged in core/notifications.py, package changes here."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from ..forms import PremiumPackageForm
from ..logs import audit
from ..models import PremiumPackage, PremiumPurchase
from ..notifications import approve_purchase as approve_and_notify
from ..notifications import premium_order_placed
from ..notifications import reject_purchase as reject_and_notify
from ..permissions import superuser_required
from ._helpers import rejection_reason


def premium_packages(request):
    """The public pricing page. Signed-in students also see their Premium time and latest order."""
    purchase = None
    if request.user.is_authenticated:
        purchase = PremiumPurchase.objects.filter(user=request.user).order_by('-timestamp', '-id').first()
    packages = list(PremiumPackage.objects.filter(is_active=True).order_by('duration_in_months', 'price'))
    for package in packages:
        package.per_month = package.price / max(package.duration_in_months, 1)
    best = min(packages, key=lambda p: p.per_month) if len(packages) > 1 else None
    # "Save X%" against the shortest plan's monthly price; only shown when it's a real saving.
    if packages:
        reference = packages[0].per_month  # ordered by duration, then price
        for package in packages:
            saving = round((1 - package.per_month / reference) * 100) if reference else 0
            package.saving = saving if saving >= 5 else None
    return render(request, 'premium/package_list.html', {
        'packages': packages,
        'best_value_id': best.id if best else None,
        'purchase': purchase,
    })


@login_required
def purchase_premium_package(request, package_id):
    package = get_object_or_404(PremiumPackage, id=package_id, is_active=True)

    if request.method == 'POST':
        if PremiumPurchase.objects.filter(user=request.user, status=PremiumPurchase.Status.PENDING).exists():
            audit('premium.order_refused', user=request.user.username, package=package.id, why='order already waiting')
            messages.info(request, 'You already have a purchase waiting for approval.')
            return redirect('checkout_pending')
        purchase = PremiumPurchase.objects.create(  # waits for an admin to approve it
            user=request.user,
            package=package,
            package_name=package.name,
            amount=package.price,
            duration_in_months=package.duration_in_months,
        )
        premium_order_placed(purchase)
        messages.success(request, f'Your purchase of {package.name} is pending approval.')
        return redirect('checkout_pending')

    return render(request, 'premium/purchase.html', {'package': package})


@login_required
def checkout_pending(request):
    purchase = PremiumPurchase.objects.filter(user=request.user).order_by('-timestamp', '-id').first()
    return render(request, 'premium/checkout_pending.html', {'purchase': purchase})


@superuser_required
def add_premium_package(request):
    if request.method == 'POST':
        form = PremiumPackageForm(request.POST)
        if form.is_valid():
            package = form.save()
            audit('package.added', package=package.id, name=package.name, price=f'{package.price:.2f}',
                  months=package.duration_in_months, by=request.user.username)
            messages.success(request, f'Package "{package.name}" added.')
            return redirect('manage_premium')
    else:
        form = PremiumPackageForm()

    return render(request, 'premium/package_add.html', {'form': form})


@superuser_required
def edit_premium_package(request, package_id):
    package = get_object_or_404(PremiumPackage, id=package_id)

    if request.method == 'POST':
        form = PremiumPackageForm(request.POST, instance=package)
        if form.is_valid():
            form.save()
            if form.changed_data:
                audit('package.edited', package=package.id, name=package.name, changed=','.join(form.changed_data),
                      price=f'{package.price:.2f}', months=package.duration_in_months, by=request.user.username)
            messages.success(request, f'Package "{package.name}" saved.')
            return redirect('manage_premium')
    else:
        form = PremiumPackageForm(instance=package)

    return render(request, 'premium/package_edit.html', {'form': form, 'package': package})


@superuser_required
@require_POST
def delete_premium_package(request, package_id):
    package = get_object_or_404(PremiumPackage, id=package_id)
    if package.purchases.exists():
        audit('package.delete_refused', package=package.id, name=package.name, why='has orders',
              by=request.user.username)
        messages.error(request, f'"{package.name}" has orders, so it can’t be deleted. Take it off sale instead.')
        return redirect('manage_premium')
    audit('package.deleted', package=package.id, name=package.name, by=request.user.username)
    package.delete()
    messages.success(request, f'Package "{package.name}" deleted.')
    return redirect('manage_premium')


@superuser_required
@require_POST
def toggle_premium_package(request, package_id):
    """Take a package off sale (hidden from the pricing page, past orders kept) or put it back."""
    package = get_object_or_404(PremiumPackage, id=package_id)
    package.is_active = not package.is_active
    package.save(update_fields=['is_active'])
    audit('package.on_sale' if package.is_active else 'package.off_sale', package=package.id, name=package.name,
          by=request.user.username)
    if package.is_active:
        messages.success(request, f'"{package.name}" is on sale again.')
    else:
        messages.success(request, f'"{package.name}" is off sale. Students no longer see it.')
    return redirect('manage_premium')


@superuser_required
@require_POST
def approve_purchase(request, purchase_id):
    purchase = get_object_or_404(PremiumPurchase.objects.select_related('user'), id=purchase_id)
    if approve_and_notify(purchase, request.user):
        until = date_format(timezone.localtime(purchase.ends_at), 'j M Y')
        messages.success(request, f'Purchase approved. {purchase.user.username} has Premium until {until}.')
    else:
        messages.warning(request, 'This purchase was already approved or rejected.')
    return redirect('manage_premium')


@superuser_required
@require_POST
def reject_purchase(request, purchase_id):
    purchase = get_object_or_404(PremiumPurchase, id=purchase_id)
    reason = rejection_reason(request)
    if not reason:
        messages.error(request, 'Please give a reason. The student sees it.')
    elif reject_and_notify(purchase, reason, request.user):
        messages.success(request, 'Purchase rejected. The student sees your reason and can order again.')
    else:
        messages.warning(request, 'This purchase was already approved or rejected.')
    return redirect('manage_premium')
