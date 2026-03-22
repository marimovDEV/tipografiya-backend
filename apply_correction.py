import os
import sys
import django

sys.path.append('/Users/ogabek/Documents/projects/erp+crm kitob/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from decimal import Decimal
from django.db.models import Sum
from api.models import Order, Transaction

def fix_overpayments():
    orders = Order.objects.all()
    fixed_count = 0
    total_corrected = Decimal('0')
    
    for order in orders:
        if not order.total_price:
            continue
            
        total_income = Transaction.objects.filter(
            order_link=order, 
            type='income'
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        total_expense = Transaction.objects.filter(
            order_link=order, 
            type='expense'
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        net_paid = total_income - total_expense
        
        if net_paid > order.total_price:
            overpaid = net_paid - order.total_price
            
            # Create a correction expense transaction
            Transaction.objects.create(
                type='expense',
                amount=overpaid,
                category='Correction',
                description=f"Auto-correction for duplicate/overpaid transactions on Order {order.order_number}",
                order_link=order,
                client=order.client
            )
            
            fixed_count += 1
            total_corrected += overpaid
            print(f"Corrected Order #{order.order_number}: Deducted {overpaid} sum.")
            
            # Update order payment status perfectly
            order.advance_payment = order.total_price
            order.payment_status = 'fully_paid'
            order.save(update_fields=['advance_payment', 'payment_status'])
            
    print(f"Finished! Corrected {fixed_count} orders. Total correction amount: {total_corrected}")

if __name__ == '__main__':
    fix_overpayments()
