from typing import Any, Optional
import requests
from fastapi import HTTPException

from .config import DUFFEL_API_TOKEN, DUFFEL_API_BASE, DUFFEL_VERSION

HEADERS = {
    "Authorization": f"Bearer {DUFFEL_API_TOKEN}",
    "Content-Type": "application/json",
    "Duffel-Version": DUFFEL_VERSION,
    "Accept-Encoding": "gzip",
}


def _request(method: str, path: str, json_body: Optional[dict] = None, params: Optional[dict] = None) -> dict:
    url = f"{DUFFEL_API_BASE}{path}"
    try:
        response = requests.request(method, url, headers=HEADERS, json=json_body, params=params, timeout=20)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Duffel: {exc}") from exc

    if response.status_code >= 400:
        # Surface Duffel's own error payload where possible — it's usually more
        # useful than a generic "bad request" when debugging from the app side.
        try:
            body: Any = response.json()
        except ValueError:
            body = response.text
        raise HTTPException(status_code=response.status_code, detail=body)

    if response.status_code == 204 or not response.content:
        return {}
    return response.json()


def create_offer_request(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    cabin_class: str = "economy",
) -> dict:
    slices = [{"origin": origin, "destination": destination, "departure_date": departure_date}]
    if return_date:
        slices.append({"origin": destination, "destination": origin, "departure_date": return_date})

    passengers = (
        [{"type": "adult"}] * max(adults, 1)
        + [{"type": "child"}] * max(children, 0)
        + [{"type": "infant_without_seat"}] * max(infants, 0)
    )

    body = _request(
        "POST",
        "/air/offer_requests",
        json_body={
            "data": {
                "slices": slices,
                "passengers": passengers,
                "cabin_class": cabin_class,
            }
        },
        # return_offers=true embeds offers directly in the offer_request response,
        # so we don't need a second call to list them.
        params={"return_offers": "true"},
    )
    return body["data"]


def get_offer(offer_id: str) -> dict:
    body = _request("GET", f"/air/offers/{offer_id}")
    return body["data"]


def create_order(offer_id: str, amount: str, currency: str, passenger: dict) -> dict:
    body = _request(
        "POST",
        "/air/orders",
        json_body={
            "data": {
                "selected_offers": [offer_id],
                "payments": [{"type": "balance", "currency": currency, "amount": amount}],
                "passengers": [passenger],
            }
        },
    )
    return body["data"]


def get_order(order_id: str) -> dict:
    body = _request("GET", f"/air/orders/{order_id}")
    return body["data"]


def list_orders(limit: int = 10) -> list:
    body = _request("GET", "/air/orders", params={"limit": limit})
    return body["data"]


def cancel_order(order_id: str) -> dict:
    body = _request("POST", "/air/order_cancellations", json_body={"data": {"order_id": order_id}})
    return body["data"]


def confirm_cancellation(cancellation_id: str) -> dict:
    body = _request("POST", f"/air/order_cancellations/{cancellation_id}/actions/confirm")
    return body.get("data", {})


def place_suggestions(query: str) -> list:
    body = _request("GET", "/places/suggestions", params={"query": query})
    return body["data"]
