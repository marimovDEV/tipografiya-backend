"""
Phase 1: Core Infrastructure Tests
Tests for BaseModel, SystemLock, Calendar, Shift, and Reservation
"""

from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta, date, time
from django.contrib.auth import get_user_model
from api.models import (
    SystemLock, Calendar, Shift, Reservation,
    Material, MaterialBatch, Order, Client, Supplier
)
from api.locking import entity_lock, LockError, check_lock_status
from api.calendar_utils import (
    populate_calendar_year, add_holiday, 
    calculate_deadline, get_production_capacity
)

User = get_user_model()


class SystemLockTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user2 = User.objects.create_user(username='user2', password='pass')
    
    def test_acquire_lock_success(self):
        """Test successful lock acquisition"""
        lock, error = SystemLock.acquire_lock('order', '123', self.user1)
        self.assertIsNotNone(lock)
        self.assertIsNone(error)
        self.assertEqual(lock.locked_by, self.user1)
    
    def test_acquire_lock_conflict(self):
        """Test lock conflict when another user holds the lock"""
        # User1 acquires lock
        SystemLock.acquire_lock('order', '123', self.user1)
        
        # User2 tries to acquire same lock
        lock, error = SystemLock.acquire_lock('order', '123', self.user2)
        self.assertIsNone(lock)
        self.assertIsNotNone(error)
        self.assertIn('user1', error)
    
    def test_release_lock(self):
        """Test lock release"""
        SystemLock.acquire_lock('order', '123', self.user1)
        SystemLock.release_lock('order', '123', self.user1)
        
        # Should be able to acquire again
        lock, error = SystemLock.acquire_lock('order', '123', self.user2)
        self.assertIsNotNone(lock)
    
    def test_expired_lock_cleanup(self):
        """Test that expired locks are cleaned up"""
        # Create an expired lock
        expired_time = timezone.now() - timedelta(hours=1)
        SystemLock.objects.create(
            entity_type='order',
            entity_id='123',
            locked_by=self.user1,
            expires_at=expired_time
        )
        
        # Try to acquire lock - should clean up expired and succeed
        lock, error = SystemLock.acquire_lock('order', '123', self.user2)
        self.assertIsNotNone(lock)
        self.assertEqual(lock.locked_by, self.user2)
    
    def test_context_manager(self):
        """Test entity_lock context manager"""
        with entity_lock('order', '123', self.user1):
            # Lock should be held
            is_locked, by_who, _ = check_lock_status('order', '123')
            self.assertTrue(is_locked)
            self.assertEqual(by_who, 'user1')
        
        # Lock should be released after context
        is_locked, _, _ = check_lock_status('order', '123')
        self.assertFalse(is_locked)
    
    def test_context_manager_conflict(self):
        """Test context manager raises LockError on conflict"""
        # User1 holds lock
        SystemLock.acquire_lock('order', '123', self.user1, duration_minutes=60)
        
        # User2 should get LockError
        with self.assertRaises(LockError):
            with entity_lock('order', '123', self.user2):
                pass


class CalendarTestCase(TestCase):
    def test_populate_calendar_year(self):
        """Test calendar population for a year"""
        count = populate_calendar_year(2026)
        self.assertEqual(count, 365)  # 2026 is not a leap year
        
        # Check weekends are marked as non-working
        saturday = Calendar.objects.get(date=date(2026, 1, 3))  # Saturday
        self.assertFalse(saturday.is_working_day)
        
        # Check weekdays are marked as working
        monday = Calendar.objects.get(date=date(2026, 1, 5))  # Monday
        self.assertTrue(monday.is_working_day)
    
    def test_add_holiday(self):
        """Test adding a holiday"""
        holiday_date = date(2026, 1, 1)
        calendar_day = add_holiday(holiday_date, "New Year")
        
        self.assertFalse(calendar_day.is_working_day)
        self.assertEqual(calendar_day.notes, "New Year")
        self.assertEqual(calendar_day.shift_count, 0)
    
    def test_working_days_count(self):
        """Test working days calculation"""
        populate_calendar_year(2026)
        
        # January 5-9, 2026 (Mon-Fri) = 5 working days
        start = date(2026, 1, 5)
        end = date(2026, 1, 9)
        
        count = Calendar.get_working_days_count(start, end)
        self.assertEqual(count, 5)
    
    def test_add_working_days(self):
        """Test adding working days to a date"""
        populate_calendar_year(2026)
        
        # Starting from Monday Jan 5, add 5 working days
        start = date(2026, 1, 5)
        result = Calendar.add_working_days(start, 5)
        
        # Should be Friday Jan 9 (skipping weekend)
        expected = date(2026, 1, 9)
        self.assertEqual(result, expected)
    
    def test_calculate_deadline(self):
        """Test deadline calculation"""
        populate_calendar_year(2026)
        
        start = date(2026, 1, 5)  # Monday
        deadline = calculate_deadline(start, 5)  # 5 working days
        
        expected = date(2026, 1, 9)  # Friday
        self.assertEqual(deadline, expected)


