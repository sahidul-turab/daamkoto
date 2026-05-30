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
cur.execute("SELECT COUNT(*) FROM products")
print("Total products:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM prices")
print("Total prices:", cur.fetchone()[0])
cur.execute("""
    SELECT r.name, COUNT(DISTINCT p2.product_id) as products, COUNT(p2.id) as price_rows
    FROM retailers r
    LEFT JOIN prices p2 ON p2.retailer_id = r.id
    GROUP BY r.name
    ORDER BY r.name
""")
rows = cur.fetchall()
print()
print("Retailer".ljust(20), "Products".rjust(10), "Price rows".rjust(12))
print("-" * 45)
for row in rows:
    print(row[0].ljust(20), str(row[1]).rjust(10), str(row[2]).rjust(12))
conn.close()
