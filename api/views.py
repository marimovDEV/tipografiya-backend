from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from django.db import models, transaction
from django.db.models import Count, Sum, F, Avg, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.contrib.auth import authenticate
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from .models import (
    User, Client, Material, Product, Order, 
    ProductionStep, Invoice, Transaction, ActivityLog, PricingSettings,
    Supplier, MaterialBatch, WarehouseLog, SettingsLog,
    EmployeeEfficiency, MachineSettings, WasteMaterial, Task, Attendance,
    ProductionTemplate, TemplateStage, ProductionLog
)
from .serializers import (
    UserSerializer, ClientSerializer, MaterialSerializer, 
    ProductSerializer, OrderSerializer, ProductionStepSerializer, InvoiceSerializer,
    ActivityLogSerializer, TransactionSerializer, PricingSettingsSerializer,
    SupplierSerializer, MaterialBatchSerializer, WarehouseLogSerializer, SettingsLogSerializer,
    EmployeeEfficiencySerializer, MachineSettingsSerializer, WasteMaterialSerializer, TaskSerializer,
    AttendanceSerializer, ProductionTemplateSerializer, TemplateStageSerializer
)
from rest_framework.authtoken.models import Token

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]  # Changed from AllowAny

    @action(detail=False, methods=['get'])
    def me(self, request):
        if not request.user.is_authenticated:
            return Response({"error": "Not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def tasks(self, request, pk=None):
        user = self.get_object()
        tasks = user.assigned_tasks.all()
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='stats')
    def list_stats(self, request):
        users = User.objects.filter(role='worker')
        data = []
        today = timezone.localdate()
        
        for user in users:
            tasks_today = user.assigned_tasks.filter(created_at__date=today).count()
            data.append({
                "id": str(user.id),
                "full_name": user.get_full_name() or user.username,
                "role": user.get_role_display(),
                "phone": user.phone,
                "status": user.status,
                "tasks_today": tasks_today,
            })
        return Response(data)

    @action(detail=False, methods=['get'], url_path='production-stats')
    def production_stats(self, request):
        """Returns production statistics for a specific user or current user"""
        user = request.user
        target_user_id = request.query_params.get('user_id')
        
        if target_user_id and user.role == 'admin':
            try:
                user = User.objects.get(id=target_user_id)
            except (User.DoesNotExist, ValueError):
                return Response({"error": "Foydalanuvchi topilmadi"}, status=status.HTTP_404_NOT_FOUND)
        
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)

        def get_metrics(start_date):
            logs = ProductionLog.objects.filter(worker=user, created_at__gte=start_date)
            totals = logs.aggregate(
                produced=Sum('produced_qty'),
                defects=Sum('defect_qty')
            )
            produced = totals['produced'] or 0
            defects = totals['defects'] or 0
            total = produced + defects
            efficiency = 0
            if total > 0:
                efficiency = round((produced / total) * 100, 1)
            
            # Calculate average speed (produced / active hours)
            # This is simplified: produced / 8 hours if today, etc.
            # In a real app we'd fetch actual attendance.
            return {
                "produced": produced,
                "defects": defects,
                "efficiency": efficiency
            }

        # Calculate today's average speed
        today_stats = get_metrics(today_start)
        attendance = Attendance.objects.filter(employee=user, date=today_start.date()).first()
        avg_speed = 0
        if attendance and attendance.total_hours and attendance.total_hours > 0:
            avg_speed = round(today_stats['produced'] / float(attendance.total_hours), 1)

        return Response({
            "today": today_stats,
            "weekly": get_metrics(week_start),
            "monthly": get_metrics(month_start),
            "plan_progress": round((today_stats['produced'] / user.daily_target) * 100) if user.daily_target > 0 else 0,
            "rating": float(user.quality_rating),
            "avg_speed": avg_speed,
            "rank": User.objects.filter(role='worker').annotate(
                today_produced=Sum('quantity_logs__produced_qty', filter=Q(quantity_logs__created_at__gte=today_start))
            ).filter(today_produced__gt=today_stats['produced']).count() + 1
        })

    @action(detail=False, methods=['get'], url_path='work-history')
    def work_history(self, request):
        """Returns recent production logs for the worker"""
        user = request.user
        target_user_id = request.query_params.get('user_id')
        
        if target_user_id and user.role == 'admin':
            try:
                user = User.objects.get(id=target_user_id)
            except (User.DoesNotExist, ValueError):
                return Response({"error": "Foydalanuvchi topilmadi"}, status=status.HTTP_404_NOT_FOUND)
        
        logs = ProductionLog.objects.filter(worker=user).order_by('-created_at')[:20]
        data = []
        for log in logs:
            data.append({
                "id": log.id,
                "date": log.created_at,
                "order_number": log.production_step.order.order_number,
                "step": log.production_step.get_step_display(),
                "produced": log.produced_qty,
                "defects": log.defect_qty,
                "notes": log.notes
            })
        return Response(data)

    @action(detail=False, methods=['post'], url_path='start-shift')
    def start_shift(self, request):
        user = request.user
        today = timezone.localdate()
        
        # Create or get attendance for today
        attendance, created = Attendance.objects.get_or_create(
            employee=user, 
            date=today,
            defaults={'status': 'working', 'clock_in': timezone.now()}
        )
        
        if not created:
            attendance.status = 'working'
            attendance.save()
            
        user.status = 'working'
        user.save()
        
        return Response({
            "status": "working",
            "message": "Smena boshlandi",
            "clock_in": attendance.clock_in
        })

    @action(detail=False, methods=['post'], url_path='end-shift')
    def end_shift(self, request):
        user = request.user
        today = timezone.localdate()
        
        attendance = Attendance.objects.filter(employee=user, date=today).first()
        if attendance:
            attendance.clock_out = timezone.now()
            attendance.status = 'finished'
            attendance.calculate_duration()
            attendance.save()

        # Auto-complete any active production tasks
        active_steps = ProductionStep.objects.filter(assigned_to=user, status='in_progress')
        for step in active_steps:
            # If no progress reported yet, assume full success
            if step.produced_qty == 0 and step.defect_qty == 0:
                step.produced_qty = step.input_qty
            
            step.status = 'completed'
            step.completed_at = timezone.now()
            step.save()

            # Cascade to next step
            next_step = ProductionStep.objects.filter(order=step.order, sequence=step.sequence + 1).first()
            if next_step:
                next_step.input_qty = step.produced_qty
                next_step.save()

            ActivityLog.objects.create(
                user=user,
                action=f"Auto-completed task on shift end: {step.get_step_display()} for Order #{step.order.order_number}"
            )
            
        user.status = 'away'
        user.save()
        
        return Response({
            "status": "away",
            "message": "Smena yakunlandi"
        })

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = str(request.data.get('username', '')).strip()
        password = request.data.get('password', '')
        
        # Case-insensitive username lookup
        try:
            user_obj = User.objects.get(username__iexact=username)
            # Use the actual username stored in DB for standard authentication
            user = authenticate(username=user_obj.username, password=password)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            # Fallback to standard authentication if lookup fails or ambiguity
            user = authenticate(username=username, password=password)
            
        if user:
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            })
        return Response({'error': 'Invalid Credentials'}, status=status.HTTP_400_BAD_REQUEST)

