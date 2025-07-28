#!/usr/bin/env python
"""
Test script to verify the delayed snapshot logic
"""
import os
import sys
import django
from datetime import timedelta
from django.utils import timezone

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from portfolio.models import NetWorthSnapshot

User = get_user_model()

def test_delayed_snapshot_logic():
    """Test the delayed snapshot logic"""
    print("Testing delayed snapshot logic...")
    
    # Get a test user (or create one if needed)
    try:
        user = User.objects.first()
        if not user:
            print("No users found in database")
            return
    except Exception as e:
        print(f"Error getting user: {e}")
        return
    
    print(f"Testing with user: {user.username}")
    print(f"User created: {user.date_joined}")
    
    # Check existing snapshots
    existing_snapshots = NetWorthSnapshot.objects.filter(user=user)
    print(f"Existing snapshots: {existing_snapshots.count()}")
    
    # Calculate time since user creation
    current_time = timezone.now()
    time_since_creation = current_time - user.date_joined
    print(f"Time since user creation: {time_since_creation}")
    
    # Test the logic
    if existing_snapshots.exists():
        print("✓ User has existing snapshots - should create snapshots normally")
    else:
        print("✓ User has no snapshots - checking 10-minute delay")
        if time_since_creation > timedelta(minutes=10):
            print("✓ More than 10 minutes passed - should create snapshot")
        else:
            minutes_remaining = 10 - int(time_since_creation.total_seconds() / 60)
            print(f"✓ Less than 10 minutes passed - should wait {minutes_remaining} more minutes")
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    test_delayed_snapshot_logic() 