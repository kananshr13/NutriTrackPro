// Shared motion utilities: scroll-reveal + count-up.
// Include with: <script src="app.js" defer></script>

document.addEventListener('DOMContentLoaded', () => {
  // Scroll-reveal: any element with class "reveal" or "reveal-group"
  // fades/slides in the first time it enters the viewport.
  const targets = document.querySelectorAll('.reveal, .reveal-group');
  if (targets.length && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in-view');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15 });

    targets.forEach((el) => io.observe(el));
  } else {
    // No IntersectionObserver support: just show everything.
    targets.forEach((el) => el.classList.add('in-view'));
  }
});


function countUp(el, target, opts = {}) {
  if (!el) return;
  const duration = opts.duration || 700;
  const decimals = opts.decimals ?? (Number.isInteger(target) ? 0 : 1);
  const suffix = opts.suffix || '';
  const start = 0;
  const startTime = performance.now();

  function tick(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    const value = start + (target - start) * eased;
    el.textContent = value.toFixed(decimals) + suffix;
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}