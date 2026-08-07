from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.SQLALCHEMY_DATABASE_URI.startswith("sqlite") else {}

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sqlite_type_for(col) -> str:
    """将 SQLAlchemy 列类型映射为 SQLite 建列字符串。"""
    t = col.type
    name = type(t).__name__.upper()
    if name in ("INTEGER", "BIGINT", "SMALLINT", "BOOLEAN"):
        return "INTEGER"
    if name in ("FLOAT", "REAL", "NUMERIC", "DECIMAL"):
        return "REAL"
    if name in ("DATETIME", "DATE", "TIME", "TIMESTAMP"):
        return "DATETIME"
    return "TEXT"


def _default_literal_for(col):
    """为已存在的行生成 ALTER ADD COLUMN 的默认值。"""
    default = col.default
    if default is not None and default.is_scalar:
        v = default.arg
        if isinstance(v, bool):
            return "0" if not v else "1"
        if isinstance(v, (int, float)):
            return str(v)
        if v is None:
            return "NULL"
        s = str(v).replace("'", "''")
        return f"'{s}'"
    # 布尔/整数默认 0，浮点默认 0.0，其他默认 NULL
    tn = type(col.type).__name__.upper()
    if tn == "BOOLEAN":
        return "0"
    if tn in ("INTEGER", "BIGINT", "SMALLINT"):
        return "0"
    if tn in ("FLOAT", "REAL", "NUMERIC", "DECIMAL"):
        return "0"
    return "NULL"


def ensure_columns():
    """SQLite 轻量迁移：对已存在的表补齐 metadata 中新增的列(仅 ADD COLUMN)。"""
    if not settings.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        return
    insp = inspect(engine)
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if not insp.has_table(table_name):
                continue
            existing = {c["name"] for c in insp.get_columns(table_name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                # 跳过主键列（无法 ALTER ADD 已存在表的主键）
                if col.primary_key:
                    continue
                col_type = _sqlite_type_for(col)
                default_val = _default_literal_for(col)
                ddl = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {col_type}'
                if not col.nullable and default_val != "NULL":
                    ddl += f" NOT NULL DEFAULT {default_val}"
                else:
                    ddl += f" DEFAULT {default_val}"
                try:
                    conn.execute(text(ddl))
                except Exception:
                    # 忽略重复/不支持等情况，避免阻断启动
                    pass
