"""Static file storage for local development."""
import os

from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import StaticFilesStorage


class DevStaticFilesStorage(StaticFilesStorage):
    """Adds ?v=<file modified time> to {% static %} URLs, so the browser fetches CSS/JS again after every
    change instead of showing a cached copy. Development only: production uses hashed file names."""

    def url(self, name):
        url = super().url(name)
        path = finders.find(name)
        if path and not isinstance(path, list):
            url += f'?v={int(os.path.getmtime(path))}'
        return url
