// NoteSolve: on narrow screens a student with past requests sees them first, and the question
// form stays closed behind an "Ask a new question" button (css/pages/notesolve.css).
(function () {
  'use strict';

  var card = document.querySelector('[data-solve-ask].is-collapsible');
  if (!card) return;
  var button = card.querySelector('[data-solve-ask-open]');
  if (!button) return;

  function open(focus) {
    card.classList.add('is-open');
    button.setAttribute('aria-expanded', 'true');
    if (focus) {
      var first = card.querySelector('.solve-form select, .solve-form input:not([type="hidden"]), .solve-form textarea');
      if (first) first.focus();
    }
  }

  button.hidden = false;
  button.addEventListener('click', function () { open(true); });
  // A link to #ask (e.g. from elsewhere on the page) opens the form too.
  window.addEventListener('hashchange', function () { if (location.hash === '#ask') open(false); });
  if (location.hash === '#ask') open(false);
})();
