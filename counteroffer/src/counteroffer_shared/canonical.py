from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from counteroffer_shared.contracts import CreateQuoteInput


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def quote_fingerprint(request: CreateQuoteInput) -> str:
    canonical = {
        "merchant_id": request.merchant_id,
        "buyer_id": request.buyer_id,
        "items": [
            {"sku": sku, "quantity": quantity}
            for sku, quantity in sorted((item.sku, item.quantity) for item in request.items)
        ],
        "discount_bps": request.discount_bps,
    }
    return hashlib.sha256(canonical_json(canonical).encode("utf-8")).hexdigest()
