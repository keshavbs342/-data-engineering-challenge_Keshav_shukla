"""
api/enricher.py
===============
Enriches raw product records using real public APIs (no key required).

APIs used
---------
1. open.er-api.com  – live INR→USD/EUR exchange rates
2. api.datamuse.com – semantic keyword expansion per product title
3. restcountries.com – India geographic / trade metadata

All calls are async, rate-limited, and fault-tolerant.
Partial failures are logged and the record is still kept.
"""

import asyncio
from typing import Dict, List, Optional

import aiohttp

from config.settings import REQUEST_TIMEOUT, ENRICH_APIS
from utils.logger import get_logger

logger = get_logger(__name__)

_EXCHANGE_CACHE: Optional[Dict] = None
_GEO_CACHE:      Optional[Dict] = None


async def _get_json(session: aiohttp.ClientSession, url: str, params: Dict = None) -> Optional[Dict]:
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as r:
            r.raise_for_status()
            return await r.json(content_type=None)
    except Exception as exc:
        logger.warning("API call failed %s: %s", url, exc)
        return None


async def fetch_exchange_rates(session: aiohttp.ClientSession) -> Dict[str, float]:
    """Fetch live INR-based exchange rates. Cached for the session."""
    global _EXCHANGE_CACHE
    if _EXCHANGE_CACHE:
        return _EXCHANGE_CACHE
    data = await _get_json(session, ENRICH_APIS["currency"])
    if data and data.get("result") == "success":
        rates = data.get("rates", {})
        _EXCHANGE_CACHE = {"USD": rates.get("USD", 0.012), "EUR": rates.get("EUR", 0.011)}
        logger.info("Exchange rates fetched: 1 INR = %.5f USD", _EXCHANGE_CACHE["USD"])
    else:
        _EXCHANGE_CACHE = {"USD": 0.012, "EUR": 0.011}
        logger.warning("Exchange rate API unavailable – using fallback rates")
    return _EXCHANGE_CACHE


async def fetch_related_keywords(session: aiohttp.ClientSession, title: str) -> List[str]:
    """
    Use Datamuse (free, no key) to fetch semantically related keywords for a product title.
    Returns up to 5 related terms.
    """
    # Use the first 2 content words as the query
    words = [w for w in title.lower().split() if len(w) > 3][:2]
    if not words:
        return []
    query = " ".join(words)
    data = await _get_json(session, ENRICH_APIS["keywords"], params={"ml": query, "max": 5})
    if data and isinstance(data, list):
        return [item["word"] for item in data if "word" in item]
    return []


async def fetch_india_geo(session: aiohttp.ClientSession) -> Dict:
    """Fetch India country metadata from RestCountries API."""
    global _GEO_CACHE
    if _GEO_CACHE:
        return _GEO_CACHE
    data = await _get_json(session, ENRICH_APIS["geo"])
    if data and isinstance(data, list) and data:
        info = data[0]
        _GEO_CACHE = {
            "region":      info.get("region", "Asia"),
            "subregion":   info.get("subregion", "Southern Asia"),
            "population":  info.get("population", 1400000000),
            "area_km2":    info.get("area", 3287263),
            "timezones":   info.get("timezones", ["UTC+05:30"]),
        }
        logger.info("India geo metadata fetched from RestCountries")
    else:
        _GEO_CACHE = {"region": "Asia", "subregion": "Southern Asia"}
        logger.warning("RestCountries API unavailable – using fallback geo")
    return _GEO_CACHE


async def enrich_batch(records: List[Dict]) -> List[Dict]:
    """
    Enrich a list of product records with:
      - price_usd, price_eur  (via live exchange rates)
      - related_keywords      (via Datamuse semantic API)
      - country_region        (via RestCountries)

    Runs concurrently with a semaphore to avoid hammering free APIs.
    """
    sem = asyncio.Semaphore(5)
    connector = aiohttp.TCPConnector(limit=10, ssl=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        # Fetch shared data once
        rates = await fetch_exchange_rates(session)
        geo   = await fetch_india_geo(session)

        logger.info(
            "Enriching %d records | rates: %s | geo: %s",
            len(records), rates, geo.get("subregion", "?"),
        )

        async def _enrich_one(rec: Dict) -> Dict:
            async with sem:
                # Price conversion
                if rec.get("price") is not None:
                    rec["price_usd"] = round(rec["price"] * rates["USD"], 2)
                    rec["price_eur"] = round(rec["price"] * rates["EUR"], 2)
                else:
                    rec["price_usd"] = None
                    rec["price_eur"] = None

                # Semantic keywords for this product title
                kws = await fetch_related_keywords(session, rec.get("title", ""))
                rec["related_keywords"] = ", ".join(kws) if kws else ""

                # Country context
                rec["country_region"]    = geo.get("region", "Asia")
                rec["country_subregion"] = geo.get("subregion", "Southern Asia")

                return rec

        enriched = await asyncio.gather(*[_enrich_one(r) for r in records])

    logger.info("Enrichment complete for %d records", len(enriched))
    return list(enriched)
