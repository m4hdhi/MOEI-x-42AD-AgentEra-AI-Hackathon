-- v4: Knowledge base for grounded answers.
--
-- Two tables, both retrieved by agents/hassan/workers/knowledge.py:
--   knowledge_facts      — hand-curated, high-stakes Q&As (always win over crawled hits)
--   knowledge_documents  — crawled pages from moei.gov.ae (populated by scripts/crawl_moei.py)
--
-- Both use Postgres built-in full-text search (tsvector + GIN index). No pgvector, no
-- embedding API calls — works on stock postgres:16-alpine.

-- ===== knowledge_documents (crawled pages) =====================================

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url           TEXT NOT NULL,
    lang          TEXT NOT NULL CHECK (lang IN ('en','ar')),
    title         TEXT,
    section       TEXT,                       -- about / services / branches / news / other
    content       TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (url, lang)
);

ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS tsv tsvector;
CREATE INDEX IF NOT EXISTS idx_kb_tsv     ON knowledge_documents USING GIN (tsv);
CREATE INDEX IF NOT EXISTS idx_kb_section ON knowledge_documents (section);
CREATE INDEX IF NOT EXISTS idx_kb_hash    ON knowledge_documents (content_hash);

CREATE OR REPLACE FUNCTION update_kb_tsv() RETURNS trigger AS $$
BEGIN
  -- 'simple' config for AR avoids English stemming on Arabic text;
  -- 'english' gives us plural/case folding for EN.
  IF NEW.lang = 'ar' THEN
    NEW.tsv := to_tsvector('simple',  coalesce(NEW.title,'') || ' ' || coalesce(NEW.content,''));
  ELSE
    NEW.tsv := to_tsvector('english', coalesce(NEW.title,'') || ' ' || coalesce(NEW.content,''));
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_kb_tsv ON knowledge_documents;
CREATE TRIGGER trg_kb_tsv BEFORE INSERT OR UPDATE OF title, content, lang
  ON knowledge_documents
  FOR EACH ROW EXECUTE FUNCTION update_kb_tsv();


-- ===== knowledge_facts (curated, hand-maintained) =============================

