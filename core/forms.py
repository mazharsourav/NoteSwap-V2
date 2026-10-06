import io
import os

from django import forms
from django.core.files.base import ContentFile
from django.core.validators import MaxValueValidator, MinValueValidator
from PIL import Image, ImageOps

from . import terms, universities
from .models import (
    CustomUser, InboxMessage, Note, NoteComment, NoteSolveFile, NoteSolveRequest, NoteSolveSolution,
    PremiumPackage, ProviderRequest, Rating, Review, Subject,
)
from .validators import UPLOAD_ACCEPT, detect_file_kind, log_if_unexpected, refused, validate_upload

FILE_WIDGET = forms.ClearableFileInput(attrs={'accept': UPLOAD_ACCEPT})


class NumberLimitsMixin:
    """Put the model's min/max checks on the number inputs (min="1" max="5"), so the browser
    checks them too. The server still checks them when the form is validated."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.NumberInput):
                continue
            for validator in self._meta.model._meta.get_field(name).validators:
                if isinstance(validator, MinValueValidator):
                    field.widget.attrs['min'] = validator.limit_value
                elif isinstance(validator, MaxValueValidator):
                    field.widget.attrs['max'] = validator.limit_value


# ========== Accounts ==========
GENDER_CHOICES = [('', 'Choose one'), ('Female', 'Female'), ('Male', 'Male'), ('Other', 'Other'),
                  ('Prefer not to say', 'Prefer not to say')]


class GenderChoiceField(forms.ChoiceField):
    """Gender as a dropdown. Older free-text values ("male", "FEMALE") still match their choice."""

    def __init__(self, **kwargs):
        for unused in ('max_length', 'empty_value'):  # passed when built from the model's CharField
            kwargs.pop(unused, None)
        super().__init__(choices=GENDER_CHOICES, **kwargs)

    def prepare_value(self, value):
        for choice, _ in GENDER_CHOICES:
            if choice and value and choice.lower() == str(value).strip().lower():
                return choice
        return value

    def to_python(self, value):
        return self.prepare_value(super().to_python(value))


class UniversityWidget(forms.MultiWidget):
    """A <select> of listed universities (with "Other") plus a text box for "Other". js/core/university.js
    turns it into a type-to-search picker; without JavaScript both controls simply show."""
    template_name = 'core/widgets/university.html'

    def __init__(self, attrs=None):
        super().__init__({
            'choice': forms.Select(choices=universities.choices()),
            'other': forms.TextInput(attrs={'maxlength': 100, 'placeholder': 'Your university’s full name',
                                            'autocomplete': 'organization'}),
        }, attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['subwidgets'][1]['attrs'].pop('required', None)  # only needed for "Other"
        return context

    def decompress(self, value):
        if not value:
            return ['', '']
        return [value, ''] if value in universities.NAMES else [universities.OTHER, value]

    def id_for_label(self, id_):
        return f'{id_}_0' if id_ else ''

    def value_from_datadict(self, data, files, name):
        # A plain `university=...` (instead of the picker's two parts) is accepted too and matched to the list.
        if f'{name}_choice' not in data and name in data:
            value = universities.normalize(data.get(name))
            return [value, ''] if value in universities.NAMES or not value else [universities.OTHER, value]
        return super().value_from_datadict(data, files, name)

    def value_omitted_from_data(self, data, files, name):
        return name not in data and super().value_omitted_from_data(data, files, name)


class UniversityField(forms.MultiValueField):
    """Pick a university from the list (stored as its code, e.g. "UAP") or type another one."""
    widget = UniversityWidget

    def __init__(self, **kwargs):
        for unused in ('max_length', 'empty_value'):  # passed when built from the model's CharField
            kwargs.pop(unused, None)
        kwargs.setdefault('label', 'University')
        kwargs.setdefault('error_messages', {'required': 'Choose your university.'})
        fields = (forms.CharField(required=False), forms.CharField(required=False, max_length=100))
        super().__init__(fields, require_all_fields=False, **kwargs)

    def compress(self, values):
        choice, other = (list(values) + ['', ''])[:2]
        if not choice:
            if self.required:
                raise forms.ValidationError('Choose your university.', code='required')
            return ''
        if choice == universities.OTHER:
            name = universities.normalize(other)
            if not name:
                raise forms.ValidationError('Type the name of your university.', code='required')
            return name
        if choice not in universities.NAMES:
            raise forms.ValidationError('Choose a university from the list.', code='invalid_choice')
        return choice


class SignupProfileForm(forms.Form):
    """
    Extra sign-up fields, added by allauth to both the normal sign-up form and the
    "complete your profile" form shown to new Google users (ACCOUNT_SIGNUP_FORM_CLASS).
    Username, email and password fields come from allauth. New users are always 'basic'.
    """
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    university = UniversityField()
    gender = GenderChoiceField()

    def signup(self, request, user):
        for field in ('first_name', 'last_name', 'university', 'gender'):
            setattr(user, field, self.cleaned_data[field])
        user.user_type = 'basic'
        user.save()


PHOTO_ACCEPT = '.jpg,.jpeg,.png,.webp'
PHOTO_MAX_UPLOAD = 10 * 1024 * 1024  # 10 MB
PHOTO_MAX_SIDE = 400  # px: the largest avatar is 104 px, so this is sharp on 3x screens


def shrink_photo(upload):
    """A profile photo as a small JPEG: turned the way the phone held it, at most PHOTO_MAX_SIDE px."""
    with Image.open(upload) as image:
        image.draft('RGB', (PHOTO_MAX_SIDE * 2, PHOTO_MAX_SIDE * 2))  # big JPEGs decode at a smaller size
        image = ImageOps.exif_transpose(image)
        image.thumbnail((PHOTO_MAX_SIDE, PHOTO_MAX_SIDE), Image.LANCZOS)
        if image.mode in ('RGBA', 'LA', 'P'):  # transparent PNG / WEBP: on white
            image = image.convert('RGBA')
            background = Image.new('RGB', image.size, 'white')
            background.paste(image, mask=image.getchannel('A'))
            image = background
        buffer = io.BytesIO()
        image.convert('RGB').save(buffer, 'JPEG', quality=85, optimize=True)
    stem = os.path.splitext(os.path.basename(upload.name))[0][:80] or 'photo'
    return ContentFile(buffer.getvalue(), name=f'{stem}.jpg')


class UserProfileForm(forms.ModelForm):
    # Email is changed on the "Email addresses" page, where the new address is verified.
    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'university',
            'gender', 'age', 'city', 'department', 'profile_picture'
        ]
        field_classes = {'gender': GenderChoiceField, 'university': UniversityField}

    def clean_profile_picture(self):
        photo = self.cleaned_data.get('profile_picture')
        if not photo or getattr(photo, '_committed', False):
            return photo  # removed, or the current photo kept
        if photo.size > PHOTO_MAX_UPLOAD:
            refused(photo, 'photo too large')
            raise forms.ValidationError('This photo is too large. The maximum is 10 MB.')
        if detect_file_kind(photo) not in ('jpeg', 'png', 'webp'):
            refused(photo, 'photo type')
            raise forms.ValidationError('Use a JPG, PNG or WEBP photo.')
        try:
            return shrink_photo(photo)
        except Exception as error:
            log_if_unexpected(error, f'the profile photo {photo.name!r}')
            refused(photo, 'damaged photo')
            raise forms.ValidationError('This photo could not be read. Try another one.')


# ========== Notes ==========
class TermSelect(forms.Select):
    """The Semester dropdown ("2-1"). A post with plain year= and semester= works too."""

    def value_from_datadict(self, data, files, name):
        if name not in data and 'year' in data and 'semester' in data:
            return f"{data.get('year')}-{data.get('semester')}"
        return super().value_from_datadict(data, files, name)

    def value_omitted_from_data(self, data, files, name):
        return name not in data and 'year' not in data and super().value_omitted_from_data(data, files, name)


class TermField(forms.ChoiceField):
    """Year and semester in one choice, written "2-1" (see core/terms.py)."""
    widget = TermSelect

    def __init__(self, **kwargs):
        kwargs.setdefault('label', 'Semester')
        kwargs.setdefault('error_messages', {'required': 'Choose the semester.',
                                             'invalid_choice': 'Choose a semester from the list, like 2-1.'})
        super().__init__(choices=terms.choices(), **kwargs)


class NoteUploadForm(NumberLimitsMixin, forms.ModelForm):
    """Upload or edit a note. Year and semester are picked together as one "2-1" choice (`term`)."""
    term = TermField(help_text='2-1 means year 2, semester 1.')

    class Meta:
        model = Note
        fields = ['name', 'caption', 'file', 'subject', 'course_code', 'university']
        labels = {'subject': 'Course'}
        field_classes = {'university': UniversityField}
        widgets = {'file': FILE_WIDGET,
                   'course_code': forms.TextInput(attrs={'placeholder': 'e.g. CSE 301', 'autocapitalize': 'characters'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subject'].queryset = Subject.objects.order_by('name')
        self.fields['subject'].empty_label = 'Choose a course'
        self.fields['course_code'].help_text = ''  # the placeholder says it; a hint would make its row uneven
        note = self.instance
        if note.pk and terms.fits(note.year, note.semester):  # an older "Sem 6" note has to pick again
            self.initial.setdefault('term', terms.label(note.year, note.semester))

    def clean_course_code(self):
        return ' '.join(self.cleaned_data['course_code'].split()).upper()

    def clean(self):
        cleaned = super().clean()
        picked = terms.parse(cleaned.get('term'))
        if picked:
            self.instance.year, self.instance.semester = picked
        return cleaned


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """A file field that takes several files and returns them as a list (checked in the form)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'accept': UPLOAD_ACCEPT}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        uploads = [upload for upload in (data if isinstance(data, (list, tuple)) else [data]) if upload]
        if not uploads:
            raise forms.ValidationError('Choose at least one file.', code='required')
        return uploads


