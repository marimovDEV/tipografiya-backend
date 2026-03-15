"""
Smart Automation System
Telegram bot smart triggers, auto-alerts, and workflow automation.
"""

from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class TelegramSmartTriggers:
    """
    Smart triggers for Telegram bot notifications.
    Automatically sends relevant alerts to users.
    """
    
    @staticmethod
    async def send_telegram_message(telegram_id, message):
        """Send message via Telegram bot (placeholder)"""
        # This would integrate with actual Telegram bot
        # For now, we'll log it
        logger.info(f"[TELEGRAM] To {telegram_id}: {message}")
        print(f"📱 Telegram to {telegram_id}: {message}")
        return True
    
    @staticmethod
    async def notify_order_status_change(order, old_status, new_status, user):
        """Notify client when order status changes"""
        from api.models import Client
        
        if not order.client.telegram_id:
            return False
        
        status_labels = {
            'pending': 'Kutilmoqda',
            'approved': 'Tasdiqlandi',
            'in_production': 'Ishlab chiqarishda',
            'ready': 'Tayyor',
            'completed': 'Yakunlandi',
            'delivered': 'Yetkazildi'
        }
        
        message = f"""
🔔 Buyurtma holati o'zgardi!

📦 Buyurtma: #{order.order_number}
📋 Mahsulot: {order.box_type}
📊 Eski holat: {status_labels.get(old_status, old_status)}
✅ Yangi holat: {status_labels.get(new_status, new_status)}

{f"📅 Tayyor bo'lish: {order.deadline.strftime('%d.%m.%Y')}" if order.deadline else ""}
        """.strip()
        
        await TelegramSmartTriggers.send_telegram_message(
            order.client.telegram_id,
            message
        )
        
        return True
    
    @staticmethod
    async def notify_deadline_approaching(order, days_left):
        """Alert when deadline is approaching"""
        if not order.client.telegram_id:
            return False
        
        urgency = "🔴 JUDA TEZKOR" if days_left <= 1 else "⚠️ TEZKOR" if days_left <= 3 else "📅"
        
        message = f"""
{urgency} Deadline yaqinlashmoqda!

📦 Buyurtma: #{order.order_number}
📋 Mahsulot: {order.box_type}
📅 Muddati: {order.deadline.strftime('%d.%m.%Y')}
⏰ Qoldi: {days_left} kun
        """.strip()
        
        await TelegramSmartTriggers.send_telegram_message(
            order.client.telegram_id,
            message
        )
        
        return True
    
    @staticmethod
    async def notify_bottleneck_alert(bottleneck_data):
        """Alert admins about production bottlenecks"""
        from api.models import User
        
        admins = User.objects.filter(role='admin', telegram_id__isnull=False)
        
        severity_emoji = "🔴" if bottleneck_data['severity'] > 0.8 else "⚠️"
        
        message = f"""
{severity_emoji} BOTTLENECK ANIQLANDI!

🏭 Bosqich: {bottleneck_data['stage']}
📊 Navbat: {bottleneck_data['queue_length']} ta buyurtma
⏱️ Kutish: {bottleneck_data['avg_wait_time']} soat
👷 Ishchilar: {bottleneck_data['workers_assigned']} kishi

💡 Tavsiya: {bottleneck_data['recommendation']}
        """.strip()
        
        for admin in admins:
            await TelegramSmartTriggers.send_telegram_message(
                admin.telegram_id,
                message
            )
        
        return True
    
    @staticmethod
    async def notify_low_stock_alert(material, current_stock, threshold):
        """Alert when material stock is low"""
        from api.models import User
        
        warehouse_staff = User.objects.filter(
            role='warehouse',
            telegram_id__isnull=False
        )
        
        message = f"""
⚠️ KAM QOLDI - Material tugamoqda!

📦 Material: {material.name}
📊 Hozirgi zaxira: {current_stock} {material.unit}
⚡ Minimal chegara: {threshold} {material.unit}

🔄 Tezda buyurtma bering!
        """.strip()
        
        for staff in warehouse_staff:
            await TelegramSmartTriggers.send_telegram_message(
                staff.telegram_id,
                message
            )
        
        return True
    
    @staticmethod
    async def notify_machine_downtime(machine, reason, estimated_hours):
        """Alert when machine goes down"""
        from api.models import User
        
        admins = User.objects.filter(
            role__in=['admin', 'project_manager'],
            telegram_id__isnull=False
        )
        
        reason_labels = {
            'maintenance': 'Texnik xizmat',
            'breakdown': 'Buzilish',
            'repair': "Ta'mirlash"
        }
        
        message = f"""
🔴 MASHINA TO'XTADI!

🏭 Mashina: {machine.machine_name}
⚠️ Sabab: {reason_labels.get(reason, reason)}
⏱️ Taxminiy vaqt: {estimated_hours} soat

📋 Ishlab chiqarish sekinlashishi mumkin!
        """.strip()
        
        for admin in admins:
            await TelegramSmartTriggers.send_telegram_message(
                admin.telegram_id,
                message
            )
        
        return True
    
    @staticmethod
    async def notify_employee_achievement(employee, achievement_type, details):
        """Celebrate employee achievements"""
        if not employee.telegram_id:
            return False
        
        achievements = {
            'high_efficiency': '🏆 YUQORI SAMARADORLIK!',
            'zero_errors': '✨ XATOSIZ ISH!',
            'fast_completion': '⚡ TEZKOR BAJARISH!'
        }
        
        message = f"""
{achievements.get(achievement_type, '🎉')} Tabriklaymiz!

👤 {employee.username}
{details}

Davom eting! 💪
        """.strip()
        
        await TelegramSmartTriggers.send_telegram_message(
            employee.telegram_id,
            message
        )
        
        return True


