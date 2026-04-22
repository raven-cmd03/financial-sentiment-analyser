import type { ModelInfo } from "@/types";

interface ModelComparisonProps {
  models: ModelInfo[];
}

export default function ModelComparison({ models }: ModelComparisonProps) {
  if (models.length === 0) {
    return (
      <div className="text-center text-sm text-gray-500 py-8">
        No models available for comparison.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-700">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-700 bg-gray-800/50">
            <th className="px-4 py-3 text-xs font-medium text-gray-400">
              Model
            </th>
            <th className="px-4 py-3 text-xs font-medium text-gray-400">
              Base
            </th>
            <th className="px-4 py-3 text-xs font-medium text-gray-400 text-right">
              Accuracy
            </th>
            <th className="px-4 py-3 text-xs font-medium text-gray-400 text-right">
              F1 Score
            </th>
            <th className="px-4 py-3 text-xs font-medium text-gray-400 text-center">
              Status
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700/50">
          {models.map((m) => (
            <tr
              key={m.id}
              className={`transition-colors hover:bg-gray-800/50 ${
                m.is_active ? "bg-blue-500/5" : ""
              }`}
            >
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-200">{m.name}</span>
                  {m.is_active && (
                    <span className="rounded-full bg-blue-500/20 px-2 py-0.5 text-[10px] font-semibold text-blue-400">
                      ACTIVE
                    </span>
                  )}
                </div>
              </td>
              <td className="px-4 py-3 text-gray-400">{m.base_model}</td>
              <td className="px-4 py-3 text-right text-gray-200">
                {m.accuracy !== undefined
                  ? `${(m.accuracy * 100).toFixed(1)}%`
                  : "—"}
              </td>
              <td className="px-4 py-3 text-right text-gray-200">
                {m.f1_score !== undefined ? m.f1_score.toFixed(3) : "—"}
              </td>
              <td className="px-4 py-3 text-center">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    m.is_active ? "bg-emerald-400" : "bg-gray-600"
                  }`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
