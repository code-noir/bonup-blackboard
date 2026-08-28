# backend/billing/store_quote.py
#
# Server-authoritative Store quote construction. This module validates proposed
# customer selections against backend commercial state and performs no mutation.

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.utils import timezone

from .blackbod import BLACKBOD_TOOL_SLUG, has_blackbod_access
from .commercial import has_tool
from .models import Product, ProductPrice
from .storage import GIB, evaluate_storage_purchase_eligibility
from .storage_commerce import get_active_product_price, get_storage_catalog

SUPPORTED_BILLING_INTERVALS = {"monthly", "annual"}
ZERO_MONEY = Decimal("0.00")
TOOL_CURRENCY = "USD"
STORAGE_SUFFICIENT_RESERVE_MESSAGE = "You currently have enough available Vault storage. Additional permanent Storage becomes available as you approach your current capacity."
STORAGE_AVAILABLE_MESSAGE = "Additional permanent Storage is available for your current selection."
STORAGE_UNAVAILABLE_MESSAGE = "This Storage option is not currently available."


@dataclass(frozen=True)
class StoreQuoteValidationError(Exception):
    code: str
    detail: str
    status_code: int = 400


def _money(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _money_string(value):
    return str(_money(value))


def _as_optional_slug(value, field_name):
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise StoreQuoteValidationError("invalid_request", f"{field_name} must be null or a non-empty string.")
    return value.strip()


def _normalize_tool_selections(tools):
    if not isinstance(tools, list):
        raise StoreQuoteValidationError("invalid_request", "tools must be a list.")

    normalized_tools = []
    seen_tool_slugs = set()
    for tool in tools:
        if not isinstance(tool, dict):
            raise StoreQuoteValidationError("invalid_request", "Each tool selection must be an object.")
        allowed_tool_keys = {"slug", "billing_interval"}
        unknown_tool_keys = set(tool.keys()) - allowed_tool_keys
        if unknown_tool_keys:
            raise StoreQuoteValidationError("invalid_request", f"Unsupported tool selection field: {sorted(unknown_tool_keys)[0]}.")

        slug = tool.get("slug")
        billing_interval = tool.get("billing_interval")
        if not isinstance(slug, str) or not slug.strip():
            raise StoreQuoteValidationError("invalid_request", "Tool slug is required.")
        if billing_interval not in SUPPORTED_BILLING_INTERVALS:
            raise StoreQuoteValidationError("unsupported_billing_interval", "Tool billing_interval must be monthly or annual.")

        slug = slug.strip()
        if slug in seen_tool_slugs:
            raise StoreQuoteValidationError("duplicate_tool", "Duplicate Tool selections are not allowed.")
        seen_tool_slugs.add(slug)
        normalized_tools.append({"slug": slug, "billing_interval": billing_interval})
    return normalized_tools


def _validate_request_shape(selection):
    if not isinstance(selection, dict):
        raise StoreQuoteValidationError("invalid_request", "Quote request must be a JSON object.")

    allowed_keys = {"tools", "storage_product_slug", "ai_product_slug"}
    unknown_keys = set(selection.keys()) - allowed_keys
    if unknown_keys:
        raise StoreQuoteValidationError("invalid_request", f"Unsupported quote field: {sorted(unknown_keys)[0]}.")

    normalized_tools = _normalize_tool_selections(selection.get("tools", []))
    storage_product_slug = _as_optional_slug(selection.get("storage_product_slug"), "storage_product_slug")
    ai_product_slug = _as_optional_slug(selection.get("ai_product_slug"), "ai_product_slug")

    if not normalized_tools and storage_product_slug is None and ai_product_slug is None:
        raise StoreQuoteValidationError("empty_selection", "Select at least one Store product to quote.")

    return {
        "tools": normalized_tools,
        "storage_product_slug": storage_product_slug,
        "ai_product_slug": ai_product_slug,
    }


def _validate_eligibility_request_shape(selection):
    if not isinstance(selection, dict):
        raise StoreQuoteValidationError("invalid_request", "Eligibility request must be a JSON object.")

    allowed_keys = {"tools", "ai_product_slug", "storage_product_slugs"}
    unknown_keys = set(selection.keys()) - allowed_keys
    if unknown_keys:
        raise StoreQuoteValidationError("invalid_request", f"Unsupported eligibility field: {sorted(unknown_keys)[0]}.")

    storage_product_slugs = selection.get("storage_product_slugs")
    if storage_product_slugs is not None:
        if not isinstance(storage_product_slugs, list):
            raise StoreQuoteValidationError("invalid_request", "storage_product_slugs must be a list when supplied.")
        normalized_storage_slugs = []
        seen_storage_slugs = set()
        for slug in storage_product_slugs:
            if not isinstance(slug, str) or not slug.strip():
                raise StoreQuoteValidationError("invalid_request", "Storage product slugs must be non-empty strings.")
            slug = slug.strip()
            if slug in seen_storage_slugs:
                raise StoreQuoteValidationError("invalid_request", "Duplicate Storage product slugs are not allowed.")
            seen_storage_slugs.add(slug)
            normalized_storage_slugs.append(slug)
    else:
        normalized_storage_slugs = None

    return {
        "tools": _normalize_tool_selections(selection.get("tools", [])),
        "ai_product_slug": _as_optional_slug(selection.get("ai_product_slug"), "ai_product_slug"),
        "storage_product_slugs": normalized_storage_slugs,
    }


def _resolve_product(slug):
    try:
        return Product.objects.select_related("tool_metadata", "storage_metadata", "ai_metadata").get(slug=slug)
    except Product.DoesNotExist:
        raise StoreQuoteValidationError("product_not_found", "Selected product was not found.")


def _add_amount(totals, amount, currency):
    if totals["currency"] is None:
        totals["currency"] = currency
    elif totals["currency"] != currency:
        raise StoreQuoteValidationError("mixed_currency", "Selected products use incompatible currencies.")
    totals["amount"] += amount


def _resolve_tool_quote_item(user, tool_selection, now):
    product = _resolve_product(tool_selection["slug"])
    if product.product_type != Product.ProductType.TOOL:
        raise StoreQuoteValidationError("invalid_product_kind", "Selected Tool slug does not reference a Tool product.")
    if not product.active:
        raise StoreQuoteValidationError("inactive_product", "Selected Tool product is inactive.")
    if not hasattr(product, "tool_metadata"):
        raise StoreQuoteValidationError("missing_product_metadata", "Selected Tool product is missing metadata.")
    if product.tool_metadata.tool_slug == BLACKBOD_TOOL_SLUG and has_blackbod_access(user, now=now):
        raise StoreQuoteValidationError("tool_already_active", "This Tool is already active for your account.", status_code=409)
    if product.tool_metadata.tool_slug != BLACKBOD_TOOL_SLUG and has_tool(user, product.tool_metadata.tool_slug, now=now):
        raise StoreQuoteValidationError("tool_already_active", "This Tool is already active for your account.", status_code=409)

    interval = tool_selection["billing_interval"]
    amount = product.monthly_price if interval == "monthly" else product.annual_price
    if amount is None:
        raise StoreQuoteValidationError("missing_product_price", "Selected Tool product is missing active pricing.")

    metadata = product.tool_metadata
    return {
        "kind": "tool",
        "product_slug": product.slug,
        "name": product.name,
        "billing_interval": interval,
        "charge_type": "recurring",
        "amount": _money_string(amount),
        "currency": TOOL_CURRENCY,
        "included_storage_bytes": metadata.included_storage_bytes,
        "included_storage_gib": metadata.included_storage_bytes // GIB,
        "included_ai": metadata.included_ai_allowance,
    }, _money(amount), TOOL_CURRENCY


def _resolve_storage_quote_item(user, storage_product_slug, now):
    product = _resolve_product(storage_product_slug)
    if product.product_type != Product.ProductType.STORAGE:
        raise StoreQuoteValidationError("invalid_product_kind", "Selected Storage slug does not reference a Storage product.")
    if not product.active:
        raise StoreQuoteValidationError("inactive_product", "Selected Storage product is inactive.")
    if not hasattr(product, "storage_metadata"):
        raise StoreQuoteValidationError("missing_product_metadata", "Selected Storage product is missing metadata.")

    try:
        price = get_active_product_price(product, ProductPrice.PriceType.ONE_TIME, now=now)
    except ValidationError as exc:
        raise StoreQuoteValidationError("ambiguous_product_price", str(exc))
    if price is None:
        raise StoreQuoteValidationError("missing_product_price", "Selected Storage product is missing active one-time pricing.")

    capacity_bytes = product.storage_metadata.capacity_bytes
    eligibility = evaluate_storage_purchase_eligibility(user, capacity_bytes, declared_upcoming_need_bytes=0, now=now)
    if not eligibility.eligible:
        raise StoreQuoteValidationError(
            "storage_ineligible",
            "Selected additional Storage cannot currently be purchased.",
            status_code=409,
        )

    return {
        "kind": "storage",
        "product_slug": product.slug,
        "name": product.name,
        "charge_type": "one_time",
        "amount": _money_string(price.amount),
        "currency": price.currency,
        "capacity_bytes": capacity_bytes,
        "capacity_gib": capacity_bytes // GIB,
        "eligibility": {
            "eligible": True,
            "reason": eligibility.reason,
        },
    }, _money(price.amount), price.currency


def build_store_quote(*, user, selection, now=None):
    now = now or timezone.now()
    normalized = _validate_request_shape(selection)

    if normalized["ai_product_slug"] is not None:
        raise StoreQuoteValidationError("unsupported_ai_product", "Additional AI products are not available yet.")

    recurring_totals = {
        "monthly": {"amount": ZERO_MONEY, "currency": None},
        "annual": {"amount": ZERO_MONEY, "currency": None},
    }
    one_time_total = {"amount": ZERO_MONEY, "currency": None}
    due_today_total = {"amount": ZERO_MONEY, "currency": None}
    items = []

    for tool_selection in normalized["tools"]:
        item, amount, currency = _resolve_tool_quote_item(user, tool_selection, now)
        items.append(item)
        _add_amount(recurring_totals[item["billing_interval"]], amount, currency)
        _add_amount(due_today_total, amount, currency)

    if normalized["storage_product_slug"] is not None:
        item, amount, currency = _resolve_storage_quote_item(user, normalized["storage_product_slug"], now)
        items.append(item)
        _add_amount(one_time_total, amount, currency)
        _add_amount(due_today_total, amount, currency)

    currency = due_today_total["currency"] or one_time_total["currency"] or "USD"
    for bucket in [recurring_totals["monthly"], recurring_totals["annual"], one_time_total]:
        if bucket["currency"] is not None and bucket["currency"] != currency:
            raise StoreQuoteValidationError("mixed_currency", "Selected products use incompatible currencies.")

    return {
        "currency": currency,
        "items": items,
        "totals": {
            "recurring": {
                "monthly": _money_string(recurring_totals["monthly"]["amount"]),
                "annual": _money_string(recurring_totals["annual"]["amount"]),
            },
            "one_time": _money_string(one_time_total["amount"]),
            "due_today": _money_string(due_today_total["amount"]),
        },
    }


def _storage_eligibility_message(code, eligible):
    if eligible:
        return STORAGE_AVAILABLE_MESSAGE
    if code == "sufficient_reserve":
        return STORAGE_SUFFICIENT_RESERVE_MESSAGE
    if code == "requested_capacity_too_small":
        return "Choose a larger Storage option for your current capacity needs."
    return STORAGE_UNAVAILABLE_MESSAGE


def _storage_eligibility_result(*, eligible, code, message=None):
    return {
        "eligible": eligible,
        "code": code,
        "message": message or _storage_eligibility_message(code, eligible),
    }


def _resolve_storage_eligibility(user, storage_product_slug, now):
    try:
        product = _resolve_product(storage_product_slug)
    except StoreQuoteValidationError as exc:
        return _storage_eligibility_result(eligible=False, code=exc.code)

    if product.product_type != Product.ProductType.STORAGE:
        return _storage_eligibility_result(eligible=False, code="invalid_product_kind")
    if not product.active:
        return _storage_eligibility_result(eligible=False, code="inactive_product")
    if not hasattr(product, "storage_metadata"):
        return _storage_eligibility_result(eligible=False, code="missing_product_metadata")

    try:
        price = get_active_product_price(product, ProductPrice.PriceType.ONE_TIME, now=now)
    except ValidationError:
        return _storage_eligibility_result(eligible=False, code="ambiguous_product_price")
    if price is None:
        return _storage_eligibility_result(eligible=False, code="missing_product_price")

    eligibility = evaluate_storage_purchase_eligibility(
        user,
        product.storage_metadata.capacity_bytes,
        declared_upcoming_need_bytes=0,
        now=now,
    )
    return _storage_eligibility_result(
        eligible=eligibility.eligible,
        code=eligibility.reason,
    )


def build_store_purchase_eligibility(*, user, selection, now=None):
    now = now or timezone.now()
    normalized = _validate_eligibility_request_shape(selection)

    if normalized["ai_product_slug"] is not None:
        raise StoreQuoteValidationError("unsupported_ai_product", "Additional AI products are not available yet.")

    storage_slugs = normalized["storage_product_slugs"]
    if storage_slugs is None:
        storage_slugs = [item.product_slug for item in get_storage_catalog(now=now)]

    return {
        "storage": {
            slug: _resolve_storage_eligibility(user, slug, now)
            for slug in storage_slugs
        }
    }
