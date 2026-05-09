from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, func
from datetime import datetime

class Base(DeclarativeBase):
    """
    The shared parent for all database models.
    """
    pass

class TimestampMixin:
    """
    A mixin that automatically adds timestamp columns to any table.
    """
    created_at: Mapped[datetime]= mapped_column(
        DateTime(timezone= True),
        server_default= func.now(),
        sort_order= -2  # Keeps it at the end of the table
    )
    updated_at: Mapped[datetime]= mapped_column(
        DateTime(timezone= True),
        server_default= func.now(),
        onupdate= func.now(),
        sort_order= -1   # Keeps it at the very end
    )