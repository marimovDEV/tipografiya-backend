import os
import sys
import django

# Robust path discovery
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from api.models import Order, Transaction

def fix_duplicates_and_overpayments():
    print("--- Starting Transaction Correction Script ---")
    
    # 1. Link orphaned transactions first if possible
    # Handover transactions were sent with 'category': 'sales' and 'notes' containing order number
    orphaned = Transaction.objects.filter(order_link__isnull=True, category='sales')
    linked_count = 0
    for t in orphaned:
        if t.notes and "Buyurtma #" in t.notes:
            order_num = t.notes.split('#')[1].split(' ')[0]
            order = Order.objects.filter(order_number=order_num).first()
            if order:
                t.order_link = order
                t.save(update_fields=['order_link'])
                linked_count += 1
    if linked_count:
        print(f"Linked {linked_count} orphaned transactions to their orders based on notes.")

    # 2. Find and DELETE true duplicates (same amount, same client/order, same minute)
    # This is a bit aggressive but safer for visual clarity as requested
    all_transactions = Transaction.objects.filter(type='income').order_by('created_at')
    deleted_duplicates = 0
    seen = {} # key: (client_id, order_id, amount, minute)
    
    for t in all_transactions:
        # Round to nearest minute for grouping duplicates
        minute = t.created_at.replace(second=0, microsecond=0)
        key = (t.client_id, t.order_link_id, t.amount, minute)
        
        if key in seen:
            # Check if it was created very close to the previous one (within 30 seconds)
            prev_time = seen[key]
            if t.created_at - prev_time < timedelta(seconds=30):
                # This is almost certainly a duplicate click
                print(f"Deleting duplicate transaction: ID {t.id}, Amount {t.amount}, Order {t.order_link}")
                t.delete()
                deleted_duplicates += 1
                continue
        
        seen[key] = t.created_at

    # 3. Correct any remaining overpayments via Correction Expense
    orders = Order.objects.all()
    overpayment_corrections = 0
    for order in orders:
        if not order.total_price:
            continue
            
        total_income = Transaction.objects.filter(
            order_link=order, 
            type='income'
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        total_expense = Transaction.objects.filter(
            order_link=order, 
            type='expense',
            category='Correction'
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        net_paid = total_income - total_expense
        
        if net_paid > order.total_price + Decimal('100'):
            overpaid = net_paid - order.total_price
            
            Transaction.objects.create(
                type='expense',
                amount=overpaid,
                category='Correction',
                description=f"Auto-correction for overpayment on Order {order.order_number}",
                order_link=order,
                client=order.client,
                date=timezone.now().date()
            )
            
            # Sync order
            order.advance_payment = order.total_price
            order.payment_status = 'fully_paid'
            order.save(update_fields=['advance_payment', 'payment_status'])
            
            overpayment_corrections += 1
            print(f"Corrected net overpayment on Order #{order.order_number}: Deducted {overpaid} sum.")

    print(f"--- Finished ---")
    print(f"Deleted duplicates: {deleted_duplicates}")
    print(f"New corrections created: {overpayment_corrections}")

if __name__ == '__main__':
    fix_duplicates_and_overpayments()