class NoteFilesForm(forms.Form):
    """Several additional files for a note at once. All or nothing: one bad file and none are added,
    with each problem named by its file."""
    MAX_FILES = 20
    files = MultipleFileField(label='Files')

    def clean_files(self):
        uploads = self.cleaned_data['files']
        if len(uploads) > self.MAX_FILES:
            raise forms.ValidationError(f'Add up to {self.MAX_FILES} files at a time.')
        problems = []
        for upload in uploads:
            try:
                validate_upload(upload)
            except forms.ValidationError as error:
                problems += [f'{upload.name}: {message}' for message in error.messages]
        if problems:
            raise forms.ValidationError(problems)
        return uploads


class NoteRatingForm(forms.ModelForm):
    class Meta:
        model = Rating
        fields = ['score']


class NoteCommentForm(forms.ModelForm):
    MAX_LENGTH = 2000
    comment = forms.CharField(max_length=MAX_LENGTH, widget=forms.Textarea(attrs={'rows': 2}))

    class Meta:
        model = NoteComment
        fields = ['comment']


class SubjectForm(forms.ModelForm):
    """Add a course: just its name. Universities, years and codes belong to each note."""

    class Meta:
        model = Subject
        fields = ['name']
        labels = {'name': 'Course name'}

    def clean_name(self):
        name = ' '.join(self.cleaned_data.get('name', '').split())
        existing = Subject.objects.filter(name__iexact=name).first()
        if existing:
            raise forms.ValidationError(f'“{existing.name}” is already in the list. Pick it from the courses.')
        return name


