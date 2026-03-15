# WebSocket Consumers for real-time updates
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from asgiref.sync import sync_to_async


class ProductionConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for production updates
    Sends real-time updates when production steps change status
    """
    async def connect(self):
        self.group_name = 'production_updates'
        
        # Join group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))
    
    async def production_update(self, event):
        """Send production update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'production_update',
            'data': event['data']
        }))


class WarehouseConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for warehouse updates
    Sends real-time updates for material stock changes
    """
    async def connect(self):
        self.group_name = 'warehouse_updates'
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    async def warehouse_update(self, event):
        """Send warehouse update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'warehouse_update',
            'data': event['data']
        }))


class OrderConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for order updates
    Sends real-time updates when orders change status
    """
    async def connect(self):
        self.group_name = 'order_updates'
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    async def order_update(self, event):
        """Send order update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'order_update',
            'data': event['data']
        }))


# Helper function to broadcast updates
async def broadcast_production_update(step_id, status, order_number):
    """Broadcast production step update to all connected clients"""
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        'production_updates',
        {
            'type': 'production_update',
            'data': {
                'step_id': str(step_id),
                'status': status,
                'order_number': order_number,
                'timestamp': str(timezone.now())
            }
        }
    )
