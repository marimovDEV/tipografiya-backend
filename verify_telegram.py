import os
import django
import sys
from unittest.mock import patch

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import Order, Client
from api.signals import send_telegram_notification

def verify_telegram_signal():
    print("--- Verifying Telegram Notification ---")
    
    # 1. Setup Data
    client, _ = Client.objects.get_or_create(
        full_name="Telegram User",
        defaults={'telegram_id': '123456789'}
    )
    # Ensure telegram_id is set
    if not client.telegram_id:
        client.telegram_id = '123456789'
        client.save()
        
    # Ensure unique test data
    Order.objects.filter(order_number="TG-TEST-01").delete()
    
    order = Order.objects.create(
        client=client,
        order_number="TG-TEST-01",
        status='pending'
    )
    
    # 2. Mock requests.post AND settings to avoid token check failure
    with patch('requests.post') as mock_post, \
         patch('django.conf.settings.TELEGRAM_BOT_TOKEN', '123456:ABC-DEF'):
        
        # Simulate status change
        order.status = 'in_production'
        order.save()
        
        if mock_post.called:
            print("SUCCESS: Signal triggered Telegram notification request.")
            args, kwargs = mock_post.call_args
            print(f"URL: {args[0]}")
            print(f"Payload: {kwargs.get('json')}")
        else:
            print("FAILURE: Signal did NOT trigger notification.")
            
            # Debug: Try calling manually
            print("Attempting manual call...")
            send_telegram_notification(order)
            if mock_post.called:
                 print("Manual call worked. Logic is fine, but Signal Pre/Post save interaction might be off.")
            else:
                 print("Manual call also failed. Check logic.")

if __name__ == '__main__':
    verify_telegram_signal()
