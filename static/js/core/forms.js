// Small form helpers, all opt-in through data attributes:
//   <form data-autosubmit>          selects and radios submit the form as soon as they change; empty
//                                   fields are left out of the address
//   <button data-confirm="...">     asks before submitting (e.g. delete, reject)
//   <label class="dropzone">        shows the chosen file's name and size; accepts drag and drop
//   <button data-password-toggle>   shows / hides the password in the same .password-field
//   <nav data-term-chips>           a sideways-scrolling chip row starts with the chosen chip in view
//   Forms disable their submit button after the first click, so a slow upload isn't sent twice.
(function () {
  'use strict';

  document.querySelectorAll('form[data-autosubmit]').forEach(function (form) {
    form.querySelectorAll('select, input[type="radio"]').forEach(function (control) {
      control.addEventListener('change', function () { form.requestSubmit ? form.requestSubmit() : form.submit(); });
    });
  });

  // Search and filter forms (GET) leave out empty fields, so the address reads ?university=UAP&term=2-1
  // rather than ?q=&university=UAP&term=2-1&sort=
  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (event.defaultPrevented || form.method.toLowerCase() !== 'get' || !form.hasAttribute('data-autosubmit')) return;
    var params = new URLSearchParams();
    new FormData(form, event.submitter).forEach(function (value, name) {
      if (typeof value === 'string' && value.trim()) params.append(name, value);
    });
    event.preventDefault();
    var query = params.toString();
    window.location.assign(form.action.split('?')[0] + (query ? '?' + query : ''));
  });

  // A row of chips that scrolls sideways on phones (notes/_term_chips.html): bring the chosen one into view
  document.querySelectorAll('[data-term-chips]').forEach(function (row) {
    var chosen = row.querySelector('.is-active');
    if (chosen && row.scrollWidth > row.clientWidth) {
      row.scrollLeft = chosen.offsetLeft - (row.clientWidth - chosen.offsetWidth) / 2;
    }
  });

  document.addEventListener('click', function (event) {
    var button = event.target.closest('button[data-confirm], input[data-confirm]');
    if (button && !window.confirm(button.getAttribute('data-confirm'))) event.preventDefault();
  });

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (event.defaultPrevented || form.method.toLowerCase() !== 'post') return;
    var button = event.submitter;
    if (!button || button.hasAttribute('data-no-busy')) return;
    // Keep the clicked button's name/value in the submission before disabling it
    if (button.name) {
      var hidden = document.createElement('input');
      hidden.type = 'hidden'; hidden.name = button.name; hidden.value = button.value;
      form.appendChild(hidden);
    }
    setTimeout(function () { button.disabled = true; button.classList.add('is-busy'); }, 0);
  });

  function formatSize(bytes) {
    if (bytes < 1024 * 1024) return Math.max(1, Math.round(bytes / 1024)) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  document.querySelectorAll('.dropzone').forEach(function (zone) {
    var input = zone.querySelector('input[type="file"]');
    var label = zone.querySelector('.dropzone__file');
    if (!input || !label) return;
    function show() {
      var files = Array.prototype.slice.call(input.files || []);
      zone.classList.toggle('has-file', files.length > 0);
      var total = files.reduce(function (sum, file) { return sum + file.size; }, 0);
      label.textContent = files.length > 1 ? files.length + ' files · ' + formatSize(total)
        : files.length ? files[0].name + ' · ' + formatSize(total) : '';
    }
    input.addEventListener('change', show);
    ['dragenter', 'dragover'].forEach(function (type) {
      zone.addEventListener(type, function (e) { e.preventDefault(); zone.classList.add('is-over'); });
    });
    ['dragleave', 'drop'].forEach(function (type) {
      zone.addEventListener(type, function () { zone.classList.remove('is-over'); });
    });
    zone.addEventListener('drop', function (e) {
      e.preventDefault();
      if (e.dataTransfer && e.dataTransfer.files.length) { input.files = e.dataTransfer.files; show(); }
    });
  });

  document.querySelectorAll('[data-password-toggle]').forEach(function (button) {
    var input = button.closest('.password-field').querySelector('input');
    button.addEventListener('click', function () {
      var hidden = input.type === 'password';
      input.type = hidden ? 'text' : 'password';
      button.setAttribute('aria-pressed', String(hidden));
      button.setAttribute('aria-label', hidden ? 'Hide password' : 'Show password');
    });
  });
})();
