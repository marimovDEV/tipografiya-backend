from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import models
from rest_framework.test import APIClient
from rest_framework import status
from .models import Client, Order, Material, ProductionStep, PricingSettings
from decimal import Decimal

User = get_user_model()

class AuthenticationTests(TestCase):
    """Test authentication and authorization"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role='project_manager'
        )
    
    def test_login_success(self):
        """Test successful login"""
        response = self.client.post('/api/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertIn('user', response.data)
    
    def test_login_failure(self):
        """Test failed login with wrong credentials"""
        response = self.client.post('/api/login/', {
            'username': 'testuser',
            'password': 'wrongpass'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_protected_endpoint_without_auth(self):
        """Test that protected endpoints require authentication"""
        response = self.client.get('/api/orders/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_protected_endpoint_with_auth(self):
        """Test that authenticated users can access protected endpoints"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/orders/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ClientTests(TestCase):
    """Test Client model and API"""
    
    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role='project_manager'
        )
        self.client_api.force_authenticate(user=self.user)
    
    def test_create_client(self):
        """Test creating a new client"""
        data = {
            'full_name': 'Test Client',
            'company': 'Test Company',
            'phone': '+998901234567',
            'email': 'test@example.com'
        }
        response = self.client_api.post('/api/customers/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Client.objects.count(), 1)
        self.assertEqual(Client.objects.first().full_name, 'Test Client')
    
    def test_list_clients(self):
        """Test listing all clients"""
        Client.objects.create(
            full_name='Client 1',
            created_by=self.user
        )
        Client.objects.create(
            full_name='Client 2',
            created_by=self.user
        )
        response = self.client_api.get('/api/customers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)


class OrderTests(TestCase):
    """Test Order model and API"""
    
    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role='project_manager'
        )
        self.client_api.force_authenticate(user=self.user)
        self.client_obj = Client.objects.create(
            full_name='Test Client',
            created_by=self.user
        )
    
    def test_create_order(self):
        """Test creating a new order"""
        data = {
            'client_id': self.client_obj.id,
            'box_type': 'Pizza Box',
            'quantity': 1000,
            'paper_type': 'coated',
            'paper_density': 300,
            'print_colors': '4+0',
            'total_price': 500000,
            'status': 'pending'
        }
        response = self.client_api.post('/api/orders/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertTrue(order.order_number.startswith('ORD-'))
    
    def test_order_number_uniqueness(self):
        """Test that order numbers are unique"""
        Order.objects.create(
            client=self.client_obj,
            box_type='Box 1',
            quantity=100,
            created_by=self.user
        )
        Order.objects.create(
            client=self.client_obj,
            box_type='Box 2',
            quantity=200,
            created_by=self.user
        )
        order_numbers = list(Order.objects.values_list('order_number', flat=True))
        self.assertEqual(len(order_numbers), len(set(order_numbers)))


class CalculationTests(TestCase):
    """Test calculation service"""
    
    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role='project_manager'
        )
        self.client_api.force_authenticate(user=self.user)
        
        # Create pricing settings
        PricingSettings.objects.create(
            paper_price_per_kg=15000,
            ink_price_per_kg=120000,
            lacquer_price_per_kg=100000,
            plate_cost=40000,
            setup_cost=50000,
            run_cost_per_box=50,
            profit_margin_percent=20
        )
    
    def test_calculate_order_cost(self):
        """Test order cost calculation"""
        data = {
            'quantity': 1000,
            'paper_width': 70,
            'paper_height': 100,
            'paper_density': 300,
            'print_colors': '4+0',
            'lacquer_type': 'none'
        }
        response = self.client_api.post('/api/orders/calculate/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('cost', response.data)
        self.assertIn('materials', response.data)
        self.assertIn('estimated_deadline', response.data)
        self.assertGreater(response.data['cost']['total_price'], 0)


class MaterialTests(TestCase):
    """Test Material/Inventory management"""
    
    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role='warehouse'
        )
        self.client_api.force_authenticate(user=self.user)
    
    def test_create_material(self):
        """Test creating a new material"""
        data = {
            'name': 'Coated Paper',
            'category': 'paper',
            'unit': 'kg',
            'current_stock': 1000,
            'min_stock': 100
        }
        response = self.client_api.post('/api/inventory/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Material.objects.count(), 1)
    
    def test_low_stock_detection(self):
        """Test low stock detection"""
        Material.objects.create(
            name='Low Stock Item',
            current_stock=50,
            min_stock=100
        )
        Material.objects.create(
            name='Normal Stock Item',
            current_stock=500,
            min_stock=100
        )
        low_stock = Material.objects.filter(current_stock__lt=models.F('min_stock'))
        self.assertEqual(low_stock.count(), 1)
