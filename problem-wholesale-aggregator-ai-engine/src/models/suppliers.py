from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Float, ForeignKey, Enum, Boolean
import enum
from src.models.base import Base, TimestampMixin

class VerificationStatus(enum.Enum):
    PENDING= "pending"
    VERIFIED= "verified"
    REJECTED= "rejected"

class Supplier(Base, TimestampMixin):
    __tablename__= "suppliers"

    id: Mapped[int]= mapped_column(primary_key= True)
    name: Mapped[str]= mapped_column(String(225), index= True)
    contact_email: Mapped[str]= mapped_column(String(255))

    # We can link this back to your first project's "Verification Status" later!
    is_verified: Mapped[bool]= mapped_column(Boolean, default= False)
    
    # New Verification Fields
    pan_number: Mapped[str | None]= mapped_column(String(10), nullable= True)
    aadhar_number: Mapped[str | None]= mapped_column(String(12), nullable= True)
    pan_image_url: Mapped[str | None]= mapped_column(String(500), nullable= True)
    aadhar_image_url: Mapped[str | None]= mapped_column(String(500), nullable= True) 
    
    verification_status: Mapped[VerificationStatus]= mapped_column(Enum(VerificationStatus), default= VerificationStatus.PENDING)
    verification_comments: Mapped[str | None]= mapped_column(String(500), nullable= True)

    # Relationship to the products they offer
    products: Mapped[list["Product"]]= relationship(back_populates= "supplier", cascade= "all, delete-orphan")

class Product(Base, TimestampMixin):
    __tablename__= "products"

    id: Mapped[int]= mapped_column(primary_key= True)
    supplier_id: Mapped[int]= mapped_column(ForeignKey("suppliers.id"))

    name: Mapped[str]= mapped_column(String(255), index= True)
    category: Mapped[str]= mapped_column(String(100), index= True)

    unit_price: Mapped[float]= mapped_column(Float)
    moq_threshold: Mapped[float]= mapped_column(Float)

    supplier: Mapped["Supplier"]= relationship(back_populates= "products")