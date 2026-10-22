# backend/app/models/property.py
# Property(전세 매물) 테이블 모델로, 주소, 상세 주소 등 부동산 관련 정보 관리
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func
from app.db.session import Base

class Property(Base):
    __tablename__ = "properties"

    property_id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(255), ForeignKey("users.user_id"), nullable=False, index=True)
    address = Column(String(255), nullable=False)
    detail_address = Column(String(255), nullable=True)
    property_value = Column(Float, nullable=True)
    estimated_price = Column(Float, nullable=True)
    risk_summary = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Property id={self.property_id} address={self.address}>"
