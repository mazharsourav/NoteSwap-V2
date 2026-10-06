import calendar
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.core.validators import MaxValueValidator, MinValueValidator
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from . import terms
from .validators import validate_upload

# Year of study and semester, as students count them (a 4-5 year degree, up to 3 semesters a year).
YEAR_OF_STUDY = [MinValueValidator(1, 'Use a year of study from 1 to 5.'),
                 MaxValueValidator(5, 'Use a year of study from 1 to 5.')]
SEMESTER = [MinValueValidator(1, 'Use a semester from 1 to 12.'),
            MaxValueValidator(12, 'Use a semester from 1 to 12.')]

# ========== Custom User Model ==========
class CustomUser(AbstractUser):
    USER_TYPES = (
        ('basic', 'Basic User'),
        ('provider', 'Provider'),
        ('moderator', 'Moderator'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='basic')
    university = models.CharField(max_length=255)
    gender = models.CharField(max_length=20)
    age = models.PositiveIntegerField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    department = models.CharField(max_length=255, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    # End of the paid Premium time; approving a purchase moves it forward (see PremiumPurchase.approve).
    premium_until = models.DateTimeField(null=True, blank=True)

    @property
    def is_premium(self):
        """The one Premium check: paid time that hasn't run out yet."""
        return self.premium_until is not None and self.premium_until > timezone.now()

# ========== Academic Models ==========

class Subject(models.Model):
    """A course, shown on the site as "Course": just a name ("Data Communication"), shared by every
    university. Each note says which university, year, semester and course code it's for."""
    name = models.CharField(max_length=255, unique=True)
    # No longer used (2026-10): a course is taught in different years at different universities.
    # Kept so old values aren't lost; notes carry their own year, semester and university.
    year = models.IntegerField(validators=YEAR_OF_STUDY, null=True, blank=True)
    semester = models.IntegerField(validators=SEMESTER, null=True, blank=True)
    university = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class Topic(models.Model):
    """No longer used on the site (2026-10): notes belong straight to a subject. Kept, with the
    existing names, so old notes keep that information and the change can be undone."""
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    year = models.IntegerField(validators=YEAR_OF_STUDY)
    semester = models.IntegerField(validators=SEMESTER)
    university = models.CharField(max_length=255)

    class Meta:
        unique_together = ('name', 'subject')  # ⛔ No duplicate topic names under the same subject

    def __str__(self):
        return self.name

# ========== Notes ==========
class NoteQuerySet(models.QuerySet):
    def awaiting_review(self):
        """New or changed notes a moderator hasn't decided on yet (not published, not rejected)."""
        return self.filter(is_verified=False, rejected_at__isnull=True)


class Note(models.Model):
    NOTE_TYPE = (
        ('image', 'Image'),
        ('pdf', 'PDF')
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='notes')
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True)  # legacy, see Topic
    provider = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    note_type = models.CharField(max_length=10, choices=NOTE_TYPE)
    file = models.FileField(upload_to='notes/', validators=[validate_upload])
    name = models.CharField(max_length=255)
    caption = models.TextField()
    course_code = models.CharField('course code', max_length=30, blank=True,
                                   help_text='The course code at this university, e.g. "CSE 301".')
    year = models.IntegerField(validators=YEAR_OF_STUDY)
    semester = models.IntegerField(validators=SEMESTER)
    university = models.CharField(max_length=255)  # a code from core/universities.py, or a typed name
    is_verified = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(default=timezone.now)
    # Set when a moderator rejects the note; cleared when the provider sends it for review again.
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    objects = NoteQuerySet.as_manager()

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.subject_id is None and self.topic_id is not None:  # older code paths that still pass a topic
            self.subject_id = Topic.objects.values_list('subject_id', flat=True).get(pk=self.topic_id)
        super().save(*args, **kwargs)

    @property
    def is_rejected(self):
        return self.rejected_at is not None

    @property
    def term(self):
        """'2-1' (year 2, semester 1), or 'Year 1, Sem 6' for an older note that doesn't fit."""
        return terms.describe(self.year, self.semester)

# ✅ New: Additional files for a note
class NoteFile(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='notes/', validators=[validate_upload])
    is_verified = models.BooleanField(default=False)  # ✅ New field
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Extra File for {self.note.name}"


# ========== Reviews & Comments ==========
class Review(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    comment = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

class Rating(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    score = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['note', 'user'], name='unique_rating_per_user_and_note'),
        ]

class NoteComment(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    comment = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

# ========== Following providers ==========
class Follow(models.Model):
    """A user following a provider, to hear about the provider's new notes."""
    follower = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='following')
    provider = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['follower', 'provider'], name='unique_follow'),
            models.CheckConstraint(condition=~models.Q(follower=models.F('provider')), name='no_self_follow'),
        ]

    def __str__(self):
        return f"{self.follower} follows {self.provider}"


