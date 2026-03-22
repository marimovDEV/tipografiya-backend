import os, django, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()
from django.test import RequestFactory
from api.views import OrderViewSet
from api.models import Order, Client
from django.contrib.auth import get_user_model
import traceback

try:
    User = get_user_model()
    user = User.objects.first()
    client, _ = Client.objects.get_or_create(full_name="Test Client", phone="123")
    Order.objects.get_or_create(order_number=9999, client=client, total_price=100)
    
    factory = RequestFactory()
    request = factory.get('/api/orders/')
    request.user = user
    view = OrderViewSet.as_view({'get': 'list'})
    response = view(request)
    if hasattr(response, 'render'):
        response.render()
    print(f"Status Output: {response.status_code}")
except Exception as e:
    traceback.print_exc()
