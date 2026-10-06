// Upload / edit note form.
//
// "Add a course" opens a pop-up (notes/_place_dialogs.html) that saves with fetch(), so the
// half-filled note stays; the new course is added to the list and picked.
(function () {
  'use strict';

  var subjectPicker = document.querySelector('[data-subject-picker]');
  if (!subjectPicker) return;

  // ---------- Add a course pop-up ----------

  function insertSorted(select, option) {
    var next = Array.prototype.find.call(select.options, function (other, i) {
      return i >= 1 && other.text.localeCompare(option.text) > 0;
    });
    select.insertBefore(option, next || null);
  }

  function subjectOption(subject) {
    var option = document.createElement('option');
    option.value = subject.id;
    option.textContent = subject.name;
    return option;
  }

  function showErrors(placeForm, errors) {
    var general = placeForm.querySelector('[data-place-error]');
    general.hidden = true;
    placeForm.querySelectorAll('.field-error').forEach(function (el) { el.remove(); });
    placeForm.querySelectorAll('.has-error').forEach(function (el) { el.classList.remove('has-error'); });
    Object.keys(errors || {}).forEach(function (name) {
      var text = errors[name].map(function (e) { return e.message; }).join(' ');
      var field = placeForm.elements[name];
      if (!field) {
        general.textContent = text;
        general.hidden = false;
        return;
      }
      var error = document.createElement('span');
      error.className = 'field-error';
      error.textContent = text;
      field.closest('.field').classList.add('has-error');
      field.closest('.field').appendChild(error);
    });
  }

  document.querySelectorAll('[data-place-form]').forEach(function (placeForm) {
    placeForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var button = placeForm.querySelector('[type="submit"]');
      button.disabled = true;
      fetch(placeForm.action, {
        method: 'POST',
        body: new FormData(placeForm),
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
      }).then(function (response) {
        return response.json().then(function (data) { return { ok: response.ok, data: data }; });
      }).then(function (result) {
        if (!result.ok) return showErrors(placeForm, result.data.errors);
        showErrors(placeForm, null);
        insertSorted(subjectPicker, subjectOption(result.data));
        subjectPicker.value = String(result.data.id);
        fillFromSubject(true);
        placeForm.reset();
        placeForm.closest('dialog').close();
        subjectPicker.focus();
      }).catch(function () {
        showErrors(placeForm, { __all__: [{ message: 'Couldn’t save it. Check your connection and try again.' }] });
      }).then(function () {
        button.disabled = false;
      });
    });
  });
})();
