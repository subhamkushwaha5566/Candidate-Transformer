# Multi-Source Candidate Data Transformer & Ingestion Dashboard

A production-grade Python application built using **Clean Architecture** designed to ingest, parse, normalize, merge, score, and project candidate profile records from multiple raw sources (Recruiter CSV, Resume PDF, and notes).

The system includes a **premium dark-mode web UI dashboard** to upload files, configure dynamic output projections, run pipeline transforms, and audit data origins.

---

## 1. Pipeline Architecture & Flow

When documents are submitted, they flow through the following decoupled service stages:

```mermaid
graph TD
    A[Recruiter CSV File] -->|CSVParser| B(Raw Candidate Dicts)
    C[Resume PDF File] -->|ResumeParser| D(Raw Candidate Dict)
    
    B -->|Normalizer| E[Normalized Profiles]
    D -->|Normalizer| E
    
    E -->|CandidateMerger| F[Canonical Candidate Object]
    
    F -->|ConfidenceEngine| G[Scored Candidate Profile]
    
    G -->|ProjectionEngine| H[Projected Output JSON]
    
    H -->|CandidateValidator| I[Validated & Serialized Output]
    
    style A fill:#4169e1,stroke:#fff,stroke-width:2px,color:#fff
    style C fill:#4169e1,stroke:#fff,stroke-width:2px,color:#fff
    style F fill:#8a2be2,stroke:#fff,stroke-width:2px,color:#fff
    style I fill:#00e676,stroke:#fff,stroke-width:2px,color:#fff
```

### Decoupled Core Services:
1. **Parsers (`app/parsers/`)**: Converts CSV sheets and PDF resume streams into structured Python dictionaries.
2. **Normalizer (`app/services/normalizer.py`)**: Sanitizes date formats (handles `"Present"` sentinels), canonicalizes skills, normalizes country codes to ISO alpha-2 (`pycountry`), and cleans phone numbers to E.164 formats (`phonenumbers`).
3. **Merger (`app/services/merger.py`)**: Resolves field conflicts using source confidences (CSV = `0.95`, Resume = `0.85`, Notes = `0.60`). Unions arrays and deeply merges overlapping nested objects like Experience and Education items.
4. **Confidence Engine (`app/services/confidence.py`)**: Scores overall profile confidence using a weighted metric across location, links, experience, education, and source-level signals.
5. **Projector (`app/services/projector.py`)**: Filters fields, renames target keys, and handles missing fields (`null` / `omit` / `error`) dynamically at runtime without mutating the canonical object.
6. **Validator (`app/services/validator.py`)**: Enforces schemas, checks completeness of required fields, and guarantees serializability.

---

## 2. Directory Structure

```text
candidate-transformer/
├── app/
│   ├── main.py                 # FastAPI configuration & Static assets mount
│   ├── config.py               # Settings & environment configuration
│   ├── api/
│   │   └── routes.py           # HTTP endpoint definitions
│   ├── schemas/
│   │   ├── candidate.py        # Pydantic schema models for canonical candidate profiles
│   │   └── projection.py       # Pydantic schemas for runtime config projections
│   ├── parsers/
│   │   ├── base_parser.py      # Abstract base parser class
│   │   ├── csv_parser.py       # Pandas-based CSV parser (dtype-safe)
│   │   └── resume_parser.py    # Regex & PDFPlumber-based resume text parser
│   ├── services/
│   │   ├── transformer.py      # CandidateTransformer orchestrator (business use case)
│   │   ├── normalizer.py       # Date, phone, country, and skill normalizer
│   │   ├── merger.py           # Conflict resolver & deep item list merger
│   │   ├── confidence.py       # Profile confidence scoring engine
│   │   ├── projector.py        # Dynamic field subsetting & path renamer
│   │   └── validator.py        # JSON schema and required fields validator
│   └── static/
│       ├── index.html          # Dashboard page HTML markup
│       ├── style.css           # Glassmorphic dark mode styling
│       └── script.js           # Interactive AJAX controller & visualizations
└── tests/                      # Core test suites (fastapi client, unit tests)
```

---

## 3. Running the Project Locally

### Step 1: Clone & Setup Virtual Environment
Create and activate a python virtual environment, and install dependencies:
```bash
# Create environment
python -m venv venv

# Activate (PowerShell)
.\venv\Scripts\Activate.ps1

# Activate (CMD)
.\venv\Scripts\activate.bat

# Activate (Bash/Git Bash)
source venv/Scripts/activate

# Install requirements
pip install -r requirements.txt
```

### Step 2: Start the FastAPI Server
Start the Uvicorn web server locally:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- **Web UI Dashboard**: [http://localhost:8000/](http://localhost:8000/)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 4. How to Test the Project

### Execute the Test Suite
Ensure the virtual environment is activated and run:
```bash
.\venv\Scripts\pytest
```
*This executes **37 tests** covering parsers, normalization edge cases, conflict mergers, and endpoint integration routes.*

---

## 5. API Reference: POST `/api/v1/transform`

Transforms raw files using a dynamically provided runtime projection config.

### Request Format (`multipart/form-data`)
- **`csv_file`**: Upload file (CSV, optional).
- **`resume_file`**: Upload file (PDF, optional).
- **`config`**: String representation of Output Configuration JSON (optional).

### Example Config JSON:
```json
{
  "fields": [
    "full_name",
    "emails",
    {"path": "primary_phone", "from": "phones[0]"},
    "skills"
  ],
  "include_confidence": true,
  "include_provenance": true,
  "on_missing": "omit"
}
```

---

## 6. Technical Implementation Details & Recent Fixes

### 1. Skill Blacklist Filtering
- Pre-checks and filters out section headers and generic category lists such as `Technical Skills`, `Skills`, `Languages`, `Framework`, and `Software Tools`.
- Cleans and strips leading list symbols (`-`, `*`, `•`) and trailing punctuation (`:`, `;`) case-insensitively before checking the blacklist.

### 2. Multi-Entry Education Parsing
- Solves combined lines like `A.Y.T Senior Secondary School 10th (2020)` and `R B T Vidyalaya 12th (2022)` by splitting them at the index of the degree/date keyword.
- Isolates and cleans the school name using `strip_dates_from_text` (preventing dates from bleeding into institution names) and processes the remaining text as the degree details (e.g. `10th` with `end_year=2020` and `12th` with `end_year=2022`), creating separate, deduplicated education profiles.

### 3. Projection Isolation & Mutation Safety
- Prevents mutation leakage of projected properties (such as mapping `emails[0]` to `primary_email`) into the canonical model.
- Utilizes `model_copy(deep=True)` to duplicate the canonical Pydantic Candidate object before transforming it into the projected dictionary, maintaining absolute data consistency.

---

--- Server Live At: https://candidate-transformer.onrender.com ----
