import os
import ssl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

if os.getenv("TESTING") == "True":
    DATABASE_URL = "sqlite:///./test.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Read database URL from environment
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # If DATABASE_URL is not set but individual MYSQL environment variables exist, construct it
    if not DATABASE_URL:
        mysql_user = os.getenv("MYSQLUSER") or os.getenv("MYSQL_USER")
        mysql_password = os.getenv("MYSQLPASSWORD") or os.getenv("MYSQL_PASSWORD")
        mysql_host = os.getenv("MYSQLHOST") or os.getenv("MYSQL_HOST")
        mysql_port = os.getenv("MYSQLPORT") or os.getenv("MYSQL_PORT") or "3306"
        mysql_db = os.getenv("MYSQLDATABASE") or os.getenv("MYSQL_DATABASE") or "defaultdb"
        
        if mysql_host and mysql_user:
            DATABASE_URL = f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_db}"
            
    # Fallback to the default Railway URL if still not set
    if not DATABASE_URL:
        DATABASE_URL = "mysql+pymysql://root:TpNHXpAmCzHPlBSZCdKhpDzHukyUSfYK@kodama.proxy.rlwy.net:57775/railway"
    
    # Normalize mysql:// protocol to mysql+pymysql:// if needed
    if DATABASE_URL.startswith("mysql://"):
        DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)
        
    # Sanitize query parameters that PyMySQL doesn't support (like ssl-mode or ssl_mode)
    if "?" in DATABASE_URL:
        from urllib.parse import parse_qs, urlencode
        base_url, query_str = DATABASE_URL.split("?", 1)
        params = parse_qs(query_str)
        params.pop("ssl-mode", None)
        params.pop("ssl_mode", None)
        if params:
            DATABASE_URL = f"{base_url}?{urlencode(params, doseq=True)}"
        else:
            DATABASE_URL = base_url
        
    connect_args = {}
    
    # Configure SSL for remote MySQL databases (e.g. Aiven)
    if "mysql" in DATABASE_URL:
        is_local = "localhost" in DATABASE_URL or "127.0.0.1" in DATABASE_URL
        if not is_local:
            # Create an SSL context that requires SSL but allows connecting
            # without verifying certificates against a local CA certificate file.
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ssl_context
    print("DATABASE_URL =", DATABASE_URL)
    engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)