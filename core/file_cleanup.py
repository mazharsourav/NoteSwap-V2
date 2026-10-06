"""
Remove uploaded files from storage when nothing uses them any more: when their row is deleted
(a note, an extra file, a rejected file, a whole account with its notes) or when a file is
replaced or cleared (a note's main file, a profile photo). Without this, deleted and rejected
uploads would stay on disk for good.

Files are removed only after the database change is committed, and only if no other row of
the same model still points at the same stored name.
"""
import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save

from .models import CustomUser, Note, NoteFile, NoteSolveFile, NoteSolveSolution

FILE_FIELDS = {
    Note: 'file',
    NoteFile: 'file',
    NoteSolveFile: 'file',
    NoteSolveSolution: 'file',
    CustomUser: 'profile_picture',
}

logger = logging.getLogger(__name__)


def _remove_later(model, field, storage, name):
    if not name:
        return

    def remove():
        if model._default_manager.filter(**{field: name}).exists():
            return
        try:
            storage.delete(name)
        except Exception:
            # The page has already done its job; the file just stays on disk until someone removes it.
            logger.exception('Could not delete %s from storage (%s.%s)', name, model.__name__, field)

    transaction.on_commit(remove)


def _remove_deleted(sender, instance, **kwargs):
    field = FILE_FIELDS[sender]
    stored = getattr(instance, field)
    _remove_later(sender, field, stored.storage, stored.name)


def _remember_old(sender, instance, update_fields=None, **kwargs):
    field = FILE_FIELDS[sender]
    instance._old_file_name = None
    if not instance.pk or (update_fields is not None and field not in update_fields):
        return  # new row, or a save that doesn't touch the file (e.g. last_login on sign-in)
    instance._old_file_name = sender._default_manager.filter(pk=instance.pk).values_list(field, flat=True).first()


def _remove_replaced(sender, instance, **kwargs):
    field = FILE_FIELDS[sender]
    stored = getattr(instance, field)
    old_name = getattr(instance, '_old_file_name', None)
    if old_name and old_name != stored.name:
        _remove_later(sender, field, stored.storage, old_name)


def connect():
    for model in FILE_FIELDS:
        name = model.__name__
        post_delete.connect(_remove_deleted, sender=model, dispatch_uid=f'file-cleanup-delete-{name}')
        pre_save.connect(_remember_old, sender=model, dispatch_uid=f'file-cleanup-remember-{name}')
        post_save.connect(_remove_replaced, sender=model, dispatch_uid=f'file-cleanup-replace-{name}')
