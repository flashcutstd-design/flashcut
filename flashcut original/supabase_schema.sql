-- FlashCut — Run this in Supabase SQL Editor

-- ── 1. Add missing columns to pricing table ──────────────────────
ALTER TABLE pricing ADD COLUMN IF NOT EXISTS label    TEXT;
ALTER TABLE pricing ADD COLUMN IF NOT EXISTS features TEXT;
ALTER TABLE pricing ADD COLUMN IF NOT EXISTS popular  BOOLEAN DEFAULT FALSE;
ALTER TABLE pricing ADD COLUMN IF NOT EXISTS cycle    TEXT DEFAULT 'per shoot';

-- ── 2. Update pricing with card data matching the screenshot ──────
UPDATE pricing SET
  label       = 'For a Single Reel',
  features    = '1-hour shoot session|1 edited reel delivered|Quick on-site reel delivery|Trained, certified Reel-Maker|Shot on the latest iPhone|FlashCut Logo Mandatory',
  popular     = FALSE,
  cycle       = 'per shoot',
  description = 'One hour of coverage for a single polished reel, shot, edited, and delivered on the spot.'
WHERE name = 'Starter';

UPDATE pricing SET
  label       = 'For Special Moments',
  features    = 'Up to 3 hours of coverage|2 edited reels delivered|Quick on-site reel delivery|Trained, certified Reel-Maker|Shot on the latest iPhone|FlashCut Logo Mandatory',
  popular     = TRUE,
  cycle       = 'per shoot',
  description = 'Up to 3 hours of coverage with quick turnaround for the moments that matter most.'
WHERE name = 'Pro';

UPDATE pricing SET
  label       = 'Full Coverage',
  features    = '2-3 day shoot coverage|Unlimited edited reels|4K cinematic footage|Dedicated director & crew|Same-day highlight reel|FlashCut Logo Mandatory',
  popular     = FALSE,
  cycle       = 'per event',
  description = '2-3 day full coverage for weddings, marriages and all functions.'
WHERE name = 'Business';

-- ── 3. Seed default contact settings into site_settings ─────────
-- (uses your existing site_settings table with setting_key/setting_value columns)
INSERT INTO site_settings (setting_key, setting_value) VALUES
  ('contact_email',   'hello@flashcut.com'),
  ('contact_phone',   '+91 98765 43210'),
  ('whatsapp',        '+91 98765 43210'),
  ('instagram',       'https://www.instagram.com/_flash.cut.studio_'),
  ('contact_address', 'Bengaluru, Karnataka, India'),
  ('site_title',      'FlashCut — Shoot. Edit. Deliver. In 10 Minutes.'),
  ('tagline',         'In 10 Minutes.'),
  ('meta_description','Professional video production with editing delivered in 10 minutes.')
ON CONFLICT (setting_key) DO NOTHING;
