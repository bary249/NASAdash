
// RealPage Report Key Extractor
(function() {
    console.log('🔍 RealPage Report Monitor Active');
    
    const reports = {};
    
    // Intercept fetch requests
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const url = args[0];
        
        if (url.includes('reportingapi.realpage.com/v1/reports/') && 
            url.includes('/report-instances')) {
            
            // Extract report ID from URL
            const match = url.match(/\/reports\/(\d+)\/report-instances/);
            if (match) {
                const reportId = match[1];
                
                // Get the request body
                if (args[1] && args[1].body) {
                    try {
                        const body = JSON.parse(args[1].body);
                        const reportKey = body.reportKey;
                        
                        if (reportKey) {
                            reports[reportId] = {
                                reportKey: reportKey,
                                reportFormat: body.reportFormat,
                                reportFormatName: body.reportFormatName,
                                timestamp: new Date().toISOString(),
                                url: url
                            };
                            
                            console.log('✅ Captured Report:', {
                                id: reportId,
                                key: reportKey,
                                format: body.reportFormatName,
                                time: new Date().toLocaleTimeString()
                            });
                        }
                    } catch (e) {
                        console.log('Could not parse body:', e);
                    }
                }
            }
        }
        
        return originalFetch.apply(this, args);
    };
    
    // Function to export captured reports
    window.exportCapturedReports = function() {
        console.log('\n📊 Captured Reports:');
        console.log(JSON.stringify(reports, null, 2));
        
        // Also copy to clipboard
        const text = JSON.stringify(reports, null, 2);
        navigator.clipboard.writeText(text).then(() => {
            console.log('📋 Copied to clipboard!');
        });
        
        return reports;
    };
    
    // Function to generate Python code for the reports
    window.generatePythonCode = function() {
        let code = '# Discovered RealPage Reports\n';
        code += 'KNOWN_REPORTS = {\n';
        
        for (const [id, info] of Object.entries(reports)) {
            code += `    "report_${id}": {\n`;
            code += `        "report_id": ${id},\n`;
            code += `        "report_key": "${info.reportKey}",\n`;
            code += `        "description": "Report ${id} (${info.reportFormatName})",\n`;
            code += `    },\n`;
        }
        
        code += '}\n\n';
        code += '# Use like:\n';
        code += '# client.download_report(report_id=4153, report_key="...")';
        
        console.log('\n🐍 Python Code:');
        console.log(code);
        
        return code;
    };
    
    console.log('💡 Commands:');
    console.log('  exportCapturedReports() - Show all captured reports');
    console.log('  generatePythonCode() - Generate Python code for reports');
    console.log('\n📝 Now trigger different reports in the UI...');
})();
