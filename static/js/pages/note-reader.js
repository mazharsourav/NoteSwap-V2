// Note page: the main file and every additional file shown as one document (js/core/reader.js).
// If the reader can't start, the list of file links in the page shows instead.
// Stored file names mean nothing to readers ("chem_lab-1_4gv5Z6V.pdf"), so the reader names each
// file by its place in the note instead: "PDF", or "Part 2 of 3 · Image" when there are several.
import { mountReader } from '../core/reader.js';

const TYPE_LABELS = { pdf: 'PDF', image: 'Image' };

const viewer = document.querySelector('[data-viewer]');
const filesData = document.getElementById('reader-files');
if (viewer && filesData) {
  const files = JSON.parse(filesData.textContent);
  files.forEach((file, i) => {
    const type = TYPE_LABELS[file.type] || 'File';
    file.name = files.length > 1 ? `Part ${i + 1} of ${files.length} · ${type}` : type;
  });
  mountReader(viewer, files);
}
