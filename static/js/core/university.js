// University picker (core/forms.py UniversityField, core/templates/core/widgets/university.html).
// Turns the <select> of universities into a type-to-search box: type "asia" or "uap" and the matches
// show in a list; the last item is always "Other (not in the list)", which reveals a text box for the
// name. The <select> stays in the form (hidden) and is what gets submitted.
// Without JavaScript the plain <select> and the "Other" text box both show.
//
// As a filter (data-uni-filter, notes/_university_filter.html) there's no "Other": the list is
// "All universities" and then the universities that have notes. Clicking the box empties it (the current
// choice stays as the placeholder) so the whole list shows and typing starts a fresh search.
(function () {
  'use strict';

  var OTHER = '__other__';
  var count = 0;

  function setup(picker) {
    var select = picker.querySelector('select');
    var otherBox = picker.querySelector('[data-uni-other]');
    var otherInput = otherBox && otherBox.querySelector('input');
    if (!select) return;
    count += 1;
    var isFilter = picker.hasAttribute('data-uni-filter');

    // The choices, read from the server-rendered <select>. "All universities" (`pinned`) shows only
    // before anything is typed.
    var items = [];
    Array.prototype.forEach.call(select.options, function (option) {
      if (!option.value && !isFilter) return;
      var parent = option.parentElement;
      var group = parent.tagName === 'OPTGROUP' ? parent.label : '';
      items.push({ value: option.value, label: option.textContent, group: group, key: option.textContent.toLowerCase(),
                   pinned: !option.value });
    });
    var placeholder = select.options[0] && !select.options[0].value ? select.options[0].textContent : 'Choose your university';

    // The search box takes over the select's id, so the field's <label for> points at it
    var input = document.createElement('input');
    var listId = 'uni-list-' + count;
    input.type = 'text';
    input.className = 'input uni-picker__search';
    input.id = select.id;
    select.id = select.id + '-select';
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-expanded', 'false');
    input.setAttribute('aria-controls', listId);
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('spellcheck', 'false');
    input.placeholder = isFilter ? 'Search universities' : 'Type to search, e.g. “UAP” or “Dhaka”';
    if (select.getAttribute('aria-invalid')) input.setAttribute('aria-invalid', 'true');

    var list = document.createElement('ul');
    list.className = 'uni-picker__list';
    list.id = listId;
    list.setAttribute('role', 'listbox');
    list.hidden = true;

    select.hidden = true;
    select.tabIndex = -1;
    picker.insertBefore(input, select);
    picker.insertBefore(list, select.nextSibling);
    picker.classList.add('is-enhanced');

    var shown = [];   // items currently in the list
    var active = -1;  // index in `shown` of the highlighted item

    function labelOf(value) {
      var item = items.find(function (i) { return i.value === value; });
      return item ? item.label : '';
    }

    function showOther(open, focus) {
      if (!otherBox) return;
      otherBox.hidden = !open;
      if (open && focus && otherInput) otherInput.focus();
    }

    function render(query) {
      var q = query.trim().toLowerCase();
      var matches = items.filter(function (item) {
        if (item.value === OTHER) return false;
        if (!q) return true;
        return !item.pinned && (item.key.indexOf(q) !== -1 || item.value.toLowerCase().indexOf(q) === 0);
      });
      var other = items.find(function (i) { return i.value === OTHER; });
      shown = other ? matches.concat([other]) : matches;
      list.replaceChildren();
      var lastGroup = null;
      if (q && !matches.length) {
        var none = document.createElement('li');
        none.className = 'uni-picker__empty';
        none.setAttribute('role', 'presentation');
        none.textContent = 'No university matches “' + query.trim() + '”. Choose Other and type its name.';
        list.append(none);
      }
      shown.forEach(function (item, index) {
        if (!q && item.group && item.group !== lastGroup) {
          var head = document.createElement('li');
          head.className = 'uni-picker__group';
          head.setAttribute('role', 'presentation');
          head.textContent = item.group;
          list.append(head);
          lastGroup = item.group;
        }
        var li = document.createElement('li');
        li.className = 'uni-picker__option' + (item.value === OTHER ? ' is-other' : '');
        li.id = listId + '-' + index;
        li.setAttribute('role', 'option');
        li.setAttribute('aria-selected', String(item.value === select.value));
        li.textContent = item.label;
        li.addEventListener('mousedown', function (event) { event.preventDefault(); });  // keep focus in the box
        li.addEventListener('click', function () { choose(item); });
        list.append(li);
      });
      highlight(q && matches.length ? 0 : -1);
    }

    function highlight(index) {
      active = index;
      list.querySelectorAll('.is-active').forEach(function (el) { el.classList.remove('is-active'); });
      if (index < 0 || !shown[index]) {
        input.removeAttribute('aria-activedescendant');
        return;
      }
      var el = document.getElementById(listId + '-' + index);
      el.classList.add('is-active');
      input.setAttribute('aria-activedescendant', el.id);
      el.scrollIntoView({ block: 'nearest' });
    }

    function open() {
      if (!list.hidden) return;
      render('');
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      var current = shown.findIndex(function (i) { return i.value === select.value; });
      if (current >= 0) highlight(current);
    }

    function close() {
      list.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
    }

    function choose(item) {
      select.value = item.value;
      input.value = item.label;
      input.removeAttribute('aria-invalid');
      close();
      showOther(item.value === OTHER, true);
      select.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function restore() {
      input.value = labelOf(select.value);
    }

    // Start from the server's value
    restore();
    showOther(select.value === OTHER, false);
    if (!select.value && !isFilter) input.placeholder = placeholder + ' (type to search)';

    input.addEventListener('focus', function () {
      if (isFilter) {
        input.placeholder = labelOf(select.value);
        input.value = '';
      } else {
        input.select();
      }
      open();
    });
    input.addEventListener('click', open);
    input.addEventListener('input', function () {
      if (list.hidden) { list.hidden = false; input.setAttribute('aria-expanded', 'true'); }
      render(input.value);
    });
    input.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (list.hidden) open();
        var step = event.key === 'ArrowDown' ? 1 : -1;
        highlight(Math.max(0, Math.min(shown.length - 1, active + step)));
      } else if (event.key === 'Enter') {
        if (!list.hidden && shown[active]) {
          event.preventDefault();  // pick the university, don't submit the form
          choose(shown[active]);
        }
      } else if (event.key === 'Escape') {
        if (!list.hidden) {
          event.preventDefault();
          close();
          restore();
        }
      } else if (event.key === 'Tab') {
        close();
      }
    });
    input.addEventListener('blur', function () {
      // Typed a full name or code exactly? Take it; otherwise go back to what was picked.
      var typed = input.value.trim().toLowerCase();
      var exact = typed && items.find(function (i) { return i.value !== OTHER && (i.key === typed || i.value.toLowerCase() === typed); });
      if (exact && exact.value !== select.value) choose(exact);
      else restore();
      close();
    });
  }

  document.querySelectorAll('[data-uni-picker]').forEach(setup);
})();
