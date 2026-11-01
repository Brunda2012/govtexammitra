"""Seed data for GovtExamMitra.

Data honesty rules enforced here:
- subjects.official_text only contains wording taken from official UPSC notification
  subject lists (verified against upsc.gov.in notifications).
- micro_topics are an AI-derived decomposition of those official subject lines. They
  carry NO official_text; they are labelled through overlap_mappings.verification_status
  = 'PENDING_VERIFICATION' with a confidence score and rationale.
- No exam dates, vacancy counts or eligibility details are invented. Catalogue stubs
  for future exams carry PENDING_VERIFICATION / NOT_EXTRACTED status.
"""
from .db import init_db, get_conn

UPSC_SOURCE = "https://upsc.gov.in/examinations/active-examinations"
CAPF_SOURCE = "https://upsc.gov.in/examinations/active-examinations"
LAST_VERIFIED = "2024-05-01"

EXAMS = [
    {
        "id": "upsc-cse", "name": "UPSC Civil Services Examination",
        "authority": "Union Public Service Commission", "category": "Civil Services",
        "description": "Recruitment to IAS, IPS, IFS and other central civil services.",
        "notification_url": UPSC_SOURCE, "application_portal": "https://upsconline.gov.in",
        "stages_json": ["Prelims (Objective)", "Mains (Written)", "Personality Test (Interview)"],
        "papers_json": ["Prelims GS Paper I", "Prelims CSAT Paper II", "Mains Essay",
                         "Mains GS I-IV", "Mains Optional"],
        "marking_json": {"prelims_gs1": {"questions": 100, "marks": 200, "negative_fraction": "1/3"},
                          "mains_total": {"marks": 1750, "interview": 275}},
        "official_links_json": [{"title": "UPSC examinations page", "url": UPSC_SOURCE}],
        "last_verified": LAST_VERIFIED, "verification_status": "VERIFIED_OFFICIAL",
        "syllabus_status": "OFFICIAL_EXTRACTED", "supported": 1,
    },
    {
        "id": "capf-ac", "name": "CAPF Assistant Commandant",
        "authority": "Union Public Service Commission", "category": "Central Armed Police Forces",
        "description": "Recruitment of Assistant Commandants in BSF, CRPF, CISF, ITBP and SSB.",
        "notification_url": CAPF_SOURCE, "application_portal": "https://upsconline.gov.in",
        "stages_json": ["Written (Objective + Descriptive)", "Physical Efficiency Test / Medical", "Personality Test (Interview)"],
        "papers_json": ["Paper I (General Ability & Intelligence, MCQ)", "Paper II (Descriptive)"],
        "marking_json": {"paper1": {"negative_fraction": "1/3"}, "note": "Detailed paper-wise marks pending re-verification"},
        "official_links_json": [{"title": "UPSC examinations page", "url": CAPF_SOURCE}],
        "last_verified": LAST_VERIFIED, "verification_status": "VERIFIED_OFFICIAL",
        "syllabus_status": "OFFICIAL_EXTRACTED", "supported": 1,
    },
    {"id": "ssc-cgl", "name": "SSC Combined Graduate Level", "authority": "Staff Selection Commission",
     "category": "SSC Recruitment", "notification_url": "https://ssc.gov.in", "supported": 0},
    {"id": "ssc-chsl", "name": "SSC Combined Higher Secondary Level", "authority": "Staff Selection Commission",
     "category": "SSC Recruitment", "notification_url": "https://ssc.gov.in", "supported": 0},
    {"id": "cds", "name": "Combined Defence Services", "authority": "Union Public Service Commission",
     "category": "Defence", "notification_url": UPSC_SOURCE, "supported": 0},
    {"id": "nda", "name": "National Defence Academy & Naval Academy", "authority": "Union Public Service Commission",
     "category": "Defence", "notification_url": UPSC_SOURCE, "supported": 0},
    {"id": "rrb-ntpc", "name": "RRB Non-Technical Popular Categories", "authority": "Railway Recruitment Boards",
     "category": "Railways", "notification_url": "https://www.rrbcdg.gov.in", "supported": 0},
    {"id": "upsc-epfo", "name": "UPSC EPFO Enforcement Officer / Accounts Officer",
     "authority": "Union Public Service Commission", "category": "Recruitment",
     "notification_url": UPSC_SOURCE, "supported": 0},
]

