import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import User, Client, ProductionTemplate, Order
from api.serializers import OrderSerializer

# Find existing client and template to bypass local DB constraint creation failures
user = User.objects.filter(role='admin').first() or User.objects.first()
client = Client.objects.first()
template = ProductionTemplate.objects.first()

if not client or not template:
    print("Cannot run test: No client or template found in local DB.")
    sys.exit(1)

data = {
    "client_id": client.id,
    "product_template": template.id,
    "box_type": template.name,
    "paper_width": 10,
    "paper_height": 20,
    "quantity": 100,
    "print_colors": "Internal: 1+1, Cover: 4+0",
    "lacquer_type": "none",
    "total_price": 20000,
    "advance_payment": 5000,
    "initial_payment_method": "cash",
    "book_name": "Test Book",
    "page_count": 50,
    "cover_type": "soft",
}

serializer = OrderSerializer(data=data)
if not serializer.is_valid():
    print("Errors:", serializer.errors)
else:
    try:
        from rest_framework.request import Request
        from django.test import RequestFactory
        req = Request(RequestFactory().post('/'))
        req.user = user
        serializer.context['request'] = req
        order = serializer.save(created_by=user)
        print("Success! Order created:", order.id)
    except Exception as e:
        import traceback
        traceback.print_exc()
