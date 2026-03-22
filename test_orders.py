from django.test import RequestFactory
from api.views import OrderViewSet
from django.contrib.auth import get_user_model
import traceback

try:
    User = get_user_model()
    user = User.objects.first()
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
