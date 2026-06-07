-- v7: Emirate dimension on cases for the National Customer Experience Command Center
-- (challenge guide Idea #11 — satisfaction heat map across the country).

ALTER TABLE cases ADD COLUMN IF NOT EXISTS emirate TEXT;

-- Backfill a realistic distribution across the 7 emirates for existing cases.
UPDATE cases SET emirate = (ARRAY['Abu Dhabi','Dubai','Sharjah','Ajman','Umm Al Quwain','Ras Al Khaimah','Fujairah'])[
  CASE
    WHEN random() < 0.30 THEN 1
    WHEN random() < 0.55 THEN 2
    WHEN random() < 0.70 THEN 3
    WHEN random() < 0.80 THEN 4
    WHEN random() < 0.86 THEN 5
    WHEN random() < 0.95 THEN 6
    ELSE 7
  END]
WHERE emirate IS NULL;

CREATE INDEX IF NOT EXISTS idx_cases_emirate ON cases (emirate);