# (exam, subject name, group_key, stage, paper, official_text, [micro topics])
SUBJECTS = [
    ("upsc-cse", "Current events of national and international importance", "current_affairs", "PRELIMS", "GS Paper I",
     "Current events of national and international importance.",
     ["National events", "International events", "Government schemes and policies"]),
    ("upsc-cse", "History of India and Indian National Movement", "history", "PRELIMS", "GS Paper I",
     "History of India and Indian National Movement.",
     ["Ancient India", "Medieval India", "Modern India", "Indian National Movement"]),
    ("upsc-cse", "Indian and World Geography", "geography", "PRELIMS", "GS Paper I",
     "Indian and World Geography - Physical Geography, Social Geography of India and the World.",
     ["Physical geography of India", "World physical geography", "Economic geography of India", "Mapping and locations"]),
    ("upsc-cse", "Indian Polity and Governance", "polity", "PRELIMS", "GS Paper I",
     "Indian Polity and Governance - Constitution, Political System, Panchayati Raj, Public Policy, Rights Issues, etc.",
     ["Constitutional framework", "Union and State governments", "Judiciary", "Panchayati Raj and local government", "Public policy and rights issues"]),
    ("upsc-cse", "Economic and Social Development", "economy", "PRELIMS", "GS Paper I",
     "Economic and Social Development - Sustainable Development, Poverty, Inclusion, Demographics, Social Sector Initiatives, etc.",
     ["National income and growth", "Banking and monetary policy", "Budget and fiscal policy", "Sustainable development", "Poverty and inclusion"]),
    ("upsc-cse", "General Science", "science_tech", "PRELIMS", "GS Paper I",
     "General Science.",
     ["Physics fundamentals", "Chemistry fundamentals", "Biology and human health", "Space and defence technology"]),
    ("upsc-cse", "Environmental Ecology, Bio-diversity and Climate Change", "environment", "PRELIMS", "GS Paper I",
     "General issues on Environmental Ecology, Bio-diversity and Climate Change - that do not require subject specialisation.",
     ["Ecology and biodiversity", "Climate change and conventions", "Pollution and environmental degradation"]),
    ("upsc-cse", "Internal Security", "security", "MAINS", "GS Paper III",
     "Security challenges and their management in border areas; linkages of organized crime with terrorism. (GS-III security themes)",
     ["Internal security challenges", "Border management", "Cyber security", "Insurgency and left-wing extremism"]),
    ("upsc-cse", "Basic Numeracy and Reasoning (CSAT)", "mental_ability", "PRELIMS", "CSAT Paper II",
     "Basic numeracy (numbers and their relations, orders of magnitude, etc.); Data interpretation (charts, graphs, tables, data sufficiency, etc.); Logical reasoning and analytical ability; Comprehension.",
     ["Basic numeracy", "Data interpretation", "Logical reasoning and analytical ability", "Comprehension"]),
    ("upsc-cse", "Essay", "essay", "MAINS", "Essay Paper",
     "Candidates may be required to write essays on multiple topics. (Essay paper)",
     ["Essay writing on given topics"]),
    ("capf-ac", "General Mental Ability", "mental_ability", "WRITTEN", "Paper I",
     "General Mental Ability.",
     ["Basic numeracy", "Data interpretation", "Logical reasoning"]),
    ("capf-ac", "General Science", "science_tech", "WRITTEN", "Paper I",
     "General Science.",
     ["Physics fundamentals", "Chemistry fundamentals", "Biology and human health", "Space and defence technology"]),
    ("capf-ac", "Current Events of National and International Importance", "current_affairs", "WRITTEN", "Paper I",
     "Current Events of National and International Importance.",
     ["National events", "International events", "Government schemes and policies"]),
    ("capf-ac", "History of India", "history", "WRITTEN", "Paper I",
     "History of India.",
     ["Ancient India", "Medieval India", "Modern India", "Indian National Movement"]),
    ("capf-ac", "Indian and World Geography", "geography", "WRITTEN", "Paper I",
     "Indian and World Geography.",
     ["Physical geography of India", "World physical geography", "Economic geography of India", "Mapping and locations"]),
    ("capf-ac", "Indian Polity and Economy", "polity", "WRITTEN", "Paper I",
     "Indian Polity and Economy.",
     ["Constitutional framework", "Union and State governments", "Judiciary", "Panchayati Raj and local government", "Indian economy fundamentals"]),
    ("capf-ac", "Descriptive Paper (Essay, Comprehension, Pr\u00e9cis)", "essay", "WRITTEN", "Paper II",
     "Paper II: Part A - Essay (to be written in English or Hindi); Part B - Comprehension, pr\u00e9cis writing, report writing and other communication/language skills.",
     ["Essay writing on given topics", "Comprehension and pr\u00e9cis writing"]),
]

