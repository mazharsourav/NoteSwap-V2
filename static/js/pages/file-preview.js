// File preview pop-up (components/_file_preview.html): a link with data-preview="file name" opens its
// file in the reader (js/core/reader.js) instead of a new tab. Ctrl/⌘/Shift-click still opens a tab.
import { mountReader } from '../core/reader.js';

const dialog = document.getElementById('file-preview');
const template = document.getElementById('file-preview-viewer');
let reader = null;

function open(url, name) {
  const viewer = template.content.firstElementChild.cloneNode(true);
  viewer.querySelector('[data-reader-name]').textContent = name;
  viewer.querySelector('[data-reader-open]').href = url;
  viewer.querySelector('[data-preview-download]').href = url;
  dialog.replaceChildren(viewer);
  dialog.showModal(); // first, so the reader can measure its width
  reader = mountReader(viewer, [{ url, name, type: /\.pdf$/i.test(name) ? 'pdf' : 'image' }]);
  viewer.querySelector('[data-reader]').focus();
}

if (dialog && template && typeof dialog.showModal === 'function') {
  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[data-preview]');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey) return;
    event.preventDefault();
    open(link.href, link.dataset.preview);
  });
  dialog.addEventListener('close', () => {
    if (reader) reader.destroy();
    reader = null;
    dialog.replaceChildren();
  });
}
