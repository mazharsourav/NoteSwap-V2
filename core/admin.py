import logging

from django.contrib import admin
from django.contrib.admin import helpers
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from .models import (
    CustomUser, Follow, InboxMessage, Note, NoteComment, NoteFile, Notification, PremiumPackage, PremiumPurchase,
    Rating, Review, Subject, Topic,
)
from django.contrib.auth.admin import UserAdmin

from .logs import audit
from .notifications import approve_purchase, publish_notes, reject_notes


# ========== Audit log for admin edits ==========
def _changed_fields(message):
    """Field names from the admin's change message, e.g. [{'changed': {'fields': ['Price']}}]."""
    fields = []
    for part in message if isinstance(message, list) else []:
        fields += part.get('changed', {}).get('fields', [])
    return ','.join(fields) or '-'


class AuditedAdmin:
    """Adds, edits and deletes made in this admin page also go to the audit log. (Django keeps
    its own list under "Recent actions", but that never reaches the log files.)"""

    def log_addition(self, request, obj, message):
        audit('admin.added', model=self.model._meta.model_name, id=obj.pk, by=request.user.username)
        return super().log_addition(request, obj, message)

    def log_change(self, request, obj, message):
        audit('admin.changed', model=self.model._meta.model_name, id=obj.pk, fields=_changed_fields(message),
              by=request.user.username)
        return super().log_change(request, obj, message)

    def log_deletions(self, request, queryset):
        ids = [str(obj.pk) for obj in queryset]
        audit('admin.deleted', model=self.model._meta.model_name, count=len(ids), ids=','.join(ids),
              by=request.user.username)
        return super().log_deletions(request, queryset)


def _when(moment):
    return timezone.localtime(moment).strftime('%Y-%m-%d %H:%M') if moment else '-'


# ========== Inline for Extra Files ==========
class NoteFileInline(admin.TabularInline):  # changes are logged with their note
    model = NoteFile
    extra = 1


