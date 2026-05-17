from abc import ABC, abstractmethod
import random
import uuid
from typing import Any, Dict 

# 1. THE PAYMENT INTERFACE & MOCK (Razorpay)
class PaymentProvider(ABC):
    """
    Abstract Base Class defining the strict contract for all payment operations.
    """
    @abstractmethod
    async def capture_payment(self, restaurant_id: str, amount: float) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def refund_payment(self, transition_id: str, amount: float) -> Dict[str, Any]:
        pass

class WalletMockProvider(PaymentProvider):
    """
    High-fidelity mock of a virtual wallet payment handler.
    Simulates successful captures, refunds, and realistic latency.
    """
    async def capture_payment(self, restaurant_id: str, amount: float) -> Dict[str, Any]:
        # Simulate payment processor receipt
        transition_id= f"pay_{uuid.uuid4().hex[:12]}"
        return {
            "transaction_id": transaction_id,
            "status": "captured",
            "amount": amount,
            "restaurant_id": restaurant_id,
            "gateway": "wallet_mock"
        }

    async def refund_payment(self, transaction_id: str, amount: float) -> Dict[str, Any]:
        return {
            "refund_id": f"ref_{uuid.uuid4().hex[:12]}",
            "original_transaction_id": transaction_id,
            "status": "refunded",
            "amount": amount
        }

# 2. THE LOGISTICS INTERFACE & MOCK (Porter)
class LogisticsProvider(ABC):
    """
    Abstract Base Class defining the contract for booking bulk deliveries.
    """
    @abstractmethod
    async def get_delivery_quote(self, origin: str, destination: str, weight_kg: float) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def book_delivery(self, quote_id: str) -> Dict[str, Any]:
        pass

class PorterMockProvider(LogisticsProvider):
    """
    High-fidelity mock provider simulating the Porter logistics service
    for commercial vehicle dispatch in Indian metros.
    """
    async def get_delivery_quote(self, origin: str, destination: str, weight_kg: float) -> Dict[str, Any]:
        quote_id= f"quote_{uuid.uuid4().hex[:12]}"
        # India market estimation logic: base fare + per kg rate + randomized fuel surcharge
        base_fare= 150.0
        weight_cost= weight_kg * 1.5
        estimated_price= base_fare + weight_cost + random.uniform(20.0, 50.0)

        return {
            "quote_id": quote_id,
            "origin": origin,
            "destination": destination,
            "weight_kg": weight_kg,
            "price_estimate": round(estimated_price, 2),
            "vehicle_type": "Tata Ace (Chota Hathi)" if weight_kg > 500 else "Three Wheeler"
        }

    async def book_delivery(self, quote_id: str) -> Dict[str, Any]:
        tracking_id= f"port_{uuid.uuid4().hex[:12]}"
        return {
            "booking_id": f"bk_{uuid.uuid4().hex[:12]}",
            "quote_id": quote_id,
            "status": "dispatched",
            "tracking_id": tracking_id,
            "driver_name": random.choice(["Ramesh Kumar", "Suresh Singh", "Amit Yadav"]),
            "eta_minutes": random.choice([30, 45, 60])
        }