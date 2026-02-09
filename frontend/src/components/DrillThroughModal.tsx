import { X } from 'lucide-react';

interface Column {
  key: string;
  label: string;
  format?: (value: unknown) => string;
  cellClassName?: (value: unknown) => string;
}

interface DrillThroughModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any[];
  columns: Column[];
  loading?: boolean;
}

export function DrillThroughModal({
  isOpen,
  onClose,
  title,
  data,
  columns,
  loading = false,
}: DrillThroughModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="fixed inset-0 bg-black/50" onClick={onClose} />
        <div className="relative bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[80vh] flex flex-col">
          <div className="flex items-center justify-between p-4 border-b">
            <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
            <button
              onClick={onClose}
              className="p-1 hover:bg-gray-100 rounded"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
          <div className="flex-1 overflow-auto p-4">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
                <span className="ml-3 text-gray-500">Loading...</span>
              </div>
            ) : data.length === 0 ? (
              <div className="text-center py-12 text-gray-500">No data available</div>
            ) : (
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    {columns.map((col) => (
                      <th
                        key={col.key}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                      >
                        {col.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {data.map((row, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      {columns.map((col) => (
                        <td key={col.key} className={`px-4 py-3 text-sm whitespace-nowrap ${col.cellClassName ? col.cellClassName(row[col.key]) : 'text-gray-900'}`}>
                          {col.format
                            ? col.format(row[col.key])
                            : String(row[col.key] ?? '—')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="p-4 border-t bg-gray-50 text-sm text-gray-500">
            {data.length} record{data.length !== 1 ? 's' : ''}
          </div>
        </div>
      </div>
    </div>
  );
}