# ========== Custom User Admin ==========
class CustomUserAdmin(AuditedAdmin, UserAdmin):
    model = CustomUser
    list_display = ('username', 'email', 'user_type', 'university', 'premium_until', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        (None, {
            'fields': (
                'user_type', 'university', 'gender', 'age',
                'city', 'department', 'profile_picture'
            )
        }),
        ('Premium', {
            'fields': ('premium_until',),
            'description': 'Set by approving purchases. Change it by hand only to correct a mistake.',
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {
            'fields': (
                'user_type', 'university', 'gender',
            )
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and 'premium_until' in form.changed_data:
            # Paid time changed by hand, not by approving an order: stands out in the log.
            audit('premium.changed_by_hand', level=logging.WARNING, user=obj.username,
                  before=_when(form.initial.get('premium_until')), after=_when(obj.premium_until),
                  by=request.user.username)


# ========== PremiumPackage Admin ==========
@admin.register(PremiumPackage)
class PremiumPackageAdmin(AuditedAdmin, admin.ModelAdmin):
    # Deleting uses Django's own action, which refuses packages that have orders (take them off sale instead).
    list_display = ('name', 'price', 'duration_in_months', 'is_active', 'description')
    list_editable = ('is_active',)
    search_fields = ('name',)
    list_filter = ('is_active', 'duration_in_months')


# ========== PremiumPurchase Admin ==========
@admin.register(PremiumPurchase)
class PremiumPurchaseAdmin(AuditedAdmin, admin.ModelAdmin):
    list_display = ['user', 'package_name', 'amount', 'status', 'timestamp', 'ends_at', 'reviewed_by']
    list_filter = ['status']
    readonly_fields = ['status', 'reviewed_at', 'reviewed_by', 'starts_at', 'ends_at']
    actions = ['approve_purchases']

    def approve_purchases(self, request, queryset):
        # One by one, so each order's months are added and the student is told (pending orders only)
        pending = queryset.filter(status=PremiumPurchase.Status.PENDING).select_related('user')
        approved = sum(approve_purchase(purchase, request.user) for purchase in pending)
        self.message_user(request, f"{approved} premium purchase(s) approved.")

    approve_purchases.short_description = "Approve selected premium purchases"


# ========== Note Admin with Verification ==========
@admin.register(Note)
class NoteAdmin(AuditedAdmin, admin.ModelAdmin):
    list_display = ('name', 'provider', 'subject', 'university', 'note_type', 'is_verified', 'is_rejected', 'view_file')
    list_filter = ('is_verified', ('rejected_at', admin.EmptyFieldListFilter), 'subject', 'university', 'note_type', 'year', 'semester')
    search_fields = ('name', 'caption', 'provider__username')
    inlines = [NoteFileInline]

    actions = ['verify_notes', 'reject_with_reason']

    def view_file(self, obj):
        # note files are served by the access-checked view, not their /media/ URL
        if not obj.file:
            return "-"
        return format_html("<a href='{}' target='_blank'>View</a>", reverse('note_file', args=[obj.id]))

    view_file.short_description = "Note File"

    @admin.display(boolean=True, description='Rejected')
    def is_rejected(self, obj):
        return obj.is_rejected

    def verify_notes(self, request, queryset):
        updated = publish_notes(queryset, by=request.user)
        self.message_user(request, f"{updated} note(s) marked as verified.")

    verify_notes.short_description = "Mark selected notes as verified"

    @admin.action(description="Reject selected notes (with a reason)")
    def reject_with_reason(self, request, queryset):
        """Same as rejecting in Manage -> Review notes: the note stays hidden and the provider is told why."""
        pending = queryset.awaiting_review().select_related('provider')
        reason = request.POST.get('reason', '').strip()[:1000]
        error = ''
        if request.POST.get('post') == 'yes':
            if reason:
                rejected = reject_notes(pending, reason, by=request.user)
                self.message_user(request, f"{rejected} note(s) rejected. The providers were told why.")
                return None
            error = 'Write a reason. The provider sees it and can fix the note.'
        return TemplateResponse(request, 'admin/core/note/reject_notes.html', {
            **self.admin_site.each_context(request),
            'title': 'Reject notes',
            'opts': self.model._meta,
            'queryset': queryset,
            'pending': pending,
            'skipped': queryset.count() - pending.count(),
            'reason': reason,
            'error': error,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
        })


# ========== Inbox: contact / feedback / ask-a-question ==========
@admin.register(InboxMessage)
class InboxMessageAdmin(AuditedAdmin, admin.ModelAdmin):
    list_display = ('created_at', 'kind', 'name', 'email', 'short_message', 'is_resolved')
    list_filter = ('kind', 'is_resolved')
    search_fields = ('name', 'email', 'message')
    readonly_fields = ('kind', 'name', 'email', 'message', 'user', 'created_at')
    actions = ['mark_resolved']

    @admin.display(description='Message')
    def short_message(self, obj):
        return obj.message if len(obj.message) <= 80 else obj.message[:77] + '...'

    @admin.action(description='Mark selected messages as resolved')
    def mark_resolved(self, request, queryset):
        ids = ','.join(str(i) for i in queryset.filter(is_resolved=False).values_list('id', flat=True))
        updated = queryset.update(is_resolved=True)
        if ids:
            audit('inbox.resolved', messages=ids, by=request.user.username)
        self.message_user(request, f"{updated} message(s) marked as resolved.")


# ========== Other Models ==========
class PlainAdmin(AuditedAdmin, admin.ModelAdmin):
    pass


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Subject, PlainAdmin)
admin.site.register(Topic, PlainAdmin)
admin.site.register(Review, PlainAdmin)
admin.site.register(Rating, PlainAdmin)
admin.site.register(NoteComment, PlainAdmin)


# ========== Following and notifications ==========
@admin.register(Follow)
class FollowAdmin(AuditedAdmin, admin.ModelAdmin):
    list_display = ('follower', 'provider', 'created_at')
    search_fields = ('follower__username', 'provider__username')
    raw_id_fields = ('follower', 'provider')


@admin.register(Notification)
class NotificationAdmin(AuditedAdmin, admin.ModelAdmin):
    list_display = ('created_at', 'recipient', 'kind', 'actor', 'note', 'is_read')
    list_filter = ('kind', 'is_read')
    search_fields = ('recipient__username', 'actor__username')
    raw_id_fields = ('recipient', 'actor', 'note')