# ========== Site reviews ==========
class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Write your comment here...',
                'class': 'form-control'
            }),
        }


# ========== Provider applications ==========
class ProviderRequestForm(forms.ModelForm):
    class Meta:
        model = ProviderRequest
        exclude = ['user', 'status', 'submitted_at', 'rejection_reason', 'reviewed_at']
        field_classes = {'gender': GenderChoiceField, 'university': UniversityField}
        widgets = {'address': forms.Textarea(attrs={'rows': 3})}


# ========== Inbox: contact / feedback / ask-a-question ==========
class InboxMessageForm(forms.ModelForm):
    class Meta:
        model = InboxMessage
        fields = ['name', 'email', 'message']
        widgets = {'message': forms.Textarea(attrs={'rows': 5})}


class AskQuestionForm(InboxMessageForm):
    class Meta(InboxMessageForm.Meta):
        labels = {'message': 'Question'}


class FeedbackForm(InboxMessageForm):
    class Meta(InboxMessageForm.Meta):
        labels = {'message': 'Feedback'}


class ContactForm(InboxMessageForm):
    pass


# ========== NoteSolve ==========
class NoteSolveRequestForm(NumberLimitsMixin, forms.ModelForm):
    class Meta:
        model = NoteSolveRequest
        fields = ['university', 'department', 'semester', 'year', 'subject', 'topic', 'problem_description']
        field_classes = {'university': UniversityField}


class NoteSolveFileForm(forms.ModelForm):
    class Meta:
        model = NoteSolveFile
        fields = ['file']
        widgets = {'file': FILE_WIDGET}


class SolveForm(forms.ModelForm):
    class Meta:
        model = NoteSolveSolution
        fields = ['solution_text', 'file']
        widgets = {'file': FILE_WIDGET}

    def clean(self):
        cleaned_data = super().clean()
        if not self.errors and not cleaned_data.get('solution_text', '').strip() and not cleaned_data.get('file'):
            raise forms.ValidationError('Write an explanation or attach your worked solution (or both).')
        return cleaned_data


class SolutionRatingForm(forms.ModelForm):
    """The requester rates a provider's NoteSolve solution."""

    rating = forms.IntegerField(min_value=1, max_value=5)  # required here, though blank in the model

    class Meta:
        model = NoteSolveSolution
        fields = ['rating']


# ========== Premium ==========
class PremiumPackageForm(NumberLimitsMixin, forms.ModelForm):
    class Meta:
        model = PremiumPackage
        fields = ['name', 'price', 'duration_in_months', 'description']
