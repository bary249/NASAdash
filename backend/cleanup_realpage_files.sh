#!/bin/bash
# Cleanup script for RealPage report integration
# Removes test files and keeps only production-ready code

echo "🧹 Cleaning up RealPage report files..."
echo ""

# Files to KEEP
echo "✅ Keeping these core files:"
echo "   - download_parse_save.py (master script)"
echo "   - generic_report_parser.py (parser)"
echo "   - realpage_reports_master.json (master tracking)"
echo "   - realpage_token.json (API token)"
echo "   - box_score_working_config.json (working config)"
echo ""

# Remove test files
echo "🗑️ Removing test files..."
rm -f test_*.py
echo "   Removed $(ls test_*.py 2>/dev/null | wc -l) test_*.py files"

rm -f analyze_*.py
echo "   Removed $(ls analyze_*.py 2>/dev/null | wc -l) analyze_*.py files"

rm -f debug_*.py
echo "   Removed $(ls debug_*.py 2>/dev/null | wc -l) debug_*.py files"

rm -f check_*.py
echo "   Removed $(ls check_*.py 2>/dev/null | wc -l) check_*.py files"

rm -f list_*.py
echo "   Removed $(ls list_*.py 2>/dev/null | wc -l) list_*.py files"

# Remove one-off attempts
echo ""
echo "🗑️ Removing one-off attempts..."
rm -f discover_report_params.py discover_reports.py
rm -f download_box_score*.py force_download.py
rm -f final_attempt.py quick_test.py safe_discover_reports.py
echo "   Removed discovery and download attempts"

# Remove generated files
echo ""
echo "🗑️ Removing generated files..."
rm -f box_score_*.xlsx box_score_*.json
rm -f report_session_*.json report_configs.json
echo "   Removed sample downloads and session logs"

# Remove other misc test files
echo ""
echo "🗑️ Removing other test files..."
rm -f update_token_from_curl.py
echo "   Removed token update script"

echo ""
echo "✨ Cleanup complete!"
echo ""
echo "Remaining files:"
ls -la *.py *.json 2>/dev/null | grep -v "^total" | awk '{print "   " $9}' | sort