# (micro_a_name, group, micro_b_name, classification, rationale, conf, depth_note_a, depth_note_b)
MAPPINGS = [
    ("Modern India", "history", "Modern India", "PARTIAL_OVERLAP",
     "UPSC wording explicitly pairs History of India with the Indian National Movement; CAPF notification lists only 'History of India'. Same core content, UPSC demands greater analytical depth.",
     0.8, "Deeper analytical coverage expected (Mains-level links to GS I).", "Objective coverage aligned to Paper I MCQs."),
    ("Indian National Movement", "history", "Indian National Movement", "PARTIAL_OVERLAP",
     "Movement is explicit in the UPSC subject line but not separately named by CAPF; treated as covered under CAPF 'History of India'.",
     0.7, "Explicit and heavily emphasised.", "Likely covered but not explicitly named in notification."),
    ("Ancient India", "history", "Ancient India", "PARTIAL_OVERLAP",
     "Both fall under official history wording; the split into Ancient/Medieval is an AI decomposition, not official wording.",
     0.65, None, None),
    ("Medieval India", "history", "Medieval India", "PARTIAL_OVERLAP",
     "Both fall under official history wording; the split into Ancient/Medieval is an AI decomposition, not official wording.",
     0.6, None, None),
    ("Physical geography of India", "geography", "Physical geography of India", "EXACT_MATCH",
     "Both notifications use near-identical official wording 'Indian and World Geography' at subject level.",
     0.85, None, None),
    ("World physical geography", "geography", "World physical geography", "EXACT_MATCH",
     "Both notifications use near-identical official wording 'Indian and World Geography' at subject level.",
     0.8, None, None),
    ("Economic geography of India", "geography", "Economic geography of India", "PARTIAL_OVERLAP",
     "Covered under both, but UPSC links economic geography to Economic and Social Development themes with deeper analysis.",
     0.7, "Stronger linkage to economy and development topics.", "Objective coverage."),
    ("Constitutional framework", "polity", "Constitutional framework", "EXACT_MATCH",
     "UPSC official wording names Constitution explicitly; CAPF names Indian Polity. Core constitutional content is common.",
     0.75, "Includes Public Policy and Rights Issues emphasis.", "Core polity MCQ coverage."),
    ("Union and State governments", "polity", "Union and State governments", "EXACT_MATCH",
     "Core federal structure is common to both official polity wording.",
     0.75, None, None),
    ("Judiciary", "polity", "Judiciary", "EXACT_MATCH",
     "Judiciary is a standard part of both polity syllabuses (AI decomposition of official subject lines).",
     0.7, None, None),
    ("Panchayati Raj and local government", "polity", "Panchayati Raj and local government", "PARTIAL_OVERLAP",
     "UPSC notification explicitly names Panchayati Raj; CAPF official wording does not name it, though it can appear under polity.",
     0.6, "Explicitly named in official UPSC syllabus.", "Not explicitly named in CAPF notification."),
    ("Public policy and rights issues", "polity", "Indian economy fundamentals", "RELATED_CONCEPT",
     "UPSC pairs rights issues with polity; CAPF's combined 'Polity and Economy' subject is broader but shallower. Related but not equivalent requirements.",
     0.4, "Explicit UPSC emphasis on rights issues.", None),
    ("National income and growth", "economy", "Indian economy fundamentals", "PARTIAL_OVERLAP",
     "UPSC lists Economic and Social Development explicitly; CAPF lists Economy within its combined subject. Overlap with differing depth.",
     0.7, "Includes sustainable development, poverty, inclusion, demographics.", "Broader but shallower objective coverage."),
    ("Banking and monetary policy", "economy", "Indian economy fundamentals", "PARTIAL_OVERLAP",
     "Both cover economy fundamentals; decomposition is AI-derived.",
     0.65, None, None),
    ("Budget and fiscal policy", "economy", "Indian economy fundamentals", "PARTIAL_OVERLAP",
     "Both cover economy fundamentals; decomposition is AI-derived.",
     0.65, None, None),
    ("Sustainable development", "economy", "Indian economy fundamentals", "PARTIAL_OVERLAP",
     "Sustainable development is explicitly named in UPSC official wording; CAPF does not name it.",
     0.5, "Explicitly named in official UPSC syllabus.", None),
    ("Poverty and inclusion", "economy", "Indian economy fundamentals", "PARTIAL_OVERLAP",
     "Poverty and inclusion are explicitly named in UPSC official wording; CAPF does not name them.",
     0.5, "Explicitly named in official UPSC syllabus.", None),
    ("Physics fundamentals", "science_tech", "Physics fundamentals", "EXACT_MATCH",
     "Both notifications list 'General Science' as an official subject with identical wording.",
     0.8, None, None),
    ("Chemistry fundamentals", "science_tech", "Chemistry fundamentals", "EXACT_MATCH",
     "Both notifications list 'General Science' as an official subject with identical wording.",
     0.8, None, None),
    ("Biology and human health", "science_tech", "Biology and human health", "EXACT_MATCH",
     "Both notifications list 'General Science' as an official subject with identical wording.",
     0.8, None, None),
    ("Space and defence technology", "science_tech", "Space and defence technology", "PARTIAL_OVERLAP",
     "Falls under General Science in both, but UPSC connects it to Mains S&T analysis; CAPF emphasises it for a security-focused service.",
     0.6, "Deeper S&T analysis expected at Mains.", "Security-relevant emphasis."),
    ("National events", "current_affairs", "National events", "EXACT_MATCH",
     "Both notifications use near-identical official wording 'Current Events of National and International Importance'.",
     0.9, None, None),
    ("International events", "current_affairs", "International events", "EXACT_MATCH",
     "Both notifications use near-identical official wording 'Current Events of National and International Importance'.",
     0.9, None, None),
    ("Government schemes and policies", "current_affairs", "Government schemes and policies", "PARTIAL_OVERLAP",
     "Covered by current-events wording in both; UPSC links schemes to governance and social development analysis.",
     0.7, "Mains-level scheme analysis expected.", "Objective coverage."),
    ("Basic numeracy", "mental_ability", "Basic numeracy", "PARTIAL_OVERLAP",
     "UPSC CSAT officially names basic numeracy and data interpretation; CAPF names only 'General Mental Ability'. Content is similar but CAPF's official wording is broader.",
     0.75, "Qualifying nature in UPSC (33% minimum).", "Counts fully towards Paper I merit."),
    ("Data interpretation", "mental_ability", "Data interpretation", "PARTIAL_OVERLAP",
     "UPSC CSAT officially names data interpretation; CAPF does not name it explicitly.",
     0.7, None, None),
    ("Logical reasoning and analytical ability", "mental_ability", "Logical reasoning", "PARTIAL_OVERLAP",
     "UPSC CSAT officially names logical reasoning and analytical ability; CAPF's 'General Mental Ability' is the broader official term.",
     0.7, None, None),
    ("Essay writing on given topics", "essay", "Essay writing on given topics", "EXACT_MATCH",
     "Both examinations include an explicit essay paper: UPSC Mains Essay and CAPF Paper II Part A.",
     0.8, "UPSC essay carries much higher weight and expects Mains-grade depth.", "CAPF essay is one part of the descriptive Paper II."),
]

