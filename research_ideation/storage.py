"""兼容原有业务导入路径；SQL 与数据库差异集中在 store 包。"""
from .store.interface import Store
from .store.local import open_database, public_record
__all__ = ["Store", "open_database", "public_record"]
