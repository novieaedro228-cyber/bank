from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100))
    balance = Column(Integer, default=0)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    auto_clicker_active = Column(Boolean, default=False)
    
    transactions = relationship("Transaction", foreign_keys="[Transaction.from_user_id]")
    received_transactions = relationship("Transaction", foreign_keys="[Transaction.to_user_id]")

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_user_id = Column(BigInteger, ForeignKey('users.user_id'))
    to_user_id = Column(BigInteger, ForeignKey('users.user_id'))
    amount = Column(Integer)
    type = Column(Text)  # 'click', 'transfer', 'bonus'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    description = Column(String(200), nullable=True)