class AutoAlertSystem:
    """
    Automatic alert system that runs periodic checks.
    Detects issues and sends notifications.
    """
    
    @staticmethod
    async def check_approaching_deadlines():
        """Check for orders with approaching deadlines"""
        from api.models import Order
        
        today = timezone.now().date()
        alerts_sent = 0
        
        # Orders due in 1 day
        urgent_orders = Order.objects.filter(
            status__in=['approved', 'in_production'],
            deadline__date=today + timedelta(days=1)
        )
        
        for order in urgent_orders:
            await TelegramSmartTriggers.notify_deadline_approaching(order, 1)
            alerts_sent += 1
        
        # Orders due in 3 days
        warning_orders = Order.objects.filter(
            status__in=['approved', 'in_production'],
            deadline__date=today + timedelta(days=3)
        )
        
        for order in warning_orders:
            await TelegramSmartTriggers.notify_deadline_approaching(order, 3)
            alerts_sent += 1
        
        return {'type': 'deadline_check', 'alerts_sent': alerts_sent}
    
    @staticmethod
    async def check_bottlenecks():
        """Periodic bottleneck detection"""
        from api.production_optimizer import BottleneckDetector
        
        bottlenecks = BottleneckDetector.detect_bottlenecks()
        alerts_sent = 0
        
        for bottleneck in bottlenecks:
            if bottleneck['severity'] > 0.7:  # Only critical bottlenecks
                await TelegramSmartTriggers.notify_bottleneck_alert(bottleneck)
                alerts_sent += 1
        
        return {'type': 'bottleneck_check', 'alerts_sent': alerts_sent}
    
    @staticmethod
    async def check_low_stock():
        """Check for low material stock"""
        from api.models import Material
        
        alerts_sent = 0
        
        materials = Material.objects.filter(is_active=True)
        
        for material in materials:
            threshold = material.minimum_stock or (material.current_stock * 0.2)  # 20% of current
            
            if material.current_stock <= threshold and material.current_stock > 0:
                await TelegramSmartTriggers.notify_low_stock_alert(
                    material,
                    material.current_stock,
                    threshold
                )
                alerts_sent += 1
        
        return {'type': 'stock_check', 'alerts_sent': alerts_sent}
    
    @staticmethod
    async def check_machine_downtimes():
        """Check active machine downtimes"""
        from api.models import MachineDowntime
        
        active_downtimes = MachineDowntime.objects.filter(is_active=True)
        critical_count = 0
        
        for downtime in active_downtimes:
            # Alert if downtime > 4 hours
            if downtime.duration_hours > 4:
                critical_count += 1
        
        return {'type': 'machine_check', 'critical_downtimes': critical_count}

    @staticmethod
    def check_currency_rates():
        """Check and update currency rates"""
        from api.currency import CurrencyService
        
        try:
            result = CurrencyService.update_exchange_rate()
            return {'type': 'currency_check', 'result': result}
        except Exception as e:
            logger.error(f"Currency check failed: {e}")
            return {'type': 'currency_check', 'error': str(e)}
    
    @staticmethod
    async def run_all_checks():
        """Run all automatic checks"""
        results = []
        
        try:
            results.append(await AutoAlertSystem.check_approaching_deadlines())
        except Exception as e:
            logger.error(f"Deadline check failed: {e}")
        
        try:
            results.append(await AutoAlertSystem.check_bottlenecks())
        except Exception as e:
            logger.error(f"Bottleneck check failed: {e}")
        
        try:
            results.append(await AutoAlertSystem.check_low_stock())
        except Exception as e:
            logger.error(f"Stock check failed: {e}")
        
        try:
            results.append(await AutoAlertSystem.check_machine_downtimes())
        except Exception as e:
            logger.error(f"Machine check failed: {e}")
            
        try:
            # Sync wrapper for currency check (it's synchronous for now)
            results.append(AutoAlertSystem.check_currency_rates())
        except Exception as e:
            logger.error(f"Currency check failed: {e}")
        
        return {
            'timestamp': timezone.now().isoformat(),
            'checks_completed': len(results),
            'results': results
        }


