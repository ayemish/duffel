from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import duffel_client as duffel
from .normalize import normalize_offer, normalize_offer_request

app = FastAPI(title="Rihla Duffel Backend")

# Wide open for now since this is a dev/test backend behind ngrok/localhost.
# Tighten allow_origins before this ever goes near production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Search — replaces GET api.rihla.cc/v2/offers/search
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    origin: str
    destination: str
    departure_date: str  # "YYYY-MM-DD"
    return_date: Optional[str] = None
    adults: int = 1
    children: int = 0
    infants: int = 0
    cabin_class: str = "economy"


@app.post("/flights/search")
def search_flights(req: SearchRequest):
    raw = duffel.create_offer_request(
        origin=req.origin.upper(),
        destination=req.destination.upper(),
        departure_date=req.departure_date,
        return_date=req.return_date,
        adults=req.adults,
        children=req.children,
        infants=req.infants,
        cabin_class=req.cabin_class,
    )
    return normalize_offer_request(raw)


# ---------------------------------------------------------------------------
# Single offer — for the offer detail sheet
# ---------------------------------------------------------------------------

@app.get("/flights/offers/{offer_id}")
def get_offer(offer_id: str):
    raw = duffel.get_offer(offer_id)
    return normalize_offer(raw)


# ---------------------------------------------------------------------------
# Orders (booking) — not wired into the app yet, but ready for when Book
# grows a checkout step.
# ---------------------------------------------------------------------------

class PassengerInfo(BaseModel):
    id: str
    title: str
    gender: str  # "m" | "f"
    given_name: str
    family_name: str
    born_on: str  # "YYYY-MM-DD"
    email: str
    phone_number: str  # E.164, e.g. "+923001234567"


class CreateOrderRequest(BaseModel):
    offer_id: str
    passenger: PassengerInfo


@app.post("/orders")
def create_order(req: CreateOrderRequest):
    # Re-fetch the offer server-side rather than trusting a client-supplied
    # price/currency — offers can expire or be re-priced, and the amount used
    # for payment should always come from Duffel directly.
    offer = duffel.get_offer(req.offer_id)
    order = duffel.create_order(
        offer_id=req.offer_id,
        amount=offer["total_amount"],
        currency=offer["total_currency"],
        passenger=req.passenger.model_dump(),
    )
    return order


@app.get("/orders")
def list_orders(limit: int = 10):
    return duffel.list_orders(limit=limit)


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    return duffel.get_order(order_id)


@app.post("/orders/{order_id}/cancel")
def request_cancellation(order_id: str):
    """Step 1 of 2: creates a cancellation quote (with refund amount) but does
    not commit it yet. Call /order-cancellations/{id}/confirm to finalize."""
    return duffel.cancel_order(order_id)


@app.post("/order-cancellations/{cancellation_id}/confirm")
def confirm_cancellation(cancellation_id: str):
    """Step 2 of 2: actually cancels the booking and triggers the refund."""
    return duffel.confirm_cancellation(cancellation_id)


# ---------------------------------------------------------------------------
# Airport / place search — could replace or complement the bundled
# ActiveAirports.csv dataset in the app.
# ---------------------------------------------------------------------------

@app.get("/places/suggestions")
def place_suggestions(query: str):
    if not query or len(query.strip()) < 2:
        raise HTTPException(status_code=400, detail="query must be at least 2 characters")
    return duffel.place_suggestions(query.strip())
