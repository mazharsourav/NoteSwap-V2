"""Small building blocks for the templates: inline icons, avatars and star ratings.

    {% load ui %}
    {% icon "search" %}                    20px stroke icon (inherits the text colour)
    {% icon "check" size="sm" %}           16px; size can be "sm", "lg" or omitted
    {% avatar user 40 %}                   profile picture, or initials on green
    {% stars note.avg_rating %}            five stars, rounded to the nearest whole star
    {{ note.file.name|filename }}          "notes/scan.pdf" -> "scan.pdf"
"""
import posixpath

from django import template
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from core import universities

register = template.Library()

# Stroke icons on a 24px grid. Keep them to one visual weight: no fills, round caps.
ICONS = {
    'alert': '<circle cx="12" cy="12" r="9.5"/><path d="M12 7.5v5"/><path d="M12 16.2h.01"/>',
    'arrow': '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
    'bell': '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    'book': '<path d="M2 4.5h6a4 4 0 0 1 4 4V21a3 3 0 0 0-3-3H2z"/><path d="M22 4.5h-6a4 4 0 0 0-4 4V21a3 3 0 0 1 3-3h7z"/>',
    'cap': '<path d="M22 10 12 5 2 10l10 5 10-5z"/><path d="M6 12v5c3 2.5 9 2.5 12 0v-5"/>',
    'check': '<path d="M20 6 9 17l-5-5"/>',
    'chev-down': '<path d="m6 9 6 6 6-6"/>',
    'chev-left': '<path d="m15 18-6-6 6-6"/>',
    'chev-right': '<path d="m9 18 6-6-6-6"/>',
    'clip': '<path d="m21.4 11.1-9.2 9.2a6 6 0 0 1-8.5-8.5l8.6-8.6a4 4 0 1 1 5.7 5.7l-8.6 8.6a2 2 0 0 1-2.8-2.8l8.5-8.5"/>',
    'clock': '<circle cx="12" cy="12" r="9.5"/><path d="M12 7v5l3 2"/>',
    'crown': '<path d="M3 8l4.5 4L12 5l4.5 7L21 8l-2 11H5z"/>',
    'download': '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    'edit': '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    'expand': ('<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/>'
               '<path d="M16 21h3a2 2 0 0 0 2-2v-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/>'),
    'external': ('<path d="M15 3h6v6"/><path d="M10 14 21 3"/>'
                 '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'),
    'eye': '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    'file': ('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>'
             '<path d="M16 13H8"/><path d="M16 17H8"/>'),
    'grid': ('<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/>'
             '<rect x="14" y="14" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/>'),
    'help': '<circle cx="12" cy="12" r="9.5"/><path d="M9.2 9a3 3 0 0 1 5.8 1c0 2-3 2.5-3 4"/><path d="M12 17.2h.01"/>',
    'image': ('<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/>'
              '<path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>'),
    'inbox': ('<path d="M22 12h-6l-2 3h-4l-2-3H2"/>'
              '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>'),
    'info': '<circle cx="12" cy="12" r="9.5"/><path d="M12 16v-4.5"/><path d="M12 8h.01"/>',
    'key': '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/>',
    'lock': '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    'logout': '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    'mail': '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
    'menu': '<path d="M4 7h16"/><path d="M4 12h16"/><path d="M4 17h16"/>',
    'message': '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    'minus': '<path d="M5 12h14"/>',
    'more': '<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>',
    'plus': '<path d="M12 5v14"/><path d="M5 12h14"/>',
    'quote': '<path d="M7 7h4v4c0 3-1.5 5-4 6"/><path d="M15 7h4v4c0 3-1.5 5-4 6"/>',
    'search': '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    'send': '<path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/>',
    'settings': ('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06'
                 'a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33'
                 'l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9'
                 'a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09'
                 'a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1'
                 'H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>'),
    'shield': '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    'sliders': ('<path d="M4 21v-7"/><path d="M4 10V3"/><path d="M12 21v-9"/><path d="M12 8V3"/><path d="M20 21v-5"/>'
                '<path d="M20 12V3"/><path d="M1 14h6"/><path d="M9 8h6"/><path d="M17 16h6"/>'),
    'star': '<path d="M12 2.8l2.85 5.95 6.45.83-4.73 4.5 1.2 6.42L12 17.38l-5.77 3.12 1.2-6.42L2.7 9.58l6.45-.83z"/>',
    'trash': ('<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>'
              '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'),
    'upload': '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    'user': '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    'users': ('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
              '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),
    'x': '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    # Profile links (About page team cards)
    'github': ('<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5'
               ' 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.4 5.4 0 0 0 4 9c0 3.5 3 5.5 6 5.5'
               '-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/>'),
    'linkedin': ('<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-4 0v7h-4v-7a6 6 0 0 1 6-6z"/>'
                 '<rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/>'),
    'instagram': ('<rect width="20" height="20" x="2" y="2" rx="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/>'
                  '<path d="M17.5 6.5h.01"/>'),
    'globe': ('<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/>'
              '<path d="M2 12h20"/>'),
    'facebook': '<path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/>',
    'x-social': '<path d="M4 4l11.733 16H20L8.267 4z"/><path d="M4 20l6.768-6.768"/><path d="M13.228 10.772 20 4"/>',
    'threads': ('<path d="M19 7.5C17.667 4.5 15.333 3 12 3 7 3 4 5.5 4 12s3.5 9 8 9 7-3 7-5-1-5-7-5c-2.5 0-3 1.25-3 2.5'
                ' 0 1.5 1 2.5 2.5 2.5 2.5 0 3.5-1.5 3.5-5s-2-4-3-4-1.833.333-2.5 1"/>'),
}


