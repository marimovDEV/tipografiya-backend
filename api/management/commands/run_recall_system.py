from django.core.management.base import BaseCommand
from django.utils import timezone
from api.models import Client, User
from api.automation import TelegramSmartTriggers
import asyncio

class Command(BaseCommand):
    help = 'Run Recall System: Identify inactive clients and notify managers'

    def handle(self, *args, **kwargs):
        self.stdout.write("Running Recall System...")
        
        # 1. Identify "Sleeping" Clients (No orders in last 60 days)
        today = timezone.now()
        threshold_date = today - timezone.timedelta(days=60)
        
        # Clients who have orders but none after threshold_date
        sleeping_clients = []
        
        all_clients = Client.objects.filter(is_active=True)
        
        for client in all_clients:
            last_order = client.orders.order_by('-created_at').first()
            
            if last_order:
                if last_order.created_at < threshold_date:
                    sleeping_clients.append({
                        'client': client,
                        'last_date': last_order.created_at,
                        'days_inactive': (today - last_order.created_at).days
                    })
            else:
                # Client has NO orders ever? Maybe created long ago
                if client.created_at < threshold_date:
                    sleeping_clients.append({
                        'client': client,
                        'last_date': client.created_at,
                        'days_inactive': (today - client.created_at).days
                    })
        
        count = len(sleeping_clients)
        self.stdout.write(f"Found {count} inactive clients.")
        
        if count == 0:
            return

        # 2. Notify Admins via Telegram
        # We need an async wrapper because TelegramSmartTriggers is async
        async def send_notifications():
            admins = User.objects.filter(role__in=['admin', 'project_manager'], telegram_id__isnull=False)
            
            if not admins.exists():
                print("No admins with Telegram ID found.")
                return

            message = f"📢 <b>RECALL SYSTEM ALERT</b>\n\n"
            message += f"Uyg'otish kerak bo'lgan {count} ta mijoz topildi:\n\n"
            
            for item in sleeping_clients[:10]: # Limit to top 10 to avoid spamming
                client = item['client']
                days = item['days_inactive']
                message += f"💤 <b>{client.full_name}</b>\n"
                message += f"   So'nggi faollik: {days} kun oldin\n"
                message += f"   Tel: {client.phone}\n\n"
            
            if count > 10:
                message += f"<i>...va yana {count - 10} ta mijoz.</i>"

            for admin in admins:
                await TelegramSmartTriggers.send_telegram_message(admin.telegram_id, message)
                
        # Run async loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_notifications())
        loop.close()

        self.stdout.write(self.style.SUCCESS('Recall System completed successfully.'))