class Notification(models.Model):
    """An in-app notification, shown under the navbar bell."""

    class Kind(models.TextChoices):
        NEW_NOTE = 'new_note', 'New note from a provider you follow'
        NEW_FOLLOWER = 'new_follower', 'New follower'
        NOTE_REJECTED = 'note_rejected', 'Your note was not approved'
        PREMIUM_APPROVED = 'premium_approved', 'Your Premium order was approved'
        PREMIUM_REJECTED = 'premium_rejected', 'Your Premium order was not approved'
        PREMIUM_ENDING = 'premium_ending', 'Your Premium ends soon'
        PREMIUM_ENDED = 'premium_ended', 'Your Premium has ended'
        PREMIUM_ORDER = 'premium_order', 'New Premium order to review'

    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    actor = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    note = models.ForeignKey('Note', on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    purchase = models.ForeignKey('PremiumPurchase', on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['recipient', 'is_read'], name='notification_unread_idx')]

    def __str__(self):
        return f"{self.get_kind_display()} for {self.recipient}"

    @property
    def text(self):
        actor = (self.actor.get_full_name() or self.actor.username) if self.actor else 'Someone'
        if self.kind == self.Kind.NEW_NOTE:
            return f'{actor} published a new note: "{self.note.name}"'
        if self.kind == self.Kind.NEW_FOLLOWER:
            return f'{actor} started following you'
        if self.kind == self.Kind.NOTE_REJECTED:
            return f'Your note "{self.note.name}" wasn\'t approved. See why and send it again.'
        if self.kind == self.Kind.PREMIUM_APPROVED:
            until = date_format(timezone.localtime(self.purchase.ends_at), 'j M Y')
            return f'Your {self.purchase.package_name} order was approved. Premium runs until {until}.'
        if self.kind == self.Kind.PREMIUM_REJECTED:
            return f'Your {self.purchase.package_name} order wasn\'t approved. See why and order again.'
        if self.kind == self.Kind.PREMIUM_ENDING:
            return 'Your Premium ends in less than a week. Renew it to keep asking on NoteSolve.'
        if self.kind == self.Kind.PREMIUM_ENDED:
            return 'Your Premium has ended. Your past NoteSolve answers are still there.'
        if self.kind == self.Kind.PREMIUM_ORDER:
            return f'{actor} ordered {self.purchase.package_name} (৳ {self.purchase.amount:.0f}). Check the payment.'
        return self.get_kind_display()

    @property
    def url(self):
        if self.kind in (self.Kind.NEW_NOTE, self.Kind.NOTE_REJECTED):
            return reverse('note_detail', args=[self.note_id])
        if self.kind == self.Kind.NEW_FOLLOWER:
            return reverse('user_profile', args=[self.actor_id])
        if self.kind == self.Kind.PREMIUM_ORDER:
            return reverse('manage_premium')
        if self.kind == self.Kind.PREMIUM_ENDED:
            return reverse('notesolve_dashboard')
        if self.kind in (self.Kind.PREMIUM_APPROVED, self.Kind.PREMIUM_REJECTED, self.Kind.PREMIUM_ENDING):
            return reverse('premium_packages')
        return reverse('notifications')


