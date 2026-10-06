// Manage tables: "select all" checkboxes, and the bulk buttons stay disabled until something is selected.
// A button with data-requires-reason makes the form's reason box required, only for that button.
(function () {
  'use strict';

  document.querySelectorAll('[data-select-group]').forEach(function (form) {
    var all = form.querySelector('[data-select-all]');
    var boxes = Array.prototype.slice.call(form.querySelectorAll('tbody input[type="checkbox"]'));
    var buttons = form.querySelectorAll('button[type="submit"]');

    function update() {
      var checked = boxes.filter(function (box) { return box.checked; }).length;
      if (all) {
        all.checked = checked > 0 && checked === boxes.length;
        all.indeterminate = checked > 0 && checked < boxes.length;
      }
      buttons.forEach(function (button) { button.disabled = checked === 0; });
      boxes.forEach(function (box) { box.closest('tr').classList.toggle('is-selected', box.checked); });
    }

    if (all) {
      all.addEventListener('change', function () {
        boxes.forEach(function (box) { box.checked = all.checked; });
        update();
      });
    }
    boxes.forEach(function (box) { box.addEventListener('change', update); });
    update();

    var reason = form.querySelector('textarea[name="reason"]');
    if (reason) {
      buttons.forEach(function (button) {
        button.addEventListener('click', function () { reason.required = button.hasAttribute('data-requires-reason'); });
      });
    }
  });
})();
