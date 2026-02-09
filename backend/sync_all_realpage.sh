#!/bin/bash
# Quick shell script to run the complete RealPage pipeline

cd "$(dirname "$0")"

echo "🚀 Starting RealPage Complete Pipeline..."
echo ""

# Run the Python pipeline script
python3 sync_all_realpage.py "$@"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "✅ Pipeline completed successfully!"
    echo "📊 Your dashboard now has the latest data."
else
    echo ""
    echo "❌ Pipeline failed. Check the output above for errors."
fi

exit $exit_code
