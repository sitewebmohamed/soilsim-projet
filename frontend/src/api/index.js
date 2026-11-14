/**
 * API client module for SoilSim frontend.
 * All backend HTTP calls go through here.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function fetchHealth() {
  const res = await fetch(`${API_BASE_URL}/api/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchRegions() {
  const res = await fetch(`${API_BASE_URL}/api/regions`);
  if (!res.ok) {
    throw new Error(`Failed to load regions: ${res.statusText}`);
  }
  return res.json();
}
