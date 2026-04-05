from datetime import datetime
from sqlalchemy import String, DateTime, Text, JSON, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    """ Standard base for all our database models """
    pass

class Supplier(Base):
    """
    Representation of a Verified Supplier in our system.
    This schema is designed to handle high-concurrency audits at the 10k scale.
    """
    __tablename__= "suppliers"

    id: Mapped[int]= mapped_column(primary_key= True)

    # indexed for sub-millisecond searches
    name: Mapped[str]= mapped_column(String(255), index= True)

    # The unique identifier for the supplier
    entity_id: Mapped[str]= mapped_column(String(50), unique= True, index= True)

    category: Mapped[str]= mapped_column(String(100), nullable= True)

    # AI-generated risk score (e.g. 0.95 = very safe)
    risk_score: Mapped[float]= mapped_column(Float, default= 0.0)

    # Store the rich AI findings
    detailed_report: Mapped[str]= mapped_column(JSON, nullable= True)

    summary: Mapped[str]= mapped_column(Text, nullable= True)

    # Time tracking for stale-data checks
    created_at: Mapped[datetime]= mapped_column(DateTime, default= datetime.utcnow)
    updated_at: Mapped[datetime]= mapped_column(DateTime, default= datetime.utcnow, onupdate= datetime.utcnow)