class WorkflowAutomation:
    """
    Workflow automation rules.
    Auto-execute actions based on conditions.
    """
    
    @staticmethod
    def auto_assign_production_step(production_step):
        """Auto-assign worker when step starts"""
        from api.production_optimizer import SmartAssignmentEngine
        
        if production_step.assigned_to:
            return None  # Already assigned
        
        optimal_worker = SmartAssignmentEngine.assign_optimal_worker(production_step)
        
        if optimal_worker:
            production_step.assigned_to = optimal_worker
            production_step.save()
            
            return {
                'action': 'auto_assigned',
                'worker': optimal_worker.username,
                'step': production_step.step
            }
        
        return None
    
    @staticmethod
    async def auto_create_accounting_entry(order):
        """Auto-create journal entry when order completed"""
        from api.accounting import AccountingService
        from api.models import User
        
        # Get system user for auto-actions
        system_user = User.objects.filter(role='admin').first()
        
        if not system_user:
            return None
        
        try:
            entry = AccountingService.record_sale(order, system_user)
            return {
                'action': 'auto_accounting',
                'journal_entry_id': entry.id,
                'is_balanced': entry.is_balanced()
            }
        except Exception as e:
            logger.error(f"Auto accounting failed: {e}")
            return None
    
    @staticmethod
    def auto_reserve_materials(order):
        """Auto-reserve materials when order approved"""
        from api.models import Reservation
        from api.services import CalculationService
        from django.forms.models import model_to_dict
        
        # Calculate material needs
        order_data = model_to_dict(order)
        usage = CalculationService.calculate_material_usage(order_data)
        
        reservations_created = []
        
        # Reserve paper
        paper_kg = usage.get('paper_kg', 0)
        if paper_kg > 0:
            reserved = Reservation.reserve_materials(
                material_type='paper',
                quantity_needed=paper_kg,
                order=order
            )
            if reserved:
                reservations_created.extend(reserved)
        
        return {
            'action': 'auto_reserved',
            'reservation_count': len(reservations_created)
        }
    
    @staticmethod
    async def execute_workflow_on_status_change(order, old_status, new_status, user):
        """Execute automated workflows based on status changes"""
        actions_taken = []
        
        # When order approved
        if new_status == 'approved' and old_status == 'pending':
            # Auto-reserve materials
            result = WorkflowAutomation.auto_reserve_materials(order)
            if result:
                actions_taken.append(result)
            
            # Notify client
            await TelegramSmartTriggers.notify_order_status_change(
                order, old_status, new_status, user
            )
            actions_taken.append({'action': 'telegram_notification'})
        
        # When order completed
        if new_status == 'completed':
            # Auto-create accounting entry
            result = await WorkflowAutomation.auto_create_accounting_entry(order)
            if result:
                actions_taken.append(result)
            
            # Notify client
            await TelegramSmartTriggers.notify_order_status_change(
                order, old_status, new_status, user
            )
            actions_taken.append({'action': 'telegram_notification'})
        
        return {
            'workflow_triggered': True,
            'actions_count': len(actions_taken),
            'actions': actions_taken
        }
