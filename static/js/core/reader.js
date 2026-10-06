// The file reader: shows one or more files (PDFs and photos) as one document, page after page.
// Photos are one page each; PDFs are drawn with PDF.js (static/vendor/pdfjs, only loaded when there
// is a PDF) instead of the browser's own viewer, so it looks the same everywhere, phones included.
// Every page fills the width (zoom multiplies that). Pages are drawn only near the visible area and
// dropped again when far away, so long files stay light.
//
// mountReader(viewer, files) fills a .viewer (markup: components/reader.css) and returns
// { destroy } to stop it. files: [{ url, name, type: 'pdf' | 'image', pending?, width?, height? }].
// Used by js/pages/note-reader.js (note page) and js/pages/file-preview.js (preview pop-up).

const ZOOMS = [0.5, 0.75, 1, 1.25, 1.5, 2, 3]; // multiples of "fit to width"
const MAX_CANVAS_PIXELS = 16e6;                 // keeps big zoomed pages within phone memory limits
const PORTRAIT = 1.414;                         // A4, until a photo of unknown size has loaded

// A page that couldn't be drawn: say so and link the file
function brokenPage(file, message) {
  const box = document.createElement('div');
  box.className = 'reader__broken';
  const text = document.createElement('p');
  text.textContent = message;
  const link = document.createElement('a');
  link.className = 'btn btn-secondary btn-sm';
  link.href = file.url;
  link.target = '_blank';
  link.rel = 'noopener';
  link.textContent = `Open ${file.name}`;
  box.append(text, link);
  return box;
}

async function loadPdfPages(file, pdfjs) {
  try {
    const pdf = await pdfjs.getDocument({ url: file.url, isEvalSupported: false }).promise;
    const numbers = Array.from({ length: pdf.numPages }, (_, i) => i + 1);
    return await Promise.all(numbers.map(async (n) => {
      const pdfPage = await pdf.getPage(n);
      const { width, height } = pdfPage.getViewport({ scale: 1 });
      return { file, kind: 'pdf', pdfPage, ratio: height / width };
    }));
  } catch (error) {
    console.error(`Reader: ${file.name}`, error);
    const message = error && error.name === 'PasswordException'
      ? 'This PDF is password-protected. Download it to open it with the password.'
      : 'This PDF can’t be shown here.';
    return [{ file, kind: 'broken', message, ratio: 0.5 }];
  }
}

