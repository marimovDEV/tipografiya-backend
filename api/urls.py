from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, ClientViewSet, MaterialViewSet,
    ProductViewSet, OrderViewSet, ProductionStepViewSet, InvoiceViewSet,
    ProductionTemplateViewSet, TemplateStageViewSet
)
from .optimizer_views import (
    OptimizationView, DownloadDXFView, DielinePreviewView
)
from .views import (
    TransactionViewSet,
    SupplierViewSet, MaterialBatchViewSet, WarehouseLogViewSet, SettingsLogViewSet,
    CalculateOrderView, PricingSettingsView, ReportsView, LoginView, DashboardView,
    EmployeeEfficiencyViewSet, MachineSettingsViewSet, CalculationPreviewView, UpdateCurrencyRateView,
    WasteMaterialViewSet, TaskViewSet, AttendanceViewSet
)
from .qc_views import (
    QCCheckpointViewSet, qc_statistics, defect_trends, my_inspections, PreflightCheckView
)
from .pricing_views import PricingCalculationView
from .phase3_views import (
    PriceLockView, ManualOverrideView, PriceHistoryView,
    ScenarioListView, CapacityStatusView, PriceVersionListView
)
from .phase4_views import (
    BottleneckAnalysisView, ParallelFlowAnalysisView, MachineDowntimeViewSet,
    MachineAvailabilityView, SmartAssignmentView, WorkloadRebalanceView
)
from .phase5_views import (
    SetupAccountsView, TrialBalanceView, BalanceSheetView,
    GrossMarginKPIView, OrderProfitabilityView, EmployeeROIView,
    MachineROIView, FinancialDashboardView, RecordSaleView,
    MonthlyPlanView
)
from .phase6_views import (
    RunAutomationChecksView, DeadlineAlertsView, BottleneckAlertsView, TriggerWorkflowView
)
from .template_views import (
    ProductTemplateViewSet, ProductTemplateLayerViewSet, ProductTemplateRoutingViewSet,
    MaterialNormativeViewSet, WorkerTimeLogViewSet
)
from .warehouse_views import (
    block_batch, unblock_batch, expiring_batches, low_stock_alerts,
    validate_order_materials, get_compatible_materials, get_material_suggestions,
    warehouse_status_report
)
from .scheduling_views import (
    get_machine_queue, assign_step_to_machine, optimize_machine_queue,
    calculate_step_times, schedule_order_production, get_production_analytics,
    update_step_priority, get_machine_availability
)
from .auth_views import login, logout, me

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'customers', ClientViewSet)
router.register(r'inventory', MaterialViewSet)
router.register(r'products', ProductViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'production', ProductionStepViewSet, basename='production')
router.register(r'production-templates', ProductionTemplateViewSet, basename='production-templates')
router.register(r'template-stages', TemplateStageViewSet, basename='template-stages')
router.register(r'invoices', InvoiceViewSet)
router.register(r'transactions', TransactionViewSet)
router.register(r'suppliers', SupplierViewSet)
router.register(r'batches', MaterialBatchViewSet)
router.register(r'warehouse-logs', WarehouseLogViewSet)
router.register(r'settings/logs', SettingsLogViewSet)
router.register(r'settings/employee-efficiency', EmployeeEfficiencyViewSet, basename='employee-efficiency')
router.register(r'settings/machines', MachineSettingsViewSet, basename='machines')
router.register(r'waste-materials', WasteMaterialViewSet, basename='waste-materials')
router.register(r'tasks', TaskViewSet)
router.register(r'attendance', AttendanceViewSet)

# Phase 7: Product Template System
router.register(r'product-templates', ProductTemplateViewSet, basename='product-templates')
router.register(r'product-template-layers', ProductTemplateLayerViewSet, basename='product-template-layers')
router.register(r'product-template-routing', ProductTemplateRoutingViewSet, basename='product-template-routing')
router.register(r'material-normatives', MaterialNormativeViewSet, basename='material-normatives')

# Phase 8: Worker Time Tracking
router.register(r'worker-time-logs', WorkerTimeLogViewSet, basename='worker-time-logs')

