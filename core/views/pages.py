"""Home page, static pages, and the contact / feedback / ask-a-question forms."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.db.models import Count, F, Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views import defaults

from ..forms import AskQuestionForm, ContactForm, FeedbackForm, ReviewForm
from ..help_content import ARTICLES, FAQS, get_article
from ..logs import audit, security, who
from ..models import CustomUser, InboxMessage, Note, Review, Subject
from ._helpers import provider_cards, published_notes


def home(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        review_form = ReviewForm(request.POST)
        if review_form.is_valid():
            review = review_form.save(commit=False)
            review.user = request.user
            review.save()
            messages.success(request, 'Thanks for your review!')
            return redirect('home')
    else:
        review_form = ReviewForm()

    notes = published_notes()
    subjects = Subject.objects.annotate(
        note_count=Count('notes', filter=Q(notes__is_verified=True), distinct=True),
    ).order_by('-note_count', 'name')[:6]
    providers = sorted(provider_cards(with_followers=True),
                       key=lambda item: (-item['note_count'], -item['follower_count']))

    followed_ids, following_notes = set(), []
    if request.user.is_authenticated:
        followed_ids = set(request.user.following.values_list('provider_id', flat=True))
        if followed_ids:
            following_notes = notes.filter(provider_id__in=followed_ids).order_by('-uploaded_at', '-id')[:4]

    return render(request, 'pages/home.html', {
        'subjects': subjects,
        'top_rated_notes': notes.order_by(F('avg_rating').desc(nulls_last=True), '-rating_count', '-id')[:4],
        'following_notes': following_notes,
        'providers': providers[:4],
        'followed_ids': followed_ids,
        'reviews': Review.objects.select_related('user').order_by('-timestamp')[:3],
        'review_form': review_form,
        'stats': {
            'notes': Note.objects.filter(is_verified=True).count(),
            'providers': len(providers),
            'students': CustomUser.objects.filter(is_superuser=False).count(),
        },
    })


# The About page team cards. Edit freely: `bio` and `facts` are drafts. A link shows only when it
# has an address (email: just the address, no "mailto:").
TEAM = [
    {
            'name': 'Mazharul Islam Sourav', 'role': 'Frontend & Backend developer', 'photo': 'img/team/sourav.jpg',
            'bio': 'Designs and builds NoteSwap end to end, from the pages you use to the code behind them.',
            'facts': [('Role', 'Full-Stack'), ('Builds with', 'Django + JS'), ('Since', '2025')],
            'links': {'portfolio': 'https://mazharsourav.me', 'github': 'https://github.com/mazharsourav',
                      'linkedin': 'www.linkedin.com/in/mazharsourav', 'instagram': '', 'facebook': '',
                      'x': '', 'threads': '', 'email': ''},
    },
    {
        'name': 'Faisal Hossain', 'role': 'Backend developer', 'photo': 'img/team/faisal.jpg',
        'bio': 'Builds the parts you don’t see: accounts, note reviews and the database behind them.',
        'facts': [('Role', 'Backend'), ('Builds with', 'Django'), ('Since', '2025')],
        'links': {'portfolio': 'https://faisal-solo.vercel.app/', 'github': 'https://github.com/HAVIC-47',
                  'linkedin': 'https://www.linkedin.com/in/faisal-hossain-havic47/', 'instagram': '',
                  'facebook': '', 'x': '', 'threads': '', 'email': ''},
    },
    
]
# Link key -> (label, icon), in the order they appear on a card
TEAM_LINKS = [
    ('portfolio', 'Portfolio', 'globe'), ('github', 'GitHub', 'github'), ('linkedin', 'LinkedIn', 'linkedin'),
    ('facebook', 'Facebook', 'facebook'), ('instagram', 'Instagram', 'instagram'), ('threads', 'Threads', 'threads'),
    ('x', 'X', 'x-social'), ('email', 'Email', 'mail'),
]


def about_page(request):
    team = [
        {**member, 'link_list': [
            {'url': f"mailto:{member['links'][key]}" if key == 'email' else member['links'][key],
             'label': label, 'icon': icon}
            for key, label, icon in TEAM_LINKS if member['links'].get(key)
        ]}
        for member in TEAM
    ]
    return render(request, 'pages/about.html', {'team': team})


def terms_of_use(request):
    return render(request, 'pages/terms.html')


# Public pages (home, courses, search, providers, help…) stay crawlable; everything that
# needs an account, or belongs to staff, is kept out of search engines.
ROBOTS_DISALLOW = [
    '/admin/', '/accounts/', '/login/', '/register/', '/logout/',
    '/manage_dash/', '/manage/', '/verify/', '/provider-requests/',
    '/profile/', '/edit-profile/', '/search/', '/following/', '/notifications/',
    '/upload/', '/add-subject/', '/become-provider/', '/files/',
    '/notesolve/', '/solve-request/', '/solved-requests/',
    '/premium/add/', '/premium/edit/', '/premium/delete/', '/premium/toggle/',
    '/premium/purchase/', '/premium/checkout/', '/premium/approve/', '/premium/reject/',
]


def robots_txt(request):
    lines = ['User-agent: *', *(f'Disallow: {path}' for path in ROBOTS_DISALLOW)]
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain')


def help_center(request):
    return render(request, 'pages/help_center.html', {'articles': ARTICLES, 'faqs': FAQS})


def help_article(request, slug):
    article = get_article(slug)
    if article is None:
        raise Http404
    sections = [
        (heading, [{'steps': block} if isinstance(block, list) else {'text': block} for block in blocks])
        for heading, blocks in article['sections']
    ]
    return render(request, 'pages/help_article.html', {
        'article': article,
        'sections': sections,
        'others': [other for other in ARTICLES if other['slug'] != slug],
    })


def _inbox_form(request, form_class, kind):
    """Bind an inbox form; on a valid POST save it and return None, else return the form."""
    initial = {}
    if request.user.is_authenticated:
        initial = {'name': request.user.get_full_name() or request.user.username, 'email': request.user.email}
    form = form_class(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        message = form.save(commit=False)
        message.kind = kind
        message.user = request.user if request.user.is_authenticated else None
        message.save()
        audit('inbox.received', message=message.id, kind=kind, user=who(request.user))  # never the text
        return None
    return form


@login_required
def ask_question(request):
    form = _inbox_form(request, AskQuestionForm, InboxMessage.Kind.QUESTION)
    if form is None:
        messages.success(request, "Your question was sent. We'll reply by email.")
        return redirect('help_center')
    return render(request, 'pages/ask_question.html', {'form': form})


@login_required
def send_feedback(request):
    form = _inbox_form(request, FeedbackForm, InboxMessage.Kind.FEEDBACK)
    if form is None:
        messages.success(request, "Thanks for your feedback!")
        return redirect('home')
    return render(request, 'pages/feedback.html', {'form': form})


def contact_page(request):
    form = _inbox_form(request, ContactForm, InboxMessage.Kind.CONTACT)
    if form is None:
        messages.success(request, "We received your message and will reply by email.")
        return redirect('contact')
    return render(request, 'pages/contact.html', {'form': form})


def permission_denied(request, exception):
    """Every 403 (wrong role, not the note's owner) is logged, then shows the normal 403 page."""
    security('access.denied', user=who(request.user), path=request.path)
    return defaults.permission_denied(request, exception)
