# Net Worth Snapshot Scheduling - Deployment Guide

## Problem Summary

Your Django application is configured to take net worth snapshots every 6 hours, but it's only taking them once per day. This is happening because:

1. **Missing APScheduler dependency** in production
2. **Scheduler not starting** in production environment
3. **Snapshots only created when visiting pages** instead of automatically

## What Was Fixed

### 1. Added APScheduler Dependency
- Added `APScheduler==3.10.4` to `requirements.txt`
- This enables the background scheduler functionality

### 2. Fixed Scheduler Configuration
- Modified `portfolio/apps.py` to work in both development and production
- Removed the `RUN_MAIN` check that was preventing production execution
- Added better error handling and logging

### 3. Improved Commands
- Enhanced `daily_networth_snapshot` command with better logging
- Created `test_snapshot` command for manual testing
- Created `check_scheduler` command to verify scheduler status

## Deployment Steps for Production (PythonAnywhere)

### Step 1: Update Requirements
```bash
# In your PythonAnywhere console
pip install APScheduler==3.10.4
```

### Step 2: Update Code
Upload the modified files to your PythonAnywhere project:
- `requirements.txt` (with APScheduler added)
- `portfolio/apps.py` (fixed scheduler configuration)
- `portfolio/management/commands/daily_networth_snapshot.py` (improved logging)
- `portfolio/management/commands/test_snapshot.py` (new test command)
- `portfolio/management/commands/check_scheduler.py` (new status command)

### Step 3: Restart Your Web App
1. Go to your PythonAnywhere Web app configuration
2. Click "Reload" to restart the application
3. This will start the scheduler with the new configuration

### Step 4: Verify Scheduler is Running
```bash
# In your PythonAnywhere console
python manage.py check_scheduler
```

### Step 5: Test Snapshot Functionality
```bash
# Test manual snapshot creation
python manage.py test_snapshot --username mateussfeir

# Check recent snapshots
python manage.py shell -c "from portfolio.models import NetWorthSnapshot; snapshots = NetWorthSnapshot.objects.filter(user__username='mateussfeir').order_by('-date')[:5]; [print(f'{s.date}: ${s.net_worth:,.2f}') for s in snapshots]"
```

## Expected Behavior After Fix

1. **Automatic Snapshots**: Every 6 hours, the system will automatically create/update net worth snapshots for all users
2. **Better Logging**: You'll see detailed logs when snapshots are created or updated
3. **Consistent Data**: Snapshots will be taken regardless of user activity

## Monitoring

### Check Scheduler Status
```bash
python manage.py check_scheduler
```

### View Recent Snapshots
```bash
python manage.py shell -c "from portfolio.models import NetWorthSnapshot; snapshots = NetWorthSnapshot.objects.all().order_by('-date')[:10]; [print(f'{s.user.username} - {s.date}: ${s.net_worth:,.2f}') for s in snapshots]"
```

### Manual Snapshot Creation
```bash
python manage.py daily_networth_snapshot
```

## Troubleshooting

### If Scheduler Still Not Working
1. Check PythonAnywhere logs for errors
2. Verify APScheduler is installed: `pip list | grep APScheduler`
3. Restart the web app again
4. Check if there are any import errors in the console

### If Snapshots Still Not Creating
1. Test manual creation: `python manage.py test_snapshot`
2. Check for errors in the net worth calculation
3. Verify database permissions

## Current Configuration

- **Frequency**: Every 6 hours
- **Currency**: USD (for consistency)
- **Users**: All active users
- **Storage**: NetWorthSnapshot model in database

The scheduler will automatically start when your Django application loads and will continue running in the background. 