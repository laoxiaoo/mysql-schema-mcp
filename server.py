from __future__ import annotations

import configparser
import re
from pathlib import Path
from typing import Any, Dict, List

import pymysql
from mcp.server.fastmcp import FastMCP


CONFIG_FILE = Path(__file__).with_name("mysql.ini")
TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

mcp = FastMCP("mysql-schema-mcp")


def load_mysql_config() -> Dict[str, Any]:
    parser = configparser.ConfigParser()
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            "Missing mysql.ini. Copy mysql.ini.example to mysql.ini and fill in MySQL settings."
        )

    parser.read(CONFIG_FILE, encoding="utf-8")
    if "mysql" not in parser:
        raise ValueError("mysql.ini must contain a [mysql] section.")

    section = parser["mysql"]
    required_keys = ("host", "user", "password", "database")
    missing_keys = [key for key in required_keys if not section.get(key)]
    if missing_keys:
        raise ValueError("mysql.ini missing required keys: " + ", ".join(missing_keys))

    return {
        "host": section.get("host"),
        "port": section.getint("port", fallback=3306),
        "user": section.get("user"),
        "password": section.get("password"),
        "database": section.get("database"),
        "charset": section.get("charset", fallback="utf8mb4"),
        "connect_timeout": section.getint("connect_timeout", fallback=10),
    }


def connect_mysql() -> pymysql.connections.Connection:
    config = load_mysql_config()
    return pymysql.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        database=config["database"],
        charset=config["charset"],
        connect_timeout=config["connect_timeout"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def validate_table_name(table_name: str) -> str:
    table_name = (table_name or "").strip()
    if not TABLE_NAME_PATTERN.match(table_name):
        raise ValueError("table_name must contain only letters, numbers, and underscores.")
    return table_name


def query_one(cursor: pymysql.cursors.DictCursor, sql: str, params: tuple) -> Dict[str, Any]:
    cursor.execute(sql, params)
    return cursor.fetchone()


def query_all(cursor: pymysql.cursors.DictCursor, sql: str, params: tuple) -> List[Dict[str, Any]]:
    cursor.execute(sql, params)
    return list(cursor.fetchall())


@mcp.tool()
def get_table_schema(table_name: str) -> Dict[str, Any]:
    """Return MySQL table metadata for a table in the configured database."""
    table_name = validate_table_name(table_name)
    config = load_mysql_config()
    database = config["database"]

    try:
        connection = connect_mysql()
    except pymysql.MySQLError as exc:
        raise RuntimeError(f"Failed to connect to MySQL: {exc}") from exc

    try:
        with connection:
            with connection.cursor() as cursor:
                table = query_one(
                    cursor,
                    """
                    SELECT TABLE_NAME, TABLE_COMMENT, ENGINE, TABLE_COLLATION
                    FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    """,
                    (database, table_name),
                )
                if not table:
                    raise ValueError(f"Table not found: {database}.{table_name}")

                columns = query_all(
                    cursor,
                    """
                    SELECT
                        COLUMN_NAME,
                        ORDINAL_POSITION,
                        COLUMN_DEFAULT,
                        IS_NULLABLE,
                        DATA_TYPE,
                        COLUMN_TYPE,
                        CHARACTER_MAXIMUM_LENGTH,
                        NUMERIC_PRECISION,
                        NUMERIC_SCALE,
                        DATETIME_PRECISION,
                        COLUMN_KEY,
                        EXTRA,
                        COLUMN_COMMENT,
                        COLLATION_NAME
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY ORDINAL_POSITION
                    """,
                    (database, table_name),
                )

                index_rows = query_all(
                    cursor,
                    """
                    SELECT
                        INDEX_NAME,
                        NON_UNIQUE,
                        SEQ_IN_INDEX,
                        COLUMN_NAME,
                        COLLATION,
                        CARDINALITY,
                        SUB_PART,
                        INDEX_TYPE,
                        COMMENT,
                        INDEX_COMMENT
                    FROM information_schema.STATISTICS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY INDEX_NAME, SEQ_IN_INDEX
                    """,
                    (database, table_name),
                )
    except pymysql.MySQLError as exc:
        raise RuntimeError(f"Failed to read table schema: {exc}") from exc

    indexes = build_indexes(index_rows)
    primary_keys = [
        row["COLUMN_NAME"]
        for row in index_rows
        if row["INDEX_NAME"] == "PRIMARY"
    ]

    return {
        "database": database,
        "table": {
            "name": table["TABLE_NAME"],
            "comment": table["TABLE_COMMENT"],
            "engine": table["ENGINE"],
            "collation": table["TABLE_COLLATION"],
        },
        "columns": columns,
        "primary_keys": primary_keys,
        "indexes": indexes,
    }


def build_indexes(index_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    indexes_by_name: Dict[str, Dict[str, Any]] = {}
    for row in index_rows:
        index_name = row["INDEX_NAME"]
        if index_name not in indexes_by_name:
            indexes_by_name[index_name] = {
                "name": index_name,
                "unique": row["NON_UNIQUE"] == 0,
                "type": row["INDEX_TYPE"],
                "comment": row["INDEX_COMMENT"] or row["COMMENT"],
                "columns": [],
            }

        indexes_by_name[index_name]["columns"].append(
            {
                "name": row["COLUMN_NAME"],
                "sequence": row["SEQ_IN_INDEX"],
                "collation": row["COLLATION"],
                "cardinality": row["CARDINALITY"],
                "sub_part": row["SUB_PART"],
            }
        )

    return list(indexes_by_name.values())


if __name__ == "__main__":
    mcp.run(transport="stdio")
