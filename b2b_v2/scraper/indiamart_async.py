"""
scraper/indiamart_async.py
==========================
Async IndiaMART scraper built on AsyncScraper.
Targets the lightweight /search directory endpoint.
"""

from typing import Dict, List
from bs4 import BeautifulSoup

from scraper.async_scraper import AsyncScraper
from utils.helpers import clean_text, parse_price, make_id

BASE = "https://dir.indiamart.com/search.mp"


class IndiaMARTAsyncScraper(AsyncScraper):

    def _build_urls(self, category: str, pages: int = 3) -> List[str]:
        return [f"{BASE}?ss={category}&page={p}" for p in range(1, pages + 1)]

    def _parse_html(self, html: str, category: str, url: str) -> List[Dict]:
        soup = BeautifulSoup(html, "lxml")
        selectors = [
            "div.prd-card", "li.listing", "div.product-item",
            "div[class*='prod']", "div[class*='listing']",
        ]
        cards = []
        for sel in selectors:
            cards = soup.select(sel)
            if cards:
                break

        products = []
        for card in cards:
            try:
                p = self._parse_card(card, category)
                if p:
                    products.append(p)
            except Exception:
                pass
        return products

    def _parse_card(self, card, category: str) -> Dict | None:
        title_tag = card.select_one("a.prd-name, h2, h3, .product-title, a[title]")
        title = clean_text(title_tag.get_text() if title_tag else "")
        if not title:
            return None

        price_tag = card.select_one(".price, .prd-price, span[class*='price']")
        price_raw = clean_text(price_tag.get_text() if price_tag else "")

        supplier_tag = card.select_one(".comp-name, .supplier, .company-name")
        supplier = clean_text(supplier_tag.get_text() if supplier_tag else "")

        loc_tag = card.select_one(".location, .loc, span[class*='loc']")
        location = clean_text(loc_tag.get_text() if loc_tag else "")

        link_tag = title_tag if (title_tag and title_tag.name == "a") else card.select_one("a[href]")
        href = (link_tag.get("href", "") if link_tag else "") or ""
        product_url = href if href.startswith("http") else f"https://www.indiamart.com{href}"

        return {
            "id":        make_id(title, supplier, category),
            "title":     title,
            "category":  category,
            "price_raw": price_raw,
            "price":     parse_price(price_raw),
            "currency":  "INR",
            "supplier":  supplier,
            "location":  location,
            "url":       product_url,
            "source":    "indiamart_live",
        }
