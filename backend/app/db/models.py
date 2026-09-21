from sqlalchemy import Column, Integer, String
from app.db.session import Base

class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, unique=True, nullable=False, index=True)
    description = Column(String, nullable=False)
