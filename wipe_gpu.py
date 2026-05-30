import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", 5432),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM prices WHERE product_id IN (SELECT id FROM products WHERE category = 'GPU')")
price_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM products WHERE category = 'GPU'")
product_count = cur.fetchone()[0]
print(f"GPU price rows : {price_count}")
print(f"GPU products   : {product_count}")

cur.execute("DELETE FROM prices WHERE product_id IN (SELECT id FROM products WHERE category = 'GPU')")
cur.execute("DELETE FROM products WHERE category = 'GPU'")
conn.commit()
print("Deleted. GPU table is clean.")
conn.close()
