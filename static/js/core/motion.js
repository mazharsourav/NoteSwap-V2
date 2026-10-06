// Gentle motion, only when the visitor hasn't asked their system to reduce it.
// The inline script in base.html adds .motion to <html> before the page paints.
//   data-reveal          fade the element up when it scrolls into view
//   data-reveal-stagger  on a grid: reveal its children one after another
//   data-count-to="123"  count up to the number when it scrolls into view
(function () {
  'use strict';

  var root = document.documentElement;
  clearTimeout(window.__motionFallback);
  if (!root.classList.contains('motion')) return;

  document.querySelectorAll('[data-reveal-stagger]').forEach(function (group) {
    Array.prototype.forEach.call(group.children, function (child, i) {
      child.setAttribute('data-reveal', '');
      child.style.setProperty('--reveal-delay', Math.min(i, 8) * 70 + 'ms');
    });
  });

  var revealer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      revealer.unobserve(entry.target);
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  document.querySelectorAll('[data-reveal]').forEach(function (el) { revealer.observe(el); });

  var counter = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      counter.unobserve(entry.target);
      countUp(entry.target);
    });
  }, { threshold: 0.6 });
  document.querySelectorAll('[data-count-to]').forEach(function (el) { counter.observe(el); });

  function countUp(el) {
    var target = parseInt(el.getAttribute('data-count-to'), 10) || 0;
    var duration = 900, start = null;
    function frame(now) {
      if (start === null) start = now;
      var t = Math.min(1, (now - start) / duration);
      var eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(target * eased).toLocaleString('en-US');
      if (t < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
})();