urlpatterns = [
    path('orders/calculate/', CalculateOrderView.as_view(), name='calculate-order'),
    path('settings/', PricingSettingsView.as_view(), name='settings-root'), # Fix for 404
    path('settings/pricing/', PricingSettingsView.as_view(), name='pricing-settings'),
    # Phase 5: Constructor
    path('dieline/preview/', DielinePreviewView.as_view(), name='dieline-preview'),
    
    # Phase 7: Optimization
    path('optimization/nesting/', OptimizationView.as_view(), name='nesting-optimize'),
    path('optimization/export-dxf/', DownloadDXFView.as_view(), name='export-dxf'),
    path('settings/update-currency/', UpdateCurrencyRateView.as_view(), name='update-currency'),
    path('reports/', ReportsView.as_view(), name='reports'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('login/', LoginView.as_view(), name='login'),
    path('orders/<int:pk>/print/', OrderViewSet.as_view({'get': 'print_receipt'}), name='order-print'),
    
    # Phase 3: Advanced Business Logic
    path('orders/<int:order_id>/lock-price/', PriceLockView.as_view(), name='lock-price'),
    path('warehouse/request-material/', MaterialViewSet.as_view({'post': 'request_material'}), name='request-material'),
    path('orders/<int:order_id>/override-price/', ManualOverrideView.as_view(), name='override-price'),
    path('orders/<int:order_id>/price-history/', PriceHistoryView.as_view(), name='price-history'),
    path('pricing/scenarios/', ScenarioListView.as_view(), name='pricing-scenarios'),
    path('pricing/calculate/', PricingCalculationView.as_view(), name='pricing-calculate'),
    path('pricing/versions/', PriceVersionListView.as_view(), name='price-versions'),
    path('production/capacity/', CapacityStatusView.as_view(), name='capacity-status'),
    
    # Phase 4: Production Optimization
    path('production/bottlenecks/', BottleneckAnalysisView.as_view(), name='bottleneck-analysis'),
    path('production/orders/<int:order_id>/parallel-flow/', ParallelFlowAnalysisView.as_view(), name='parallel-flow'),
    path('production/machine-downtime/', MachineDowntimeViewSet.as_view({'get': 'list', 'post': 'create'}), name='machine-downtime'),
    path('production/machine-downtime/<int:pk>/', MachineDowntimeViewSet.as_view({'patch': 'partial_update'}), name='machine-downtime-detail'),
    path('production/machines/availability/', MachineAvailabilityView.as_view(), name='machine-availability'),
    path('production/machines/<int:machine_id>/availability/', MachineAvailabilityView.as_view(), name='machine-availability-detail'),
    path('production/steps/<int:step_id>/smart-assign/', SmartAssignmentView.as_view(), name='smart-assign'),
    path('production/workload/rebalance/', WorkloadRebalanceView.as_view(), name='workload-rebalance'),
    
    # Phase 5: Financial Module
    path('accounting/setup/', SetupAccountsView.as_view(), name='accounting-setup'),
    path('accounting/trial-balance/', TrialBalanceView.as_view(), name='trial-balance'),
    path('accounting/balance-sheet/', BalanceSheetView.as_view(), name='balance-sheet'),
    path('accounting/orders/<int:order_id>/record-sale/', RecordSaleView.as_view(), name='record-sale'),
    path('kpi/gross-margin/', GrossMarginKPIView.as_view(), name='gross-margin-kpi'),
    path('kpi/orders/<int:order_id>/profitability/', OrderProfitabilityView.as_view(), name='order-profitability'),
    path('kpi/employees/<int:employee_id>/roi/', EmployeeROIView.as_view(), name='employee-roi'),
    path('kpi/machines/<int:machine_id>/roi/', MachineROIView.as_view(), name='machine-roi'),
    path('dashboard/financial/', FinancialDashboardView.as_view(), name='financial-dashboard'),
    path('finance/monthly-plan/', MonthlyPlanView.as_view(), name='monthly-plan'),
    
    
    # Phase 3: Pre-press & QC
    path('qc/preflight/', PreflightCheckView.as_view(), name='qc-preflight'),
    
    # Phase 7 & 8: Warehouse Enhancements & Order Validation (PrintERP TZ Sections 4 & 6)
    path('warehouse/batches/<uuid:batch_id>/block/', block_batch, name='block-batch'),
    path('warehouse/batches/<uuid:batch_id>/unblock/', unblock_batch, name='unblock-batch'),
    path('warehouse/expiring-batches/', expiring_batches, name='expiring-batches'),
    path('warehouse/low-stock-alerts/', low_stock_alerts, name='low-stock-alerts'),
    path('warehouse/status-report/', warehouse_status_report, name='warehouse-status-report'),
    
    # Order Validation
    path('orders/validate-materials/', validate_order_materials, name='validate-order-materials'),
    path('orders/compatible-materials/', get_compatible_materials, name='compatible-materials'),
    path('orders/material-suggestions/', get_material_suggestions, name='material-suggestions'),
    
    # Phase 3: Production Scheduling (PrintERP TZ Section 7)
    # The following scheduling paths are being replaced/reorganized by the new instruction.
    # path('scheduling/machines/queues/', get_machine_queue, name='all-machine-queues'),
    # path('scheduling/machines/<uuid:machine_id>/queue/', get_machine_queue, name='machine-queue'),
    # path('scheduling/machines/<uuid:machine_id>/optimize/', optimize_machine_queue, name='optimize-queue'),
    # path('scheduling/machines/<uuid:machine_id>/availability/', get_machine_availability, name='machine-availability'),
    # path('scheduling/assign-to-machine/', assign_step_to_machine, name='assign-to-machine'),
    # path('scheduling/steps/<uuid:step_id>/calculate-times/', calculate_step_times, name='calculate-step-times'),
    # path('scheduling/steps/<uuid:step_id>/update-priority/', update_step_priority, name='update-priority'),
    # path('scheduling/orders/<uuid:order_id>/schedule/', schedule_order_production, name='schedule-order'),
    # path('scheduling/analytics/', get_production_analytics, name='production-analytics'),
    
    # Scheduling
    path('production/queue/', get_machine_queue, name='machine-queue'),
    path('production/assign/', assign_step_to_machine, name='assign-step'),
    path('production/optimize/', optimize_machine_queue, name='optimize-queue'),
    path('production/calculate-times/', calculate_step_times, name='calculate-times'),
    path('production/schedule/', schedule_order_production, name='schedule-production'),
    path('production/analytics/', get_production_analytics, name='production-analytics'),
    path('production/<uuid:step_id>/priority/', update_step_priority, name='update-priority'),
    path('machines/availability/', get_machine_availability, name='machine-availability'),
    
    # Authentication
    path('auth/login/', login, name='login'),
    path('auth/logout/', logout, name='logout'),
    path('auth/me/', me, name='me'),
    
    # Router URLs
    path('', include(router.urls)),
]
