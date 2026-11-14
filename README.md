# SoilSim
> **SoilSim is a crop-rotation decision-support prototype that combines agronomic rules with demonstration data to help farmers explore sustainable, climate-resilient crop rotations.**
> *NASA Space Apps Challenge 2026*

---

> [!IMPORTANT]
> **Notice:** *This tool supports farmer judgment and does not replace local expertise.*

---

## Technical Overview & Architecture

SoilSim helps farmers choose sustainable, climate-resilient crop rotations. Instead of relying on opaque AI predictions, SoilSim is built upon verifiable data and transparent agronomic rules:

```
FRONTEND  React + Vite + Tailwind
  Field → Wishes → Futures (Underground + Ribbon + Replay + Advisor) → Souk
        │  JSON over HTTP
BACKEND  FastAPI (Python)
  routers/ → services/ → engine/   (engine = pure agronomic calculations)
               ├─ advisor/   Grounded LLM tool-calling + knowledge cards
               ├─ market/    Listings, offers, passport
               └─ features/  Reads prepared data files
        │  Reads cached files only (never calls external APIs at runtime)
DATA PIPELINE  Offline Python scripts
     Planned sources: NASA POWER · SoilGrids · MODIS NDVI / SMAP
     Current prototype: clearly labelled demonstration data
```

### Core Design Rules (from `AGENTS.md`)
1. **Pure Engine**: `backend/engine/` contains pure functions only (no HTTP, no LLM, no file writes).
2. **Strict Agronomic Grounding**: Agronomic parameters should be supported by `data/crops.csv` and documented references in `Docs/SOURCES.md`.
3. **Display Only**: The frontend never calculates agronomy; it renders API responses.
4. **Advisor Grounding**: The LLM never calculates numbers; it calls engine tools and phrases results.
5. **Offline Pipeline**: Runtime code never calls NASA or SoilGrids APIs directly.
6. **Unified Schema**: Fake and real data share an identical schema with an `is_fake` boolean flag.
7. **Secrets**: API keys live in `.env` only.
8. **Theme Tokens**: All styling adheres to custom tokens (`cream`, `sand`, `forest`, `terracotta`, `ochre`, `river`).
9. **Full i18n**: Multilingual support for English, French, and Arabic (RTL).
10. **Farmer Judgment Disclaimer**: Displayed on all screens.

---

## Milestone M0 Status

- **Folder Structure**: Full project scaffolding aligned with Section 6 of `docs/SPEC.md`.
- **Data Pipeline**: `pipeline/make_fake.py` generates 10 years (2014–2023) of monthly features across 3 demo regions (**Meknès**, **Saïss**, and **Souss**), including historical drought anomalies (2020, 2022).
- **Backend**: FastAPI app with CORS middleware, health check, demo region metadata, and dynamic `DATA_MODE=fake|real` support in `backend/config.py`.
- **Frontend**: Vite + React 18 + Tailwind CSS configured with the Figma design tokens, multilingual i18n (`en`, `fr`, `ar`), and backend health verification.
- **Test Suite**: Automated tests in `backend/tests/test_m0.py` verifying endpoints, dataset structure, schema integrity, and the farmer judgment disclaimer.

---

## Directory Structure

```
soilsim/
├── AGENTS.md                  # Non-negotiable agent guidelines
├── README.md                  # System documentation and run commands
├── .env.example               # Environment template
├──
├── requirements.txt           # Python dependencies
├── data/
│   ├── raw/                   # Raw pipeline downloads (git-ignored)
│   ├── processed/             # Harmonized monthly features and soil profiles
│   │   ├── features/          # {field_id}.parquet and {field_id}.csv
│   │   ├── soil/              # {field_id}.json
│   │   ├── features_fake.parquet
│   │   └── features_fake.csv
│   ├── crops.csv              # Crop traits with citations (Milestone M1)
│   ├── knowledge/             # Sourced knowledge cards
│   └── demo_regions.json      # Meknès, Saïss, Souss coordinates & metadata
├── pipeline/
│   ├── make_fake.py           # Generates 10-yr plausible fake features
│   ├── fetch_power.py         # NASA POWER fetcher stub
│   ├── fetch_soilgrids.py     # ISRIC SoilGrids fetcher stub
│   ├── fetch_ndvi.py          # MODIS NDVI fetcher stub
│   └── build_features.py      # Harmonization script stub
├── backend/
│   ├── main.py                # FastAPI entry point
│   ├── config.py              # Configuration & Pydantic settings
│   ├── routers/               # fields, plans, replay, advisor, market
│   ├── engine/                # Pure agronomic functions (Milestone M2)
│   ├── advisor/               # LLM tool-calling & knowledge cards
│   ├── market/                # Marketplace models & passport builder
│   └── tests/                 # Backend test suite
├── frontend/
│   ├── index.html             # HTML entry point with Google Fonts
│   ├── vite.config.js         # Vite configuration
│   ├── tailwind.config.js     # Tailwind theme tokens
│   └── src/
│       ├── main.jsx           # React DOM root render
│       ├── App.jsx            # Main M0 verification view
│       ├── index.css          # Tailwind base directives
│       ├── screens/           # Field, Wishes, Futures, Souk
│       ├── components/        # Underground, Ribbon, PlanCard, AdvisorChat, SwipeDeck
│       ├── api/               # API client (fetchHealth, fetchRegions)
│       ├── i18n/              # Translations (en, fr, ar)
│       └── theme/             # Design tokens
└── Docs/
    ├── SPEC.md                # Full architectural specification
    ├── SOURCES.md             # Agronomic references & citations
    └── METHOD.md              # Scientific methodology
```

---

## How to Run

### 1. Backend Setup

Ensure you have Python 3.10+ installed.

```bash
# Optional: create and activate a virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Re)generate the 10-year fake dataset
python pipeline/make_fake.py

# Run backend unit tests
pytest

# Start the FastAPI server (runs on http://localhost:8000)
uvicorn backend.main:app --reload --port 8000
```

FastAPI interactive documentation will be available at:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/api/health](http://localhost:8000/api/health)
- Demo Regions: [http://localhost:8000/api/regions](http://localhost:8000/api/regions)

---

### 2. Frontend Setup

Ensure you have Node.js 18+ installed.

```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Start the Vite development server (runs on http://localhost:5173)
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser. You will see:
- Real-time connection status to the FastAPI backend.
- The active `DATA_MODE` (`fake`).
- Visual swatches for all Section 3 design tokens (`cream`, `sand`, `forest`, `terracotta`, `ochre`, `river`).
- The 3 demo regions loaded from `/api/regions`.
- Interactive language toggling (`EN`, `FR`, `AR` with RTL support).
- The mandatory farmer judgment disclaimer banner.
