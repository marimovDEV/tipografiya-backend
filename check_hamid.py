import os
import django
import sys

# Setup Django environment
sys.path.append(os.path.abspath(os.path.join(os.getcwd())))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import Transaction, Client, Order

def check():
    client = Client.objects.filter(full_name__icontains='Hamid').first()
    if not client:
        print("Client Hamid not found.")
        return

    print(f"Client found: {client.full_name} (ID: {client.id})")
    
    orders = Order.objects.filter(client=client)
    print("\nOrders:")
    for o in orders:
        print(f"  Order #{o.order_number}: Total={o.total_price}, Advance={o.advance_payment}, Status={o.payment_status}, CalcStatus={o.calculated_payment_status}")
    
    transactions = Transaction.objects.filter(client=client)
    print("\nTransactions:")
    for t in transactions:
        print(f"  ID: {t.id}, Amount: {t.amount}, Category: {t.category}, Type: {t.type}, Order: {t.order_link}")

if __name__ == "__main__":
    check()
