// Modal dialogs: <button data-dialog-open="some-id"> opens <dialog id="some-id">.
// Buttons with data-dialog-close, the Escape key and a click on the backdrop close it.
// A dialog with data-open opens as soon as the page loads (e.g. to show form errors).
(function () {
  'use strict';

  document.querySelectorAll('dialog[data-open]').forEach(function (dialog) {
    if (typeof dialog.showModal === 'function') dialog.showModal();
  });

  document.addEventListener('click', function (event) {
    var opener = event.target.closest('[data-dialog-open]');
    if (opener) {
      var dialog = document.getElementById(opener.getAttribute('data-dialog-open'));
      if (dialog && typeof dialog.showModal === 'function') {
        event.preventDefault();
        dialog.showModal();
        var field = dialog.querySelector('textarea, input:not([type="hidden"])');
        if (field) field.focus();
      }
      return;
    }
    if (event.target.closest('[data-dialog-close]')) {
      event.target.closest('dialog').close();
      return;
    }
    // A click on the backdrop lands on the <dialog> element itself
    if (event.target.tagName === 'DIALOG' && event.target.open) event.target.close();
  });
})();
