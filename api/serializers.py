from rest_framework import serializers
from django.db import models
from .models import (
    User, Client, Material, Product, Order, ProductionStep, 
    Invoice, PricingSettings, ActivityLog, Transaction,
    Supplier, MaterialBatch, WarehouseLog, SettingsLog,
    EmployeeEfficiency, MachineSettings,
    SystemLock, Calendar, Shift, Reservation, OrderGeometry,
    WasteMaterial, MonthlyPlan, Task, Attendance,
    ProductionTemplate, TemplateStage, ProductionLog
)

class OrderGeometrySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderGeometry
        fields = '__all__'

class PricingSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingSettings
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'role', 
            'avatar_url', 'password', 'phone', 'telegram_id', 'status',
            'department', 'shift', 'supervisor', 'assigned_stages',
            'is_active', 'daily_target', 'quality_rating'
        ]

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create_user(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance

class ClientSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    total_orders = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    
    class Meta:
        model = Client
        fields = '__all__'
        
    def get_balance(self, obj):
        # Calculate balance: Total Payments - Total Orders
        # Negative means debt, Positive means credit
        total_orders = self.get_total_orders(obj)
        total_paid = self.get_total_paid(obj)
        return total_paid - total_orders

    def get_total_orders(self, obj):
        return obj.orders.exclude(status='rejected').aggregate(models.Sum('total_price'))['total_price__sum'] or 0

    def get_total_paid(self, obj):
        return obj.transactions.filter(type='income').aggregate(models.Sum('amount'))['amount__sum'] or 0

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'

class MaterialBatchSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source='supplier.name')
    material_name = serializers.ReadOnlyField(source='material.name')

    class Meta:
        model = MaterialBatch
        fields = '__all__'

class MaterialSerializer(serializers.ModelSerializer):
    batches = MaterialBatchSerializer(many=True, read_only=True)
    available_quantity = serializers.SerializerMethodField()
    available_colors = serializers.SerializerMethodField()
    
    class Meta:
        model = Material
        fields = '__all__'

    def get_available_quantity(self, obj):
        """Calculate total available quantity from active batches"""
        batches = MaterialBatch.objects.filter(
            material=obj, 
            is_active=True
        ).exclude(quality_status='blocked')
        return batches.aggregate(models.Sum('current_quantity'))['current_quantity__sum'] or 0

    def get_available_colors(self, obj):
        """Get unique available colors from active batches"""
        batches = MaterialBatch.objects.filter(
            material=obj,
            is_active=True,
            color__isnull=False
        ).exclude(quality_status='blocked')
        return list(batches.values_list('color', flat=True).distinct())

class WasteMaterialSerializer(serializers.ModelSerializer):
    material_name = serializers.ReadOnlyField(source='material.name')
    material_unit = serializers.ReadOnlyField(source='material.unit')

    class Meta:
        model = WasteMaterial
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'

class WarehouseLogSerializer(serializers.ModelSerializer):
    material_name = serializers.ReadOnlyField(source='material.name')
    product_name = serializers.ReadOnlyField(source='product.name')
    user_name = serializers.ReadOnlyField(source='user.username')
    batch_number = serializers.ReadOnlyField(source='material_batch.batch_number')

    class Meta:
        model = WarehouseLog
        fields = '__all__'

class TemplateStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateStage
        fields = '__all__'

class ProductionTemplateSerializer(serializers.ModelSerializer):
    stages = TemplateStageSerializer(many=True, read_only=True)
    
    class Meta:
        model = ProductionTemplate
        fields = '__all__'

class ProductionLogSerializer(serializers.ModelSerializer):
    worker_name = serializers.ReadOnlyField(source='worker.get_full_name')

    class Meta:
        model = ProductionLog
        fields = ['id', 'worker', 'worker_name', 'produced_qty', 'defect_qty', 'notes', 'created_at']

class ProductionStepSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()
    production_logs = ProductionLogSerializer(many=True, read_only=True)
    order_number = serializers.ReadOnlyField(source='order.order_number')
    product_name = serializers.ReadOnlyField(source='order.box_type')
    step_name_display = serializers.CharField(source='get_step_display', read_only=True)
    deadline = serializers.ReadOnlyField(source='order.deadline')
    client_name = serializers.ReadOnlyField(source='order.client.full_name')
    quantity = serializers.ReadOnlyField(source='order.quantity')
    all_steps = serializers.SerializerMethodField()
    # Order Specs
    dimensions = serializers.ReadOnlyField(source='order.dimensions')
    paper_type = serializers.ReadOnlyField(source='order.paper_type')
    paper_density = serializers.ReadOnlyField(source='order.paper_density')
    print_colors = serializers.ReadOnlyField(source='order.print_colors')
    print_type = serializers.ReadOnlyField(source='order.print_type')
    lacquer_type = serializers.ReadOnlyField(source='order.lacquer_type')
    cutting_type = serializers.ReadOnlyField(source='order.cutting_type')
    mockup_url = serializers.ReadOnlyField(source='order.mockup_url')
    additional_processing = serializers.ReadOnlyField(source='order.additional_processing')
    order_notes = serializers.ReadOnlyField(source='order.notes')
    # Book Specs
    book_name = serializers.ReadOnlyField(source='order.book_name')
    page_count = serializers.ReadOnlyField(source='order.page_count')
    cover_type = serializers.ReadOnlyField(source='order.cover_type')
    binding_type = serializers.ReadOnlyField(source='order.binding_type')
    paper_weight = serializers.ReadOnlyField(source='order.paper_weight')
    cover_weight = serializers.ReadOnlyField(source='order.cover_weight')
    lamination = serializers.ReadOnlyField(source='order.lamination')
    format = serializers.ReadOnlyField(source='order.format')

    class Meta:
        model = ProductionStep
        fields = [
            'id', 'order', 'step', 'sequence', 'input_qty', 'status', 'assigned_to', 'assigned_to_name',
            'started_at', 'completed_at', 'notes', 'produced_qty', 'defect_qty',
            'created_at', 'machine', 'estimated_start',
            'estimated_end', 'estimated_duration_minutes', 'actual_duration_minutes',
            'priority', 'queue_position', 'order_number', 'product_name',
            'step_name_display', 'deadline', 'client_name', 'quantity',
            'available_qty', 'is_ready_to_start', 'production_logs', 'progress_percent',
            'all_steps', 'dimensions', 'paper_type', 'paper_density', 'print_colors',
            'print_type', 'lacquer_type', 'cutting_type', 'mockup_url',
            'additional_processing', 'order_notes', 'book_name', 'page_count',
            'cover_type', 'binding_type', 'paper_weight', 'cover_weight',
            'lamination', 'format'
        ]

    def get_assigned_to_name(self, obj):
        return obj.assigned_to.username if obj.assigned_to else "Biriktirilmagan"

    def get_progress_percent(self, obj):
        if obj.status == 'completed':
            return 100
        produced = obj.produced_qty or 0
        input_q = obj.input_qty or 0
        if input_q > 0:
            return round((produced / input_q) * 100)
        return 0

    def get_all_steps(self, obj):
        steps = obj.order.production_steps.all().order_by('sequence')
        return [
            {
                "id": str(s.id),
                "step": s.step,
                "sequence": s.sequence,
                "status": s.status,
                "step_display": s.get_step_display()
            } for s in steps
        ]

class OrderSerializer(serializers.ModelSerializer):
    client = ClientSerializer(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(), source='client', write_only=True
    )
    template = ProductionTemplateSerializer(read_only=True)
    template_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductionTemplate.objects.all(), source='template', write_only=True, required=False, allow_null=True
    )
    production_steps = ProductionStepSerializer(many=True, read_only=True)
    production_time_hours = serializers.SerializerMethodField()
    is_delayed = serializers.SerializerMethodField()
    overall_progress = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'client', 'client_id', 'total_price', 'total_cost', 'advance_payment',
            'payment_status', 'status', 'deadline', 'completed_at', 'box_type',
            'quantity', 'price_per_unit', 'paper_type', 'paper_density', 'print_colors', 'lacquer_type',
            'cutting_type', 'print_type', 'template',
            'template_id', 'production_steps', 'production_time_hours', 'is_delayed',
            'overall_progress', 'book_name', 'page_count', 'cover_type',
            'binding_type', 'paper_weight', 'cover_weight', 'lamination', 'format'
        ]

    def get_overall_progress(self, obj):
        steps = obj.production_steps.all()
        if not steps:
            return 0
        
        total_progress = 0
        for s in steps:
            if s.status == 'completed':
                total_progress += 100
            else:
                input_q = s.input_qty or 0
                produced = s.produced_qty or 0
                if input_q > 0:
                    total_progress += round((produced / input_q) * 100)
                    
        return round(total_progress / len(steps))

    def validate(self, data):
        """
        Debt Control Logic: Check if client has exceeded credit limit.
        """
        client = data.get('client')
        # Note: client comes as PK from client_id write_only field, but 'client' read_only field won't be in data on input.
        # We need to get client from the input data.
        
        # In create/update, client is passed via client_id (primary key)
        # DRF automatically looks up the instance for PrimaryKeyRelatedField if passing instance to serializer, 
        # but in 'data' before save it might be just the ID or the object depending on validation stage.
        # Let's check 'client' source='client' write_only field
        
        # 'client' field in Meta is read_only serializer. 'client_id' is write_only.
        # So we look for 'client' from client_id field.
        
        # Actually, for validate(), 'client' key corresponds to the source='client' field from client_id.
        client_obj = data.get('client')
        
        if client_obj:
            current_debt = client_obj.current_debt
            credit_limit = client_obj.credit_limit
            
            # If client is already over limit
            if current_debt > credit_limit:
                 raise serializers.ValidationError({
                    "non_field_errors": [
                        f"DIQQAT: Mijoz qarzdorligi limitdan oshgan! (Qarz: {current_debt:,.0f} / Limit: {credit_limit:,.0f}). Yangi buyurtma yaratish taqiqlanadi."
                    ]
                })
        
        return data

    def get_production_time_hours(self, obj):
        steps = obj.production_steps.all()
        start = steps.filter(started_at__isnull=False).order_by('started_at').first()
        end = steps.filter(completed_at__isnull=False).order_by('-completed_at').first()
        if start and end and start.started_at and end.completed_at:
            diff = end.completed_at - start.started_at
            return round(diff.total_seconds() / 3600, 1)
        return None

    def get_is_delayed(self, obj):
        if obj.deadline and obj.completed_at:
            return obj.completed_at > obj.deadline
        if obj.deadline and obj.status not in ['completed', 'delivered', 'canceled']:
            from django.utils import timezone
            return timezone.now() > obj.deadline
        return False

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get('request')
        
        # Hide internal financial data for non-admins/non-accountants
        is_staff = request and request.user.is_authenticated and (request.user.role in ['admin', 'accountant'])
        
        if not is_staff:
            ret.pop('total_price', None)
            
        return ret