@register.simple_tag
def icon(name, size='', cls=''):
    """Inline SVG icon. Decorative: label the surrounding link or button instead."""
    classes = ' '.join(c for c in ('icon', f'icon-{size}' if size else '', cls) if c)
    return format_html(
        '<svg class="{}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{}</svg>',
        classes, _raw(ICONS[name]),
    )


def _raw(markup):
    # The icon paths are constants defined above, never user input.
    return mark_safe(markup)


def display_name(user):
    return user.get_full_name() or user.username


def initials(user):
    parts = (user.get_full_name() or user.username).split()
    letters = ''.join(p[0] for p in parts[:2]) if len(parts) > 1 else parts[0][:2]
    return letters.upper()


@register.filter(name='display_name')
def display_name_filter(user):
    return display_name(user)


@register.filter
def uni_short(value):
    """A stored university as a short name: "UAP" (or the typed name of one that isn't listed)."""
    return universities.short_name(value)


@register.filter
def uni_full(value):
    """A stored university as its full name: "University of Asia Pacific"."""
    return universities.full_name(value)


@register.filter
def filename(path):
    """The file name of a stored file's path, without its upload folder."""
    return posixpath.basename(str(path or ''))


@register.simple_tag
def avatar(user, size=40, cls=''):
    """A round avatar: the profile picture if there is one, otherwise the user's initials."""
    size = int(size)
    classes = f'avatar {cls}'.strip()
    if getattr(user, 'profile_picture', None):
        return format_html(
            '<img class="{}" src="{}" alt="" width="{}" height="{}" style="--size: {}px" loading="lazy" decoding="async">',
            classes, user.profile_picture.url, size, size, size,
        )
    return format_html(
        '<span class="{}" style="--size: {}px" aria-hidden="true">{}</span>',
        classes, size, initials(user),
    )


@register.simple_tag
def stars(value, size=16):
    """Five stars for a 0–5 average; the label carries the exact value for screen readers."""
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        value = 0
    filled = max(0, min(5, int(value + 0.5)))
    items = format_html_join(
        '', '<svg class="star{}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{}</svg>',
        ((' is-on' if i < filled else '', _raw(ICONS['star'])) for i in range(5)),
    )
    return format_html(
        '<span class="stars" style="--star: {}px" role="img" aria-label="Rated {} out of 5">{}</span>',
        int(size), f'{value:.1f}'.rstrip('0').rstrip('.') or '0', items,
    )