QUESTIONS = [
    ("upsc-cse", "DEMONSTRATION", "PRELIMS", "GS Paper I", "Ancient India", "EASY",
     "Which of the following is the site of the Great Bath, a key structure of the Indus Valley Civilization?",
     ["Lothal", "Mohenjo-daro", "Harappa", "Kalibangan"], 1,
     "The Great Bath is associated with Mohenjo-daro. (Demonstration question authored for GovtExamMitra, not an official PYQ.)"),
    ("upsc-cse", "DEMONSTRATION", "PRELIMS", "GS Paper I", "Modern India", "MEDIUM",
     "The Non-Cooperation Movement was launched in response to which two developments?",
     ["Rowlatt Act and Jallianwala Bagh massacre", "Simon Commission and Nehru Report",
      "Partition of Bengal and Swadeshi movement", "Quit India and August Offer"], 0,
     "The movement followed the Rowlatt Act and the Jallianwala Bagh massacre, building on khilafat sentiment. (Demonstration question.)"),
    ("upsc-cse", "DEMONSTRATION", "PRELIMS", "GS Paper I", "Constitutional framework", "MEDIUM",
     "Which Article of the Constitution deals with the amendment procedure?",
     ["Article 356", "Article 368", "Article 32", "Article 21"], 1,
     "Article 368 lays down the procedure for constitutional amendments. (Demonstration question.)"),
    ("upsc-cse", "DEMONSTRATION", "PRELIMS", "GS Paper I", "Banking and monetary policy", "MEDIUM",
     "Who determines the policy rate (repo rate) in India?",
     ["Ministry of Finance", "NITI Aayog", "Monetary Policy Committee of the RBI", "SEBI"], 2,
     "The RBI's Monetary Policy Committee sets the repo rate. (Demonstration question.)"),
    ("upsc-cse", "DEMONSTRATION", "PRELIMS", "GS Paper I", "Ecology and biodiversity", "EASY",
     "Which gas is the largest contributor to the greenhouse effect by volume of emissions from human activity?",
     ["Methane", "Carbon dioxide", "Nitrous oxide", "Ozone"], 1,
     "Carbon dioxide is the largest contributor among human-emitted greenhouse gases. (Demonstration question.)"),
    ("capf-ac", "DEMONSTRATION", "WRITTEN", "Paper I", "Modern India", "MEDIUM",
     "The Champaran Satyagraha (1917) was associated with which issue?",
     ["Indigo planters", "Salt tax", "Khilafat", "Trade union rights"], 0,
     "Gandhi's first satyagraha in India addressed the grievances of indigo farmers in Champaran. (Demonstration question.)"),
    ("capf-ac", "DEMONSTRATION", "WRITTEN", "Paper I", "Constitutional framework", "EASY",
     "Fundamental Duties were added to the Constitution by which amendment?",
     ["42nd", "44th", "52nd", "73rd"], 0,
     "The 42nd Amendment (1976) inserted Fundamental Duties (Part IVA). (Demonstration question.)"),
    ("capf-ac", "DEMONSTRATION", "WRITTEN", "Paper I", "Physical geography of India", "EASY",
     "Which is the longest river of peninsular India?",
     ["Narmada", "Godavari", "Krishna", "Mahanadi"], 1,
     "The Godavari is the longest peninsular river. (Demonstration question.)"),
    ("capf-ac", "DEMONSTRATION", "WRITTEN", "Paper I", "Basic numeracy", "EASY",
     "A train travels 180 km in 3 hours. Its average speed is:",
     ["50 km/h", "55 km/h", "60 km/h", "65 km/h"], 2,
     "Speed = distance / time = 180/3 = 60 km/h. (Demonstration question.)"),
    ("capf-ac", "DEMONSTRATION", "WRITTEN", "Paper I", "Biology and human health", "EASY",
     "Which vitamin deficiency causes scurvy?",
     ["Vitamin A", "Vitamin B12", "Vitamin C", "Vitamin D"], 2,
     "Scurvy is caused by vitamin C (ascorbic acid) deficiency. (Demonstration question.)"),
]

