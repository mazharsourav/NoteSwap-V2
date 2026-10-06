// Note page: the viewer's "Full screen" button (only shown where the browser supports it).
(function () {
  'use strict';

  var viewer = document.querySelector('[data-viewer]');
  var button = viewer && viewer.querySelector('[data-fullscreen]');
  if (!button || !document.fullscreenEnabled) return;

  button.hidden = false;
  button.addEventListener('click', function () {
    if (document.fullscreenElement) document.exitFullscreen();
    else viewer.requestFullscreen();
  });
  document.addEventListener('fullscreenchange', function () {
    var on = document.fullscreenElement === viewer;
    viewer.classList.toggle('is-fullscreen', on);
    button.querySelector('span').textContent = on ? 'Exit full screen' : 'Full screen';
  });
})();
