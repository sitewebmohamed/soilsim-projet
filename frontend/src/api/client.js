/**
 * SoilSim API Client
 *
 * USE_MOCK = true: Loads JSON files from frontend/src/mock/
 * USE_MOCK = false: Calls the live FastAPI backend at API_BASE_URL
 *
 * No agronomic calculations occur here. This module only fetches and returns data.
 */

const USE_MOCK = true;
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ── Mock imports ────────────────────────────────────────────────────────────
import mockCrops from "../mock/crops.json";
import mockRegions from "../mock/regions.json";
import mockPlansMeknes from "../mock/plans_meknes.json";
import mockPlansSaiss from "../mock/plans_saiss.json";
import mockPlansSouss from "../mock/plans_souss.json";

const MOCK_PLANS = {
  meknes: mockPlansMeknes,
  saiss: mockPlansSaiss,
  souss: mockPlansSouss,
};

// ── Helpers ──────────────────────────────────────────────────────────────────
async function liveGet(path) {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

// ── Public API ────────────────────────────────────────────────────────────────

/** Returns list of crop objects with multilingual names and agronomic traits. */
export async function getCrops() {
  if (USE_MOCK) return mockCrops;
  return liveGet("/api/crops");
}

/** Returns list of demo regions with coordinates and climate type. */
export async function getRegions() {
  if (USE_MOCK) return mockRegions;
  return liveGet("/api/regions");
}

/**
 * Returns field summary for a region.
 * Currently returns region data with a note about synthetic data.
 */
export async function getField(regionId) {
  if (USE_MOCK) {
    const region = mockRegions.find((r) => r.id === regionId);
    if (!region) throw new Error(`Region not found: ${regionId}`);
    return { ...region, data_mode: "fake" };
  }
  return liveGet(`/api/field/${regionId}`);
}

/**
 * Returns the three compared rotation plans for a field/region.
 * Plans contain scores, ribbons, underground and confidence data.
 *
 * In mock mode, returns pre-generated plans (rotation_ids ignored).
 * In live mode, sends rotation and weights to the backend.
 */
export async function getPlans(regionId, _rotationIds, _weights, _availableWater) {
  if (USE_MOCK) {
    const plans = MOCK_PLANS[regionId];
    if (!plans) throw new Error(`No mock plans for region: ${regionId}`);
    return plans;
  }
  return liveGet(`/api/plans/${regionId}`);
}

/**
 * Returns hindcast replay for a plan in a specific year.
 * Live API stub — not available in mock mode.
 */
export async function getReplay(planId, year) {
  if (USE_MOCK) {
    return { plan_id: planId, year, note: "Replay not available in mock mode." };
  }
  return liveGet(`/api/plans/${planId}/replay?year=${year}`);
}

/**
 * Returns what-if rescored plan given temperature and rainfall perturbations.
 * Live API stub — not available in mock mode.
 */
export async function getWhatIf(planId, tempDeltaC, rainFactor) {
  if (USE_MOCK) {
    return { plan_id: planId, note: "What-if not available in mock mode." };
  }
  return liveGet(`/api/plans/${planId}/whatif?temp_delta_c=${tempDeltaC}&rain_factor=${rainFactor}`);
}

/**
 * Returns the natural-language explanation object for a plan.
 * Live API stub — not available in mock mode.
 */
export async function getExplain(planId) {
  if (USE_MOCK) {
    return { plan_id: planId, note: "Explanation not available in mock mode." };
  }
  return liveGet(`/api/plans/${planId}/explain`);
}
