/* ─── Shared Navigation — injected on every page ─── */
(function () {
  const currentPage = location.pathname.split('/').pop() || 'index.html';

  function isActive(page) {
    return currentPage === page ? 'active' : '';
  }

  // Logo HTML — clean text logo
  const LOGO_HTML = `<a href="index.html" class="logo">
    Flash<span>Cut</span>
  </a>`;

  // ── MOBILE TOP BAR (logo left, avatar right) ──────────
  if (!document.getElementById('mobileTopBar')) {
    const bar = document.createElement('div');
    bar.id = 'mobileTopBar';
    bar.className = 'mobile-top-bar';
    bar.innerHTML = `
      ${LOGO_HTML}
      <button class="mobile-top-avatar" onclick="openMoreDrawer()" aria-label="Profile">
        <svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="18" cy="18" r="17" stroke="rgba(212,160,23,0.5)" stroke-width="1.5"/>
          <circle cx="18" cy="14" r="6" fill="rgba(212,160,23,0.7)"/>
          <path d="M6 30c0-6.627 5.373-10 12-10s12 3.373 12 10" fill="rgba(212,160,23,0.5)"/>
        </svg>
      </button>
    `;
    document.body.prepend(bar);
  }

  // ── DESKTOP NAV ──────────────────────────────────────
  const desktopNav = document.getElementById('navbar');
  if (desktopNav) {
    desktopNav.innerHTML = `
      <div class="nav-inner">
        ${LOGO_HTML}
        <ul class="nav-links">
          <li><a href="about.html" class="${isActive('about.html')}">About</a></li>
          <li><a href="how-it-works.html" class="${isActive('how-it-works.html')}">How It Works</a></li>
          <li><a href="portfolio.html" class="${isActive('portfolio.html')}">Portfolio</a></li>
          <li><a href="pricing.html" class="${isActive('pricing.html')}">Pricing</a></li>
          <li><a href="testimonials.html" class="${isActive('testimonials.html')}">Reviews</a></li>
        </ul>
        ${currentPage === 'index.html' || currentPage === 'pricing.html' ? '<a href="booking.html" class="btn-nav">Book a Shoot</a>' : '<a href="booking.html" class="btn-nav">Book a Shoot</a>'}
      </div>
    `;
  }

  // ── MOBILE BOTTOM NAV ────────────────────────────────
  const mobileNav = document.querySelector('.nav-mobile');
  if (mobileNav) {
    mobileNav.innerHTML = `
      <a href="index.html" class="mobile-nav-item ${isActive('index.html')}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg>
        <span>Home</span>
      </a>
      <a href="portfolio.html" class="mobile-nav-item ${isActive('portfolio.html')}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.5 10c-.83 0-1.5-.67-1.5-1.5v-5c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5v5c0 .83-.67 1.5-1.5 1.5z"/><path d="M20.5 10H19V8.5c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/><path d="M9.5 14c.83 0 1.5.67 1.5 1.5v5c0 .83-.67 1.5-1.5 1.5S8 21.33 8 20.5v-5c0-.83.67-1.5 1.5-1.5z"/><path d="M3.5 14H5v1.5c0 .83-.67 1.5-1.5 1.5S2 16.33 2 15.5 2.67 14 3.5 14z"/><path d="M14 14.5c0-.83.67-1.5 1.5-1.5h5c.83 0 1.5.67 1.5 1.5s-.67 1.5-1.5 1.5h-5c-.83 0-1.5-.67-1.5-1.5z"/><path d="M15.5 19H14v1.5c0 .83.67 1.5 1.5 1.5s1.5-.67 1.5-1.5-.67-1.5-1.5-1.5z"/><path d="M10 9.5C10 8.67 9.33 8 8.5 8h-5C2.67 8 2 8.67 2 9.5S2.67 11 3.5 11h5c.83 0 1.5-.67 1.5-1.5z"/><path d="M8.5 5H10V3.5C10 2.67 9.33 2 8.5 2S7 2.67 7 3.5 7.67 5 8.5 5z"/></svg>
        <span>Portfolio</span>
      </a>
      ${currentPage === 'index.html' || currentPage === 'pricing.html'
        ? '<a href="booking.html" class="mobile-nav-item cta">\n        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>\n        <span>Book</span>\n      </a>'
        : '<a href="booking.html" class="mobile-nav-item cta">\n        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>\n        <span>Book</span>\n      </a>'}
      <a href="pricing.html" class="mobile-nav-item ${isActive('pricing.html')}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>
        <span>Pricing</span>
      </a>
      <button class="mobile-nav-item" onclick="openMoreDrawer()" style="background:none;border:none;cursor:pointer;color:var(--text-muted);">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></svg>
        <span>More</span>
      </button>
    `;
  }

  // ── MORE DRAWER ───────────────────────────────────────
  // Inject drawer if not already present
  if (!document.getElementById('moreDrawer')) {
    const drawer = document.createElement('div');
    drawer.className = 'more-drawer';
    drawer.id = 'moreDrawer';
    drawer.innerHTML = `
      <div class="more-drawer-backdrop" onclick="closeMoreDrawer()"></div>
      <div class="more-drawer-panel">
        <div class="more-drawer-handle"></div>
        <a href="about.html" class="more-drawer-item" onclick="closeMoreDrawer()">
          <span class="more-drawer-icon">👤</span> About
        </a>
        <a href="contact.html" class="more-drawer-item" onclick="closeMoreDrawer()">
          <span class="more-drawer-icon">✉️</span> Contact
        </a>
        <a href="how-it-works.html" class="more-drawer-item" onclick="closeMoreDrawer()">
          <span class="more-drawer-icon">🎬</span> How It Works
        </a>
        <a href="testimonials.html" class="more-drawer-item" onclick="closeMoreDrawer()">
          <span class="more-drawer-icon">⭐</span> Reviews
        </a>
      </div>
    `;
    document.body.appendChild(drawer);
  }

  // ── STICKY NAV SCROLL ─────────────────────────────────
  const navbar = document.getElementById('navbar');
  if (navbar) {
    window.addEventListener('scroll', () => {
      navbar.classList.toggle('scrolled', window.scrollY > 40);
    }, { passive: true });
  }
})();

// ── MORE DRAWER CONTROLS ──────────────────────────────
function openMoreDrawer() {
  const d = document.getElementById('moreDrawer');
  if (d) d.classList.add('open');
}
function closeMoreDrawer() {
  const d = document.getElementById('moreDrawer');
  if (d) d.classList.remove('open');
}
