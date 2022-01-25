import os
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

from sqlmodel import (
    Column,
    DateTime,
    Field,
    Relationship,
    Session,
    SQLModel,
    create_engine,
    select,
)

class Reports(SQLModel, table=True):
    id: int = Field(primary_key=True)
    chain_id: int
    # Transaction fields
    block: int
    txn_hash: str
    txn_to: str
    txn_from: str
    txn_gas_used: int
    txn_gas_price: int
    txn_fee_eth: float
    txn_fee_usd: float
    # Event fields
    vault_address: str
    strategy_address: str
    gain: int
    loss: int
    debt_paid: int
    total_gain: int
    total_loss: int
    total_debt: int
    debt_added: int
    debt_ratio: int
    # Looked-up fields
    want_token: str
    vault_api: str
    vault_name: str
    vault_symbol: str
    vault_decimals: int
    strategy_name: str
    strategy_api: str
    previous_report_id: int
    # Date fields
    date: datetime
    date_string: str
    timestamp: str
    updated_timestamp: datetime
    


user = os.environ.get('POSTGRES_USER', 'POSTGRES_PASS')
host = os.environ.get('POSTGRES_HOST')

dsn = f'postgresql://{user}@{host}:5432/harvests'
engine = create_engine(dsn, echo=False)

# SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)