class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Client.objects.filter(is_active=True).order_by('-created_at')

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def add_payment(self, request, pk=None):
        client = self.get_object()
        amount = request.data.get('amount')
        method = request.data.get('method', 'cash')
        description = request.data.get('description', '')
        
        if not amount:
            return Response({"error": "Summa kiritilishi shart"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if payment exceeds debt
        if client.balance >= 0:
            return Response({"error": "Mijozning qarzi yo'q. To'lov qabul qilinmadi."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            amount_decimal = Decimal(str(amount))
            if amount_decimal <= 0:
                return Response({"error": "Summa noldan katta bo'lishi kerak"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Max possible payment is the debt amount
            max_payment = abs(client.balance)
            if amount_decimal > max_payment:
                return Response({"error": f"To'lov qarzdan ({max_payment:,.0f} so'm) ko'p bo'lishi mumkin emas"}, status=status.HTTP_400_BAD_REQUEST)
        except (InvalidOperation, ValueError, TypeError):
            return Response({"error": "Noto'g'ri summa formati"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            transaction = Transaction.objects.create(
                type='income',
                amount=amount_decimal,
                category='Mijoz to\'lovi',
                client=client,
                payment_method=method,
                date=timezone.localdate(),
                description=description or f"{client.full_name} tomonidan to'lov"
            )
            return Response(TransactionSerializer(transaction).data)
        except Exception as e:
            return Response({"error": f"To'lovni saqlashda ichki xatolik: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def orders(self, request, pk=None):
        client = self.get_object()
        orders = client.orders.all().order_by('-created_at')
        return Response(OrderSerializer(orders, many=True).data)

class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all().order_by('-created_at')
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        client_id = self.request.query_params.get('client')
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        return queryset

class MaterialViewSet(viewsets.ModelViewSet):
    queryset = Material.objects.all().order_by('name')
    serializer_class = MaterialSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'])
    def report_waste(self, request, pk=None):
        material = self.get_object()
        quantity = request.data.get('quantity')
        reason = request.data.get('reason')
        
        if not quantity:
            return Response({"error": "Miqdor kiritilishi shart"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            qty_decimal = Decimal(str(quantity))
        except:
            return Response({"error": "Noto'g'ri miqdor"}, status=status.HTTP_400_BAD_REQUEST)

        # Check stock
        if material.current_stock < qty_decimal:
            return Response({"error": "Omborda yetarli mahsulot yo'q"}, status=status.HTTP_400_BAD_REQUEST)
            
        waste = WasteMaterial.objects.create(
            material=material,
            quantity=qty_decimal,
            reason=reason or "Sabab ko'rsatilmadi"
        )
        
        # Reduce stock
        material.current_stock -= qty_decimal
        material.save()
        
        # Log it
        WarehouseLog.objects.create(
            material=material,
            change_amount=qty_decimal,
            type='out',
            notes=f"YAROQSIZ: {reason}",
            user=request.user if request.user.is_authenticated else None
        )
        
        return Response(WasteMaterialSerializer(waste).data)

    @action(detail=False, methods=['post'], url_path='request-material')
    def request_material(self, request):
        """Worker takes material directly from warehouse (logged for admin)"""
        material_id = request.data.get('material_id')
        quantity = request.data.get('quantity')
        step_id = request.data.get('production_step_id')
        notes = request.data.get('notes', 'Ombordan olindi')
        
        try:
            quantity_decimal = Decimal(str(quantity))
            material = Material.objects.get(id=material_id)
            step = ProductionStep.objects.get(id=step_id)
            order = step.order
            
            # --- STRICT STOCK CHECK ---
            if material.current_stock < quantity_decimal:
                return Response({
                    "error": f"Omborda yetarli qoldiq yo'q. Mavjud: {material.current_stock} {material.unit}"
                }, status=400)
            
            # --- FIFO DEDUCTION ---
            deducted_total = Decimal('0')
            batches = MaterialBatch.objects.filter(
                material=material, 
                is_active=True, 
                current_quantity__gt=0
            ).order_by('received_date')
            
            remaining = quantity_decimal
            for batch in batches:
                if remaining <= 0: break
                
                qty_in_batch = Decimal(str(batch.current_quantity))
                deduct = min(qty_in_batch, remaining)
                
                batch.current_quantity = qty_in_batch - deduct
                remaining -= deduct
                
                if batch.current_quantity <= 0:
                    batch.is_active = False
                batch.save()
                
                # Log batch-specific deduction
                WarehouseLog.objects.create(
                    material=material,
                    material_batch=batch,
                    change_amount=deduct,
                    type='out',
                    order=order,
                    user=request.user,
                    notes=f"ISHCHI (FIFO): {notes} (Bosqich: {step.get_step_display()})"
                )
                deducted_total += deduct
            
            # Update global stock
            material.current_stock -= deducted_total
            material.save()
            
            return Response({
                "status": "success", 
                "message": f"{quantity} {material.unit} {material.name} olindi.",
                "current_stock": material.current_stock
            })
        except Material.DoesNotExist:
            return Response({"error": "Material topilmadi"}, status=404)
        except ProductionStep.DoesNotExist:
            return Response({"error": "Bosqich topilmadi"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class WasteMaterialViewSet(viewsets.ModelViewSet):
    queryset = WasteMaterial.objects.all().order_by('-date')
    serializer_class = WasteMaterialSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def available_colors(self, request):
        """
        Get all unique colors from MaterialBatch inventory
        Returns: [{"name": "Oq", "count": 3}, {"name": "Qizil", "count": 2}]
        """
        colors = MaterialBatch.objects.filter(
            color__isnull=False,
            is_active=True
        ).exclude(
            color=''
        ).values('color').annotate(
            count=Count('id')
        ).order_by('color')
        
        return Response([
            {'name': c['color'], 'count': c['count']} 
            for c in colors
        ])

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('-created_at')
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]  # Changed from AllowAny
class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all().order_by('name')
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated]

class MaterialBatchViewSet(viewsets.ModelViewSet):
    queryset = MaterialBatch.objects.all().order_by('-received_date')
    serializer_class = MaterialBatchSerializer
    permission_classes = [permissions.IsAuthenticated]

from django_filters.rest_framework import DjangoFilterBackend

class WarehouseLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WarehouseLog.objects.all().order_by('-created_at')
    serializer_class = WarehouseLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['material', 'product', 'type', 'order']



class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by('-created_at')
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'client': ['exact'],
        'status': ['exact'],
        'created_at': ['gte', 'lte'],
        'deadline': ['gte', 'lte'],
        'completed_at': ['gte', 'lte'],
    }
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """Override to auto-create production steps when order is created"""
        order = serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)
        
        # Auto-create production steps
        try:
            template_id = self.request.data.get('product_template_id')
            if template_id:
                try:
                    product_template = ProductTemplate.objects.get(id=template_id)
                    # Automatically create production steps from template routing
                    routing_steps = product_template.routing_steps.all().order_by('sequence')
                    
                    for step in routing_steps:
                        ProductionStep.objects.create(
                            order=order,
                            step=step.stage_name or step.step_name or "Noma'lum",
                            sequence=step.sequence,
                            status='pending',
                            department=step.department,
                            auto_start=step.auto_start,
                            requires_operator=step.requires_operator,
                            machine=step.machine,
                            estimated_time_minutes=step.estimated_time_minutes
                        )
                except ProductTemplate.DoesNotExist:
                    pass
            else:
                # Fallback legacy logic
                settings = PricingSettings.load()
                steps = [
                    {"step_name": "Sklad", "assigned_to": settings.default_warehouse_user},
                    {"step_name": "Kesish", "assigned_to": settings.default_cutter_user},
                    {"step_name": "Bosma (Universal)", "assigned_to": settings.default_printer_user},
                    {"step_name": "Yelimlash", "assigned_to": settings.default_finisher_user},
                    {"step_name": "Qadoqlash", "assigned_to": settings.default_finisher_user},
                    {"step_name": "Tayyor (Sklad)", "assigned_to": settings.default_warehouse_user},
                ]
                
                for idx, s in enumerate(steps, start=1):
                    ProductionStep.objects.create(
                        order=order,
                        step=s['step_name'],
                        sequence=idx,
                        input_qty=order.quantity if idx == 1 else 0,
                        status='pending',
                        assigned_to=s['assigned_to']
                    )
        except Exception as e:
            print(f"Error creating production steps: {e}")
        
        # Log activity
        ActivityLog.objects.create(
            user=self.request.user,
            action=f"Yangi buyurtma yaratildi: #{order.order_number}",
            details=f"Mijoz: {order.client.full_name if order.client else 'N/A'}"
        )

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Returns statistical summary for finished orders."""
        finished_statuses = ['delivered', 'completed']
        queryset = self.get_queryset().filter(status__in=finished_statuses)
        
        # Apply date filters if provided
        start_date = request.query_params.get('completed_at__gte')
        end_date = request.query_params.get('completed_at__lte')
        if start_date:
            queryset = queryset.filter(completed_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(completed_at__lte=end_date)
            
        stats_data = queryset.aggregate(
            total_orders=Count('id'),
            total_revenue=Sum('total_price'),
            total_cost=Sum('total_cost'),
        )
        
        rev = float(stats_data['total_revenue'] or 0)
        cost = float(stats_data['total_cost'] or 0)
        
        return Response({
            "total_orders": stats_data['total_orders'],
            "total_revenue": rev,
            "total_cost": cost,
            "total_profit": rev - cost,
            "avg_profit_per_order": (rev - cost) / stats_data['total_orders'] if stats_data['total_orders'] > 0 else 0
        })
    
    @action(detail=False, methods=['get'])
    def production(self, request):
        """Returns orders that are currently in the production lifecycle."""
        production_statuses = ['approved', 'in_production', 'ready']
        queryset = self.get_queryset().filter(status__in=production_statuses).order_by('deadline')
        
        # Apply filters if any
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


    @action(detail=True, methods=['get'])
    def print_receipt(self, request, pk=None):
        order = self.get_object()
        print_type = request.query_params.get('type', 'customer')
        
        from django.http import HttpResponse
        
        # Professional Print Template
        html_content = f"""
        <html>
        <head>
            <title>Buyurtma #{order.order_number}</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 40px; color: #333; }}
                .container {{ max-width: 800px; margin: auto; border: 1px solid #eee; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.05); }}
                .header {{ display: flex; justify-content: space-between; border-bottom: 2px solid #333; padding-bottom: 20px; }}
                .logo {{ font-size: 24px; font-weight: 800; }}
                .info {{ margin: 30px 0; display: grid; grid-template-cols: 1fr 1fr; gap: 20px; }}
                .info-item {{ margin-bottom: 10px; }}
                .label {{ color: #888; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
                .value {{ font-size: 16px; font-weight: bold; }}
                table {{ w-full border-collapse; margin-top: 30px; }}
                th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid #eee; }}
                th {{ background: #f9f9f9; text-transform: uppercase; font-size: 12px; }}
                .total-section {{ margin-top: 40px; text-align: right; border-top: 2px solid #333; padding-top: 20px; }}
                .grand-total {{ font-size: 24px; font-weight: 900; color: #000; }}
                .footer {{ margin-top: 50px; text-align: center; color: #aaa; font-size: 12px; }}
                @media print {{ body {{ padding: 0; }} .container {{ box-shadow: none; border: none; }} }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">ERP PRINT SOLUTIONS</div>
                    <div>
                        <div style="font-weight: bold;">Buyurtma #{order.order_number}</div>
                        <div style="font-size: 14px; color: #888;">{timezone.now().strftime('%d.%m.%Y %H:%M')}</div>
                    </div>
                </div>
                
                <div class="info">
                    <div class="info-item">
                        <div class="label">Mijoz</div>
                        <div class="value">{order.client.full_name}</div>
                    </div>
                    <div class="info-item" style="text-align: right;">
                        <div class="label">Telefon</div>
                        <div class="value">{order.client.phone or '—'}</div>
                    </div>
                    <div class="info-item">
                        <div class="label">Tayyor bo'lish vaqti</div>
                        <div class="value">{order.completed_at.strftime('%d.%m.%Y %H:%M') if order.completed_at else '—'}</div>
                    </div>
                </div>

                <table>
                    <thead>
                        <tr>
                            <th>Tavsif</th>
                            <th>Parametrlar</th>
                            <th style="text-align: right;">Miqdor</th>
                            <th style="text-align: right;">Narx</th>
                            <th style="text-align: right;">Jami</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="font-weight: bold;">{order.box_type}</td>
                            <td style="font-size: 12px; color: #666;">
                                {order.paper_type} ({order.paper_density}gr)<br/>
                                {order.print_colors} | {order.lacquer_type or "Lak yo'q"}
                            </td>
                            <td style="text-align: right;">{order.quantity:,}</td>
                            <td style="text-align: right;">{order.price_per_unit or 0:,}</td>
                            <td style="text-align: right; font-weight: bold;">{order.total_price or 0:,}</td>
                        </tr>
                    </tbody>
                </table>

                {f'''
                <div style="margin-top: 40px; background: #fff8f8; padding: 20px; border-radius: 8px; border-left: 5px solid #ff4d4d;">
                    <div class="label" style="color: #cc0000; margin-bottom: 10px;">Ichki Moliyaviy Tahlil (FAQAT ADMIN)</div>
                    <div style="display: flex; justify-content: space-between;">
                        <span>Haqiqiy Tannarx:</span>
                        <span style="font-weight: bold;">{order.total_cost or 0:,} so'm</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 10px;">
                        <span>Sof Foyda:</span>
                        <span style="font-weight: bold; color: #2ecc71;">{(order.total_price or 0) - (order.total_cost or 0):,} so'm</span>
                    </div>
                </div>
                ''' if print_type == 'internal' else ''}

                <div class="total-section">
                    <div class="label">UMUMIY TO'LOV</div>
                    <div class="grand-total">{order.total_price or 0:,} so'm</div>
                </div>

                <div class="footer">
                    Tizim orqali avtomatik shakllantirildi. Rahmat!<br/>
                    <strong>ERP CRM v2.0</strong>
                </div>
            </div>
            <script>window.print();</script>
        </body>
        </html>
        """
        return HttpResponse(html_content)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        order = self.get_object()
        if order.status != 'pending':
            return Response({"error": "Order already processed"}, status=status.HTTP_400_BAD_REQUEST)
        
        settings = PricingSettings.load()
        
        # 1. Calculate and save total_cost
        try:
            from .services import CalculationService
            from django.forms.models import model_to_dict
            order_data = model_to_dict(order)
            usage = CalculationService.calculate_material_usage(order_data)
            cost_data = CalculationService.calculate_cost(order_data, usage)
            order.total_cost = cost_data.get('breakdown', {}).get('material_cost', 0) + cost_data.get('breakdown', {}).get('operational_cost', 0)
        except Exception as e:
            print(f"Error calculating cost: {e}")

        # 2. Update Status
        order.status = 'in_production'
        order.save()
        
        # 3. Generate Production Steps (Consolidated Routing)
        try:
            from .services import ProductionAssignmentService
            ProductionAssignmentService.auto_assign_production_steps(order)
        except Exception as e:
            print(f"Error generating production steps: {e}")
            
        ActivityLog.objects.create(
            user=request.user,
            action=f"Buyurtma #{order.order_number} tasdiqlandi va ishlab chiqarishga yuborildi",
            details=f"Taxminiy tannarx: {order.total_cost}"
        )
            
        return Response({"status": "approved", "message": "Order moved to production"})

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get('status')
        valid_statuses = [s[0] for s in Order.STATUS_CHOICES]
        
        if new_status not in valid_statuses:
            return Response({"error": "Noma'lum status"}, status=status.HTTP_400_BAD_REQUEST)
        
        if new_status == 'completed' and not order.completed_at:
            order.completed_at = timezone.now()
        
        order.status = new_status
        order.save()

        # Logging
        status_labels = dict(Order.STATUS_CHOICES)
        ActivityLog.objects.create(
            user=request.user,
            action=f"Buyurtma #{order.order_number} statusi o'zgardi",
            details=f"Eski: {status_labels.get(old_status)} -> Yangi: {status_labels.get(new_status)}"
        )

        return Response({"status": order.status, "label": status_labels.get(order.status)})

class ProductionTemplateViewSet(viewsets.ModelViewSet):
    queryset = ProductionTemplate.objects.all()
    serializer_class = ProductionTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        template = serializer.save()
        # Default stages requested by user
        default_stages = ['sklad', 'cutting', 'printing', 'gluing', 'packaging', 'tayyor_sklad']
        for idx, stage_code in enumerate(default_stages, start=1):
            TemplateStage.objects.create(
                template=template,
                stage_name=stage_code,
                sequence=idx
            )

class TemplateStageViewSet(viewsets.ModelViewSet):
    queryset = TemplateStage.objects.all().order_by('sequence')
    serializer_class = TemplateStageSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """
        Expects a list of stage IDs in their new order: [id1, id2, id3, ...]
        """
        ordered_ids = request.data.get('ordered_ids', [])
        if not isinstance(ordered_ids, list):
            return Response({"error": "ordered_ids must be a list"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                # Step 1: Set sequences to negative to avoid unique constraint collisions
                for index, stage_id in enumerate(ordered_ids, start=1):
                    TemplateStage.objects.filter(id=stage_id).update(sequence=-index)
                # Step 2: Set them to positive correct sequences
                for index, stage_id in enumerate(ordered_ids, start=1):
                    TemplateStage.objects.filter(id=stage_id).update(sequence=index)
            return Response({"status": "success"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ProductionStepViewSet(viewsets.ModelViewSet):
    serializer_class = ProductionStepSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return ProductionStep.objects.none()
            
        # Base Query
        if user.role == 'admin':
            qs = ProductionStep.objects.all()
        elif getattr(self, 'detail', False) or self.action in ['claim', 'report_progress']:
            # Allow workers to access specific steps for claiming/reporting
            qs = ProductionStep.objects.all()
        else:
            # For workers, show tasks assigned to them OR unassigned tasks in the general pool
            qs = ProductionStep.objects.filter(
                Q(assigned_to=user) | Q(assigned_to__isnull=True)
            )
            # If user has specific skills, filter pool by those skills
            if hasattr(user, 'assigned_stages') and user.assigned_stages:
                qs = qs.filter(step__in=user.assigned_stages)
            
        # Priority Logic
        from django.db.models import Case, When, Value, IntegerField
            
        # Annotate & Sort: Urgent(1) < High(2) < Normal(3)
        qs = qs.annotate(
            priority_score=Case(
                When(order__priority='urgent', then=Value(1)),
                When(order__priority='high', then=Value(2)),
                When(order__priority='normal', then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        ).order_by('priority_score', 'order__deadline', '-created_at')
        
        return qs

    @action(detail=False, methods=['get'])
    def available(self, request):
        """Returns pending tasks ready to start (assigned or in pool)"""
        user = request.user
        
        # Base filter: Assigned to current user OR Unassigned
        qs = ProductionStep.objects.filter(
            Q(assigned_to=user) | Q(assigned_to__isnull=True),
            status='pending'
        )
        
        # Filter by skills if they are set
        if hasattr(user, 'assigned_stages') and user.assigned_stages:
            qs = qs.filter(step__in=user.assigned_stages)
            
        available_steps = [step for step in qs if step.is_ready_to_start]
        
        serializer = self.get_serializer(available_steps, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Returns the current active step for the worker"""
        user = request.user
        target_user_id = request.query_params.get('user_id')
        
        if target_user_id and user.role == 'admin':
            try:
                user = User.objects.get(id=target_user_id)
            except (User.DoesNotExist, ValueError):
                return Response({"error": "Foydalanuvchi topilmadi"}, status=status.HTTP_404_NOT_FOUND)
                
        qs = ProductionStep.objects.filter(assigned_to=user, status='in_progress')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def claim(self, request, pk=None):
        """Start an assigned step or claim from pool and move to in_progress"""
        user = request.user
        step = self.get_object()
        
        if ProductionStep.objects.filter(assigned_to=user, status='in_progress').exists():
            return Response(
                {"error": "Sizda allaqachon faol vazifa bor. Yangisini boshlashdan oldin uni yakunlang."}, 
                status=400
            )

        # Allow if already assigned to current user OR unassigned pool
        if step.assigned_to and step.assigned_to != user and user.role != 'admin':
            return Response({"error": "Ushbu vazifa boshqa ishchiga biriktirilgan."}, status=403)
        
        # Skill-set validation when claiming from pool
        if not step.assigned_to and hasattr(user, 'assigned_stages') and user.assigned_stages:
            if step.step not in user.assigned_stages:
                return Response({
                    "error": f"Sizga '{step.step}' bosqichi biriktirilmagan. Profilingizni tekshiring."
                }, status=403)
        
        if step.status == 'completed':
            return Response({"error": "Vazifa allaqachon tugatilgan."}, status=400)

        # Force assign to user if claimed from pool
        if not step.assigned_to:
            step.assigned_to = user

        step.status = 'in_progress'
        if not step.started_at:
            step.started_at = timezone.now()
        step.save()
        
        ActivityLog.objects.create(
            user=user,
            action=f"Started/Claimed task: {step.get_step_display()} for Order #{step.order.order_number}"
        )
        
        return Response(self.get_serializer(step).data)

    @action(detail=False, methods=['post'], url_path='report-progress')
    def report_progress(self, request):
        """Report produced and defect quantities and create log entry"""
        step_id = request.data.get('production_step_id')
        produced_qty = request.data.get('produced_qty', 0)
        defect_qty = request.data.get('defect_qty', 0)
        notes = request.data.get('notes', '')
        
        try:
            # Safety cast
            try:
                new_produced = int(produced_qty)
                new_defect = int(defect_qty)
            except (ValueError, TypeError):
                return Response({"error": "Soni noto'g'ri formatda kiritildi"}, status=400)

            step = ProductionStep.objects.get(id=step_id)

            # Cumulative logic
            step.produced_qty += new_produced
            step.defect_qty += new_defect
            
            # Validation
            total_active = step.produced_qty + step.defect_qty
            
            # If nothing reported yet, allow it
            if new_produced == 0 and new_defect == 0:
                pass
            elif step.sequence > 1:
                prev_step = ProductionStep.objects.filter(order=step.order, sequence=step.sequence - 1).first()
                if prev_step and total_active > prev_step.produced_qty:
                     return Response({
                        "error": f"Xatolik: Oldingi bosqichda faqat {prev_step.produced_qty} ta mahsulot tayyorlangan. Undan ko'pini kiritib bo'lmaydi."
                    }, status=400)
            else:
                # For first step, use order quantity as limit
                if total_active > step.order.quantity:
                    return Response({
                        "error": f"Xatolik: Buyurtma miqdori {step.order.quantity} ta. Undan ko'pini kiritib bo'lmaydi."
                    }, status=400)

            step.save()
            
            # Create Production Log history entry
            ProductionLog.objects.create(
                production_step=step,
                worker=request.user,
                produced_qty=new_produced,
                defect_qty=new_defect,
                notes=notes
            )

            # Cascade produced_qty to next stage's input_qty
            next_step = ProductionStep.objects.filter(order=step.order, sequence=step.sequence + 1).first()
            if next_step:
                next_step.input_qty = step.produced_qty
                next_step.save()

            return Response({
                "status": "success", 
                "total_produced": step.produced_qty,
                "total_defect": step.defect_qty
            })
        except ProductionStep.DoesNotExist:
            return Response({"error": "Vazifa topilmadi"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete_step(self, request, pk=None):
        """Mark step as completed and cascade quantities"""
        step = self.get_object()
        
        # If no progress reported yet, assume full success
        if step.produced_qty == 0 and step.defect_qty == 0:
            step.produced_qty = step.input_qty
            
        step.status = 'completed'
        from django.utils import timezone
        step.completed_at = timezone.now()
        step.save()

        # Cascade produced_qty to next stage's input_qty
        next_step = ProductionStep.objects.filter(order=step.order, sequence=step.sequence + 1).first()
        if next_step:
            next_step.input_qty = step.produced_qty
            next_step.save()

        ActivityLog.objects.create(
            user=request.user,
            action=f"Completed task: {step.get_step_display()} for Order #{step.order.order_number}"
        )

        return Response(self.get_serializer(step).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Returns pending counts and total available quantities per step"""
        try:
            user = request.user
            
            # If worker, show stats for tasks they can actually claim
            if user.role == 'worker':
                qs = ProductionStep.objects.filter(
                    status='pending'
                ).filter(
                    Q(assigned_to=user) | Q(assigned_to__isnull=True)
                )
                if hasattr(user, 'assigned_stages') and user.assigned_stages:
                    # worker might have stages stored as names or codes
                    qs = qs.filter(step__in=user.assigned_stages)
                pending_steps = qs
            else:
                # If admin, show all unassigned pending tasks
                pending_steps = ProductionStep.objects.filter(status='pending', assigned_to__isnull=True)
            
            # Aggregate by step type
            stats_data = {}
            # Ensure we have STEP_CHOICES or fallback
            step_choices = getattr(ProductionStep, 'STEP_CHOICES', [])
            
            for step_code, step_display in step_choices:
                # We filter by both code and display name just in case
                # since the database might use either depending on how it was created
                type_qs = pending_steps.filter(Q(step=step_code) | Q(step=step_display))
                
                # Use list comprehension to filter by property
                ready_steps = [s for s in type_qs if s.is_ready_to_start]
                
                if ready_steps:
                    count = len(ready_steps)
                    try:
                        total_available = sum(s.available_qty for s in ready_steps)
                    except Exception:
                        total_available = 0
                        
                    stats_data[step_code] = {
                        "display": step_display,
                        "count": count,
                        "total_available": total_available
                    }
            
            return Response(stats_data)
        except Exception as e:
            import traceback
            print(f"Stats Error: {e}")
            print(traceback.format_exc())
            return Response({"error": str(e)}, status=500)

    @action(detail=True, methods=['post'])
    def assign_worker(self, request, pk=None):
        step = self.get_object()
        worker_id = request.data.get('worker_id')
        if not worker_id:
            return Response({"error": "Worker ID required"}, status=400)
        
        try:
            worker = User.objects.get(id=worker_id)
            step.assigned_to = worker
            step.save()
            return Response({"status": "assigned", "worker": worker.username})
        except User.DoesNotExist:
            return Response({"error": "Worker not found"}, status=404)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        step = self.get_object()
        new_status = request.data.get('status')
        if new_status not in ['pending', 'in_progress', 'completed', 'problem']:
            return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
        
        step.status = new_status
        if new_status == 'in_progress' and not step.started_at:
            from django.utils import timezone
            step.started_at = timezone.now()
        elif new_status == 'completed':
            from django.utils import timezone
            step.completed_at = timezone.now()
            
            # Phase 2: Maintenance Logic
            # Calculate duration in hours
            if step.started_at:
                duration_hrs = (step.completed_at - step.started_at).total_seconds() / 3600.0
                
                # Find associated machine (Simplified mapping based on step name)
                # Ideally, ProductionStep should have a 'machine' FK.
                # For now, we map step -> machine_type -> active MachineSettings
                
                step_machine_map = {
                    'printing': 'printer',
                    'cutting': 'cutter',
                    'gluing': 'folder', # or other
                    'lamination': 'laminator'
                }
                m_type = step_machine_map.get(step.step)
                if m_type:
                    # Find active machine of this type
                    machine = MachineSettings.objects.filter(machine_type=m_type, is_active=True).first()
                    if machine:
                        machine.current_operating_hours = float(machine.current_operating_hours) + duration_hrs
                        machine.save()
            
        step.save()

        # Translate for Logging
        status_map = {
            'pending': 'Kutilmoqda',
            'in_progress': 'Jarayonda',
            'completed': 'Tamomlandi',
            'problem': 'Muammo Bor'
        }
        step_map = {
            'queue': 'Navbatda',
            'prepress': 'Prepress (maket)',
            'printing_internal': 'Bosma (ichki)',
            'printing_cover': 'Bosma (muqova)',
            'folding': 'Faltsovka',
            'assembly': "Yig'ish",
            'binding': 'Termokley / Tikish',
            'trimming': 'Uch tomondan kesish',
            'printing': 'Chop etish',
            'gluing': 'Yelimlash',
            'drying': 'Quritish',
            'packaging': 'Qadoqlash',
            'ready': 'Tayyor (Sklad)'
        }
        
        status_uz = status_map.get(new_status, new_status)
        step_uz = step_map.get(step.step, step.step)

        # Log Activity
        ActivityLog.objects.create(
            user=request.user,
            action=f"Buyurtma #{step.order.order_number} bosqichi o'zgardi",
            details=f"{step_uz}: {status_uz}"
        )

        # MATERIAL DEDUCTION LOGIC: Trigger on first step 'in_progress' or 'completed'
        is_first_step = not step.order.production_steps.filter(status='completed').exclude(id=step.id).exists()
        
        if is_first_step and new_status == 'in_progress':
            if step.order.status == 'approved':
                step.order.status = 'in_production'
                step.order.save()
            try:
                from .services import CalculationService
                from django.forms.models import model_to_dict
                
                order = step.order
                order_data = model_to_dict(order)
                # Ensure date/decimal fields are handled if needed, but calculate_material_usage handles basics
                usage = CalculationService.calculate_material_usage(order_data)
                
                def deduct_material_fifo(material_obj, amount_needed):
                    if not material_obj: return 0, []
                    
                    actual_cost = Decimal('0')
                    deducted_total = Decimal('0')
                    logs = []
                    
                    # Get active batches ordered by received_date (FIFO)
                    batches = MaterialBatch.objects.filter(
                        material=material_obj, 
                        is_active=True, 
                        current_quantity__gt=0
                    ).order_by('received_date')
                    
                    remaining = Decimal(str(amount_needed))
                    for batch in batches:
                        if remaining <= 0: break
                        
                        # Use Decimal for all math
                        qty_in_batch = Decimal(str(batch.current_quantity))
                        deduct = min(qty_in_batch, remaining)
                        
                        batch.current_quantity = qty_in_batch - deduct
                        remaining -= deduct
                        
                        # Calculate cost for this portion
                        # Calculate cost for this portion
                        batch_cost = deduct * Decimal(str(batch.cost_per_unit))
                        actual_cost += batch_cost
                        deducted_total += deduct
                        
                        if batch.current_quantity <= 0:
                            batch.is_active = False
                        batch.save()
                        
                        # Create WarehouseLog
                        WarehouseLog.objects.create(
                            material=material_obj,
                            material_batch=batch,
                            change_amount=deduct,
                            type='out',
                            order=order,
                            user=request.user,
                            notes=f"Ishlab chiqarish uchun FIFO yechildi (Buyurtma #{order.order_number})"
                        )
                        logs.append(f"{material_obj.name} (Batch: {batch.batch_number}): -{deduct}")
                    
                    # Update global stock
                    material_obj.current_stock -= deducted_total
                    material_obj.save()
                    
                    return actual_cost, logs

                total_actual_cost = 0
                all_deduction_details = []

                # 1. Deduct Paper
                paper_kg = usage.get('paper_kg', 0)
                if paper_kg > 0:
                    paper_name = f"{order.paper_type} {order.paper_density}g/m²"
                    material = Material.objects.filter(name__iexact=paper_name).first()
                    if not material:
                         material = Material.objects.filter(name__icontains=order.paper_type, category='qogoz').first()
                    
                    if material:
                        cost, logs = deduct_material_fifo(material, paper_kg)
                        total_actual_cost += cost
                        all_deduction_details.extend(logs)
                    else:
                        all_deduction_details.append(f"Qog'oz ({paper_name}) topilmadi")

                # 2. Deduct Ink
                ink_kg = usage.get('ink_kg', 0)
                if ink_kg > 0:
                    ink = Material.objects.filter(name__icontains="Bo'yoq").first()
                    if ink:
                        cost, logs = deduct_material_fifo(ink, ink_kg)
                        total_actual_cost += cost
                        all_deduction_details.extend(logs)

                # 3. Deduct Lacquer
                lacquer_kg = usage.get('lacquer_kg', 0)
                if lacquer_kg > 0:
                    l_type = order.lacquer_type
                    lacquer = Material.objects.filter(name__icontains=l_type, category='lak').first()
                    if lacquer:
                        cost, logs = deduct_material_fifo(lacquer, lacquer_kg)
                        total_actual_cost += cost
                        all_deduction_details.extend(logs)

                # Update order's actual total_cost based on actual batch prices
                if total_actual_cost > 0:
                    order.total_cost = total_actual_cost
                    order.save()

                    ActivityLog.objects.create(
                        user=request.user,
                        action=f"Materiallar FIFO bo'yicha yechildi (#{order.order_number})",
                        details=", ".join(all_deduction_details) + f" | Jami tannarx: {total_actual_cost}"
                    )
            except Exception as e:
                print(f"Error deducting materials: {e}")
                ActivityLog.objects.create(
                    user=request.user,
                    action=f"Material yechishda xatolik (#{step.order.order_number})",
                    details=str(e)
                )

        # Check if all steps for this order are completed
        order = step.order
        order_completed = False
        if not order.production_steps.exclude(status='completed').exists():
            # If all production is done, order is 'completed' (Archive) as per user request
            if order.status != 'completed':
                order.status = 'completed'
                from django.utils import timezone
                order.completed_at = timezone.now()
                order.save()
                order_completed = True
                
                # Log the completion
                ActivityLog.objects.create(
                    user=request.user,
                    action=f"🎉 Buyurtma #{order.order_number} to'liq yakunlandi!",
                    details=f"Barcha bosqichlar bajarildi. Arxivga o'tkazildi."
                )
                
                # AUTOMATIC WAREHOUSE ENTRY (Finished Goods)
                try:
                    product_name = f"{order.box_type} ({order.client.full_name})"
                    product, created = Product.objects.get_or_create(
                        sku=f"ORD-{order.order_number}",
                        defaults={
                            'name': product_name,
                            'category': 'Tayyor mahsulot',
                            'price': order.price_per_unit or 0,
                            'current_stock': 0
                        }
                    )
                    product.current_stock += order.quantity
                    product.save()
                    
                    WarehouseLog.objects.create(
                        material=None,  # It's a product, but model assumes material or product?
                        product=product,
                        change_amount=order.quantity,
                        type='in',
                        notes=f"Ishlab chiqarishdan tayyor bo'ldi. Buyurtma #{order.order_number}"
                    )
                except Exception as e:
                    print(f"Warehouse entry error: {e}")

                ActivityLog.objects.create(
                    user=request.user,
                    action=f"Buyurtma #{order.order_number} to'liq tayyor",
                    details="Barcha ishlab chiqarish bosqichlari yakunlandi va skladga olindi"
                )

        return Response({"status": step.status, "order_completed": order_completed})

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().order_by('-created_at')
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]  # Changed from AllowAny

from .services import CalculationService
from .pricing_logic import ScenarioPricingService, CapacityAwareCalculator

class CalculateOrderView(APIView):
    """
    API endpoint to calculate price and material usage before saving order.
    NOW WITH: Scenario pricing + Capacity-aware deadline
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            scenario = data.get('scenario', 'Standard')
            
            # Material usage calculation
            usage = CalculationService.calculate_material_usage(data)
            
            # Base cost calculation
            cost_data = CalculationService.calculate_cost(data, usage)
            base_price = cost_data.get('total_price', 0)
            
            # Apply scenario pricing
            final_price = ScenarioPricingService.calculate_with_scenario(base_price, scenario)
            scenario_multiplier = ScenarioPricingService.get_scenario_multiplier(scenario)
            
            # Calculate estimated deadline based on quantity and complexity
            from django.utils import timezone
            from datetime import timedelta
            
            quantity = int(data.get('quantity', 0))
            
            # Simple formula: 1-2 days per 1000 items + base 1 day
            base_days = 1
            production_days = max(1, quantity // 1000) 
            
            # Add complexity factors
            if data.get('lacquer_type') and data.get('lacquer_type') != 'none':
                production_days += 1  # Extra day for lacquering
            
            # Scenario adjustments
            if scenario == 'Express':
                production_days = max(1, production_days - 1)
            elif scenario == 'VIP':
                production_days = max(1, production_days - 2)
            elif scenario == 'Economy':
                production_days += 2
            
            total_days = base_days + production_days
            estimated_deadline = timezone.localdate() + timedelta(days=total_days)
            
            # Capacity status (simplified)
            capacity_status = {
                'current_load': Order.objects.filter(status__in=['in_production', 'approved']).count(),
                'max_capacity': 20,
                'status': 'normal'
            }
            
            if capacity_status['current_load'] > 15:
                capacity_status['status'] = 'high'
                total_days += 1
                estimated_deadline = timezone.localdate() + timedelta(days=total_days)
            
            response_data = {
                "materials": usage,
                "cost": {
                    **cost_data,
                    'base_price': base_price,
                    'scenario': scenario,
                    'scenario_multiplier': scenario_multiplier,
                    'final_price': final_price
                },
                "estimated_days": total_days,
                "estimated_deadline": estimated_deadline.isoformat(),
                "capacity_status": capacity_status
            }
            return Response(response_data)
        except Exception as e:
            print(f"Calculate error: {e}")
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=400)




class PricingSettingsView(APIView):
    """
    Get or Update Pricing configuration with Audit Logging
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        settings = PricingSettings.load()
        serializer = PricingSettingsSerializer(settings)
        return Response(serializer.data)

    def put(self, request):
        settings = PricingSettings.load()
        old_data = PricingSettingsSerializer(settings).data
        serializer = PricingSettingsSerializer(settings, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            new_data = serializer.data
            
            # Log individual changes
            for key, new_val in new_data.items():
                if key in ['id', 'pricing_profiles']: continue # Skip ID and complex fields for simple log
                old_val = old_data.get(key)
                if str(old_val) != str(new_val):
                    SettingsLog.objects.create(
                        user=request.user,
                        setting_type=key,
                        old_value=str(old_val),
                        new_value=str(new_val)
                    )
            
            return Response(new_data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        """Handle POST as PUT for compatibility"""
        return self.put(request)

class SettingsLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SettingsLog.objects.all().order_by('-created_at')
    serializer_class = SettingsLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        user_id = self.request.query_params.get('user')
        setting_type = self.request.query_params.get('type')
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if setting_type:
            queryset = queryset.filter(setting_type=setting_type)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore a previous setting value"""
        log = self.get_object()
        settings = PricingSettings.load()
        
        # Restore the old value
        if hasattr(settings, log.setting_type):
            setattr(settings, log.setting_type, log.old_value)
            settings.save()
            
            # Create a new log entry for the restore action
            SettingsLog.objects.create(
                user=request.user,
                setting_type=log.setting_type,
                old_value=log.new_value,
                new_value=log.old_value
            )
            
            return Response({"status": "restored", "setting": log.setting_type})
        
        return Response({"error": "Setting not found"}, status=status.HTTP_400_BAD_REQUEST)


class EmployeeEfficiencyViewSet(viewsets.ModelViewSet):
    """Employee efficiency tracking and management"""
    queryset = EmployeeEfficiency.objects.all().order_by('-effective_from')
    serializer_class = EmployeeEfficiencySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        employee_id = self.request.query_params.get('employee_id')
        stage = self.request.query_params.get('stage')
        
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        if stage:
            queryset = queryset.filter(production_stage=stage)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def by_employee(self, request):
        """Get efficiency history for a specific employee"""
        employee_id = request.query_params.get('employee_id')
        if not employee_id:
            return Response({"error": "employee_id parameter required"}, status=status.HTTP_400_BAD_REQUEST)
        
        records = self.queryset.filter(employee_id=employee_id).order_by('-effective_from')
        serializer = self.get_serializer(records, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def alerts(self, request):
        """Get employees with low efficiency or high error rates"""
        # Get the latest efficiency record for each employee-stage combination
        from django.db.models import OuterRef, Subquery
        
        latest_records = EmployeeEfficiency.objects.filter(
            employee=OuterRef('employee'),
            production_stage=OuterRef('production_stage')
        ).order_by('-effective_from')
        
        all_records = EmployeeEfficiency.objects.filter(
            id__in=Subquery(latest_records.values('id')[:1])
        )
        
        # Filter for low efficiency (< 10 units/hour) or high error rate (> 10%)
        alerts = all_records.filter(
            Q(units_per_hour__lt=10) | Q(error_rate_percent__gt=10)
        )
        
        serializer = self.get_serializer(alerts, many=True)
        return Response(serializer.data)


class MachineSettingsViewSet(viewsets.ModelViewSet):
    """Machine configuration and management"""
    queryset = MachineSettings.objects.all().order_by('machine_name')
    serializer_class = MachineSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        machine_type = self.request.query_params.get('type')
        is_active = self.request.query_params.get('is_active')
        
        if machine_type:
            queryset = queryset.filter(machine_type=machine_type)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset


class CalculationPreviewView(APIView):
    """
    Calculate detailed order cost breakdown without saving
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        from .services import CalculationService
        
        data = request.data
        
        # Get material usage
        usage = CalculationService.calculate_material_usage(data)
        
        # Get cost breakdown
        cost_data = CalculationService.calculate_cost(data, usage)
        
        # Get settings for waste percentages
        settings = PricingSettings.load()
        
        # Calculate with waste
        paper_kg = usage.get('paper_kg', 0)
        ink_kg = usage.get('ink_kg', 0)
        lacquer_kg = usage.get('lacquer_kg', 0)
        
        paper_with_waste = paper_kg * (1 + settings.waste_percentage_paper / 100)
        ink_with_waste = ink_kg * (1 + settings.waste_percentage_ink / 100)
        lacquer_with_waste = lacquer_kg * (1 + settings.waste_percentage_lacquer / 100)
        
        # Material costs
        material_breakdown = {
            "paper": {
                "quantity_kg": round(paper_kg, 2),
                "waste_percent": settings.waste_percentage_paper,
                "quantity_with_waste_kg": round(paper_with_waste, 2),
                "price_per_kg": float(settings.paper_price_per_kg),
                "total_cost": round(paper_with_waste * float(settings.paper_price_per_kg), 2)
            },
            "ink": {
                "quantity_kg": round(ink_kg, 2),
                "waste_percent": settings.waste_percentage_ink,
                "quantity_with_waste_kg": round(ink_with_waste, 2),
                "price_per_kg": float(settings.ink_price_per_kg),
                "total_cost": round(ink_with_waste * float(settings.ink_price_per_kg), 2)
            },
            "lacquer": {
                "quantity_kg": round(lacquer_kg, 2),
                "waste_percent": settings.waste_percentage_lacquer,
                "quantity_with_waste_kg": round(lacquer_with_waste, 2),
                "price_per_kg": float(settings.lacquer_price_per_kg),
                "total_cost": round(lacquer_with_waste * float(settings.lacquer_price_per_kg), 2)
            }
        }
        
        total_material_cost = (
            material_breakdown['paper']['total_cost'] +
            material_breakdown['ink']['total_cost'] +
            material_breakdown['lacquer']['total_cost']
        )
        
        # Operational costs
        num_colors = int(data.get('print_colors', '4+0').split('+')[0])
        quantity = int(data.get('quantity', 1))
        
        operational_breakdown = {
            "plate_cost": {
                "num_colors": num_colors,
                "cost_per_color": float(settings.plate_cost),
                "total_cost": num_colors * float(settings.plate_cost)
            },
            "setup_cost": float(settings.setup_cost),
            "run_cost": {
                "cost_per_box": float(settings.run_cost_per_box),
                "quantity": quantity,
                "total_cost": quantity * float(settings.run_cost_per_box)
            }
        }
        
        total_operational_cost = (
            operational_breakdown['plate_cost']['total_cost'] +
            operational_breakdown['setup_cost'] +
            operational_breakdown['run_cost']['total_cost']
        )
        
        # Get pricing profile
        pricing_profile = data.get('pricing_profile', settings.default_pricing_profile)
        profit_margin = settings.pricing_profiles.get(pricing_profile, settings.profit_margin_percent)
        
        # Calculate totals
        subtotal = total_material_cost + total_operational_cost
        profit_amount = subtotal * (profit_margin / 100)
        before_tax = subtotal + profit_amount
        tax_amount = before_tax * (settings.tax_percent / 100)
        total_price = before_tax + tax_amount
        
        response_data = {
            "materials": material_breakdown,
            "operational": operational_breakdown,
            "summary": {
                "material_cost": round(total_material_cost, 2),
                "operational_cost": round(total_operational_cost, 2),
                "subtotal": round(subtotal, 2),
                "pricing_profile": pricing_profile,
                "profit_margin_percent": profit_margin,
                "profit_amount": round(profit_amount, 2),
                "tax_percent": settings.tax_percent,
                "tax_amount": round(tax_amount, 2),
                "total_price": round(total_price, 2)
            },
            "raw_usage": usage,
            "original_cost_data": cost_data
        }
        
        return Response(response_data)


class UpdateCurrencyRateView(APIView):
    """
    Fetch current USD -> UZS exchange rate from CBU API and update settings
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        import requests
        
        try:
            # Fetch from Central Bank of Uzbekistan API
            response = requests.get('https://cbu.uz/uz/arkhiv-kursov-valyut/json/', timeout=10)
            
            if response.status_code != 200:
                return Response(
                    {"error": "Markaziy Bank API dan ma'lumot olib bo'lmadi"}, 
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            data = response.json()
            
            # Find USD rate (Code: USD or Ccy: USD)
            usd_rate = None
            for currency in data:
                if currency.get('Ccy') == 'USD' or currency.get('Code') == 'USD':
                    usd_rate = currency.get('Rate')
                    break
            
            if not usd_rate:
                return Response(
                    {"error": "USD kursi topilmadi"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Update settings
            settings = PricingSettings.load()
            old_rate = float(settings.exchange_rate)
            settings.exchange_rate = Decimal(str(usd_rate))
            settings.save()
            
            # Log the change
            SettingsLog.objects.create(
                user=request.user,
                setting_type='exchange_rate',
                old_value=str(old_rate),
                new_value=str(usd_rate)
            )
            
            return Response({
                "success": True,
                "old_rate": old_rate,
                "new_rate": float(usd_rate),
                "message": "Valyuta kursi yangilandi"
            })
            
        except requests.exceptions.RequestException as e:
            return Response(
                {"error": f"Internet bilan bog'lanishda xatolik: {str(e)}"}, 
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            return Response(
                {"error": f"Xatolik yuz berdi: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ReportsView(APIView):
    """
    API for Dashboard and Reports stats - ERP Level
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        # Default to last 30 days if no dates provided
        now = timezone.now()
        try:
            if start_date_str:
                if start_date_str.endswith('Z'):
                    start_date_str = start_date_str.replace('Z', '+00:00')
                start_date = timezone.datetime.fromisoformat(start_date_str)
            else:
                start_date = now - timedelta(days=30)
                
            if end_date_str:
                if end_date_str.endswith('Z'):
                    end_date_str = end_date_str.replace('Z', '+00:00')
                end_date = timezone.datetime.fromisoformat(end_date_str)
            else:
                end_date = now
        except ValueError as e:
            return Response(
                {"error": f"Invalid date format: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Filters
        order_filter = Q(created_at__range=(start_date, end_date))
        log_filter = Q(created_at__range=(start_date, end_date))
        step_filter = Q(completed_at__range=(start_date, end_date))

        # 1. Financials (Based on Transactions as per TZ)
        transactions = Transaction.objects.filter(date__range=(start_date.date(), end_date.date()))
        income_total = transactions.filter(type='income').aggregate(total=Sum('amount'))['total'] or 0
        expense_total = transactions.filter(type='expense').aggregate(total=Sum('amount'))['total'] or 0
        
        # Order-based count and average check
        orders_period = Order.objects.filter(order_filter)
        completed_orders = orders_period.filter(status='completed')
        order_count = completed_orders.count()
        
        total_revenue = float(income_total)
        total_cost = float(expense_total)
        net_profit = total_revenue - total_cost
        avg_order_value = (total_revenue / order_count) if order_count > 0 else 0
        rentability = (net_profit / total_revenue * 100) if total_revenue > 0 else 0

        # 2. Production Analytics (Bottlenecks)
        # Average time per step
        finished_steps = ProductionStep.objects.filter(step_filter, status='completed', started_at__isnull=False)
        # In Django we can use F expressions to calculate duration
        avg_times = finished_steps.values('step').annotate(
            avg_duration=Avg(F('completed_at') - F('started_at'))
        )
        
        bottlenecks = []
        for stage in avg_times:
            if stage['avg_duration']:
                # Convert timedelta to minutes/hours
                minutes = stage['avg_duration'].total_seconds() / 60
                bottlenecks.append({
                    "step": stage['step'],
                    "avg_minutes": round(minutes, 1)
                })

        # 3. Warehouse / Material Consumption
        # Sum change_amount for 'out' logs (material consumption)
        consumption = WarehouseLog.objects.filter(log_filter, type='out', material__isnull=False).values(
            'material__name'
        ).annotate(
            total_used=Sum('change_amount')
        ).order_by('-total_used')[:5]

        # 4. Worker Efficiency
        worker_stats = ProductionStep.objects.filter(step_filter, status='completed').values(
            'assigned_to__first_name', 'assigned_to__last_name'
        ).annotate(
            completed_count=Count('id')
        ).order_by('-completed_count')

        # 5. Product Popularity
        # Support both box_type and book_name for Kitob-centric TZ
        top_products_query = completed_orders.values('box_type', 'book_name').annotate(
            total_sold=Sum('quantity'),
            revenue=Sum('total_price')
        ).order_by('-revenue')[:5]
        
        top_products = []
        for p in top_products_query:
            top_products.append({
                "box_type": p['book_name'] if p['book_name'] else (p['box_type'] if p['box_type'] else "Noma'lum"),
                "total_sold": p['total_sold'],
                "revenue": p['revenue']
            })

        # 6. Chart Data (Daily Dynamics)
        daily_stats = Transaction.objects.filter(
            date__range=(start_date.date(), end_date.date())
        ).values('date').annotate(
            daily_income=Sum('amount', filter=Q(type='income')),
            daily_expense=Sum('amount', filter=Q(type='expense'))
        ).order_by('date')

        return Response({
            "financials": {
                "total_revenue": total_revenue,
                "total_cost": total_cost,
                "net_profit": net_profit,
                "avg_order_value": round(avg_order_value, 2),
                "order_count": order_count,
                "rentability": round(rentability, 1)
            },
            "bottlenecks": bottlenecks,
            "consumption": list(consumption),
            "worker_performance": list(worker_stats),
            "top_products": list(top_products),
            "charts": {
                "labels": [str(d['date']) for d in daily_stats],
                "revenue": [float(d['daily_income'] or 0) for d in daily_stats],
                "profit": [float((d['daily_income'] or 0) - (d['daily_expense'] or 0)) for d in daily_stats]
            },
            "inventory_health": {
                "low_stock_count": Material.objects.filter(current_stock__lt=F('minimum_stock')).count()
            }
        })

class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        start_of_month = today.replace(day=1)
        
        # 1. CORE STATS
        total_orders = Order.objects.count()
        active_orders = Order.objects.filter(status__in=['approved', 'in_production']).count()
        
        # Today's Stats
        today_orders_count = Order.objects.filter(created_at__date=today).count()
        waiting_advance_count = Order.objects.filter(payment_status='unpaid').count()
        
        # Financial Today
        today_income = Transaction.objects.filter(type='income', date=today).aggregate(Sum('amount'))['amount__sum'] or 0
        today_expense = Transaction.objects.filter(type='expense', date=today).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Production Today
        today_production = ProductionLog.objects.filter(created_at__date=today).aggregate(
            produced=Sum('produced_qty'),
            defect=Sum('defect_qty')
        )
        today_produced_qty = today_production['produced'] or 0
        today_defect_qty = today_production['defect'] or 0
        
        # Efficiency % (Today)
        total_attempted = today_produced_qty + today_defect_qty
        today_efficiency = round((today_produced_qty / total_attempted * 100), 1) if total_attempted > 0 else 0

        # Delayed Orders
        delayed_orders_count = Order.objects.filter(deadline__lt=timezone.now(), status__in=['pending', 'in_production']).count()
        delayed_orders_list = Order.objects.filter(
            deadline__lt=timezone.now(), 
            status__in=['pending', 'in_production']
        ).values('id', 'order_number', 'client__full_name', 'deadline')[:5]

        # 2. FINANCIALS (Monthly)
        monthly_income = Transaction.objects.filter(type='income', date__gte=start_of_month).aggregate(Sum('amount'))['amount__sum'] or 0
        monthly_expense = Transaction.objects.filter(type='expense', date__gte=start_of_month).aggregate(Sum('amount'))['amount__sum'] or 0
        monthly_profit = monthly_income - monthly_expense

        # Admin Internal Profit (Calculated from Orders)
        # We need to sum (Price - Cost) for completed orders this month to be accurate on "Profit on Sales"
        # User requested "Internal Profit" -> likely means (Order Price - Material Cost).
        # Let's calculate estimated profit for completed orders this month.
        
        # Calculate actual revenue from finished orders
        completed_orders_month = Order.objects.filter(status='completed', completed_at__date__gte=start_of_month)
        order_financials = completed_orders_month.aggregate(
            total_rev=Sum('total_price')
        )
        total_revenue_month = float(order_financials['total_rev'] or 0)
        # Internal profit is monthly income from transactions minus expenses
        internal_profit = monthly_profit 

        # 3. PRODUCTION STAGES (Visual)
        # Group by step and status
        # We want to know how many orders are in each stage
        # Aggregate ProductionStep where status != completed (active steps)
        # However, an order might have multiple active steps? Usually sequential.
        stage_counts = ProductionStep.objects.filter(status__in=['pending', 'in_progress']).values('step').annotate(count=Count('id'))
        stage_data = {item['step']: item['count'] for item in stage_counts}
        
        # 4. ALERTS / URGENT
        # Orders due today
        due_today_count = Order.objects.filter(deadline__date=today, status__in=['pending', 'in_production']).count()
        due_today_list = Order.objects.filter(
            deadline__date=today, status__in=['pending', 'in_production']
        ).values('id', 'order_number', 'client__full_name')[:5]

        # Low Stock
        low_stock_items = Material.objects.filter(current_stock__lt=F('min_stock')).values('name', 'current_stock', 'min_stock')[:5]

        # 5. WORKER STATS (Active)
        # Who is working on what?
        active_workers = ProductionStep.objects.filter(status='in_progress', assigned_to__isnull=False).select_related(
            'assigned_to', 'order'
        ).values(
            'assigned_to__id',
            'assigned_to__first_name', 
            'assigned_to__last_name', 
            'step', 
            'order__order_number',
            'produced_qty',
            'defect_qty'
        )

        top_worker = ProductionLog.objects.filter(created_at__date=today).values(
            'worker__first_name', 'worker__last_name', 'worker__username'
        ).annotate(
            total_produced=Sum('produced_qty'),
            total_defect=Sum('defect_qty')
        ).order_by('-total_produced').first()

        # 6. CHART DATA (Last 6 months)
        chart_labels = []
        chart_income = []
        chart_expense = []
        
        # Use a more stable month-to-month calculation
        current_date = today.replace(day=1)
        for i in range(5, -1, -1):
            m_date = current_date - timedelta(days=i*30)
            m_date = m_date.replace(day=1) # normalize to start of month
            label = m_date.strftime("%b").upper()
            chart_labels.append(label)
            
            inc = Transaction.objects.filter(type='income', date__year=m_date.year, date__month=m_date.month).aggregate(Sum('amount'))['amount__sum'] or 0
            exp = Transaction.objects.filter(type='expense', date__year=m_date.year, date__month=m_date.month).aggregate(Sum('amount'))['amount__sum'] or 0
            chart_income.append(float(inc))
            chart_expense.append(float(exp))

        # Recent Activities
        recent_activities = ActivityLog.objects.all().select_related('user')[:10]

        return Response({
            "stats": {
                "total_orders": total_orders,
                "active_orders": active_orders,
                "today_orders": today_orders_count,
                "waiting_advance": waiting_advance_count,
                "today_income": float(today_income),
                "today_expense": float(today_expense),
                "today_produced_qty": today_produced_qty,
                "today_defect_qty": today_defect_qty,
                "today_efficiency": today_efficiency,
                "delayed_orders_count": delayed_orders_count,
                "monthly_income": float(monthly_income),
                "monthly_expense": float(monthly_expense),
                "monthly_internal_profit": float(internal_profit) if request.user.role == 'admin' else None,
                "due_today_count": due_today_count
            },
            "production_stages": stage_data,
            "alerts": {
                "delayed": delayed_orders_list,
                "due_today": due_today_list,
                "low_stock": list(low_stock_items)
            },
            "active_workers": list(active_workers),
            "top_worker": top_worker,
            "chart_data": {
                "labels": chart_labels,
                "income": chart_income,
                "expense": chart_expense
            },
            "recent_activities": ActivityLogSerializer(recent_activities, many=True).data,
            "task_stats": {
                "total": Task.objects.count(),
                "pending": Task.objects.filter(status='pending').count(),
                "in_progress": Task.objects.filter(status='in_progress').count(),
                "completed": Task.objects.filter(status='completed').count(),
                "delayed": Task.objects.filter(status='delayed').count(),
            }
        })

class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Task.objects.all()
        employee_id = self.request.query_params.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def perform_create(self, serializer):
        if self.request.user.role != 'admin':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Faqat adminlar vazifa yarata oladi.")
        serializer.save()

    @action(detail=True, methods=['post'])
    def start_task(self, request, pk=None):
        task = self.get_object()
        task.status = 'in_progress'
        task.started_at = timezone.now()
        task.save()
        return Response(TaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def complete_task(self, request, pk=None):
        task = self.get_object()
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save()
        return Response(TaskSerializer(task).data)

class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def clock_in(self, request):
        today = timezone.localdate()
        attendance, created = Attendance.objects.get_or_create(
            employee=request.user,
            date=today,
            defaults={'status': 'working'}
        )
        if not created:
            return Response({"error": "Siz allaqachon ish boshlagansiz"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Also update user status
        request.user.status = 'working'
        request.user.save()
        
        return Response(AttendanceSerializer(attendance).data)

    @action(detail=False, methods=['post'])
    def clock_out(self, request):
        today = timezone.localdate()
        try:
            attendance = Attendance.objects.get(employee=request.user, date=today)
            if attendance.clock_out:
                return Response({"error": "Ish kuni allaqachon yakunlangan"}, status=status.HTTP_400_BAD_REQUEST)
            
            attendance.clock_out = timezone.now()
            attendance.status = 'finished'
            attendance.calculate_duration()
            attendance.save()

            # Auto-complete any active production tasks
            active_steps = ProductionStep.objects.filter(assigned_to=request.user, status='in_progress')
            for step in active_steps:
                # If no progress reported yet, assume full success
                if step.produced_qty == 0 and step.defect_qty == 0:
                    step.produced_qty = step.input_qty

                step.status = 'completed'
                step.completed_at = timezone.now()
                step.save()

                # Cascade to next step
                next_step = ProductionStep.objects.filter(order=step.order, sequence=step.sequence + 1).first()
                if next_step:
                    next_step.input_qty = step.produced_qty
                    next_step.save()

                ActivityLog.objects.create(
                    user=request.user,
                    action=f"Auto-completed task on clock out: {step.get_step_display()} for Order #{step.order.order_number}"
                )
            
            # Also update user status
            request.user.status = 'away'
            request.user.save()
            
            return Response(AttendanceSerializer(attendance).data)
        except Attendance.DoesNotExist:
            return Response({"error": "Ish kuni boshlanmagan"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def start_break(self, request):
        today = timezone.localdate()
        try:
            attendance = Attendance.objects.get(employee=request.user, date=today)
            if attendance.status != 'working':
                return Response({"error": "Hozirda ishlamayapsiz"}, status=status.HTTP_400_BAD_REQUEST)
            
            attendance.break_start = timezone.now()
            attendance.status = 'on_break'
            attendance.save()
            
            # Update user status
            request.user.status = 'away'
            request.user.save()
            
            return Response(AttendanceSerializer(attendance).data)
        except Attendance.DoesNotExist:
            return Response({"error": "Ish kuni boshlanmagan"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def end_break(self, request):
        today = timezone.localdate()
        try:
            attendance = Attendance.objects.get(employee=request.user, date=today)
            if attendance.status != 'on_break' or not attendance.break_start:
                return Response({"error": "Pauzada emassiz"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Calculate break duration
            duration = (timezone.now() - attendance.break_start).total_seconds() / 60
            attendance.total_break_minutes += int(duration)
            attendance.break_start = None
            attendance.status = 'working'
            attendance.save()
            
            # Update user status
            request.user.status = 'working'
            request.user.save()
            
            return Response(AttendanceSerializer(attendance).data)
        except Attendance.DoesNotExist:
            return Response({"error": "Ish kuni boshlanmagan"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def today(self, request):
        user = request.user
        target_user_id = request.query_params.get('user_id')
        
        if target_user_id and user.role == 'admin':
            try:
                user = User.objects.get(id=target_user_id)
            except (User.DoesNotExist, ValueError):
                return Response({"error": "Foydalanuvchi topilmadi"}, status=status.HTTP_404_NOT_FOUND)
                
        today = timezone.localdate()
        attendance = Attendance.objects.filter(employee=user, date=today).first()
        if attendance:
            return Response(AttendanceSerializer(attendance).data)
        return Response(None, status=status.HTTP_204_NO_CONTENT)
