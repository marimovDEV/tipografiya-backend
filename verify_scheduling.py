import os
import django
import sys
from datetime import timedelta
from django.utils import timezone

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import Order, ProductionStep, Client, User
from api.views import ProductionStepViewSet
from rest_framework.test import APIRequestFactory, force_authenticate

def verify_scheduling():
    print("--- Verifying Scheduling Module ---")
    
    # 1. Setup Data
    user, _ = User.objects.get_or_create(username='test_admin_sched', role='admin')
    client, _ = Client.objects.get_or_create(full_name="Sched Client")
    
    Order.objects.filter(client=client).delete()
    
    # Order 1: Normal (Deadline T+5)
    o1 = Order.objects.create(
        client=client, order_number="ORD-NORM", status='in_production', priority='normal',
        deadline=timezone.now() + timedelta(days=5)
    )
    # Order 2: Urgent (Deadline T+10) - Should be First due to Priority
    o2 = Order.objects.create(
        client=client, order_number="ORD-URG", status='in_production', priority='urgent',
        deadline=timezone.now() + timedelta(days=10)
    )
    # Order 3: High (Deadline T+3) - Should be Second
    o3 = Order.objects.create(
        client=client, order_number="ORD-HIGH", status='in_production', priority='high',
        deadline=timezone.now() + timedelta(days=3)
    )
    
    p1 = ProductionStep.objects.create(order=o1, step='printing', status='pending')
    p2 = ProductionStep.objects.create(order=o2, step='printing', status='pending')
    p3 = ProductionStep.objects.create(order=o3, step='printing', status='pending')
    
    # 2. Test ViewSet Sorting
    factory = APIRequestFactory()
    request = factory.get('/api/production-steps/')
    request.user = user # Manually set for direct ViewSet usage
    force_authenticate(request, user=user)
    
    view = ProductionStepViewSet()
    view.request = request
    view.format_kwarg = None
    
    queryset = view.get_queryset()
    
    # 3. Validation
    results = list(queryset)
    print(f"Results count: {len(results)}")
    
    expected_order = ['ORD-URG', 'ORD-HIGH', 'ORD-NORM']
    actual_order = [s.order.order_number for s in results if s.order.client == client]
    
    print(f"Expected: {expected_order}")
    print(f"Actual:   {actual_order}")
    
    if actual_order == expected_order:
        print("SUCCESS: Priority Sorting works!")
    else:
        print("FAILURE: Sorting incorrect.")

if __name__ == '__main__':
    verify_scheduling()
