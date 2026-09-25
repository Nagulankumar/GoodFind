// Dismiss a notification without reloading the page.
document.querySelectorAll('form[data-dismiss]').forEach(function (form) {
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    fetch(form.action, { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function () {
        var card = form.closest('[data-note]');
        if (card) { card.classList.add('read'); form.remove(); }
      });
  });
});

// Keep the message thread scrolled to the newest message.
var bubbles = document.querySelector('.bubbles');
if (bubbles) { bubbles.scrollTop = bubbles.scrollHeight; }

// Show the chosen photo before the form is submitted.
document.querySelectorAll('input[type="file"][data-preview]').forEach(function (input) {
  var img = document.querySelector(input.dataset.preview);
  if (!img) { return; }
  input.addEventListener('change', function () {
    var file = input.files && input.files[0];
    if (!file) { img.hidden = true; return; }
    img.src = URL.createObjectURL(file);
    img.hidden = false;
  });
});
