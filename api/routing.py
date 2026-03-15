# WebSocket URL routing
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/production/$', consumers.ProductionConsumer.as_asgi()),
    re_path(r'ws/warehouse/$', consumers.WarehouseConsumer.as_asgi()),
    re_path(r'ws/orders/$', consumers.OrderConsumer.as_asgi()),
]
