"""SoilGrids (ISRIC 250m) data fetcher.

Planned for data pipeline milestone:
Fetches soil texture, organic carbon, pH, and bulk density for field coordinates.
Caches output into data/processed/soil/{field_id}.json.
"""

def fetch_soilgrids(lat: float, lon: float, field_id: str):
    raise NotImplementedError("Offline pipeline script - scheduled for data pipeline milestone.")