class ShiftTestCase(TestCase):
    def test_shift_duration_normal(self):
        """Test shift duration for normal day shift"""
        shift = Shift.objects.create(
            name="Morning",
            start_time=time(8, 0),
            end_time=time(17, 0),
            capacity_multiplier=1.0
        )
        
        self.assertEqual(shift.duration_hours, 9.0)
    
    def test_shift_duration_overnight(self):
        """Test shift duration for overnight shift"""
        shift = Shift.objects.create(
            name="Night",
            start_time=time(22, 0),
            end_time=time(6, 0),
            capacity_multiplier=0.8
        )
        
        self.assertEqual(shift.duration_hours, 8.0)
    
    def test_production_capacity(self):
        """Test production capacity calculation"""
        # Create shifts
        Shift.objects.create(
            name="Day",
            start_time=time(8, 0),
            end_time=time(17, 0),
            capacity_multiplier=1.0,
            is_active=True
        )
        
        # Populate calendar
        populate_calendar_year(2026)
        
        # Calculate capacity for a week (Jan 5-9, 2026 = 5 working days)
        capacity = get_production_capacity(date(2026, 1, 5), date(2026, 1, 9))
        
        # 5 days * 9 hours = 45 hours
        self.assertEqual(capacity, 45.0)


class ReservationTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.client = Client.objects.create(
            full_name="Test Client",
            created_by=self.user
        )
        self.supplier = Supplier.objects.create(name="Test Supplier")
        
        # Create material
        self.material = Material.objects.create(
            name="Paper A4",
            category="paper",
            unit="kg",
            current_stock=100
        )
        
        # Create batch
        self.batch = MaterialBatch.objects.create(
            material=self.material,
            supplier=self.supplier,
            batch_number="BATCH-001",
            initial_quantity=100,
            current_quantity=100
        )
        
        # Create order
        self.order = Order.objects.create(
            client=self.client,
            quantity=100,
            created_by=self.user
        )
    
    def test_reserve_materials(self):
        """Test material reservation"""
        material_usage = {
            self.material.id: 10  # Reserve 10 kg
        }
        
        reservations = Reservation.reserve_materials(self.order, material_usage)
        
        self.assertEqual(len(reservations), 1)
        self.assertEqual(float(reservations[0].reserved_qty), 10.0)
        self.assertEqual(reservations[0].order, self.order)
        self.assertFalse(reservations[0].consumed)
    
    def test_reservation_fifo(self):
        """Test FIFO reservation from multiple batches"""
        # Create older batch
        old_batch = MaterialBatch.objects.create(
            material=self.material,
            supplier=self.supplier,
            batch_number="BATCH-OLD",
            initial_quantity=20,
            current_quantity=20,
            received_date=date(2025, 1, 1)
        )
        
        # Reserve 30 kg (should take 20 from old, 10 from new)
        material_usage = {self.material.id: 30}
        reservations = Reservation.reserve_materials(self.order, material_usage)
        
        self.assertEqual(len(reservations), 2)
        # First reservation should be from older batch
        self.assertEqual(reservations[0].material_batch, old_batch)
        self.assertEqual(float(reservations[0].reserved_qty), 20.0)
    
    def test_consume_reservation(self):
        """Test reservation consumption"""
        material_usage = {self.material.id: 10}
        reservations = Reservation.reserve_materials(self.order, material_usage)
        
        reservation = reservations[0]
        initial_batch_qty = self.batch.current_quantity
        
        reservation.consume()
        
        # Refresh from DB
        self.batch.refresh_from_db()
        reservation.refresh_from_db()
        
        self.assertTrue(reservation.consumed)
        self.assertIsNotNone(reservation.consumed_at)
        self.assertEqual(self.batch.current_quantity, initial_batch_qty - 10)
    
    def test_insufficient_stock_error(self):
        """Test error when insufficient stock"""
        material_usage = {self.material.id: 200}  # More than available
        
        with self.assertRaises(ValueError) as context:
            Reservation.reserve_materials(self.order, material_usage)
        
        self.assertIn("Insufficient stock", str(context.exception))


print("✅ Phase 1 Tests Created")
