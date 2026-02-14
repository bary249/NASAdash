"""
Timeframe logic per spec Section 2.
Provides date range calculations for CM, PM, and YTD.
"""
from datetime import datetime, date
from calendar import monthrange
from typing import Tuple
from app.models import Timeframe


def get_date_range(timeframe: Timeframe, reference_date: date = None) -> Tuple[date, date]:
    """
    Calculate date range based on timeframe.
    
    Args:
        timeframe: CM (Current Month), PM (Previous Month), or YTD (Year-to-Date)
        reference_date: Reference date (defaults to today)
    
    Returns:
        Tuple of (start_date, end_date)
    
    Logic per spec:
    - CM: 1st day of current month to "Current Timestamp"
    - PM: 1st to last day of preceding month (static benchmark)
    - YTD: January 1st to "Current Timestamp"
    """
    if reference_date is None:
        reference_date = date.today()
    
    if timeframe == Timeframe.CM:
        # Current Month: 1st of current month to now
        start = reference_date.replace(day=1)
        end = reference_date
        
    elif timeframe == Timeframe.PM:
        # Previous Month: Full previous month (static)
        if reference_date.month == 1:
            prev_year = reference_date.year - 1
            prev_month = 12
        else:
            prev_year = reference_date.year
            prev_month = reference_date.month - 1
        
        start = date(prev_year, prev_month, 1)
        _, last_day = monthrange(prev_year, prev_month)
        end = date(prev_year, prev_month, last_day)
        
    elif timeframe == Timeframe.L30:
        # Last 30 Days: 30 days ago to now
        from datetime import timedelta
        start = reference_date - timedelta(days=30)
        end = reference_date
    
    elif timeframe == Timeframe.L7:
        # Last 7 Days: 7 days ago to now
        from datetime import timedelta
        start = reference_date - timedelta(days=7)
        end = reference_date
    
    elif timeframe == Timeframe.YTD:
        # Year-to-Date: Jan 1st to now
        start = date(reference_date.year, 1, 1)
        end = reference_date
    
    else:
        # Default to current month
        start = reference_date.replace(day=1)
        end = reference_date
    
    return start, end


def format_date_yardi(d: date) -> str:
    """Format date for Yardi API (MM/DD/YYYY)."""
    return d.strftime("%m/%d/%Y")


def format_date_iso(d: date) -> str:
    """Format date as ISO (YYYY-MM-DD)."""
    return d.isoformat()


def parse_yardi_date(date_str: str) -> date:
    """Parse Yardi date format (M/D/YYYY or MM/DD/YYYY) to date object."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%m/%d/%Y").date()
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None


def days_between(d1: date, d2: date) -> int:
    """Calculate days between two dates."""
    if d1 is None or d2 is None:
        return 0
    return abs((d2 - d1).days)


def is_within_days(target_date: date, reference_date: date, days: int) -> bool:
    """Check if target_date is within N days of reference_date (future)."""
    if target_date is None or reference_date is None:
        return False
    diff = (target_date - reference_date).days
    return 0 <= diff <= days


def is_in_period(target_date: date, start: date, end: date) -> bool:
    """Check if target_date falls within the period."""
    if target_date is None:
        return False
    return start <= target_date <= end
