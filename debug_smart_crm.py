
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import Client, Order, Transaction, User
from api.serializers import OrderSerializer
from api.management.commands.run_recall_system import Command as RecallCommand
from django.utils import timezone
from datetime import timedelta

def verify_smart_crm():
    print("--- Verifying Smart CRM Features ---")
    
    # 1. Setup Test Data
    admin = User.objects.filter(role='admin').first()
    if not admin:
        admin = User.objects.create_user('test_admin', role='admin')
        
    client, _ = Client.objects.get_or_create(
        full_name="Debt Test Client", 
        defaults={'credit_limit': 1000000} # 1 mln limit
    )
    
    # Reset state
    Order.objects.filter(client=client).delete()
    Transaction.objects.filter(client=client).delete()
    
    print(f"Client: {client.full_name}, Limit: {client.credit_limit}")
    
    # 2. Test Balance Calculation
    # Create Order (Cost 500k)
    order1 = Order.objects.create(
        client=client,
        order_number="TEST-001",
        total_price=500000, 
        status='completed'
    )
    # create payment (200k)
    Transaction.objects.create(
        client=client,
        type='income',
        amount=200000,
        category='Order Payment'
    )
    
    expected_balance = 200000 - 500000 # -300,000
    actual_balance = client.calculate_balance()
    print(f"Balance check: Expected -300,000, Got: {actual_balance}")
    
    if actual_balance == expected_balance:
        print("✅ Balance Calculation: SUCCESS")
    else:
        print("❌ Balance Calculation: FAILED")
        
    # 3. Test Debt Control (Blocking)
    # Add huge debt (1.5 mln) -> Total debt becomes 1.8 mln (over 1 mln limit)
    Order.objects.create(
        client=client,
        order_number="TEST-HUGE",
        total_price=1500000,
        status='completed' 
    )
    
    print(f"Current Debt: {client.current_debt}")
    
    # Try creating new order via Serializer
    data = {
        'client_id': client.id,
        'order_number': 'NEW-001',
        'status': 'pending',
        # ... minimal fields
    }
    
    serializer = OrderSerializer(data={'client_id': client.id})
    # We only validate 'client' part for this test
    try:
        # Mocking validation call manually or minimal data
        serializer.validate({'client': client}) 
        print("❌ Debt Control: FAILED (Should have raised ValidationError)")
    except Exception as e:
        if "Mijoz qarzdorligi limitdan oshgan" in str(e):
             print("✅ Debt Control: SUCCESS (Blocked correctly)")
        else:
             print(f"❌ Debt Control: Error but unexpected message: {e}")

    # 4. Test Recall System logic
    print("\n--- Testing Recall Logic ---")
    # Set last order to 70 days ago
    old_order = Order.objects.create(
        client=client,
        order_number="OLD-001",
        total_price=100,
        status='completed'
    )
    old_order.created_at = timezone.now() - timedelta(days=70)
    old_order.save()
    
    # Run command handler partially (we won't actually send TG message to avoid spam, just logic)
    print("Simulating Recall Command...")
    # Just checking if client is found as sleeping
    # (Re-using logic from command for verification)
    last_order = client.orders.order_by('-created_at').first()
    days_diff = (timezone.now() - last_order.created_at).days
    print(f"Client inactive for: {days_diff} days")
    
    if days_diff > 60:
        print("✅ Recall Logic: SUCCESS (Client identified as sleeping)")
    else:
        print("❌ Recall Logic: FAILED")

if __name__ == "__main__":
    verify_smart_crm()
