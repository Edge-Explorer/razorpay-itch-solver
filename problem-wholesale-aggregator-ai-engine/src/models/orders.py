from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, ForeignKey, Enum
import enum
from src.models.base import Base, TimestampMixin

class PoolStatus(enum.Enum):
    OPEN= "open"
    SOFT_LOCK= "soft_lock"
    HARD_LOCK= "hard_lock"
    FULFILLED= "fulfilled"
    FAILED= "failed"

class OrderPool(Base, TimestampMixin):
    __tablename__= "order_pools"

    id: Mapped[int]= mapped_column(primary_key= True)
    product_name: Mapped[str]= mapped_column(String(255), index= True)
    canonical_product_id: Mapped[str]= mapped_column(String(100), index= True, nullable= True)
    zip_code: Mapped[str]= mapped_column(String(10), index= True)
    
    target_quantity: Mapped[float]= mapped_column(Float) # The MOQ
    current_quantity: Mapped[float]= mapped_column(Float, default= 0.0)

    status: Mapped[PoolStatus]= mapped_column(Enum(PoolStatus), default= PoolStatus.OPEN)

    # Relationship to the individual intents
    intents: Mapped[list["Intent"]]= relationship(back_populates= "pool", cascade= "all, delete-orphan")

class Intent(Base, TimestampMixin):
    __tablename__= "intents"

    id: Mapped[int]= mapped_column(primary_key= True)
    pool_id: Mapped[int]= mapped_column(ForeignKey("order_pools.id"))
    restaurant_id: Mapped[str]= mapped_column(String(100), index= True)

    quantity: Mapped[float]= mapped_column(Float)
    price_limit: Mapped[float]= mapped_column(Float)  # Max price the restaurant is willing to pay

    # Relationship back to the pool
    pool: Mapped["OrderPool"]= relationship(back_populates= "intents")