export function mountReader(viewer, files) {
  const root = viewer.querySelector('[data-reader]');
  const tools = viewer.querySelector('[data-reader-tools]');
  const cleanups = [];
  let stopped = false;

  function fail(error) {
    if (stopped) return;
    console.error('Reader:', error);
    viewer.classList.add('is-failed');
    tools.hidden = true;
  }

  start().catch(fail);
  return {
    destroy() {
      stopped = true;
      cleanups.forEach((cleanup) => cleanup());
    },
  };

  async function start() {
    const status = root.querySelector('[data-reader-status]');
    const pageNow = tools.querySelector('[data-reader-page]');
    const fitButton = tools.querySelector('[data-reader-zoom="fit"]');
    const nameLabel = viewer.querySelector('[data-reader-name]');
    const openLink = viewer.querySelector('[data-reader-open]');

    // Build the page list in reading order. Every page's shape is known before anything is drawn,
    // so the layout never jumps.
    let pdfjs = null;
    if (files.some((file) => file.type === 'pdf')) {
      pdfjs = await import(root.dataset.lib);
      pdfjs.GlobalWorkerOptions.workerSrc = root.dataset.worker;
    }
    const perFile = await Promise.all(files.map((file) => {
      if (file.type === 'pdf') return loadPdfPages(file, pdfjs);
      const known = file.width && file.height;
      return [{ file, kind: 'image', ratio: known ? file.height / file.width : PORTRAIT, sized: known }];
    }));
    if (stopped) return;
    const pages = perFile.flat().map((page, i) => {
      const el = document.createElement('div');
      el.className = 'reader__page';
      el.dataset.index = i;
      if (page.file.pending) {
        const badge = document.createElement('span');
        badge.className = 'chip chip-gray chip-sm reader__badge';
        badge.textContent = 'Waiting for review';
        el.append(badge);
      }
      return Object.assign(page, { n: i + 1, el, task: null, token: 0, visible: false });
    });

    if (status) status.remove();
    root.append(...pages.map((p) => p.el));
    tools.querySelector('[data-reader-pages]').textContent = pages.length;
    tools.hidden = false;

    let width = 0; // display width of a page at "Fit"
    let zoom = 1;  // one of ZOOMS

    const pageWidth = () => Math.floor(width * zoom);

    function measureFit() {
      const style = getComputedStyle(root);
      width = Math.max(root.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight), 100);
    }

    function size(p) {
      p.el.style.width = `${pageWidth()}px`;
      p.el.style.height = `${Math.floor(pageWidth() * p.ratio)}px`;
    }

    // Replace what's drawn on a page, keeping its "Waiting for review" badge
    function show(p, content) {
      p.el.querySelectorAll(':scope > :not(.reader__badge)').forEach((old) => old.remove());
      if (content) p.el.append(content);
    }

    async function draw(p) {
      const token = ++p.token;
      if (p.task) p.task.cancel();

      if (p.kind === 'broken') {
        show(p, brokenPage(p.file, p.message));
        return;
      }
      if (p.kind === 'image') {
        if (p.el.querySelector('img')) return; // already shown; CSS scales it to any zoom
        const img = new Image();
        img.alt = p.file.name;
        img.decoding = 'async';
        img.src = p.file.url;
        try {
          await img.decode();
        } catch (error) {
          if (token === p.token) show(p, brokenPage(p.file, 'This image can’t be shown here.'));
          return;
        }
        if (token !== p.token) return;
        if (!p.sized) { // the server didn't know its size: use the real one now
          p.sized = true;
          p.ratio = img.naturalHeight / img.naturalWidth;
          size(p);
        }
        show(p, img); // swap in finished drawings only, so nothing flashes blank
        return;
      }

      const natural = p.pdfPage.getViewport({ scale: 1 });
      let pixels = (pageWidth() / natural.width) * Math.min(window.devicePixelRatio || 1, 2);
      if (natural.width * natural.height * pixels * pixels > MAX_CANVAS_PIXELS) {
        pixels = Math.sqrt(MAX_CANVAS_PIXELS / (natural.width * natural.height));
      }
      const viewport = p.pdfPage.getViewport({ scale: pixels });
      const canvas = document.createElement('canvas');
      canvas.width = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);

      p.task = p.pdfPage.render({ canvas, viewport });
      try {
        await p.task.promise;
      } catch (error) {
        if (error && error.name === 'RenderingCancelledException') return;
        throw error;
      }
      if (token !== p.token) return;
      p.task = null;
      show(p, canvas);
    }

    function drop(p) {
      p.token++;
      if (p.task) p.task.cancel();
      p.task = null;
      show(p, null);
    }

    const nearby = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        const p = pages[entry.target.dataset.index];
        p.visible = entry.isIntersecting;
        if (p.visible) draw(p).catch(fail);
        else drop(p);
      });
    }, { root, rootMargin: '100% 0px' });

    // The page at 40% down the window counts as "the current page"
    function currentPage() {
      const line = root.scrollTop + root.clientHeight * 0.4;
      let current = pages[0];
      for (const p of pages) {
        if (p.el.offsetTop > line) break;
        current = p;
      }
      return current;
    }

    // Page counter, and the name / "open in new tab" of the file that page belongs to
    let shownFile = null;
    function showPage() {
      const p = currentPage();
      pageNow.textContent = p.n;
      if (p.file !== shownFile) {
        shownFile = p.file;
        if (nameLabel) nameLabel.textContent = p.file.name;
        if (openLink) openLink.href = p.file.url;
      }
    }

    // Resize every page and keep the same spot of the same page in view
    function relayout() {
      const anchor = currentPage();
      const into = (root.scrollTop - anchor.el.offsetTop) / anchor.el.offsetHeight;
      pages.forEach(size);
      root.scrollTop = anchor.el.offsetTop + into * anchor.el.offsetHeight;
      root.scrollLeft = (root.scrollWidth - root.clientWidth) / 2;
      pages.filter((p) => p.visible && p.kind === 'pdf').forEach((p) => draw(p).catch(fail));
      fitButton.textContent = zoom === 1 ? 'Fit' : `${Math.round(zoom * 100)}%`;
      tools.querySelector('[data-reader-zoom="out"]').disabled = zoom === ZOOMS[0];
      tools.querySelector('[data-reader-zoom="in"]').disabled = zoom === ZOOMS[ZOOMS.length - 1];
      showPage();
    }

    function onZoom(event) {
      const button = event.target.closest('[data-reader-zoom]');
      if (!button) return;
      const step = ZOOMS.indexOf(zoom);
      const action = button.dataset.readerZoom;
      if (action === 'in') zoom = ZOOMS[Math.min(step + 1, ZOOMS.length - 1)];
      else if (action === 'out') zoom = ZOOMS[Math.max(step - 1, 0)];
      else zoom = 1;
      relayout();
    }
    tools.addEventListener('click', onZoom);

    let scrolling = false;
    function onScroll() {
      if (scrolling) return;
      scrolling = true;
      requestAnimationFrame(() => { scrolling = false; showPage(); });
    }
    root.addEventListener('scroll', onScroll, { passive: true });

    // Refit when the width changes (window resize, phone rotation, full screen)
    let lastWidth = root.clientWidth;
    let resizeTimer;
    const resized = new ResizeObserver(() => {
      if (root.clientWidth === lastWidth) return;
      lastWidth = root.clientWidth;
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => { measureFit(); relayout(); }, 120);
    });
    resized.observe(root);

    cleanups.push(() => {
      nearby.disconnect();
      resized.disconnect();
      clearTimeout(resizeTimer);
      tools.removeEventListener('click', onZoom);
      root.removeEventListener('scroll', onScroll);
      pages.forEach((p) => { if (p.task) p.task.cancel(); });
    });

    measureFit();
    relayout();
    pages.forEach((p) => nearby.observe(p.el));
  }
}
