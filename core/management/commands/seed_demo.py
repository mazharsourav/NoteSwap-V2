"""Fill an empty database with a ready-to-show demo: a superuser, demo accounts for every role, the UAP
CSE courses, sample notes (as real PDFs), ratings, follows, Premium packages and one NoteSolve request.

    python manage.py seed_demo --admin-email you@example.com

Passwords are never stored in the code. Set them in the environment (SEED_ADMIN_PASSWORD,
SEED_DEMO_PASSWORD) or pass --admin-password / --demo-password; anything not given is generated and
printed once at the end. Safe to run again: whatever already exists is left as it is.
"""
import os
import secrets
import textwrap
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from core import demo_data as data
from core.models import (CustomUser, Follow, Note, NoteComment, NoteSolveRequest, PremiumPackage, PremiumPurchase,
                         Rating, Subject)
from core.notifications import approve_purchase, notify_new_follower, publish_notes


class Command(BaseCommand):
    help = 'Create a superuser, demo accounts, the UAP CSE courses and sample notes for a demo site.'

    def add_arguments(self, parser):
        parser.add_argument('--admin-username', default=os.environ.get('SEED_ADMIN_USERNAME', 'admin'))
        parser.add_argument('--admin-email', default=os.environ.get('SEED_ADMIN_EMAIL', ''),
                            help='Your real email: password resets and error emails go here.')
        parser.add_argument('--admin-password', default=os.environ.get('SEED_ADMIN_PASSWORD', ''),
                            help='Default: $SEED_ADMIN_PASSWORD, else a generated one.')
        parser.add_argument('--demo-password', default=os.environ.get('SEED_DEMO_PASSWORD', ''),
                            help='One password for every demo_* account. Default: $SEED_DEMO_PASSWORD, '
                                 'else a generated one.')
        parser.add_argument('--no-admin', action='store_true', help="Don't create the superuser.")

    def handle(self, *args, **options):
        self.generated, self.used = {}, set()
        admin_email = options['admin_email'] or f"{options['admin_username']}@example.com"
        admin_password = self.password(options['admin_password'], 'admin')
        demo_password = self.password(options['demo_password'], 'demo')

        with transaction.atomic():
            admin = None if options['no_admin'] else self.user(
                'admin', options['admin_username'], admin_email, admin_password,
                first_name='Site', last_name='Admin', user_type='basic', gender='Other',
                is_staff=True, is_superuser=True)
            people = {key: self.user('demo', info['username'], f"{info['username']}@example.com", demo_password,
                                     **{k: v for k, v in info.items() if k != 'username'})
                      for key, info in data.ACCOUNTS.items()}
            courses = self.courses()
            self.follows(people)
            self.notes(people, courses)
            self.feedback(people)
            self.premium(people, reviewer=admin or people['moderator'])
            self.notesolve(people)

        self.report(options, admin)

    # --- accounts -------------------------------------------------------------------------------

    def password(self, given, label):
        if given:
            try:
                validate_password(given)
            except ValidationError as error:
                raise CommandError(f'The {label} password is too weak: {" ".join(error.messages)}')
            return given
        self.generated[label] = secrets.token_urlsafe(12)
        return self.generated[label]

    def user(self, label, username, email, password, **fields):
        """`label` says which password this is ('admin' or 'demo'), so only passwords set get printed."""
        user = CustomUser.objects.filter(username=username).first()
        if user:
            self.line('kept', f'account {username} (already exists, password unchanged)')
            return user
        self.used.add(label)
        user = CustomUser(username=username, email=email, university=data.UNIVERSITY,
                          department=data.DEPARTMENT, **fields)
        user.set_password(password)
        user.save()
        # Sign-in needs a confirmed email address; these are confirmed from the start.
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        self.line('created', f"account {username} ({'superuser' if user.is_superuser else user.user_type})")
        return user

    def follows(self, people):
        pairs = [('basic', 'provider'), ('basic', 'provider2'),
                 ('premium', 'provider'), ('premium', 'provider2'), ('premium', 'provider3')]
        for follower, provider in pairs:
            follow, created = Follow.objects.get_or_create(follower=people[follower], provider=people[provider])
            if created:
                notify_new_follower(follow)

    # --- courses and notes ----------------------------------------------------------------------

    def courses(self):
        by_code, created = {}, 0
        for code, title, *_ in data.COURSES:
            by_code[code], new = Subject.objects.get_or_create(name=title)
            created += new
        self.line('created', f'{created} courses ({len(data.COURSES) - created} already there)')
        return by_code

    def notes(self, people, courses):
        info = {code: (title, credits, year, semester, kind)
                for code, title, credits, year, semester, kind in data.COURSES}
        now, created, to_publish = timezone.now(), 0, []
        for code, provider_key, name, published, days_ago, sections in data.NOTES:
            provider = people[provider_key]
            if Note.objects.filter(provider=provider, name=name).exists():
                continue
            title, credits, year, semester, kind = info[code]
            note = Note(subject=courses[code], provider=provider, name=name, note_type='pdf',
                        course_code=code, year=year, semester=semester, university=data.UNIVERSITY,
                        uploaded_at=now - timedelta(days=days_ago, hours=secrets.randbelow(10)),
                        caption=f'{code} {title} ({kind.lower()}, {credits:g} credits), year {year} '
                                f'semester {semester}. ' + ' '.join(h + '.' for h, _ in sections))
            pdf = note_pdf(name, f'{code}  {title}',
                           f'University of Asia Pacific  |  {year}-{semester}  |  {credits:g} credits  |  '
                           f'by {provider.get_full_name()}', sections)
            note.file.save(f'{slugify(code)}-{slugify(name)[:60]}.pdf', ContentFile(pdf), save=False)
            note.save()
            created += 1
            if published:
                to_publish.append(note.id)
        publish_notes(Note.objects.filter(id__in=to_publish), by=people['moderator'])
        if created:
            self.line('created', f'{created} notes ({len(to_publish)} published, the rest wait for review)')
        else:
            self.line('kept', 'all sample notes (already there)')

    def feedback(self, people):
        for name, reader, stars, comment in data.FEEDBACK:
            note = Note.objects.filter(name=name).first()
            if note is None or note.provider_id == people[reader].id:
                continue  # providers can't rate their own notes
            Rating.objects.get_or_create(note=note, user=people[reader], defaults={'score': stars})
            if comment:
                NoteComment.objects.get_or_create(note=note, user=people[reader], comment=comment)

    # --- Premium and NoteSolve ------------------------------------------------------------------

    def premium(self, people, reviewer):
        for name, description, price, months in data.PREMIUM_PACKAGES:
            PremiumPackage.objects.get_or_create(
                name=name, defaults={'description': description, 'price': price, 'duration_in_months': months})
        student = people['premium']
        if not student.is_premium:
            package = PremiumPackage.objects.get(name='Semester')
            order = PremiumPurchase.objects.create(
                user=student, package=package, package_name=package.name, amount=package.price,
                duration_in_months=package.duration_in_months)
            approve_purchase(order, reviewer)
            self.line('created', f'Premium for {student.username} ({package.duration_in_months} months)')

    def notesolve(self, people):
        NoteSolveRequest.objects.get_or_create(
            user=people['premium'], requested_to=people['provider2'], subject='Data Structures and Algorithms I',
            defaults={'university': data.UNIVERSITY, 'department': data.DEPARTMENT, 'year': 2, 'semester': '1',
                      'topic': 'Quick sort',
                      'problem_description': 'Why is quick sort O(n log n) on average but O(n^2) in the worst '
                                             'case? Please show it with the array 1, 2, 3, 4, 5.'})

    # --- output ---------------------------------------------------------------------------------

    def line(self, what, text):
        self.stdout.write(f'  {what:8} {text}')

    def report(self, options, admin):
        self.stdout.write(self.style.SUCCESS('\nDemo data ready.'))
        if admin:
            self.stdout.write(f'  Superuser: {admin.username} ({admin.email})')
        self.stdout.write('  Demo accounts: ' + ', '.join(info['username'] for info in data.ACCOUNTS.values()))
        generated = {label: value for label, value in self.generated.items() if label in self.used}
        if generated:
            self.stdout.write(self.style.WARNING('\nGenerated passwords (shown once, save them now):'))
            for label, value in generated.items():
                who = options['admin_username'] if label == 'admin' else 'every demo_* account'
                self.stdout.write(f'  {who}: {value}')


