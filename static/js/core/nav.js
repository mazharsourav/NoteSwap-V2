// Header behaviour: shadow once the page scrolls, the account dropdown, and the phone menu.
(function () {
  'use strict';

  // Header shadow
  var header = document.querySelector('[data-header]');
  if (header) {
    var onScroll = function () { header.classList.toggle('is-scrolled', window.scrollY > 4); };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  // Dropdowns: <div data-dropdown> <button data-dropdown-toggle aria-expanded> <div data-dropdown-panel hidden>
  document.querySelectorAll('[data-dropdown]').forEach(function (root) {
    var toggle = root.querySelector('[data-dropdown-toggle]');
    var panel = root.querySelector('[data-dropdown-panel]');
    if (!toggle || !panel) return;

    function setOpen(open, returnFocus) {
      panel.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
      if (!open && returnFocus) toggle.focus();
    }

    toggle.addEventListener('click', function () { setOpen(panel.hidden); });
    document.addEventListener('click', function (event) {
      if (!panel.hidden && !root.contains(event.target)) setOpen(false);
    });
    root.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !panel.hidden) setOpen(false, true);
    });
    root.addEventListener('focusout', function (event) {
      if (!panel.hidden && event.relatedTarget && !root.contains(event.relatedTarget)) setOpen(false);
    });
  });

  // Sidebars that turn into a dropdown on phones (account and Manage): <nav data-side-menu>
  // with a [data-side-menu-toggle] button. The button shows the current page, and a count of
  // what is waiting on the other pages so nothing hides behind the closed menu.
  document.querySelectorAll('[data-side-menu]').forEach(function (nav) {
    var toggle = nav.querySelector('[data-side-menu-toggle]');
    if (!toggle) return;
    var current = nav.querySelector('[data-side-menu-current]');
    var active = nav.querySelector('.sidelink.is-active');
    if (active && current) {
      var icon = active.querySelector('.icon');
      var label = active.querySelector('span');
      current.textContent = '';
      if (icon) current.appendChild(icon.cloneNode(true));
      current.appendChild(document.createTextNode(label ? label.textContent : active.textContent.trim()));
    }
    var waiting = 0;
    nav.querySelectorAll('.sidelink:not(.is-active) .count').forEach(function (count) {
      waiting += parseInt(count.textContent, 10) || 0;
    });
    var badge = nav.querySelector('[data-side-menu-waiting]');
    if (badge && waiting) {
      badge.textContent = waiting;
      badge.title = waiting + ' waiting on other pages';
      badge.hidden = false;
    }

    function setOpen(open, returnFocus) {
      nav.classList.toggle('is-open', open);
      toggle.setAttribute('aria-expanded', String(open));
      if (!open && returnFocus) toggle.focus();
    }

    toggle.hidden = false;
    toggle.addEventListener('click', function () { setOpen(!nav.classList.contains('is-open')); });
    document.addEventListener('click', function (event) {
      if (nav.classList.contains('is-open') && !nav.contains(event.target)) setOpen(false);
    });
    nav.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && nav.classList.contains('is-open')) setOpen(false, true);
    });
    // Back on a wide screen the toggle is hidden: drop the open state with it.
    window.addEventListener('resize', function () {
      if (nav.classList.contains('is-open') && !toggle.offsetParent) setOpen(false);
    });
  });

  // Phone menu: <button data-menu-open aria-controls="mobile-menu"> opens #mobile-menu
  var openBtn = document.querySelector('[data-menu-open]');
  var menu = openBtn && document.getElementById(openBtn.getAttribute('aria-controls'));
  if (openBtn && menu) {
    var closeBtn = menu.querySelector('[data-menu-close]');

    var setMenu = function (open) {
      menu.hidden = !open;
      openBtn.setAttribute('aria-expanded', String(open));
      document.body.classList.toggle('is-locked', open);
      (open ? closeBtn : openBtn).focus();
    };

    openBtn.addEventListener('click', function () { setMenu(true); });
    closeBtn.addEventListener('click', function () { setMenu(false); });
    menu.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') setMenu(false);
      // Keep keyboard focus inside the open menu
      if (event.key !== 'Tab') return;
      var items = menu.querySelectorAll('a[href], button:not([disabled]), input:not([type="hidden"])');
      var first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    window.matchMedia('(min-width: 901px)').addEventListener('change', function (mq) {
      if (mq.matches && !menu.hidden) setMenu(false);
    });
  }
})();