class InvoiceSerializer(serializers.ModelSerializer):
    order_number = serializers.ReadOnlyField(source='order.order_number')
    client_name = serializers.ReadOnlyField(source='order.client.full_name')

    class Meta:
        model = Invoice
        fields = '__all__'

class ActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source='user.username')
    class Meta:
        model = ActivityLog
        fields = '__all__'

class TransactionSerializer(serializers.ModelSerializer):
    client_name = serializers.ReadOnlyField(source='client.full_name')
    worker_name = serializers.ReadOnlyField(source='worker.get_full_name')
    
    class Meta:
        model = Transaction
        fields = '__all__'

class SettingsLogSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source='user.username')
    class Meta:
        model = SettingsLog
        fields = '__all__'


class EmployeeEfficiencySerializer(serializers.ModelSerializer):
    employee_name = serializers.ReadOnlyField(source='employee.username')
    employee_full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeEfficiency
        fields = '__all__'
    
    def get_employee_full_name(self, obj):
        if obj.employee.first_name or obj.employee.last_name:
            return f"{obj.employee.first_name} {obj.employee.last_name}".strip()
        return obj.employee.username


class MachineSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MachineSettings
        fields = '__all__'


# ========================================
# PHASE 1: INFRASTRUCTURE SERIALIZERS
# ========================================

class SystemLockSerializer(serializers.ModelSerializer):
    locked_by_name = serializers.ReadOnlyField(source='locked_by.username')
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = SystemLock
        fields = '__all__'
    
    def get_is_expired(self, obj):
        from django.utils import timezone
        return obj.expires_at < timezone.now()


class CalendarSerializer(serializers.ModelSerializer):
    day_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Calendar
        fields = '__all__'
    
    def get_day_name(self, obj):
        days = ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba']
        return days[obj.date.weekday()]


class ShiftSerializer(serializers.ModelSerializer):
    duration_hours = serializers.ReadOnlyField()
    
    class Meta:
        model = Shift
        fields = '__all__'


class ReservationSerializer(serializers.ModelSerializer):
    material_name = serializers.ReadOnlyField(source='material.name')
    batch_number = serializers.ReadOnlyField(source='material_batch.batch_number')
    order_number = serializers.ReadOnlyField(source='order.order_number')
    
    class Meta:
        model = Reservation
        fields = '__all__'


class MonthlyPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyPlan
        fields = '__all__'
class TaskSerializer(serializers.ModelSerializer):
    employee_name = serializers.ReadOnlyField(source='employee.get_full_name')
    employee_username = serializers.ReadOnlyField(source='employee.username')

    class Meta:
        model = Task
        fields = ['id', 'title', 'description', 'employee', 'employee_name', 'employee_username', 'deadline', 'priority', 'status', 'started_at', 'completed_at', 'created_at']

class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.ReadOnlyField(source='employee.get_full_name')

    class Meta:
        model = Attendance
        fields = '__all__'