CREATE TABLE IF NOT EXISTS knowledge_facts (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic       TEXT NOT NULL,           -- e.g. 'call_centre', 'hq_address'
    lang        TEXT NOT NULL DEFAULT 'en' CHECK (lang IN ('en','ar')),
    keywords    TEXT NOT NULL,           -- trigger words used in FTS
    title       TEXT NOT NULL,
    answer      TEXT NOT NULL,
    source_url  TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_facts_topic ON knowledge_facts (topic);

ALTER TABLE knowledge_facts ADD COLUMN IF NOT EXISTS tsv tsvector;
CREATE INDEX IF NOT EXISTS idx_facts_tsv ON knowledge_facts USING GIN (tsv);

CREATE OR REPLACE FUNCTION update_facts_tsv() RETURNS trigger AS $$
BEGIN
  IF NEW.lang = 'ar' THEN
    NEW.tsv := to_tsvector('simple',
                 coalesce(NEW.keywords,'') || ' ' || coalesce(NEW.title,'') || ' ' || coalesce(NEW.answer,''));
  ELSE
    NEW.tsv := to_tsvector('english',
                 coalesce(NEW.keywords,'') || ' ' || coalesce(NEW.title,'') || ' ' || coalesce(NEW.answer,''));
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_facts_tsv ON knowledge_facts;
CREATE TRIGGER trg_facts_tsv BEFORE INSERT OR UPDATE OF keywords, title, answer, lang
  ON knowledge_facts
  FOR EACH ROW EXECUTE FUNCTION update_facts_tsv();


-- ===== Curated facts seed (re-runnable) ======================================
-- These ALWAYS win over crawled content for the topics they cover. Update them when
-- ministry policies change — they're meant for legal/comms review.

INSERT INTO knowledge_facts (topic, lang, keywords, title, answer, source_url) VALUES
('call_centre','en','call hotline phone number contact 800 6634 customer service',
 'MOEI Call Centre — 800 6634',
 'The Ministry of Energy and Infrastructure call centre is reachable 24/7 on 800 6634 from inside the UAE. From outside the UAE dial +971 800 6634. The call centre handles housing programmes, energy, transport, and infrastructure enquiries in Arabic and English.',
 'https://www.moei.gov.ae/en/contact-us'),

('call_centre','ar','اتصال هاتف مركز الاتصال خدمة العملاء 800',
 'مركز اتصال الوزارة — 800 6634',
 'يمكنك الاتصال بمركز اتصال وزارة الطاقة والبنية التحتية على الرقم 800 6634 على مدار الساعة من داخل الإمارات. من خارج الدولة اتصل بـ +971 800 6634.',
 'https://www.moei.gov.ae/ar/contact-us'),

('hq_address','en','headquarters HQ head office address location Abu Dhabi where ministry',
 'MOEI Headquarters',
 'MOEI headquarters is located in Abu Dhabi. The ministry has additional service customer happiness centres in Dubai and the Northern Emirates. For exact branch addresses and hours, see the contact page.',
 'https://www.moei.gov.ae/en/contact-us'),

('working_hours','en','hours open timing working days weekend friday saturday sunday',
 'Working hours',
 'MOEI customer happiness centres operate Monday to Thursday 07:30 to 15:30, and Friday 07:30 to 12:00, closed on weekends. The 800 6634 call centre and digital channels operate 24/7.',
 'https://www.moei.gov.ae/en/contact-us'),

('mission','en','mission vision strategy strategic pillars goals objectives ministry about',
 'MOEI Strategy & Mission',
 'MOEI is responsible for the federal energy, infrastructure, housing, transport, and maritime sectors of the UAE. Strategic priorities include the UAE Energy Strategy 2050 (clean energy mix), housing welfare for Emirati citizens via the Sheikh Zayed Housing Programme, and federal road & maritime infrastructure.',
 'https://www.moei.gov.ae/en/about-ministry'),

('szhp','en','sheikh zayed housing programme SZHP loan grant emirati citizen housing reschedule',
 'Sheikh Zayed Housing Programme',
 'The Sheikh Zayed Housing Programme (SZHP) provides interest-free housing loans and grants to Emirati citizens. Agent42 can triage your eligibility for loan rescheduling in under 90 seconds if you share your salary band and current commitment.',
 'https://www.moei.gov.ae/en/services/housing-services'),

('services_list','en','services list catalog all available what services provided',
 'MOEI services',
 'MOEI offers federal services across four sectors: Housing (SZHP loans, rescheduling, hardship), Energy (electricity & water enquiries, tariffs, outages — federal coordination role), Transport (driver and vehicle federal coordination), and Maritime (vessel registration, seafarer certificates, ports). Agent42 supports 18 of the most-requested services end-to-end on web, voice, WhatsApp, and mobile.',
 'https://www.moei.gov.ae/en/services'),

('uae_pass','en','UAE PASS digital identity login authentication sign in',
 'UAE PASS for Agent42',
 'Agent42 uses UAE PASS as the federated digital identity. Tap "Sign in with UAE PASS" on the citizen site to authenticate. In this hackathon demo, the mock UAE PASS flow uses the staging credentials Ministry of Identity publishes to developers; production would point to id.uaepass.ae.',
 'https://uaepass.ae'),

('languages','en','language arabic english bilingual khaliji emirati dialect',
 'Languages',
 'Agent42 replies in Arabic or English automatically based on the language you write in. The voice channel supports both English (US) and Arabic (UAE/Khaliji). All four channels — web, WhatsApp, voice, mobile — share the same supervisor and memory, so you can switch languages mid-conversation.',
 'https://www.moei.gov.ae/en'),

('escalation','en','human agent escalate talk to person not satisfied complaint',
 'Reaching a human agent',
 'If Agent42 cannot resolve your request, you can ask to be escalated and a human MOEI agent will be assigned, with full visibility into your prior chat, voice, or WhatsApp transcript. Call 800 6634 to be routed directly to a human.',
 'https://www.moei.gov.ae/en/contact-us'),

('complaints','en','complaint complain feedback unhappy issue problem case',
 'Filing a complaint or feedback',
 'You can file a complaint or share feedback through the MOEI Customer Happiness Centre at 800 6634, or after any case closes you''ll receive a short CSAT survey. Every complaint generates a tracked case number you can follow on any channel.',
 'https://www.moei.gov.ae/en/customer-happiness/complaints-suggestions'),

('news_disclaimer','en','news announcement update recent latest media center',
 'News & announcements',
 'For the latest ministry announcements, refer to the official Media Centre. Agent42 can summarise the headlines but always check the source page for full context and dates.',
 'https://www.moei.gov.ae/en/media-centre')
ON CONFLICT DO NOTHING;
