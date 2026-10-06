// Flash messages (see templates/partials/_messages.html): close with the x. Success and info
// messages leave on their own after a few seconds (paused while the pointer is over them);
// warnings and errors stay until closed.
(function () {
  'use strict';

  document.querySelectorAll('.flash').forEach(function (flash) {
    var timer = null;

    function dismiss() {
      if (flash.classList.contains('is-leaving')) return;
      flash.classList.add('is-leaving');
      flash.addEventListener('animationend', function () { flash.remove(); }, { once: true });
      setTimeout(function () { flash.remove(); }, 400); // in case animations are off
    }
    function schedule() { timer = setTimeout(dismiss, 6000); }

    flash.querySelector('.flash__close').addEventListener('click', dismiss);

    if (flash.classList.contains('flash--success') || flash.classList.contains('flash--info')) {
      schedule();
      flash.addEventListener('mouseenter', function () { clearTimeout(timer); });
      flash.addEventListener('mouseleave', schedule);
    }
  });
})();
