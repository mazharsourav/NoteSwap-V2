// Help Center: filter the articles and FAQs as you type.
(function () {
  'use strict';

  var input = document.querySelector('[data-help-search]');
  if (!input) return;
  var items = document.querySelectorAll('[data-help-item]');
  var none = document.querySelector('[data-help-empty]');

  input.addEventListener('input', function () {
    var words = input.value.toLowerCase().split(/\s+/).filter(Boolean);
    var shown = 0;
    items.forEach(function (item) {
      var text = item.getAttribute('data-help-item').toLowerCase();
      var match = words.every(function (word) { return text.indexOf(word) !== -1; });
      item.hidden = !match;
      if (match) shown += 1;
    });
    if (none) none.hidden = shown > 0;
  });
})();
