"""
Locking Service for concurrent editing protection.
Provides context manager and decorator for easy lock management.
"""

from django.utils import timezone
from functools import wraps
from contextlib import contextmanager
from .models import SystemLock


class LockError(Exception):
    """Raised when lock cannot be acquired"""
    pass


@contextmanager
def entity_lock(entity_type, entity_id, user, duration_minutes=10, reason='editing'):
    """
    Context manager for entity locking.
    
    Usage:
        with entity_lock('order', order_id, user):
            # ... perform operations
            order.save()
    """
    lock, error = SystemLock.acquire_lock(
        entity_type=entity_type,
        entity_id=str(entity_id),
        user=user,
        duration_minutes=duration_minutes,
        reason=reason
    )
    
    if error:
        raise LockError(error)
    
    try:
        yield lock
    finally:
        # Release lock when context exits
        SystemLock.release_lock(entity_type, str(entity_id), user)


def requires_lock(entity_type_field, entity_id_field='pk', duration_minutes=10):
    """
    Decorator for views that require entity locking.
    
    Usage:
        @requires_lock('order', 'pk')
        def update_order(self, request, pk=None):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(view_instance, request, *args, **kwargs):
            entity_type = entity_type_field
            entity_id = kwargs.get(entity_id_field) or request.data.get(entity_id_field)
            
            if not entity_id:
                raise ValueError(f"Entity ID not found in kwargs or request data")
            
            user = request.user
            
            # Try to acquire lock
            lock, error = SystemLock.acquire_lock(
                entity_type=entity_type,
                entity_id=str(entity_id),
                user=user,
                duration_minutes=duration_minutes
            )
            
            if error:
                from rest_framework.response import Response
                from rest_framework import status
                return Response(
                    {'error': error, 'locked': True},
                    status=status.HTTP_423_LOCKED
                )
            
            try:
                # Execute the view function
                result = func(view_instance, request, *args, **kwargs)
                return result
            finally:
                # Release lock after execution
                SystemLock.release_lock(entity_type, str(entity_id), user)
        
        return wrapper
    return decorator


def check_lock_status(entity_type, entity_id):
    """
    Check if an entity is currently locked.
    Returns (is_locked, locked_by_username, expires_at) tuple.
    """
    # Clean expired locks first
    SystemLock.objects.filter(expires_at__lt=timezone.now()).delete()
    
    try:
        lock = SystemLock.objects.get(
            entity_type=entity_type,
            entity_id=str(entity_id)
        )
        return True, lock.locked_by.username, lock.expires_at
    except SystemLock.DoesNotExist:
        return False, None, None


def release_all_user_locks(user):
    """Release all locks held by a user (e.g., on logout)"""
    count = SystemLock.objects.filter(locked_by=user).delete()[0]
    return count


def cleanup_expired_locks():
    """Clean up all expired locks. Should be run periodically."""
    count = SystemLock.objects.filter(expires_at__lt=timezone.now()).delete()[0]
    return count
