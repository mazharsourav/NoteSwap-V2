// Links that change data (approve, reject, logout, ...) are marked with
// data-post-url. Clicking one submits the shared CSRF-protected form in
// base.html as a POST instead of following the link with a GET.
// Optional data-confirm="..." asks for confirmation first.
document.addEventListener('click', function (event) {
  const link = event.target.closest('a[data-post-url]');
  if (!link) return;
  event.preventDefault();

  const message = link.dataset.confirm;
  if (message && !window.confirm(message)) return;

  const form = document.getElementById('post-action-form');
  form.action = link.dataset.postUrl;
  form.submit();
});
