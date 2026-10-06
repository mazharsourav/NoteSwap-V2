"""
Help Center articles and FAQs (templates/pages/help_center.html, help_article.html).

Each article is a list of sections; a section has a heading and blocks. A block is either a
paragraph (str) or a list of steps (list of str). `links` are (label, url name) pairs shown at
the end of the article. Keep the text in sync with how the site actually works.
"""

ARTICLES = [
    {
        'slug': 'getting-started',
        'icon': 'user',
        'title': 'Creating an account and signing in',
        'summary': 'Sign up, confirm your email, sign in with Google, and reset a forgotten password.',
        'sections': [
            ('Create an account', [
                'Browsing courses and notes is open to everyone. To open, download, rate or comment on a note, '
                'you need a free account.',
                ['Choose “Create account” at the top of any page.',
                 'Fill in your name, university, username, email and a password.',
                 'Open the email we send you and click the confirmation link. Your account is ready.'],
                'You can also choose “Sign up with Google”. We then ask once for your university so we can show '
                'you the right notes.',
            ]),
            ('Sign in', [
                'Sign in with your username or your email address and your password, or with Google if you signed '
                'up that way. After several wrong passwords in a row, sign-in is paused for a few minutes to '
                'protect your account.',
            ]),
            ('Forgot your password?', [
                ['On the sign-in page, choose “Forgot password?”.',
                 'Enter the email address on your account.',
                 'Open the email and follow the link to choose a new password.'],
                'The link works once and expires after a while. If the email doesn’t arrive, check your spam folder.',
            ]),
        ],
        'links': [('Create an account', 'account_signup'), ('Sign in', 'account_login'),
                  ('Reset your password', 'account_reset_password')],
    },
    {
        'slug': 'finding-notes',
        'icon': 'search',
        'title': 'Finding and reading notes',
        'summary': 'Browse by course, search, read on your phone, download, rate and comment.',
        'sections': [
            ('Browse or search', [
                'Notes are organised by course, like “Data Communication”, and each course has notes from every '
                'university. Open “Notes” in the menu: pick your university and a semester chip like “2-1” (year 2, '
                'semester 1) to see only those courses, then open one to see its notes, best rated first. The filter '
                'stays on inside the course, where you can also sort by newest or filter by title, course code or provider.',
                'To jump straight to something, use the search box on the home page or the search icon in the '
                'header. It looks through courses, course codes (“CSE 301”), note titles, universities and providers at once.',
            ]),
            ('Read and download', [
                'On a computer, PDFs open right on the note page; use “Full screen” for more room. On a phone, '
                'choose “Read full screen” to open the PDF in your phone’s own viewer, which is easier to read. '
                '“Download” saves a copy.',
                'Every note was checked by a moderator before it went live.',
            ]),
            ('Rate and comment', [
                'Tap a star on the note page to rate it from 1 to 5. You can change your rating at any time; each '
                'student rates a note once. Comments are public, so be kind and specific.',
            ]),
        ],
        'links': [('Browse notes', 'subject_list'), ('Search', 'search')],
    },
    {
        'slug': 'following',
        'icon': 'bell',
        'title': 'Following providers and notifications',
        'summary': 'Follow the students whose notes you like and get notified when they publish.',
        'sections': [
            ('Follow a provider', [
                'Choose “Follow” on a provider’s card, profile or note. When a moderator approves a new note from '
                'someone you follow, you get a notification.',
                'Hover over “Following” and choose “Unfollow” to stop. Your list is on the Following page.',
            ]),
            ('Notifications', [
                'The bell in the header shows how many notifications you haven’t seen. Opening the Notifications '
                'page marks them as seen. Providers are also told when someone new follows them.',
            ]),
        ],
        'links': [('Providers', 'providers'), ('Following', 'following'), ('Notifications', 'notifications')],
    },
    {
        'slug': 'becoming-a-provider',
        'icon': 'upload',
        'title': 'Becoming a provider and uploading notes',
        'summary': 'Apply, upload, what happens in review, and editing your notes and their files.',
        'sections': [
            ('Apply', [
                ['Open “Become a provider” and fill in the form about you and your studies.',
                 'A moderator reviews it, usually within a few days.',
                 'If you’re accepted, you can upload straight away. If not, you’ll see the reason and can apply '
                 'again after 30 days.'],
            ]),
            ('Upload a note', [
                'Choose “Upload” in the header. Give the note a clear title and description, attach the file (PDF, '
                'JPG, PNG or WEBP, up to 20 MB), pick the course (or add it), and say which university and '
                'semester (like “2-1”) it’s for. The course code at your university, like “CSE 301”, is optional but helps '
                'students find it.',
                'A moderator checks every note before it goes live. Once it’s approved, your followers are notified.',
            ]),
            ('If your note isn’t approved', [
                'You get a notification, and the moderator’s reason shows at the top of the note. The note stays '
                'hidden from everyone else. Fix what the reason asks for, then save your changes with “Edit” or '
                'choose “Send for review again”, and it goes back to a moderator.',
            ]),
            ('Edit your note', [
                'Open your note and choose “Edit”. Changes to the title, description or details show right away. '
                'A new main file goes to a moderator first, and the note is hidden until it’s approved.',
            ]),
            ('Add or remove files', [
                'Choose “Files” on your note to see all its files in reading order. Add more photos or PDFs '
                '(up to 20 at a time); they show on the note once a moderator approves them. To take out a wrong '
                'photo or PDF, choose “Delete” next to it. The rest of the note stays as it is.',
            ]),
            ('Delete a note', [
                'Choose “Delete” on your note to remove it with all its files, ratings and comments. This can’t be '
                'undone.',
            ]),
        ],
        'links': [('Become a provider', 'become_provider'), ('Upload a note', 'upload_note')],
    },
    {
        'slug': 'premium-and-notesolve',
        'icon': 'crown',
        'title': 'Premium and NoteSolve',
        'summary': 'What Premium includes, how an order is approved, and how to ask a provider for help.',
        'sections': [
            ('What Premium gives you', [
                'Premium unlocks NoteSolve: you send a problem you’re stuck on to a provider, and they send back '
                'a worked solution. Reading, downloading, rating and following stay free for everyone.',
            ]),
            ('Buying Premium', [
                ['Open “Premium” and choose a plan.',
                 'Confirm your order.',
                 'An admin checks the payment and switches Premium on, usually within a day.'],
            ]),
            ('Asking on NoteSolve', [
                'Choose a provider (providers from your university and department are suggested first), describe '
                'the problem and attach a photo or PDF. You’ll find the answer under “Your requests”, where you '
                'can rate it.',
                'If a provider can’t take your question, they say why and you can send it to someone else.',
            ]),
        ],
        'links': [('See Premium plans', 'premium_packages')],
    },
    {
        'slug': 'your-account',
        'icon': 'settings',
        'title': 'Your profile and account settings',
        'summary': 'Edit your profile, change your email or password, connect Google, or close your account.',
        'sections': [
            ('Profile', [
                'Your name, university, department and photo appear on your comments and reviews, and on your '
                'public page if you’re a provider. Change them under “Edit profile”.',
            ]),
            ('Email and password', [
                'Add or change your email under “Email addresses”; a new address has to be confirmed before it '
                'can be used. Change your password under “Password”. If you signed up with Google, you can set a '
                'password there too.',
            ]),
            ('Close your account', [
                'Send us a message through the Contact page from the email on your account, and we’ll remove it.',
            ]),
        ],
        'links': [('Edit profile', 'edit_profile'), ('Email addresses', 'account_email'),
                  ('Password', 'account_change_password')],
    },
    {
        'slug': 'rules-and-reporting',
        'icon': 'shield',
        'title': 'Rules and reporting a problem',
        'summary': 'What can be shared on NoteSwap, and how to tell us about something wrong.',
        'sections': [
            ('What’s allowed', [
                'Share notes you wrote yourself or have permission to share. Don’t upload copyrighted books, exam '
                'papers you aren’t allowed to share, or anything harmful. Moderators remove notes that break the '
                'rules, and accounts that keep breaking them can be closed.',
            ]),
            ('Report something', [
                'If a note is wrong, copied or inappropriate, or a comment is abusive, tell us through the Contact '
                'page with a link to it. A moderator will look at it.',
            ]),
        ],
        'links': [('Contact us', 'contact'), ('Terms of use', 'terms_of_use')],
    },
]

FAQS = [
    ('Is NoteSwap free?',
     'Yes. Browsing, reading, downloading, rating and following are free with an account. Premium is optional '
     'and only adds NoteSolve.'),
    ('Why do I have to sign in to open a note?',
     'It keeps providers’ work from being copied around anonymously, and lets you rate and follow.'),
    ('Who checks the notes?',
     'NoteSwap moderators look at every new note, every replaced file and every added file before it goes '
     'live. If they don’t approve a note, the provider is told why and can fix it.'),
    ('Can I upload notes?',
     'Providers can. Apply on the “Become a provider” page; a moderator reviews your application.'),
    ('I didn’t get the confirmation email.',
     'Check your spam folder. You can send it again from “Email addresses” after signing in, or by signing in '
     'and following the prompt.'),
    ('How do I change my email address?',
     'Go to your account’s “Email addresses” page, add the new address and confirm it from your inbox.'),
]


def get_article(slug):
    return next((article for article in ARTICLES if article['slug'] == slug), None)
