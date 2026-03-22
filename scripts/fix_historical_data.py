import os
import sys
import django
from decimal import Decimal

# Setup Django environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import Transaction, Order, Client
from django.utils import timezone

def fix_historical_discrepancies():
    print("Tizimli ma'lumotlarni tuzatish boshlandi...")

    # 1. Akbar (#002) - Missing Advance Payment
    try:
        # Searching for Order #002 or containing 002
        akbar_order = Order.objects.filter(order_number__contains='002').first()
        if akbar_order:
            # Check if transaction already exists to avoid double-fixing
            exists = Transaction.objects.filter(
                order_link=akbar_order, 
                amount=Decimal('1400000'),
                category='Order Advance'
            ).exists()
            
            if not exists:
                print(f"Akbar uchun (#002) 1,400,000 avans yaratilmoqda...")
                Transaction.objects.create(
                    type='income',
                    amount=Decimal('1400000'),
                    category='Order Advance',
                    client=akbar_order.client,
                    order_link=akbar_order,
                    payment_method='cash',
                    date=akbar_order.created_at.date(),
                    description=f"Tizimli tuzatish: Buyurtma {akbar_order.order_number} uchun olingan avans"
                )
            else:
                print("Akbar uchun avans allaqachon mavjud.")
        else:
            print("Akbar orderi (#002) topilmadi.")
    except Exception as e:
        print(f"Akbar fixida xatolik: {e}")

    # 2. General check for any orders with advance_payment > 0 but NO transactions
    print("Barcha buyurtmalarni tekshirilmoqda (avans bor lekin tranzaksiya yo'q)...")
    orders_with_advances = Order.objects.filter(advance_payment__gt=0)
    for order in orders_with_advances:
        if not Transaction.objects.filter(order_link=order).exists():
            print(f"Buyurtma {order.order_number} uchun yetishmayotgan {order.advance_payment} avansi yaratilmoqda...")
            Transaction.objects.create(
                type='income',
                amount=order.advance_payment,
                category='Order Advance',
                client=order.client,
                order_link=order,
                payment_method=order.initial_payment_method or 'cash',
                date=order.created_at.date(),
                description=f"Tizimli tuzatish: Buyurtma {order.order_number} uchun avans tiklandi"
            )

    print("Tugallandi.")

if __name__ == "__main__":
    fix_historical_discrepancies()
