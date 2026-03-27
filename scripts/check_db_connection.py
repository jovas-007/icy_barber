from dotenv import load_dotenv
import os
import pymysql


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().strip("\"'")


load_dotenv()

host = clean(os.getenv("DB_HOST"))
port = int(clean(os.getenv("DB_PORT") or "4000"))
user = clean(os.getenv("DB_USERNAME") or os.getenv("DB_USER"))
password = clean(os.getenv("DB_PASSWORD"))
database = clean(os.getenv("DB_DATABASE") or os.getenv("DB_NAME"))

print("host:", host)
print("port:", port)
print("user:", user)
print("database:", database)

conn = pymysql.connect(
    host=host,
    port=port,
    user=user,
    password=password,
    database=database,
    ssl={"ssl_verify_cert": True, "ssl_verify_identity": True},
)

with conn.cursor() as cur:
    cur.execute("SELECT 1")
    result = cur.fetchone()
    print("db_ok:", result[0])

conn.close()
