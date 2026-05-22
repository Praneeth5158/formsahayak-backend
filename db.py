import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "mysql+pymysql://root:TpNHXpAmCzHPlBSZCdKhpDzHukyUSfYK@kodama.proxy.rlwy.net:57775/railway"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)