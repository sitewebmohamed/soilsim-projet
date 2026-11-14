# **SoilSim: Build Spec for Antigravity**

NASA Space Apps 2026 · Crop rotation decision-support · 2-day MVP

## **0\. How to use this document**

1. Read sections 1 to 5 yourselves. They explain the idea and the decisions.  
2. Put section 11 (`AGENTS.md`) in the repo root. Antigravity reads it before every task.  
3. Give Antigravity **one milestone at a time** from section 10, using the prompt written there. Do not paste the whole document and say "build it".  
4. After each milestone, run the tests, look at the screen, and come back to Claude with the diff or the error.

**Working loop:** Claude writes the spec → you give it to Antigravity → Antigravity builds → you test → Claude reviews.

---

## **1\. The product in one paragraph**

SoilSim helps a farmer choose a crop rotation that protects soil and water under a changing climate. The farmer picks a field, says what matters (water, income, soil, animals), and gets **three plans**: the current rotation, a recommended one, and a different alternative. Each plan is explained in plain language, scored with transparent rules, and tested against the **last 10 real years of weather**. A farmer can chat with the **SoilSim Advisor** (an AI grounded in our own calculations) in Darija, Arabic, French or English. A good rotation earns a **Soil Passport**, which unlocks better offers in a small marketplace (the Souk).

The tool supports farmer judgment. It never replaces it, and that sentence is visible in the app at all times.

---

## **2\. Decision: "our own AI" and the chat bot**

The idea of a chat bot is good, and it is achievable if we define "our own AI" correctly.

**What is out of reach in 2 days:** training a model from scratch. We have no data linking rotations to real outcomes (yields, soil carbon over time), so a trained model would be invented numbers with a confident voice. Judges would catch it.

**What is realistic and still original:** the **SoilSim Advisor**, built from three parts that are ours:

| Part | What it is | Who owns the truth |
| ----- | ----- | ----- |
| **Engine** | Python functions that compute water balance, soil health, resilience, hindcast scores | Our code, with sources |
| **Knowledge cards** | About 20 short, sourced text cards (what ET is, why legumes fix nitrogen, what NDVI means, frost rules) | Us, reviewed by an agronomy-literate person |
| **LLM with tools** | A language model that can *call* our engine and *read* our cards, then explain the results | The LLM only phrases things |

The Advisor never invents numbers. If a farmer asks "what if it rains 30% less?", the LLM calls our `what_if` tool, the engine reruns the plans, and the LLM explains the result. If a question is not covered by tools or cards, it says so and points to the local agricultural extension office.

**Pitch line:** "An AI that can only say what our calculations support, and shows the evidence behind every answer."

**If time runs short:** drop the free chat and keep the one-shot "Why this?" explanation. The tools underneath are the same, so nothing is wasted.

---

## **3\. Design tokens (from the Figma, nothing else is copied)**

Only the look is reused: palette, fonts, and the illustration mood. Layout and features are our own. The hex values were estimated from screenshots, so confirm them with Figma's eyedropper.

| Token | Approx. hex | Use |
| ----- | ----- | ----- |
| `cream` | `#F5EAD7` | page background |
| `sand` | `#E8D9BA` | cards, panels |
| `forest` | `#14504F` | nav, text on cream |
| `terracotta` | `#C8341F` | primary buttons, active state |
| `ochre` | `#D9892B` | heat, warnings |
| `river` | `#1F8A8A` | water, moisture |