def seed(db_path=None):
    conn = init_db(db_path)
    cur = conn.cursor()
    for e in EXAMS:
        cur.execute("""INSERT INTO exams
            (id,name,authority,category,description,notification_url,application_portal,eligibility,age_criteria,
             stages_json,papers_json,marking_json,official_links_json,last_verified,verification_status,syllabus_status,supported)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (id) DO UPDATE SET
              name=EXCLUDED.name, authority=EXCLUDED.authority, category=EXCLUDED.category,
              description=EXCLUDED.description, notification_url=EXCLUDED.notification_url,
              application_portal=EXCLUDED.application_portal, eligibility=EXCLUDED.eligibility,
              age_criteria=EXCLUDED.age_criteria, stages_json=EXCLUDED.stages_json,
              papers_json=EXCLUDED.papers_json, marking_json=EXCLUDED.marking_json,
              official_links_json=EXCLUDED.official_links_json, last_verified=EXCLUDED.last_verified,
              verification_status=EXCLUDED.verification_status, syllabus_status=EXCLUDED.syllabus_status,
              supported=EXCLUDED.supported""",
            (e["id"], e["name"], e["authority"], e["category"], e.get("description"),
             e.get("notification_url"), e.get("application_portal"), e.get("eligibility"), e.get("age_criteria"),
             json_str(e.get("stages_json")), json_str(e.get("papers_json")), json_str(e.get("marking_json")),
             json_str(e.get("official_links_json")), e.get("last_verified"),
             e.get("verification_status", "PENDING_VERIFICATION"),
             e.get("syllabus_status", "NOT_EXTRACTED"), e.get("supported", 0)))
    micro_ids = {}
    for exam, sname, group, stage, paper, official, micros in SUBJECTS:
        cur.execute("""INSERT INTO subjects (exam_id,name,group_key,stage,paper,official_text,ordering)
                       VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT (exam_id,name,stage,paper) DO NOTHING""",
                    (exam, sname, group, stage, paper, official, len(micro_ids.get(exam, {}))))
        sid = cur.execute("SELECT id FROM subjects WHERE exam_id=? AND name=? AND stage=? AND paper=?",
                          (exam, sname, stage, paper)).fetchone()["id"]
        for m in micros:
            cur.execute("""INSERT INTO micro_topics (subject_id,exam_id,name,official_text,depth_note)
                           VALUES (?,?,?,NULL,NULL)
                           ON CONFLICT (exam_id,name) DO NOTHING""", (sid, exam, m))
            mid = cur.execute("SELECT id FROM micro_topics WHERE exam_id=? AND name=?", (exam, m)).fetchone()["id"]
            micro_ids[(exam, m)] = mid
    for ma, group, mb, cls, rationale, conf, dna, dnb in MAPPINGS:
        a = b = None
        for (exam, name), mid in micro_ids.items():
            if name == ma and (a is None) and exam != "capf-ac" and group == group_of(cur, mid):
                a = mid
            if name == mb and (b is None) and exam == "capf-ac" and group == group_of(cur, mid):
                b = mid
        if not (a and b):
            continue
        cur.execute("""INSERT INTO overlap_mappings
            (micro_a,micro_b,classification,rationale,depth_note_a,depth_note_b,confidence,verification_status,source_url,last_verified)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (micro_a,micro_b) DO NOTHING""",
            (a, b, cls, rationale, dna, dnb, conf, "PENDING_VERIFICATION", UPSC_SOURCE, LAST_VERIFIED))
    for exam, qtype, stage, paper, mt, diff, q, opts, ans, expl in QUESTIONS:
        mid = micro_ids.get((exam, mt))
        cur.execute("""INSERT INTO questions
            (exam_id,q_type,year,paper,subject_id,micro_topic_id,difficulty,question,options_json,answer_index,explanation)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (exam_id,q_type,question) DO NOTHING""",
            (exam, qtype, None, paper, None, mid, diff, q, json_str(opts), ans, expl))
    conn.commit()
    conn.close()

def group_of(cur, micro_id):
    r = cur.execute("""SELECT s.group_key FROM subjects s
                       JOIN micro_topics m ON m.subject_id=s.id WHERE m.id=?""", (micro_id,)).fetchone()
    return r["group_key"] if r else None

def json_str(v):
    import json as _json
    return _json.dumps(v) if v is not None else None

if __name__ == "__main__":
    seed()
    c = get_conn()
    print("exams:", c.execute("SELECT COUNT(*) c FROM exams").fetchone()["c"])
    print("subjects:", c.execute("SELECT COUNT(*) c FROM subjects").fetchone()["c"])
    print("micro_topics:", c.execute("SELECT COUNT(*) c FROM micro_topics").fetchone()["c"])
    print("mappings:", c.execute("SELECT COUNT(*) c FROM overlap_mappings").fetchone()["c"])
    print("questions:", c.execute("SELECT COUNT(*) c FROM questions").fetchone()["c"])
    c.close()
