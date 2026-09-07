// ─── Animated Background Canvas ───────────────────────
(function () {
  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  let W, H;
  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  const orbs = [
    {
      color: [212, 160, 23],   // gold #d4a017
      alpha: 0.55,
      size: 0.5,
      speed: 0.012,
      phase: 0,
      pathX: (t) => 0.5 + 0.42 * Math.sin(t),
      pathY: (t) => 0.5 + 0.38 * Math.cos(t * 0.8),
    },
    {
      color: [184, 134, 11],   // dark gold #b8860b
      alpha: 0.45,
      size: 0.55,
      speed: 0.009,
      phase: Math.PI,
      pathX: (t) => 0.5 + 0.42 * Math.sin(t + Math.PI),
      pathY: (t) => 0.5 + 0.38 * Math.cos(t * 0.8 + Math.PI),
    },
  ];

  let t = 0;

  function draw() {
    ctx.fillStyle = 'rgba(10,8,5,0.18)';
    ctx.fillRect(0, 0, W, H);

    for (const orb of orbs) {
      const time = t * orb.speed + orb.phase;
      const cx = orb.pathX(time) * W;
      const cy = orb.pathY(time) * H;
      const radius = orb.size * Math.min(W, H);
      const [r, g, b] = orb.color;

      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
      grad.addColorStop(0,    `rgba(${r},${g},${b},${orb.alpha})`);
      grad.addColorStop(0.45, `rgba(${r},${g},${b},${orb.alpha * 0.4})`);
      grad.addColorStop(1,    `rgba(${r},${g},${b},0)`);

      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();
    }

    t++;
    requestAnimationFrame(draw);
  }

  ctx.fillStyle = '#0a0805';
  ctx.fillRect(0, 0, W, H);
  draw();
})();

// ─── Typing Animation ─────────────────────────────────
(function () {
  const typedEl = document.getElementById('typed-text');
  const cursorEl = document.querySelector('.cursor');
  if (!typedEl) return;

  const segments = [
    { text: 'Shoot. ', red: false },
    { text: 'Edit. ',  red: false },
    { text: 'Deliver.', red: true  },
  ];

  const fullString = segments.map(s => s.text).join('');
  let charIndex = 0;
  const TYPE_SPEED = 85;

  function buildHTML(len) {
    let html = '';
    let pos = 0;
    for (const seg of segments) {
      if (pos >= len) break;
      const visible = seg.text.slice(0, Math.min(len - pos, seg.text.length));
      html += seg.red
        ? `<span style="color:var(--accent)">${visible}</span>`
        : `<span style="color:#f0f0f0">${visible}</span>`;
      pos += seg.text.length;
    }
    return html;
  }

  function type() {
    charIndex++;
    typedEl.innerHTML = buildHTML(charIndex);
    if (charIndex < fullString.length) {
      setTimeout(type, TYPE_SPEED);
    } else {
      if (cursorEl) cursorEl.style.display = 'none';
    }
  }

  setTimeout(type, 700);
})();

// ─── Sticky Nav ───────────────────────────────────────
const navbar = document.getElementById('navbar');
if (navbar) {
  window.addEventListener('scroll', () => {
    navbar.classList.toggle('scrolled', window.scrollY > 40);
  }, { passive: true });
}

// ─── Scroll Reveal ────────────────────────────────────
(function () {
  const revealEls = document.querySelectorAll(
    '.stat-card, .step, .portfolio-item, .pricing-card, .testimonial-card, .section-header, .reveal'
  );

  revealEls.forEach(el => {
    if (!el.classList.contains('reveal')) el.classList.add('reveal');
  });

  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        setTimeout(() => entry.target.classList.add('visible'), i * 80);
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  revealEls.forEach(el => revealObserver.observe(el));
})();

// ─── Counter Animation ────────────────────────────────
(function () {
  function animateCounter(el) {
    const target = parseInt(el.dataset.target, 10);
    const duration = 1800;
    const start = performance.now();

    function update(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = Math.floor(eased * target).toLocaleString();
      if (progress < 1) requestAnimationFrame(update);
      else el.textContent = target.toLocaleString();
    }

    requestAnimationFrame(update);
  }

  const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        animateCounter(entry.target);
        counterObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.5 });

  document.querySelectorAll('.stat-number').forEach(el => counterObserver.observe(el));
})();

// ─── Mobile Nav Active State ──────────────────────────
(function () {
  const mobileLinks = document.querySelectorAll('.mobile-nav-item');
  const sections = document.querySelectorAll('section[id]');

  function updateActiveNav() {
    let current = '';
    sections.forEach(section => {
      if (window.scrollY >= section.offsetTop - 200) current = section.id;
    });
    mobileLinks.forEach(link => {
      link.classList.remove('active');
      const raw = link.getAttribute('href');
      if (!raw) return;
      const href = raw.replace('#', '');
      if (href === current) link.classList.add('active');
    });
  }

  window.addEventListener('scroll', updateActiveNav, { passive: true });
})();

// ─── Portfolio 3D Tilt ────────────────────────────────
document.querySelectorAll('.portfolio-thumb').forEach(card => {
  card.addEventListener('mousemove', (e) => {
    const rect = card.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width  - 0.5) * 12;
    const y = ((e.clientY - rect.top)  / rect.height - 0.5) * 12;
    card.style.transform = `perspective(600px) rotateX(${-y}deg) rotateY(${x}deg) scale(1.02)`;
  });
  card.addEventListener('mouseleave', () => {
    card.style.transform = '';
  });
});

// ─── More Drawer ──────────────────────────────────────
function openMoreDrawer() {
  const drawer = document.getElementById('moreDrawer');
  if (drawer) drawer.classList.add('open');
}

function closeMoreDrawer() {
  const drawer = document.getElementById('moreDrawer');
  if (drawer) drawer.classList.remove('open');
}

// ─── Booking Modal ───────────────────────────────────
(function () {
  const modal = document.getElementById('bookingModal');
  const form = document.getElementById('bookingForm');
  const successMsg = document.getElementById('bookingSuccess');
  const openButtons = document.querySelectorAll('.open-booking');
  const closeButtons = modal ? modal.querySelectorAll('.booking-modal-close, [data-close-booking]') : [];

  function setBodyScroll(enabled) {
    document.body.style.overflow = enabled ? '' : 'hidden';
  }

  function openBooking() {
    if (!modal) return;
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    setBodyScroll(false);
  }

  function closeBooking() {
    if (!modal) return;
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    setBodyScroll(true);
    if (successMsg) successMsg.hidden = true;
  }

  openButtons.forEach(button => {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      openBooking();
    });
  });

  closeButtons.forEach(button => {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      closeBooking();
    });
  });

  if (modal) {
    modal.addEventListener('click', (event) => {
      if (event.target === modal) {
        closeBooking();
      }
    });
  }

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeBooking();
    }
  });

  if (form) {
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      if (successMsg) {
        successMsg.hidden = false;
        successMsg.textContent = 'Thanks! Your booking request has been sent. We’ll contact you shortly.';
      }
      form.reset();
      setTimeout(closeBooking, 1700);
    });
  }
})();