**Fonts:** headings look like a heavy grotesque (similar to Bricolage Grotesque; check the exact name in Figma's Typography panel). Body: DM Sans. Arabic: Noto Kufi Arabic or Cairo.

**Illustration mood:** flat, layered, folk-art landscapes with grain and contour lines. We generate this style in code (see the Underground below).

---

## **4\. The creative core**

Most teams will show dashboards. We show **stories the farmer already understands**.

### **4.1 Signature idea: "Would this plan have survived your worst year?"**

We do not forecast, because honest forecasting of one field is not possible. Instead we **replay the last 10 observed years** on each plan (a *hindcast*). The farmer taps **"Bring back the worst year"** (the real worst year in the data, for example a drought year) and watches each plan's ribbon play out. The plan that holds stays green. The one that fails browns out.

This is honest (observed NASA data), emotional (farmers remember bad years), and scientifically clean (ten outcomes give a typical year and a worst year without made-up uncertainty).

### **4.2 The Living Underground**

The illustration **is** the data. A soil cross-section is drawn procedurally in SVG from the selected plan's computed values:

* root depth and root count → length and branching of roots  
* organic-matter score → how dark the soil is  
* soil moisture → blue glow between particles  
* cover days → vegetation or residue on the surface  
* N-fixing crop → small nodules on roots

Switch from plan A to plan B and the roots grow, the soil darkens, and the surface covers over. No charts.

### **4.3 The Field Ribbon**

A 12-month strip for the plan: green (crop growing), brown (bare), ochre (heat or water stress), river-blue (frost risk). It is the only "timeline" in the app.

### **4.4 The Souk**

Buyers post demands (crop, quantity, base price, and a premium if Soil Passport score ≥ X). Farmers swipe: accept, pass, or counter-offer. The Passport has a privacy toggle, so the farmer decides whether buyers see the history. This is the reward loop: better rotation, better price. It stays a single screen with seeded data.

### **4.5 Accessibility as a feature**

Icon-first UI, large touch targets, a 6th-grade reading level, voice in and voice out, French / Arabic (RTL) / English. The Web Speech API for Moroccan Arabic is unreliable, so test it early. Icon cards are the guaranteed path and voice is a bonus.

---

## **5\. System architecture**

```
FRONTEND  React + Vite + Tailwind
  Field → Wishes → Futures (Underground + Ribbon + Replay + Advisor) → Souk
        │  JSON over HTTP
BACKEND  FastAPI (Python)
  routers/ → services/ → engine/   (engine = pure science, no web code)
               ├─ advisor/   LLM tool-calling + knowledge cards
               ├─ market/    listings, offers, passport (SQLite)
               └─ features/  reads prepared data files
        │  reads files only (never calls NASA live)
DATA PIPELINE  offline Python scripts, run once
  NASA POWER · SoilGrids · MODIS NDVI / SMAP · crops.csv → /data/processed
```

**Rules that keep it clean:**

1. **The pipeline runs offline.** Live NASA calls during a demo are the top way to fail. The app only reads cached files.  
2. **The engine is pure functions.** Inputs in, numbers out. No HTTP, no LLM. It can be unit-tested and defended to judges.  
3. **The frontend never calculates agronomy.** Every number on screen came from the backend.  
4. **The LLM never calculates.** It calls engine tools and phrases the results.  
5. **Fake data and real data share one schema.** On Friday, change a config value, not code.

---

## **6\. Folder structure**

```
soilsim/
├── AGENTS.md
├── README.md
├── .env.example               # EARTHDATA_USER, LLM_API_KEY (never commit .env)
├── data/
│   ├── raw/                   # downloads, git-ignored
│   ├── processed/             # features/{field_id}.parquet, soil/{field_id}.json
│   ├── crops.csv              # crop traits, with a `source` column
│   ├── knowledge/             # ~20 short .md cards, each with sources
│   └── demo_regions.json      # 3 regions: Meknès, Saïss, Souss
├── pipeline/
│   ├── fetch_power.py
│   ├── fetch_soilgrids.py
│   ├── fetch_ndvi.py          # optional
│   ├── make_fake.py           # same schema as real data
│   └── build_features.py      # harmonize to one monthly table per field
├── backend/
│   ├── main.py
│   ├── config.py              # DATA_MODE=fake|real
│   ├── routers/               # fields, plans, replay, advisor, market
│   ├── engine/
│   │   ├── et0.py             # FAO-56 Penman-Monteith, Hargreaves fallback
│   │   ├── water_balance.py
│   │   ├── crops.py
│   │   ├── generate.py        # candidate rotations
│   │   ├── score.py           # scoring + confidence
│   │   ├── hindcast.py        # replay past years
│   │   └── whatif.py          # perturb temp/rain and rerun
│   ├── advisor/               # tools.py, prompts.py, client.py, cards.py
│   ├── market/                # models.py, passport.py, seed.py
│   └── tests/
├── frontend/src/
│   ├── screens/               # Field, Wishes, Futures, Souk
│   ├── components/            # Underground, Ribbon, PlanCard, AdvisorChat, SwipeDeck
│   ├── api/                   # all fetch calls in one place
│   ├── i18n/                  # fr.json, ar.json, en.json
│   └── theme/                 # tokens from section 3
└── docs/                      # SOURCES.md, METHOD.md, pitch notes
```

---

## **7\. Data pipeline, step by step, with sources**

| \# | Step | Source / method |
| ----- | ----- | ----- |
| 1 | Daily weather for the field's grid cell: `T2M_MAX`, `T2M_MIN`, `PRECTOTCORR`, `RH2M`, `WS2M`, `ALLSKY_SFC_SW_DWN`, 10 years | **NASA POWER** daily API (no login) |
| 2 | Reference evapotranspiration ET₀ | **FAO-56 Penman-Monteith** (Allen et al., 1998); Hargreaves if inputs are missing |
| 3 | Crop water demand: `ETc = Kc × ET₀` | **FAO-56** crop coefficients |
| 4 | Monthly water deficit \= ETc − effective rainfall | FAO-56 with USDA-SCS effective rainfall |
| 5 | Soil texture, organic carbon, pH | **SoilGrids (ISRIC)**, 250 m. Fetch once per field and cache, because the API is rate-limited |
| 6 | Soil wetness context | POWER root-zone wetness (`GWETROOT`); **SMAP** if the Friday data includes it |
| 7 | Bare-soil periods and stress | **MODIS NDVI** if available. Otherwise a documented proxy, such as months with rain-fed crop absent. Say which one was used in the confidence badge |
| 8 | Frost days (Tmin ≤ 0 °C) and heat days (Tmax above the crop's limit) | Computed from POWER daily data |
| 9 | Crop traits: cycle length, temperature range, water need, root depth, plant family, N-fixing | **FAO EcoCrop** \+ FAO-56, one `source` per row in `crops.csv` |
| 10 | Harmonize everything to **monthly**, one table per field | `build_features.py` |

**Credibility rule:** every number in `crops.csv` and every threshold in the engine has a line in `docs/SOURCES.md`. Anything we guessed is tagged `ASSUMPTION`, shown to the user as lower confidence, and listed under "data gaps" in the explanation. Have someone with agronomy knowledge review the crop table.

**Do not fight the Earthdata login for MODIS or SMAP before Friday.** Build with POWER and fake data first. Add the official data when it arrives.

---

## **8\. Engine specification**

### **8.1 Generate candidates**

Build 3-year sequences from crops that fit the local season window (temperature range, cycle length, water). The three outputs are the **existing rotation**, the **top-scoring plan**, and the **best plan from a different crop family mix** (so the alternative is truly different).

### **8.2 Score (transparent, weighted)**

```py
def score_plan(plan, features, weights):
    parts = {
        "water":      water_fit(plan, features),    # 0-100, smaller deficit = better
        "soil":       soil_health(plan, features),  # bare days, N-fixation, root depth, residue
        "resilience": resilience(plan, features),   # heat/frost overlap with sensitive stages
        "income":     income(plan),                 # rough margin from crops.csv
        "pest_break": pest_break(plan),             # penalize same family within 2 seasons
    }
    total = sum(parts[k] * weights[k] for k in parts) / sum(weights.values())
    return total, parts
```

Why this form: anyone can see why plan B beat plan A, which the NASA brief asks for.

### **8.3 Hindcast (the signature feature)**

Run `score_plan` on each of the 10 historical years. Report `typical` (median), `worst` (minimum and its year), and `best`. The "Bring back the worst year" button reads these.

### **8.4 What-if**

`what_if(plan, temp_delta_c, rain_factor)` adds a temperature offset and multiplies rainfall in the features, then reruns the scoring. It powers both the slider and the Advisor.

### **8.5 Confidence badge**

High / medium / low from: share of inputs that are real data vs assumed, years of coverage, and whether NDVI or SMAP was used. This is our uncertainty story.

### **8.6 Explanation object (feeds "Why this?")**

Every plan returns: `why_suggested`, `evidence` (data used), `benefits`, `data_gaps`, `risks_needing_local_review`. This covers the brief's requirements directly.

---

## **9\. The SoilSim Advisor (grounded chat)**

**Where it lives:** `backend/advisor/`. The API key stays on the backend only.

**Tools the LLM can call:**

| Tool | Returns |
| ----- | ----- |
| `get_field_summary(field_id)` | soil, 10-year climate story, data coverage |
| `get_plans(field_id, weights)` | 3 plans with scores and parts |
| `explain_plan(plan_id)` | the explanation object from 8.6 |
| `replay_year(plan_id, year)` | how the plan did in that year |
| `what_if(plan_id, temp_delta_c, rain_factor)` | rescored plan |
| `lookup_card(topic)` | a knowledge card (what NDVI is, why legumes help) |
| `parse_wishes(text)` | `{water, income, soil, animals}` weights |

**Rules in the system prompt:**

1. Use only numbers returned by tools. If a number is not in a tool result, do not state it.  
2. If tools and cards do not cover the question, say so and suggest the local extension office.  
3. Reply in the user's language (Darija, Arabic, French or English), at a simple reading level.  
4. For anything about pesticides, fertilizer rates, or legal rules, decline and refer to local experts.  
5. Always end advice with what a human should verify locally.

**UI detail that sells it:** under each answer, show small **evidence chips** ("Used: Plan B hindcast, 2022 replay, card: nitrogen"). Judges see the AI is grounded.

**Same component, two uses:** the "Why this?" panel and the free chat both call the same tools. If chat gets cut, the explanation stays.

**Future step (say it in the pitch, do not build it):** once real yield or soil-carbon measurements exist, calibrate the scoring weights against them. That is the honest path to a learned model.

---

## **10\. API endpoints**

| Method | Endpoint | Purpose |
| ----- | ----- | ----- |
| GET | `/api/regions` | demo regions |
| POST | `/api/field` | `{lat, lon, area_ha}` → field summary and data coverage |
| POST | `/api/wishes/parse` | text or transcript → weights |
| POST | `/api/plans` | `{field_id, weights, current_rotation}` → 3 plans, scores, ribbons, underground parameters, confidence |
| POST | `/api/plans/{id}/replay` | `{year}` → performance in that year |
| POST | `/api/plans/{id}/whatif` | `{temp_delta_c, rain_factor}` → rescored plan |
| POST | `/api/plans/{id}/explain` | explanation object plus friendly text |
| POST | `/api/advisor/chat` | `{field_id, messages}` → answer plus evidence chips |
| POST | `/api/passport` | builds the Soil Passport |
| GET | `/api/listings` | buyer demands |
| POST | `/api/offers` | accept, pass, or counter `{listing_id, price}` |

---

## **11\. Milestones and Antigravity prompts**

### **MVP scope**

**In:** 3 cached regions (Meknès first), map field pick (MapLibre, no key), 4 icon wishes plus text or voice, 3 plans, Underground and Ribbon, worst-year replay, "Why this?", Advisor chat, Passport with privacy toggle, Souk with 8 to 10 seeded buyers, FR / AR (RTL) / EN, permanent "supports, never replaces" note.

**Out:** accounts, payments, live API calls, computer vision, more than 3 regions, chart-heavy dashboards.

**Cut order if behind:** Souk counter-offer → Arabic RTL polish → replay animation → free chat (keep "Why this?"). Never cut the engine, the Underground, or "Why this?".

### **Pre-Friday**

**M0: scaffold and fake data.** Prompt:

> Read AGENTS.md. Create the folder structure from the spec. Set up FastAPI (`backend/main.py`, `config.py` with `DATA_MODE=fake|real`) and a Vite \+ React \+ Tailwind frontend with the theme tokens. In `pipeline/make_fake.py`, generate 10 years of plausible monthly features for 3 regions using the schema: `field_id, year, month, tmax, tmin, rain_mm, et0_mm, soil_wetness, ndvi, frost_days, heat_days`. Fake data must be clearly flagged `is_fake=true`. Add a README with run commands. Do not write any engine logic yet.

**M1: crop table.** Claude drafts `crops.csv` (12 to 15 crops) with source per row. You get it reviewed. Antigravity only loads and validates it (`engine/crops.py`) and fails loudly on missing sources.

**M2: engine v0 with tests.** Prompt (Claude supplies the exact formulas per function):

> Implement `engine/` as pure functions with type hints and docstrings citing the source. Add pytest tests for each function using hand-computed examples. No web or LLM code in `engine/`. If a number is not in `crops.csv` or `docs/SOURCES.md`, stop and ask.

**M3: static screens.** Build the four screens with routing, tokens, and i18n, using mock JSON. No API calls yet.

### **Day 1**

* **Morning:** drop in Friday's data and fix what breaks. Build `/field` and `/plans`. Build the Ribbon component.  
* **Afternoon:** Underground SVG component (the hardest visual, start early). Wishes screen. Plan cards.  
* **Evening:** `/explain`, the confidence badge, and the Advisor tools plus chat endpoint.

### **Day 2**

* **Morning:** hindcast and replay animation, what-if slider, Passport.  
* **Early afternoon:** Souk.  
* **Late afternoon:** freeze features, bug-bash, record a backup demo video, rehearse.

### **Demo script (about 3 minutes)**

1. A farmer says a wish out loud. Cards appear.  
2. The three futures show, and the Underground changes between plans.  
3. Tap "Bring back the worst year". The weak plan browns out and the recommended one holds.  
4. Ask the Advisor "what if it rains 30% less?" and show the evidence chips.  
5. Generate the Soil Passport. A buyer's premium offer unlocks.  
6. Close: "Supports the farmer, never replaces them."

---

## **12\. Contents for `AGENTS.md`**

```
# SoilSim rules for the coding agent

1. The engine (backend/engine) contains pure functions only: no HTTP, no LLM, no file writes.
2. No agronomy number may be written in code unless it comes from data/crops.csv or is cited in docs/SOURCES.md. If missing, stop and ask.
3. The frontend never calculates agronomy. It renders what the API returns.
4. The LLM never calculates. It calls tools in backend/advisor and phrases the results.
5. The app never calls NASA or other data APIs at runtime. Only pipeline/ scripts do, and they write to data/processed.
6. Fake and real data share one schema. Fake rows are flagged is_fake.
7. API keys live in .env only. Never in code, never in the frontend.
8. Every engine function has a pytest test before it is considered done.
9. Small commits, one milestone at a time. After each task, list what changed and how to run it.
10. Use theme tokens for every color and font. No hard-coded colors.
11. UI text goes through i18n. No hard-coded strings in components.
12. Every screen shows: "This tool supports farmer judgment and does not replace local expertise."
```

---

## **13\. Who does what**

**Claude (architect, mentor, reviewer):** writes specs, formulas, schemas, prompts and tests per milestone; explains each piece in simple terms; reviews your diffs for bugs and unsourced numbers; drafts the crop table, knowledge cards and demo script.

**Antigravity (implementer):** scaffolds and writes code from one milestone spec at a time; runs tests and fixes errors; uses its browser agent to check screens against the tokens. It never invents agronomy numbers.

**You (owners):** create the Earthdata and LLM API accounts and keep keys in `.env`; run the pipeline and sanity-check outputs; get the crop table and cards reviewed by someone who knows agronomy; make design assets and the pitch; make final decisions; understand each piece well enough to answer judges.

**Suggested split for a team of 3 to 4:** one person on pipeline and engine, one on frontend (Ribbon, Underground, cards), one on Advisor, market and API glue, one on design polish and pitch.

---

## **14\. Risks and how we handle them**

| Risk | Handling |
| ----- | ----- |
| Friday's data format differs from our schema | Adapter in `build_features.py` only. Everything downstream reads the same schema |
| MODIS/SMAP access is slow | Use POWER and a documented proxy; mark confidence lower |
| LLM says something agronomically wrong | Tool-only numbers, rules in the system prompt, evidence chips, local-review notes |
| Demo internet fails | Everything cached; record a backup video |
| Underground SVG takes too long | Start it first on Day 1; fall back to 3 preset illustrations that swap by score |
| Scores look made up | Every parameter sourced; hindcast gives real variation; scores shown as modeled estimates, not certified results |

**Honesty line for the pitch:** scores are modeled estimates from satellite-derived data and published agronomy references. They are not certified outcomes. Verification with satellite data and farmer confirmation is the next step.

