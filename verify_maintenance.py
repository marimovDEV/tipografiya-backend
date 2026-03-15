import os
import sys
import django
from decimal import Decimal
from datetime import timedelta

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import MachineSettings, ProductionStep, Order, Client, User
from django.utils import timezone

def verify_maintenance():
    print("🚀 Verifying Machine Maintenance Logic...")
    
    # 1. Setup Data
    # Ensure we have a Printer Machine
    printer, _ = MachineSettings.objects.get_or_create(
        machine_name="Heidelberg XL",
        machine_type="printer",
        defaults={
            'hourly_rate': 50,
            'maintenance_interval_hours': 100,
            'current_operating_hours': 0
        }
    )
    # Reset hours for clean test
    printer.current_operating_hours = 0
    printer.save()
    
    print(f"📠 Machine: {printer.machine_name}, Start Hours: {printer.current_operating_hours}")
    
    # Create Order & Step
    client, _ = Client.objects.get_or_create(full_name="Maint Test Client")
    import random
    suffix = random.randint(1000, 9999)
    order = Order.objects.create(
        client=client, 
        order_number=f"MAINT-{suffix}",
        status='in_production'
    )
    
    step = ProductionStep.objects.create(
        order=order,
        step='printing', # Should map to 'printer'
        status='pending'
    )
    
    # 2. Simulate Production
    print("🔄 Starting Step (In Progress)...")
    # Simulate API call logic by manually setting times and calling save logic? 
    # Or rely on view logic? We can rely on viewset action simulation again or just manual save if logic is in view.
    # Logic IS in view 'update_status'. So we must use viewset simulation.
    
    from rest_framework.test import APIRequestFactory
    from api.views import ProductionStepViewSet
    
    user = User.objects.filter(is_superuser=True).first()
    factory = APIRequestFactory()
    view = ProductionStepViewSet.as_view({'post': 'update_status'})
    
    # Start
    request = factory.post(f'/api/steps/{step.id}/update_status/', {'status': 'in_progress'})
    request.user = user
    view(request, pk=step.id)
    
    # Refresh step to get started_at
    step.refresh_from_db()
    
    # Fast forward time: pretend it started 2.5 hours ago
    step.started_at = timezone.now() - timedelta(hours=2, minutes=30)
    step.save()
    
    print("t⌛ Fast Forward 2.5 hours...")
    
    # Complete
    print("✅ Completing Step...")
    request = factory.post(f'/api/steps/{step.id}/update_status/', {'status': 'completed'})
    request.user = user
    view(request, pk=step.id)
    
    # 3. Verify Machine Hours
    printer.refresh_from_db()
    print(f"📠 Machine Hours After: {printer.current_operating_hours}")
    
    # Expected: 2.5 hours
    if 2.4 <= printer.current_operating_hours <= 2.6:
        print("🎉 SUCCESS: Machine hours tracked correctly!")
    else:
        print(f"❌ FAILURE: Expected approx 2.5 hours, got {printer.current_operating_hours}")

if __name__ == "__main__":
    verify_maintenance()
