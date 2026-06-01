# Night Squirrels

A full-stack Flask web application for tutoring question-and-answer services, featuring transparent pricing, AI-assisted workflows, PayPal payments, and a curated reference library. Built as a real, production-grade project — not a toy demo.

> *"Find new ideas, forge your tools, get solutions."*

---

## What it does

Students submit academic questions through a rich editor, receive a transparent price quote, and pay only when the answer is delivered. Tutors and admins manage the workflow from their own dashboards. Parents or guardians can be linked as payers via PayPal.

### User roles

| Role | What they can do |
|---|---|
| **Student** | Submit questions, choose a quote, attach files, comment on answers |
| **Tutor** | Claim questions, deliver answers, manage ideas and references |
| **Admin** | Full oversight: users, questions, library, examples, pricing, rebase |
| **Payer** | Connect a PayPal account on behalf of a student (parent/guardian) |

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, Flask, Flask-Login, Flask-Babel |
| Database | PostgreSQL via psycopg2 (no ORM) |
| Frontend | Bootstrap 5.3, Jinja2, Vanilla JS |
| Rich editor | Quill + KaTeX (maths rendering) |
| AI | Anthropic API — Claude Sonnet 4.6 / Haiku 4.5 |
| Payments | PayPal API (vault-based recurring charges) |
| File storage | AWS S3 + boto3 |
| Real-time | Pusher Channels (comment threads) |
| Image handling | Cropper.js (client), Pillow (server thumbnails) |
| Book metadata | Google Books API + OpenLibrary fallback |
| Biographical data | Wikipedia REST API + Nobel Prize API v2.1 |
| Email | External mailer service (MailerToGo-based) |
| Localisation | pyBabel — Italian (default) and English |
| Deployment | Heroku |

---

## AI features

All AI capabilities are powered by the **Anthropic API** and designed to fail-open: the platform continues working normally if the API is unavailable.

### 1. Image OCR and content extraction
When a student uploads an image as the body of a question, Claude vision (`claude-sonnet-4-6`) extracts the content — plain text and LaTeX formulas — into a Quill delta placed directly in the editor. The extraction is confidence-scored (0–1).

### 2. Question sustainability gate
Every time a question is saved (pre-acceptance), Claude analyses whether it is clear, complete, and answerable. Vision-aware path for image-heavy questions (`claude-sonnet-4-6`); text-only path for plain questions (`claude-sonnet-4-5`). Returns a quotability flag, a student-facing hint if rejected, and semantic metadata (subject, grade, difficulty, complexity).

### 3. Person biography enrichment
Admins can enrich author records with bilingual biographies (IT/EN). The system fetches introductory extracts from Wikipedia and passes them to Claude (`claude-sonnet-4-6`), which produces a standardised short caption. Falls back to Claude's own knowledge if Wikipedia returns nothing.

### 4. Fuzzy person and publisher matching
During ISBN import, author and publisher names from the external API are matched to existing database records via a three-step cascade: exact match → AI fuzzy match (`claude-haiku-4-5`) → create new. Prevents duplicate entries without manual intervention.

---

## Main use case flow

```
Student submits question (Quill + optional image/PDF)
        │
        ▼
AI sustainability gate — is the question quotable?
        │ yes
        ▼
Pricing engine generates a multi-axis quote (pricing.py)
        │
        ▼
Student accepts quote → payment method checked
        │
        ▼
Tutor claims and delivers answer
        │
        ▼
Payment charged via PayPal vault → student notified
        │
        ▼
Student comments / closes ticket
```

---

## Project structure

```
nightsquirrel/
├── nightsquirrel/          # Flask application package
│   ├── bl_*.py             # Blueprints (one per feature area)
│   ├── db_*.py             # Database layer (raw SQL, no ORM)
│   ├── auth.py             # before_app_request, decorators, cookie policy
│   ├── ai_provider.py      # Anthropic API wrapper
│   ├── question_analysis.py# AI sustainability gate
│   ├── pricing.py          # Quote generation engine
│   ├── payment.py          # PayPal integration
│   ├── states.py           # Ticket state machine
│   ├── notifications.py    # Email notification triggers
│   ├── user_model.py       # Flask-Login User class
│   ├── templates/          # Jinja2 templates
│   ├── static/             # CSS, JS, images
│   └── translations/       # pyBabel .po/.mo files (it, en)
├── database scripts/       # Ordered SQL scripts (see below)
├── docs/                   # Architecture notes and draw.io diagrams
├── scripts/                # One-off admin/enrichment scripts
├── babel.cfg               # pyBabel extraction config
├── requirements.txt
├── Procfile
└── runtime.txt
```

---

## Database setup

Scripts must be run in order using psql or pgAdmin:

| # | File | Purpose |
|---|---|---|
| 1 | `1-create-database.sql` | Schema creation |
| 2 | `2-fill-database-nightsquirrel.sql` | Core seed data |
| 3 | `3-payment-tables.sql` | Payment tables |
| 4 | `4-document-table.sql` | Attached documents |
| 5 | `5-comment-table.sql` | Comment threads |
| 6 | `6-reference-tables.sql` | Library references |
| 7 | `7-tag-tables.sql` | Tagging system |
| 8 | `8-book-draft-tables.sql` | ISBN import drafts |
| 9 | `9-library-seed.sql` | Library data — see note below |
| 10 | `10-example-tables.sql` | Example page tables |
| 11 | `11-example-seed.sql` | Example page content |
| 12 | `12-idea-tables.sql` | Ideas / whiteboard |

> **Note on `9-library-seed.sql` and `11-example-seed.sql`:** these files contain curated content and are not distributed. In their place you will find documented placeholder files explaining the structure. The admin panel's **Library seed** and **Example seed** buttons regenerate them from the live database (see *Rebase workflow* below).

---

## Local setup

```bash
# Clone and create virtualenv
git clone https://github.com/VarianceDigital/nightsquirrels-public.git
cd nightsquirrels-public
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy and fill in environment variables
cp main.py main-private.py   # edit main-private.py with your credentials
```

Required environment variables: `SESSION_SECRET`, `DATABASE_URL`, `JWT_SECRET_HTML`, `JWT_MAILER_SECRET`, `MAILER_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_TILES_BUCKET_NAME`, `AWS_TILES_BUCKET_URL`, `ANTHROPIC_API_KEY`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PUSHER_APP_ID`, `PUSHER_KEY`, `PUSHER_SECRET`, `PUSHER_CLUSTER`.

---

## Rebase workflow

The admin dashboard exposes four special functions for database maintenance:

- **Rebase SQL** — concatenates all `database scripts/*.sql` files into a single downloadable script to recreate the database from scratch.
- **Library seed** — generates/downloads `9-library-seed.sql` with all reference library data (persons, publishers, books, tags).
- **Example seed** — generates/downloads `11-example-seed.sql` with all localised examples.
- **Purge S3** — removes orphaned reference images from the S3 bucket.

To fully rebase: generate both seed files → replace local copies → commit and deploy → run the complete SQL against the target database.

---

## Localisation (pyBabel)

Italian is the default language; users can switch to English on the fly. After adding or modifying any translatable string in a template:

```bash
# 1. Extract
venv/bin/pybabel extract -F babel.cfg -k _l -o messages.pot .

# 2. Update .po files
venv/bin/pybabel update -i messages.pot -d nightsquirrel/translations

# 3. Translate — edit nightsquirrel/translations/it/LC_MESSAGES/messages.po

# 4. Compile
venv/bin/pybabel compile -d nightsquirrel/translations
```

Always run from the project root with `.` as the input directory.

---

## Licence

See `LICENCE.md`.
