# NoteSwap

A note-sharing platform for university students. Providers upload notes that admins verify, students browse and rate them, and premium users can send problems to providers through **NoteSolve**.

**Live demo: [mazharsourav.pythonanywhere.com](https://mazharsourav.pythonanywhere.com)**

[![NoteSwap home page](.github/screenshots/home.png)](https://mazharsourav.pythonanywhere.com)

Built with Django 5.2 (LTS) and server-rendered templates. The demo runs on sample data: the
[UAP BSc in CSE](https://cse.uap-bd.edu/academics/courses/) course list and made-up accounts and notes.

## Project structure

```
.
├── config/                 Django project config (settings, root urls, wsgi/asgi)
├── core/                   Main app: models, forms, urls, migrations, template tags
│   ├── views/              One module per area: accounts, notes, providers, pages, social
│   │                       (following + notifications), notesolve, premium, dashboard, files
│   ├── notifications.py    Creating notifications (publishing / rejecting notes, new followers)
│   ├── file_cleanup.py     Removes stored files once nothing uses them (deleted, rejected, replaced)
│   ├── help_content.py     Help Center articles and FAQs
│   └── templatetags/ui.py  {% icon %}, {% avatar %}, {% stars %} for the templates
├── templates/              All page templates, grouped by area
│   ├── base.html           Site shell: header, footer, messages, shared CSS/JS
│   ├── partials/           header (with account menu + phone menu), footer, messages, logo
│   ├── components/         reusable pieces: note card, provider card, follow button,
│   │                       form field, file drop zone, pagination
│   ├── pages/              home, about, contact, terms, help center + articles, feedback
│   ├── account/            sign in, sign up, password field, settings sidebar (allauth overrides)
│   ├── socialaccount/      "complete your profile" step after Google sign-in
│   ├── allauth/            layouts + elements: every other allauth page uses the site design
│   ├── accounts/           profile, edit profile, user profile, user search
│   ├── notes/              subjects, topics, note list/detail/upload/edit, search, review queue
│   ├── providers/          provider list/detail, apply, provider applications
│   ├── notesolve/          NoteSolve page, provider inbox, answer page
│   ├── premium/            pricing, checkout, package form
│   ├── social/             following, notifications
│   └── dashboard/          Manage layout, overview, inbox, Premium
├── static/
│   ├── css/base/           tokens.css (every colour, size, timing), base.css, layout.css
│   ├── css/components/     buttons, forms, cards, header, footer, messages, navigation, dialogs
│   ├── css/pages/          one file per area, loaded only on its pages ({% block styles %})
│   ├── js/core/            menus, messages, dialogs, form helpers, scroll motion, POST links,
│   │                       reader.js (the PDF / photo reader, an ES module)
│   ├── js/pages/           page-only scripts (note reader, file preview pop-up, note form, manage tables, help search)
│   ├── vendor/pdfjs/       PDF.js 6.3.289 (Mozilla, Apache-2.0): draws PDFs on the note page
│   └── img/                brand/mark.svg (logo + favicon), team/
├── media/                  User uploads (local dev only, not committed)
├── manage.py
├── requirements.txt        Runtime dependencies
├── requirements-dev.txt    + test tooling
└── .env.example            Every supported environment variable
```

`_archive/` holds legacy files and per-phase snapshots. It is local only and not part of the app.

## Getting started

Requires Python 3.12.

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Configure the environment
copy .env.example .env               # macOS/Linux: cp .env.example .env
#    then set DJANGO_SECRET_KEY, e.g. generate one with:
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"

# 4. Set up the database and an admin account
python manage.py migrate
python manage.py createsuperuser

# 5. Run
python manage.py runserver
```

Open http://127.0.0.1:8000.

### Demo data

Instead of `createsuperuser`, an empty database can be filled with a ready-to-show demo:

```powershell
python manage.py seed_demo --admin-email you@example.com
```

It creates a superuser (`admin`), one account per role (`demo_moderator`, `demo_provider`,
`demo_provider2`, `demo_provider3`, `demo_basic`, `demo_premium` with active Premium), all 59 courses
of the [UAP BSc in CSE](https://cse.uap-bd.edu/academics/courses/) programme, 25 sample notes as PDFs
(22 published, 3 waiting for review), ratings, comments, follows, Premium packages and a NoteSolve
request. Every account has a confirmed email, so it can sign in right away.

Passwords are not in the code: set `SEED_ADMIN_PASSWORD` / `SEED_DEMO_PASSWORD` (or pass
`--admin-password` / `--demo-password`), otherwise they are generated and printed once. Running it
again adds only what is missing and never changes existing accounts or passwords. The people in the
demo are made up; course data lives in `core/demo_data.py`.

## Configuration

All settings that differ between environments come from environment variables (or `.env`). See [.env.example](.env.example) for the full list.

| Variable | Purpose | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Cryptographic signing key, **required**, 50+ random chars | none |
| `DJANGO_DEBUG` | Debug mode, set `True` only locally | `False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames, required when debug is off | empty |
| `NOTESWAP_SITE_URL` | Site address used in email links (e.g. `https://noteswap.com`), required when debug is off | `http://127.0.0.1:8000` with debug on |
| `DATABASE_URL` | Database connection, e.g. `postgres://...` | local `db.sqlite3` |
| `DJANGO_MEDIA_ROOT` | Where uploads are stored | `media/` |
| `EMAIL_URL` | How email is sent, e.g. `smtp+tls://login:key@smtp-relay.brevo.com:587` | print to terminal |
| `DJANGO_DEFAULT_FROM_EMAIL` | Sender of verification / reset emails | `NoteSwap <no-reply@noteswap.local>` |
| `DJANGO_EMAIL_VERIFICATION` | `mandatory` (must confirm email before signing in) or `optional` | `mandatory` |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google sign-in; empty hides the button | empty |
| `NOTESWAP_DEVELOPER_NAME`, `NOTESWAP_DEVELOPER_URL` | Footer credit "Built by NAME" (linked to the URL); an empty name hides it | Mazharul Islam Sourav, `https://mazharsourav.me` |

When `DJANGO_DEBUG` is off, HTTPS redirects and secure cookies are switched on automatically.

## Accounts and sign-in

Handled by [django-allauth](https://docs.allauth.org/) under `/accounts/` (`/login/` and `/register/` redirect there).

- **Sign up** asks for username, email, name, university, gender and a password. The account is created as *basic* and must **confirm its email** (link in the verification email) before it can sign in.
- **Sign in** with username or email. 5 wrong passwords for the same account lock it for 15 minutes.
- **Forgot password** sends a reset link. Signed-in users can change their password and manage email addresses from their profile (*Account & security*).
- **Google sign-in**: new Google users fill in a short "complete your profile" form once (Google's email counts as verified). If the Google email already belongs to an account, nothing is linked; the owner gets an email saying an account already exists, and can connect Google after signing in normally (*Profile → Connected accounts*).
- **While developing**, emails are printed in the `runserver` terminal; copy the link from there.
- Accounts made with `createsuperuser` have no verified email yet: sign in once on the site and click the link printed in the terminal (the Django admin at `/admin/` works without it).

### Setting up Google sign-in

1. Go to <https://console.cloud.google.com/>, create a project (e.g. "NoteSwap").
2. **APIs & Services → OAuth consent screen**: choose *External*, fill in app name, support email and developer email. Scopes: keep the defaults (`email`, `profile`, `openid`). While the app is in *Testing*, add your own Google address under *Test users*; press *Publish app* when you launch.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**, type *Web application*.
   - Authorised JavaScript origins: `http://127.0.0.1:8000` (and later `https://your-domain.com`)
   - Authorised redirect URIs: `http://127.0.0.1:8000/accounts/google/login/callback/` (and later `https://your-domain.com/accounts/google/login/callback/`)
4. Copy the client ID and secret into `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, restart `runserver`. The Google button appears on the sign-in and sign-up pages.

Open the site as `http://127.0.0.1:8000` (not `localhost`) so the address matches the redirect URI exactly.

## Roles and access

| Role | How it's assigned | Can do |
|---|---|---|
| Superuser | `createsuperuser` | Everything, including premium packages and purchase approval |
| Moderator | Django admin → user → *User type: Moderator* | Verify notes/files, review provider applications |
| Provider | A moderator accepts their application | Upload and edit their own notes, answer NoteSolve requests sent to them |
| Basic | Default for every signup | Browse, open notes (when logged in), rate, comment, follow providers |

Permission checks live in [core/permissions.py](core/permissions.py). Actions that change data accept POST only.

## Site rules

- **Ratings:** one per user per note (1–5), changeable; providers can't rate their own notes.
- **Note review:** a new note (or one with a replaced file) waits in *Manage → Review notes*. Approving publishes it and notifies the provider's followers. Rejecting needs a reason: the note stays hidden, the provider is notified, sees the reason on the note and can fix it and send it again (saving the edit form, or *Send for review again*). Rejected extra files are removed.
- **Provider applications:** pending → accepted or rejected. A rejection needs a reason, which the applicant sees; they can reapply 30 days later.
- **NoteSolve requests:** pending → solved or rejected. A rejection needs a reason; the student can resend the request to another provider.
- **Contact / Feedback / Ask a Question:** saved to the inbox at *Manage → Inbox* (`/manage/inbox/`), for moderators and superusers.
- **Note type** (PDF or image) is detected from the uploaded file.
- **A note's files:** the owner manages them on the note's *Files* page (`/note/<id>/files/`): add several files at once (up to 20; one invalid file and none are added) or delete a single additional file, which also removes it from storage. The main file can't be deleted on its own, only replaced on the edit page or deleted with the whole note. New files show to readers once a moderator approves them.
- **Following:** any signed-in user can follow a provider (not themselves). Followers get a notification (navbar bell, `/notifications/`) the first time each of the provider's notes is published; providers get one when someone follows them. Opening the notifications page marks what it shows as read.

## Uploaded files

- Notes and NoteSolve files are **not** public. They are served by access-checked views under `/files/...`, never by their `/media/` path.
- Stored files are removed automatically once nothing uses them: when a note, an extra file or an account is deleted, when extra files are rejected, and when a note's file or a profile photo is replaced ([core/file_cleanup.py](core/file_cleanup.py)).
- NoteSolve question and solution files open in the same reader, in a pop-up (`data-preview` links, [static/js/pages/file-preview.js](static/js/pages/file-preview.js)).
- Only `media/profiles/` (profile pictures) is public. In production, configure the web server to expose **only** `MEDIA_ROOT/profiles/` at `/media/profiles/`.
- Uploads must be real PDF, JPG, PNG or WEBP files of at most 20 MB. The content is checked, not just the extension ([core/validators.py](core/validators.py)).
- The note page shows the main file and the additional files as **one document**, page after page, in upload order ([static/js/pages/note-reader.js](static/js/pages/note-reader.js)). Photos are one page each; PDFs are drawn by [PDF.js](https://mozilla.github.io/pdf.js/) (`static/vendor/pdfjs/`) instead of the browser's own viewer, so they look the same everywhere, phones included. Owners and moderators also see additional files still waiting for review, marked as such. *Download* offers the whole note as a zip (`/files/notes/<id>/all.zip`, files numbered in reading order) or one file at a time. To update it, replace `pdf.min.mjs` and `pdf.worker.min.mjs` with the files of a newer release. The web server must send `.mjs` files as `text/javascript` (nginx: add `mjs` to the `application/javascript` line of `mime.types` if it's missing).

## Languages

The site is English only, but ready for a second language: the shared header, phone menu and footer text is marked with `{% translate %}`, and `config/settings.py` has `LANGUAGES` and `LOCALE_PATHS` set up. To add a language: add it to `LANGUAGES`, add `django.middleware.locale.LocaleMiddleware`, mark the remaining page templates, run `python manage.py makemessages -l bn` and translate the `.po` file.

## Tests

```powershell
python manage.py test core      # unit/security tests, uses a temporary database
ruff check core config          # lint (rules in ruff.toml)
```

Custom error pages live in `templates/403.html`, `404.html` and `500.html`. With `DJANGO_DEBUG=True` Django shows its debug pages instead, so preview them at `/__preview__/403/`, `/__preview__/404/` and `/__preview__/500/` (debug mode only).