# --- a small PDF writer (no extra library needed) --------------------------------------------------

PAGE_W, PAGE_H, MARGIN = 595, 842, 56   # A4 in points
GREEN = '0.09 0.45 0.29'


def _text(value):
    value = value.encode('latin-1', 'replace').decode('latin-1')
    return value.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def note_pdf(title, course, meta, sections):
    """A simple, readable A4 note: title, course line, then each section's points."""
    lines = [('F2', 20, GREEN, part, 26) for part in textwrap.wrap(title, 40)]
    lines += [('F1', 11, '0 0 0', course, 22), ('F1', 9, '0.4 0.4 0.4', meta, 30)]
    for heading, points in sections:
        lines.append(('F2', 13, GREEN, heading, 22))
        for point in points:
            for i, part in enumerate(textwrap.wrap(point, 82)):
                lines.append(('F1', 11, '0.1 0.1 0.1', ('-  ' if i == 0 else '   ') + part, 17))
        lines.append(('F1', 11, '0 0 0', '', 10))

    pages, current, y = [], [], PAGE_H - MARGIN
    for font, size, color, text, step in lines:
        if y - step < MARGIN:
            pages.append(current)
            current, y = [], PAGE_H - MARGIN
        y -= step
        if text:
            current.append(f'{color} rg BT /{font} {size} Tf {MARGIN} {y} Td ({_text(text)}) Tj ET')
    pages.append(current)

    footer = 'NoteSwap demo note. Sample content for showing the site.'
    objects = ['<< /Type /Catalog /Pages 2 0 R >>', None,
               '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
               '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>']
    kids = []
    for number, commands in enumerate(pages, 1):
        stream = '\n'.join(commands + [
            f'0.6 0.6 0.6 rg BT /F1 8 Tf {MARGIN} 30 Td ({_text(footer)}  Page {number} of {len(pages)}) Tj ET',
        ])
        objects.append(f'<< /Length {len(stream.encode("latin-1"))} >>\nstream\n{stream}\nendstream')
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] '
                       f'/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {len(objects)} 0 R >>')
        kids.append(f'{len(objects)} 0 R')
    objects[1] = f'<< /Type /Pages /Kids [{" ".join(kids)}] /Count {len(kids)} >>'

    out, offsets = bytearray(b'%PDF-1.4\n'), []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f'{number} 0 obj\n{body}\nendobj\n'.encode('latin-1')
    xref = len(out)
    out += f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n'.encode()
    out += ''.join(f'{offset:010d} 00000 n \n' for offset in offsets).encode()
    out += f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    return bytes(out)
