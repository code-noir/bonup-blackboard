export default function Dashboard() {
  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500">
        Here's what's happening across your contracts and obligations.
      </p>

      {/* Placeholder stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: 'Active Contracts', value: '—' },
          { label: 'Obligations Due', value: '—' },
          { label: 'Pending Payments', value: '—' },
          { label: 'Upcoming Sessions', value: '—' },
        ].map(({ label, value }) => (
          <div
            key={label}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <p className="text-sm text-slate-500">{label}</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">
              {value}
            </p>
          </div>
        ))}
      </div>

      {/* Placeholder content area */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="mb-4 text-base font-semibold text-slate-800">
          Recent Activity
        </h3>
        <p className="text-sm text-slate-500">
          Activity feed coming soon.
        </p>
      </div>
    </div>
  )
}
