"""
Leasing Report Parser - Parses RealPage leasing reports into funnel metrics.
READ-ONLY: Only parses Excel files, no data modifications.
"""
import xlrd


def _safe_int(value):
    try:
        if value == '' or value is None:
            return 0
        return int(float(value))
    except (ValueError, TypeError):
        return 0


def parse_online_leasing_summary(file_path):
    wb = xlrd.open_workbook(file_path)
    sheet = wb.sheet_by_index(0)
    
    property_name = ""
    report_date = ""
    date_range = ""
    
    for i in range(min(20, sheet.nrows)):
        for j in range(sheet.ncols):
            val = str(sheet.cell_value(i, j)).strip()
            if val.startswith("Date range:"):
                date_range = val.replace("Date range:", "").strip()
        if sheet.ncols > 14:
            date_val = str(sheet.cell_value(i, 14)).strip()
            if "/" in date_val and len(date_val) > 8:
                report_date = date_val.split()[0] if " " in date_val else date_val
    
    for i in range(10, 20):
        for j in range(sheet.ncols):
            val = str(sheet.cell_value(i, j)).strip()
            if val and val not in ['', 'Total', 'GuestCards', 'Online'] and not val.startswith('Date'):
                if i + 2 < sheet.nrows:
                    next_val = str(sheet.cell_value(i + 2, 3)).strip()
                    if 'GuestCards' in next_val or next_val.replace('.', '').isdigit():
                        property_name = val
                        break
        if property_name:
            break
    
    total_gc = apps = screenings = docusign = rp_esign = ofsa = 0
    
    for i in range(15, sheet.nrows):
        row_vals = [sheet.cell_value(i, j) for j in range(min(15, sheet.ncols))]
        if isinstance(row_vals[3], (int, float)) and row_vals[3] > 0:
            col2 = str(row_vals[2]).strip().lower()
            if 'total' not in col2:
                total_gc = _safe_int(row_vals[3])
                apps = _safe_int(row_vals[6])
                screenings = _safe_int(row_vals[8])
                docusign = _safe_int(row_vals[10])
                rp_esign = _safe_int(row_vals[12])
                ofsa = _safe_int(row_vals[13])
                break
    
    return {
        "property_name": property_name,
        "report_date": report_date,
        "date_range": date_range,
        "guest_cards": total_gc,
        "applications": apps,
        "screenings": screenings,
        "leases_signed": docusign + rp_esign + ofsa,
    }


def parse_leasing_activity_summary(file_path):
    wb = xlrd.open_workbook(file_path)
    sheet = wb.sheet_by_index(0)
    
    total_visits = 0
    in_consultant_section = False
    
    for i in range(sheet.nrows):
        row_vals = [sheet.cell_value(i, j) for j in range(min(15, sheet.ncols))]
        col1 = str(row_vals[1]).strip() if len(row_vals) > 1 else ""
        
        if "Summary By Leasing Consultant" in col1:
            in_consultant_section = True
            continue
        elif "Summary By Floor Plan" in col1:
            break
        
        if in_consultant_section and col1 == 'Totals':
            total_visits = _safe_int(row_vals[9])
            break
    
    return {"total_visits": total_visits}


def parse_leasing_funnel(funnel_file, activity_file):
    """Parse both reports and return funnel metrics matching LeasingFunnelMetrics type."""
    funnel_data = parse_online_leasing_summary(funnel_file)
    activity_data = parse_leasing_activity_summary(activity_file)
    
    leads = funnel_data["guest_cards"]
    tours = activity_data["total_visits"]
    apps = funnel_data["applications"]
    leases = funnel_data["leases_signed"]
    
    lead_to_tour = round((tours / leads * 100), 1) if leads > 0 else 0
    tour_to_app = round((apps / tours * 100), 1) if tours > 0 else 0
    app_to_lease = round((leases / apps * 100), 1) if apps > 0 else 0
    lead_to_lease = round((leases / leads * 100), 1) if leads > 0 else 0
    
    # Return snake_case to match LeasingFunnelMetrics type
    return {
        "property_name": funnel_data["property_name"],
        "report_date": funnel_data["report_date"],
        "date_range": funnel_data["date_range"],
        "leads": leads,
        "tours": tours,
        "applications": apps,
        "lease_signs": leases,
        "denials": 0,
        "lead_to_tour_rate": lead_to_tour,
        "tour_to_app_rate": tour_to_app,
        "app_to_lease_rate": app_to_lease,
        "lead_to_lease_rate": lead_to_lease,
    }
