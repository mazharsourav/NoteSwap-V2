from django import template

register = template.Library()


# Extract value from a dictionary by key
@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


# Number of filled stars (0-5) for an average rating, rounded half up
@register.filter
def filled_stars(value):
    try:
        return max(0, min(5, int(float(value) + 0.5)))
    except (TypeError, ValueError):
        return 0