class ProviderRequest(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    university = models.CharField(max_length=255)
    department = models.CharField(max_length=255)
    cgpa = models.DecimalField(max_digits=4, decimal_places=2)
    gender = models.CharField(max_length=20)
    nationality = models.CharField(max_length=100)
    profession = models.CharField(max_length=100)
    address = models.TextField()
    phone_number = models.CharField(max_length=20)
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'

    REAPPLY_COOLDOWN = timedelta(days=30)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    rejection_reason = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Provider Request: {self.user.username}"

    @property
    def can_reapply_at(self):
        """When a rejected applicant may apply again (None = right away)."""
        if self.status != self.Status.REJECTED or self.reviewed_at is None:
            return None
        return self.reviewed_at + self.REAPPLY_COOLDOWN

    @property
    def can_reapply(self):
        return self.can_reapply_at is None or timezone.now() >= self.can_reapply_at

def add_months(moment, months):
    """`moment` plus whole calendar months in local time (31 Jan + 1 month = 28/29 Feb)."""
    local = timezone.localtime(moment)
    month_index = local.month - 1 + months
    year, month = local.year + month_index // 12, month_index % 12 + 1
    return local.replace(year=year, month=month, day=min(local.day, calendar.monthrange(year, month)[1]))


class PremiumPurchase(models.Model):
    """One Premium order. Kept forever, approved or rejected, as the payment record."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Waiting for approval'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    # A package with orders can't be deleted, only taken off sale (PremiumPackage.is_active).
    package = models.ForeignKey('PremiumPackage', on_delete=models.PROTECT, null=True, blank=True,
                                related_name='purchases')
    # Copied from the package when ordering, so later package edits don't change past orders.
    package_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    duration_in_months = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(36)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    rejection_reason = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)  # when the student ordered
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    # The paid time this order added (set on approval).
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.package_name}"

    def approve(self, reviewer=None):
        """Approve a waiting order and add its months to the user's Premium.

        The months start now, or when the user's current Premium ends, so renewals stack.
        Returns False (and changes nothing) if the order was already reviewed.
        """
        with transaction.atomic():
            order = PremiumPurchase.objects.select_for_update().get(pk=self.pk)
            if order.status != self.Status.PENDING:
                return False
            user = CustomUser.objects.select_for_update().get(pk=self.user_id)
            now = timezone.now()
            self.starts_at = max(now, user.premium_until) if user.premium_until else now
            self.ends_at = add_months(self.starts_at, self.duration_in_months)
            self.status, self.reviewed_at, self.reviewed_by, self.rejection_reason = (
                self.Status.APPROVED, now, reviewer, '')
            self.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'rejection_reason', 'starts_at', 'ends_at'])
            user.premium_until = self.ends_at
            user.save(update_fields=['premium_until'])
        if 'user' in self._state.fields_cache:
            self.user.premium_until = self.ends_at
        return True

    def reject(self, reason, reviewer=None):
        """Reject a waiting order; the student sees the reason and can order again."""
        updated = PremiumPurchase.objects.filter(pk=self.pk, status=self.Status.PENDING).update(
            status=self.Status.REJECTED, rejection_reason=reason, reviewed_at=timezone.now(), reviewed_by=reviewer,
        )
        if updated:
            self.refresh_from_db()
        return bool(updated)

class NoteSolveRequest(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    university = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    semester = models.CharField(max_length=20)
    year = models.IntegerField(validators=YEAR_OF_STUDY)
    subject = models.CharField(max_length=100)
    topic = models.CharField(max_length=100)
    problem_description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    requested_to = models.ForeignKey(CustomUser, on_delete=models.CASCADE,related_name='received_notesolve_requests')

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SOLVED = 'solved', 'Solved'
        REJECTED = 'rejected', 'Rejected'

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    rejection_reason = models.TextField(blank=True)


class NoteSolveFile(models.Model):
    solve_request = models.ForeignKey(NoteSolveRequest, related_name='files', on_delete=models.CASCADE)
    file = models.FileField(upload_to='notesolve_files/', validators=[validate_upload])
    uploaded_at = models.DateTimeField(auto_now_add=True)



class NoteSolveSolution(models.Model):
    solve_request = models.ForeignKey(
        'NoteSolveRequest',
        on_delete=models.CASCADE,
        related_name='solutions'  # 🔧 Required for reverse querying
    )
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    solution_text = models.TextField(blank=True)
    file = models.FileField(upload_to='note_solve_solutions/', null=True, blank=True, validators=[validate_upload])
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)
    rating = models.IntegerField(  # given by the requester after review
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    def __str__(self):
        return f"Solution by {self.provider.username} for request #{self.solve_request.id}"


class PremiumPackage(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2,
                                validators=[MinValueValidator(1, 'The price must be at least 1 taka.')])
    duration_in_months = models.IntegerField(validators=[
        MinValueValidator(1, 'Use 1 to 36 months.'), MaxValueValidator(36, 'Use 1 to 36 months.'),
    ])
    # Off-sale packages are hidden from the pricing page but stay linked to past orders.
    is_active = models.BooleanField('on sale', default=True)

    def __str__(self):
        return self.name


class InboxMessage(models.Model):
    """Messages sent through the Contact, Feedback and Ask-a-Question forms."""

    class Kind(models.TextChoices):
        CONTACT = 'contact', 'Contact'
        FEEDBACK = 'feedback', 'Feedback'
        QUESTION = 'question', 'Question'

    kind = models.CharField(max_length=10, choices=Kind.choices)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_kind_display()} from {self.name}"
