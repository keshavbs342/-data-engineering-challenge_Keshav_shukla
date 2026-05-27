"""
scraper/mock_scraper.py
=======================
Generates statistically realistic B2B product records.
Mirrors IndiaMART data structure including intentional quality gaps.
"""

import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List

from utils.helpers import make_id

CATEGORY_DATA: Dict[str, Dict] = {
    "industrial-machinery": {
        "products": [
            "Hydraulic Press Machine", "CNC Lathe Machine", "Industrial Conveyor Belt",
            "Pneumatic Drill Press", "Automatic Welding Machine", "Metal Cutting Bandsaw",
            "Industrial Air Compressor", "Gear Hobbing Machine", "Injection Moulding Machine",
            "Rotary Furnace", "Centrifugal Pump", "Industrial Mixer", "Power Press Machine",
            "Grinding Mill", "Screw Compressor",
        ],
        "price_range": (15000, 4500000),
        "units": ["piece", "set", "unit"],
        "keywords": ["heavy duty", "automatic", "semi-automatic", "high speed", "energy efficient"],
    },
    "electronics-components": {
        "products": [
            "Printed Circuit Board", "Arduino Microcontroller", "MOSFET Transistor",
            "LED Strip Light", "Capacitor Pack", "Resistor Kit", "Solar Panel 100W",
            "Li-ion Battery Cell", "RF Module 433MHz", "Raspberry Pi 4", "ESP32 Module",
            "Stepper Motor Driver", "OLED Display Module", "DC-DC Buck Converter",
            "Hall Effect Sensor",
        ],
        "price_range": (50, 85000),
        "units": ["piece", "pack", "lot", "dozen"],
        "keywords": ["original", "imported", "genuine", "SMD", "RoHS compliant"],
    },
    "textile-fabric": {
        "products": [
            "Cotton Grey Fabric", "Polyester Blended Yarn", "Silk Dupioni Fabric",
            "Denim Fabric 10oz", "Rayon Printed Fabric", "Wool Tweed Fabric",
            "Linen Shirting Fabric", "Viscose Jersey Knit", "Chiffon Georgette Fabric",
            "Technical Non-Woven Fabric", "Spandex Stretch Denim", "Jacquard Brocade Fabric",
        ],
        "price_range": (80, 1500),
        "units": ["meter", "kg", "roll", "yard"],
        "keywords": ["GSM", "OE spun", "ring spun", "combed", "mercerized"],
    },
    "agriculture-equipment": {
        "products": [
            "Mini Tractor 20HP", "Drip Irrigation Kit", "Rotavator 5ft",
            "Power Sprayer 16L", "Paddy Transplanter", "Grain Moisture Meter",
            "Manual Seeder 5-Row", "Greenhouse Polythene Sheet", "Solar Water Pump 2HP",
            "Chaff Cutter Machine", "Vegetable Transplanter", "Bio Pesticide Sprayer",
        ],
        "price_range": (2500, 850000),
        "units": ["piece", "set", "unit", "kit"],
        "keywords": ["BIS certified", "diesel", "electric", "portable", "imported"],
    },
    "construction-materials": {
        "products": [
            "TMT Steel Bar Fe500", "Portland Cement 53 Grade", "AAC Block 600x200x150",
            "HDPE Pipe 110mm", "Ceramic Floor Tile 600x600", "Plywood 18mm Marine Grade",
            "Glass Wool Insulation", "Steel Angle 50x50x5", "PVC Conduit Pipe",
            "Waterproofing Membrane", "Aluminium Composite Panel", "Gypsum Board 12mm",
        ],
        "price_range": (120, 95000),
        "units": ["bag", "ton", "sq ft", "sq meter", "piece", "bundle"],
        "keywords": ["ISI marked", "BIS certified", "premium grade", "weather resistant"],
    },
}

INDIAN_CITIES = [
    ("Mumbai", "Maharashtra"), ("Delhi", "Delhi"), ("Surat", "Gujarat"),
    ("Ludhiana", "Punjab"), ("Coimbatore", "Tamil Nadu"), ("Rajkot", "Gujarat"),
    ("Pune", "Maharashtra"), ("Hyderabad", "Telangana"), ("Ahmedabad", "Gujarat"),
    ("Chennai", "Tamil Nadu"), ("Kolkata", "West Bengal"), ("Jaipur", "Rajasthan"),
    ("Faridabad", "Haryana"), ("Kanpur", "Uttar Pradesh"), ("Nagpur", "Maharashtra"),
    ("Indore", "Madhya Pradesh"), ("Thane", "Maharashtra"), ("Vadodara", "Gujarat"),
    ("Visakhapatnam", "Andhra Pradesh"), ("Noida", "Uttar Pradesh"),
    ("Gurgaon", "Haryana"), ("Kochi", "Kerala"), ("Nashik", "Maharashtra"),
]

SUPPLIER_SUFFIXES = [
    "Industries", "Enterprises", "Corporation", "Trading Co.", "Pvt. Ltd.",
    "Manufacturing Co.", "Export House", "Suppliers", "Works", "Solutions",
]
SUPPLIER_PREFIXES = [
    "Shree", "Sri", "National", "Global", "Pioneer", "Bharat", "Prime",
    "Excellent", "Quality", "Modern", "Universal", "Supreme", "Apex", "Star",
]
CERTS = ["ISO 9001:2015", "BIS", "CE", "ROHS", "MSME Registered", None, None, None]


def generate(categories: List[str], per_category: int = 120, seed: int = 42) -> List[Dict]:
    random.seed(seed)
    records = []
    for cat in categories:
        meta = CATEGORY_DATA.get(cat)
        if not meta:
            continue
        for _ in range(per_category):
            records.append(_make_record(cat, meta))
    return records


def _make_record(category: str, meta: Dict) -> Dict:
    base   = random.choice(meta["products"])
    kw     = random.choice(meta["keywords"])
    title  = f"{kw.title()} {base}" if random.random() > 0.4 else base
    city, state = random.choice(INDIAN_CITIES)
    supplier = (
        f"{random.choice(SUPPLIER_PREFIXES)} {random.choice(SUPPLIER_PREFIXES)} "
        f"{random.choice(SUPPLIER_SUFFIXES)}"
    )
    lo, hi = meta["price_range"]
    price  = round(random.uniform(lo, hi), 2)
    unit   = random.choice(meta["units"])

    # ~8% missing prices to simulate real scraping noise
    if random.random() < 0.08:
        price     = None
        price_raw = "Get Latest Price"
    else:
        price_raw = f"₹{price:,.0f} / {unit}"

    days_ago = random.randint(0, 365)
    return {
        "id":                make_id(title, supplier, city),
        "title":             title,
        "category":          category,
        "price_raw":         price_raw,
        "price":             price,
        "currency":          "INR",
        "unit":              unit,
        "moq":               random.choice([1, 5, 10, 25, 50, 100, 500]),
        "supplier":          supplier,
        "city":              city,
        "state":             state,
        "location":          f"{city}, {state}",
        "rating":            round(random.uniform(3.0, 5.0), 1) if random.random() > 0.3 else None,
        "response_rate_pct": random.randint(50, 100) if random.random() > 0.15 else None,
        "response_time":     random.choice(["Within 1 Hour", "Within 4 Hours", "Within 24 Hours", "2-3 Days", None]),
        "certification":     random.choice(CERTS),
        "years_in_business": random.randint(1, 35) if random.random() > 0.2 else None,
        "listed_date":       (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
        "source":            "indiamart_mock",
        "url":               f"https://www.indiamart.com/proddetail/{uuid.uuid4().hex[:8]}.html",
    }
