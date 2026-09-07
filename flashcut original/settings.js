/**
 * settings.js — loads live contact details from /api/settings
 * and updates all matching elements on every page.
 * Included on every HTML page automatically.
 */
(function () {
  fetch('/api/settings')
    .then(function (r) { return r.json(); })
    .then(function (s) {
      if (!s || s.error) return;

      // ── Helper to update href + text ───────────────────
      function setLink(el, href, text) {
        if (href) el.href = href;
        if (text && el.textContent.trim()) el.textContent = text;
      }

      // ── Email ──────────────────────────────────────────
      var email = (s.contact_email || '').trim();
      if (email) {
        // data-setting="email" elements
        document.querySelectorAll('[data-setting="email"]').forEach(function (el) {
          if (el.tagName === 'A') setLink(el, 'mailto:' + email, email);
          else el.textContent = email;
        });
        // Any mailto: links pointing to old email
        document.querySelectorAll('a[href^="mailto:"]').forEach(function (el) {
          if (el.href.includes('flashcut.com') || el.href.includes('flashcut.io')) {
            el.href = 'mailto:' + email;
            if (el.textContent.includes('@')) el.textContent = email;
          }
        });
      }

      // ── Phone ──────────────────────────────────────────
      var phone = (s.contact_phone || '').trim();
      if (phone) {
        var telClean = phone.replace(/[^\d+]/g, '');
        document.querySelectorAll('[data-setting="phone"]').forEach(function (el) {
          if (el.tagName === 'A') setLink(el, 'tel:' + telClean, phone);
          else el.textContent = phone;
        });
        document.querySelectorAll('a[href^="tel:"]').forEach(function (el) {
          el.href = 'tel:' + telClean;
          if (el.textContent.trim().match(/^\+?[\d\s\-\(\)]+$/)) {
            el.textContent = phone;
          }
        });
      }

      // ── Address ────────────────────────────────────────
      var address = (s.contact_address || '').trim();
      if (address) {
        document.querySelectorAll('[data-setting="address"]').forEach(function (el) {
          el.innerHTML = address.replace(/,\s*/g, ',<br>');
        });
        // Find and replace old hardcoded address blocks
        document.querySelectorAll('.info-value').forEach(function (el) {
          var t = el.innerText || el.textContent || '';
          if (t.includes('Creative Studio') || t.includes('San Francisco') || t.includes('CA 94')) {
            el.innerHTML = address.replace(/,\s*/g, ',<br>');
          }
        });
      }

      // ── WhatsApp float ─────────────────────────────────
      var wa = (s.whatsapp || phone || '').trim();
      if (wa) {
        var waNum = wa.replace(/[^\d]/g, '');
        document.querySelectorAll('a.wa-float, a[href^="https://wa.me/"]').forEach(function (el) {
          el.href = 'https://wa.me/' + waNum;
        });
      }

      // ── Instagram ──────────────────────────────────────
      var ig = (s.instagram || '').trim();
      if (ig) {
        document.querySelectorAll('a[href*="instagram.com"]').forEach(function (el) {
          // Update all Instagram links (not just the specific studio one)
          el.href = ig;
        });
      }
    })
    .catch(function () {
      // /api/settings not available — keep hardcoded values, no error shown
    });
})();
