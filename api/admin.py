from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, Client, Material, Product, Order, ProductionStep, Invoice,
    PricingSettings, SettingsLog, EmployeeEfficiency, MachineSettings,
    Supplier, MaterialBatch, WarehouseLog,
    SystemLock, Calendar, Shift, Reservation,
    ReworkLog, ChartOfAccounts, JournalEntry, JournalEntryLine, PriceVersion,
    MachineDowntime,
    ProductTemplate, ProductTemplateLayer, ProductTemplateRouting, MaterialNormative,
    WorkerTimeLog
)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'avatar_url')}),
    )

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'company', 'phone', 'email', 'pricing_profile', 'created_at')
    search_fields = ('full_name', 'company', 'phone')
    list_filter = ('pricing_profile', 'status')

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'current_stock', 'unit', 'min_stock')
    list_filter = ('category',)
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'box_type', 'created_at')
    search_fields = ('name', 'box_type')

class ProductionStepInline(admin.TabularInline):
    model = ProductionStep
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'client', 'status', 'quantity', 'total_price', 'pricing_profile_used', 'deadline')
    list_filter = ('status', 'client', 'pricing_profile_used')
    search_fields = ('order_number', 'client__full_name')
    inlines = [ProductionStepInline]

@admin.register(ProductionStep)
class ProductionStepAdmin(admin.ModelAdmin):
    list_display = ('order', 'step', 'status', 'assigned_to', 'started_at', 'completed_at')
    list_filter = ('step', 'status', 'assigned_to')

admin.site.register(Supplier)
admin.site.register(WarehouseLog)

# Phase 1: Infrastructure Models
admin.site.register(SystemLock)
admin.site.register(Calendar)
admin.site.register(Shift)
admin.site.register(Reservation)

@admin.register(MaterialBatch)
class MaterialBatchAdmin(admin.ModelAdmin):
    list_display = ('batch_number', 'material', 'supplier', 'initial_quantity', 'current_quantity', 'received_date')
    search_fields = ('batch_number', 'material__name', 'supplier__name')
    list_filter = ('received_date', 'supplier')

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'order', 'amount', 'status', 'due_date')
    list_filter = ('status',)

@admin.register(PricingSettings)
class PricingSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'profit_margin_percent', 'exchange_rate', 'tax_percent', 'default_pricing_profile')
    
    def has_add_permission(self, request):
        # Only one settings instance should exist
        return not PricingSettings.objects.exists()

@admin.register(SettingsLog)
class SettingsLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'setting_type', 'old_value', 'new_value', 'created_at')
    list_filter = ('setting_type', 'user', 'created_at')
    search_fields = ('setting_type',)
    readonly_fields = ('user', 'setting_type', 'old_value', 'new_value', 'created_at')

@admin.register(EmployeeEfficiency)
class EmployeeEfficiencyAdmin(admin.ModelAdmin):
    list_display = ('employee', 'production_stage', 'units_per_hour', 'error_rate_percent', 'hourly_labor_cost', 'effective_from')
    list_filter = ('production_stage', 'employee', 'effective_from')
    search_fields = ('employee__username', 'employee__first_name', 'employee__last_name')

@admin.register(MachineSettings)
class MachineSettingsAdmin(admin.ModelAdmin):
    list_display = ('machine_name', 'machine_type', 'hourly_rate', 'setup_time_minutes', 'is_active')
    list_filter = ('machine_type', 'is_active')
    search_fields = ('machine_name',)

# Phase 2: Advanced Business Models
admin.site.register(ReworkLog)
admin.site.register(ChartOfAccounts)
admin.site.register(JournalEntry)
admin.site.register(JournalEntryLine)
admin.site.register(PriceVersion)

# Phase 4: Production Optimization
admin.site.register(MachineDowntime)


# Phase 7: Product Template System
class ProductTemplateLayerInline(admin.TabularInline):
    model = ProductTemplateLayer
    extra = 1
    filter_horizontal = ('compatible_materials',)

class ProductTemplateRoutingInline(admin.TabularInline):
    model = ProductTemplateRouting
    extra = 1

class MaterialNormativeInline(admin.TabularInline):
    model = MaterialNormative
    extra = 1

@admin.register(ProductTemplate)
class ProductTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'layer_count', 'default_waste_percent', 'is_active', 'created_at')
    list_filter = ('category', 'is_active', 'layer_count')
    search_fields = ('name', 'description')
    inlines = [ProductTemplateLayerInline, ProductTemplateRoutingInline, MaterialNormativeInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category', 'layer_count', 'description', 'is_active')
        }),
        ('Default Dimensions', {
            'fields': ('default_width', 'default_height', 'default_depth'),
            'classes': ('collapse',)
        }),
        ('Waste Configuration', {
            'fields': ('default_waste_percent',)
        }),
    )

@admin.register(ProductTemplateLayer)
class ProductTemplateLayerAdmin(admin.ModelAdmin):
    list_display = ('template', 'layer_number', 'material_category', 'min_density', 'max_density')
    list_filter = ('template', 'material_category')
    filter_horizontal = ('compatible_materials',)

@admin.register(ProductTemplateRouting)
class ProductTemplateRoutingAdmin(admin.ModelAdmin):
    list_display = ('template', 'sequence', 'step_name', 'required_machine_type', 'qc_checkpoint', 'is_optional')
    list_filter = ('template', 'step_name', 'qc_checkpoint', 'is_optional')
    ordering = ('template', 'sequence')

@admin.register(MaterialNormative)
class MaterialNormativeAdmin(admin.ModelAdmin):
    list_display = ('product_template', 'material_type', 'color_count', 'consumption_per_unit', 'unit_of_measure', 'waste_percent', 'effective_from')
    list_filter = ('product_template', 'material_type', 'color_count', 'effective_from')
    search_fields = ('product_template__name',)
    date_hierarchy = 'effective_from'

# Phase 8: Worker Time Tracking
@admin.register(WorkerTimeLog)
class WorkerTimeLogAdmin(admin.ModelAdmin):
    list_display = ('production_step', 'worker', 'action', 'timestamp', 'pause_reason', 'location')
    list_filter = ('action', 'worker', 'pause_reason', 'timestamp')
    search_fields = ('worker__username', 'production_step__order__order_number', 'notes')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
