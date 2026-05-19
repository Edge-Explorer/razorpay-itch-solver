import enum
from sqlalchemy import String, ForeignKey, Enum, Float 
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base, TimestampMixin

class DisputeStatus(enum.Enum):
    SUBMITTED= "submitted"
    PENDING_SUPPLIER_RESPONSE= "pending_supplier_response"
    UNDER_REVIEW= "under_review"
    RESOLVED_IN_FAVOR_OF_BUYER= "resolved_in_favor_of_buyer"
    RESOLVED_IN_FAVOR_OF_SUPPLIER= "resolved_in_favor_of_supplier"
    LOGISTICS_FAULT= "logistics_fault"

class DisputeSeverity(enum.Enum):
    LOW= "low"  # Minor transit lag, slight packaging wear
    MEDIUM= "medium"  # Missing minor items, partially damaged shipment
    HIGH= "high"  # Mold, fungus, rotting food, hazardous materials

class Dispute(Base, TimestampMixin):
    __tablename__= "disputes"

    id: Mapped[int]= mapped_column(primary_key= True)
    pool_id: Mapped[int]= mapped_column(ForeignKey("order_pools.id"))
    restaurant_id: Mapped[str]= mapped_column(String(100), index= True)
    supplier_id: Mapped[int]= mapped_column(ForeignKey("suppliers.id"))

    # Details of the dispute
    description: Mapped[str]= mapped_column(String(1000))
    evidence_url: Mapped[str]= mapped_column(String(500), nullable= True)  # Photo uploads

    # Status and Severity classification (evaluated by QA AI Agent)
    status: Mapped[DisputeStatus] = mapped_column(Enum(DisputeStatus), default=DisputeStatus.SUBMITTED)
    severity: Mapped[DisputeSeverity] = mapped_column(Enum(DisputeSeverity), default=DisputeSeverity.LOW)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)  # AI triage confidence

    # Resolution comments
    resolution_notes: Mapped[str] = mapped_column(String(1000), nullable=True)