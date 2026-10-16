"""Export a complete, paginated Lifecycle snapshot for production review.

Lifecycle's product UI currently loads a maximum of 200 products and its CSV
export can therefore be incomplete.  This script uses the REST pagination
metadata, validates the result and writes stable CSV/JSON files without
changing any Lifecycle data.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from plm_client import call


ROOT = Path(__file__).parent
DEFAULT_OUTPUT_DIR = ROOT / "output" / "plm_snapshot"
PRODUCT_PAGE_SIZE = 100

CUSTOM_FIELD_NAMES = {
    "mv6jnln121cc81_kategorie_code": "Kategorie-Code",
    "muxy47ha94z24q_plenty_produkt_id": "Plenty Produkt-ID",
    "muxy5365hi2xhz_uvp": "UVP",
    "muxy5sc1s5a8yw_einkaufspreis": "Einkaufspreis",
}


def get(path: str, **params: Any) -> Any:
    status, data = call("GET", path, **params)
    if status != 200:
        raise RuntimeError(f"GET {path} failed with HTTP {status}: {data}")
    return data


def get_all_products() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    products: list[dict[str, Any]] = []
    page = 1
    expected_total: int | None = None

    while True:
        payload = get("products", page=page, limit=PRODUCT_PAGE_SIZE)
        batch = payload.get("data") or []
        pagination = payload.get("pagination") or {}
        if expected_total is None:
            expected_total = int(pagination.get("total") or 0)
        products.extend(batch)

        pages = int(pagination.get("pages") or 1)
        if page >= pages:
            break
        page += 1

    ids = [product.get("id") for product in products]
    duplicate_ids = [item_id for item_id, count in Counter(ids).items() if count > 1]
    if duplicate_ids:
        raise RuntimeError(f"Duplicate product IDs returned: {duplicate_ids}")
    if expected_total != len(products):
        raise RuntimeError(
            f"Incomplete product export: API reports {expected_total}, fetched {len(products)}"
        )

    return products, {
        "expected": expected_total,
        "exported": len(products),
        "pages": page,
        "complete": True,
    }


def scalar_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("title") or value.get("status") or "")
    return str(value or "")


def status_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("status") or value.get("name") or "")
    return str(value or "")


def product_rows(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for product in products:
        custom = product.get("customFields") or {}
        row = {
            "Lifecycle ID": product.get("id") or "",
            "Name": product.get("name") or "",
            "SKU": product.get("sku") or "",
            "Status": status_name(product.get("status")),
            "Year": product.get("year") or "",
            "Collection": scalar_name(product.get("collection")),
            "Category": scalar_name(product.get("category")),
            "Main Manufacturer": scalar_name(product.get("mainManufacturer")),
            "Sizes": ", ".join(map(str, product.get("sizes") or [])),
            "Variant Count": len(product.get("variants") or []),
            "BOM Line Count": len(product.get("billOfMaterials") or []),
            "Description": product.get("description") or "",
            "Tags": product.get("tags") or "",
        }
        for key, label in CUSTOM_FIELD_NAMES.items():
            row[label] = custom.get(key, "")
        rows.append(row)
    return rows


def order_rows(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for order in orders:
        items = order.get("items") or []
        payments = order.get("payments") or []
        linked = sum(bool(item.get("product")) for item in items)
        rows.append(
            {
                "Lifecycle ID": order.get("id") or "",
                "Title": order.get("title") or "",
                "PO Number": order.get("poNumber") or "",
                "Status": status_name(order.get("status")),
                "Vendor": scalar_name(order.get("manufacturer")),
                "Currency": order.get("currency") or "",
                "Total Cost": order.get("totalCost") or 0,
                "Total Pieces": order.get("totalNumberOfPieces") or 0,
                "Item Count": len(items),
                "Linked Items": linked,
                "Unlinked Items": len(items) - linked,
                "Payment Count": len(payments),
            }
        )
    return rows


def vendor_rows(vendors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Lifecycle ID": vendor.get("id") or "",
            "Name": vendor.get("name") or "",
            "Description": vendor.get("description") or "",
            "Contact Count": len(vendor.get("contacts") or []),
            "Address Count": len(vendor.get("addresses") or []),
        }
        for vendor in vendors
    ]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    products, product_validation = get_all_products()
    orders = get("orders")
    vendors = get("vendors")
    shipments = get("shipments")

    products_csv = output_dir / "products_complete.csv"
    orders_csv = output_dir / "orders_complete.csv"
    vendors_csv = output_dir / "vendors_complete.csv"
    inventory_json = output_dir / "inventory.json"

    write_csv(products_csv, product_rows(products))
    write_csv(orders_csv, order_rows(orders))
    write_csv(vendors_csv, vendor_rows(vendors))

    inventory = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "Lifecycle REST API v1 (read-only)",
        "counts": {
            "products": len(products),
            "orders": len(orders),
            "vendors": len(vendors),
            "shipments": len(shipments),
        },
        "validation": {"products": product_validation},
        "files": {
            "products": products_csv.name,
            "orders": orders_csv.name,
            "vendors": vendors_csv.name,
        },
    }
    inventory_json.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(inventory, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
