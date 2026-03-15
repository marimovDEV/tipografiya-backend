from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from django.db.models import Sum
import requests
import logging
from .models import Order, MaterialBatch, Material
from .services import ProductionAssignmentService

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Order)
def order_pre_save(sender, instance, **kwargs):
    """
    Store the old status on the instance to check for changes in post_save.
    """
    if instance.pk:
        try:
            old_order = Order.objects.get(pk=instance.pk)
            instance._old_status = old_order.status
        except Order.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

@receiver(post_save, sender=Order)
def order_post_save(sender, instance, created, **kwargs):
    """
    1. Trigger auto-assignment if status -> 'in_production'.
    2. Send Telegram notification if status changed.
    """
    # 1. Auto-assignment (DEPRECATED: Now handled explicitly in views.approve to avoid duplication)
    # if instance.status == 'in_production':
    #     ProductionAssignmentService.auto_assign_production_steps(instance)
    
    # 2. Telegram Notification
    old_status = getattr(instance, '_old_status', None)
    if old_status and old_status != instance.status:
        send_telegram_notification(instance)

def send_telegram_notification(order):
    """
    Sends a message to the client's Telegram ID if available.
    Using synchronous requests for simplicity in signal.
    """
    if not order.client or not order.client.telegram_id:
        return
        
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or token == 'YOUR_BOT_TOKEN_HERE':
        return

    # Status translation
    status_labels = dict(Order.STATUS_CHOICES)
    status_text = status_labels.get(order.status, order.status)
    
    from django.utils import timezone
    current_time = timezone.now().strftime('%d.%m.%Y %H:%M')
    
    message = (
        f"📦 <b>Buyurtma holati o'zgardi!</b>\n\n"
        f"🆔 Buyurtma: #{order.order_number}\n"
        f"📊 Yangi holat: <b>{status_text}</b>\n"
        f"📅 Sana: {current_time}\n\n"
        f"<i>Batafsil ma'lumot uchun menejerga murojaat qiling.</i>"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": order.client.telegram_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code != 200:
            logger.error(f"Telegram notification failed: {response.text}")
    except Exception as e:
        logger.error(f"Telegram notification error: {e}")


# ============================================================================
# Material Stock Auto-Update Signal
# ============================================================================

def recalculate_material_stock(material):
    """Recalculate and update the current_stock for a Material based on its active batches."""
    if not material:
        return
    
    total = material.batches.filter(is_active=True).aggregate(
        total=Sum('current_quantity')
    )['total'] or 0
    
    material.current_stock = total
    material.save(update_fields=['current_stock'])
    logger.info(f"Updated stock for Material '{material.name}': {total}")


@receiver(post_save, sender=MaterialBatch)
def update_material_stock_on_batch_save(sender, instance, **kwargs):
    """Update Material.current_stock when a batch is saved."""
    recalculate_material_stock(instance.material)


@receiver(post_delete, sender=MaterialBatch)
def update_material_stock_on_batch_delete(sender, instance, **kwargs):
    """Update Material.current_stock when a batch is deleted."""
    recalculate_material_stock(instance.material)
