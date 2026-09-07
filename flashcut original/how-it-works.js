// how-it-works.js — page-specific JS (script.js handles canvas + nav)

// ─── Scroll Reveal for HIW-specific elements ──────────
(function () {
  const els = document.querySelectorAll('.flow-node, .trust-card, .hiw-cta-inner');
  els.forEach(el => el.classList.add('reveal'));

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        setTimeout(() => entry.target.classList.add('visible'), i * 100);
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  els.forEach(el => observer.observe(el));
})();

// ─── Timeline steps — slide in from alternating sides ─
(function () {
  document.querySelectorAll('.timeline-step').forEach((step, i) => {
    step.style.opacity = '0';
    step.style.transform = i % 2 === 0 ? 'translateX(-40px)' : 'translateX(40px)';
    step.style.transition = 'opacity 0.7s ease, transform 0.7s ease';

    const obs = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        step.style.opacity = '1';
        step.style.transform = 'translateX(0)';
        obs.unobserve(step);
      }
    }, { threshold: 0.12 });

    obs.observe(step);
  });
})();

// ─── Journey pill dot cycle ────────────────────────────
(function () {
  const dots = document.querySelectorAll('.pill-dot');
  if (!dots.length) return;
  let active = 0;

  setInterval(() => {
    dots.forEach(d => d.classList.remove('active'));
    active = (active + 1) % dots.length;
    dots[active].classList.add('active');
  }, 1200);
})();

// ─── AI progress bar animate on scroll ────────────────
(function () {
  const step4 = document.getElementById('step4');
  if (!step4) return;

  const obs = new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting) {
      const bar = step4.querySelector('.ai-task.active .ai-bar');
      if (bar) bar.style.animation = 'aiProgress 1.5s ease infinite alternate';
      obs.unobserve(step4);
    }
  }, { threshold: 0.3 });

  obs.observe(step4);
})();
