export default function Dashboard() {
  return (
    <div className="space-y-6">
      <p className="py-4 text-sm text-slate-500">
        Here's what's happening across your contracts and obligations.
      </p>

      {/* Stat cards */}
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
            <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
          </div>
        ))}
      </div>

      {/* Recent Activity */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="mb-4 text-base font-semibold text-slate-800">Recent Activity</h3>
        <p className="text-sm text-slate-500">Activity feed coming soon.</p>
      </div>

      {/* Contracts Overview */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="mb-4 text-base font-semibold text-slate-800">Contracts Overview</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs font-medium uppercase tracking-wide text-slate-400">
                <th className="pb-3 pr-6">Contract ID</th>
                <th className="pb-3 pr-6">Party</th>
                <th className="pb-3 pr-6">Status</th>
                <th className="pb-3 pr-6">Amount</th>
                <th className="pb-3">Due Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {[
                { id: 'CON-00091', party: 'Meridian Labs', status: 'Active',    amount: '$12,500', due: '2026-05-01' },
                { id: 'CON-00087', party: 'Vanta Digital', status: 'Pending',   amount: '$4,200',  due: '2026-04-18' },
                { id: 'CON-00083', party: 'Orin Staffing', status: 'Active',    amount: '$8,750',  due: '2026-06-15' },
                { id: 'CON-00079', party: 'Clearpath Inc', status: 'Completed', amount: '$3,000',  due: '2026-03-30' },
                { id: 'CON-00072', party: 'Fenix Creative', status: 'Active',   amount: '$21,000', due: '2026-07-01' },
              ].map((row) => (
                <tr key={row.id} className="text-slate-700">
                  <td className="py-3 pr-6 font-mono text-xs text-slate-500">{row.id}</td>
                  <td className="py-3 pr-6 font-medium">{row.party}</td>
                  <td className="py-3 pr-6">
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      row.status === 'Active'    ? 'bg-green-50 text-green-700' :
                      row.status === 'Pending'   ? 'bg-yellow-50 text-yellow-700' :
                                                   'bg-slate-100 text-slate-500'
                    }`}>
                      {row.status}
                    </span>
                  </td>
                  <td className="py-3 pr-6">{row.amount}</td>
                  <td className="py-3 text-slate-500">{row.due}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Upcoming Obligations */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="mb-4 text-base font-semibold text-slate-800">Upcoming Obligations</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { type: 'Payment',  status: 'ACTIVE', due: '2026-04-10' },
            { type: 'Delivery', status: 'ACTIVE', due: '2026-04-14' },
            { type: 'Review',   status: 'ACTIVE', due: '2026-04-20' },
            { type: 'Sign-off', status: 'ACTIVE', due: '2026-04-28' },
          ].map((ob, i) => (
            <div key={i} className="rounded-lg border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-800">{ob.type}</p>
              <span className="mt-1 inline-flex rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                {ob.status}
              </span>
              <p className="mt-2 text-xs text-slate-400">Due {ob.due}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Payments */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="mb-4 text-base font-semibold text-slate-800">Recent Payments</h3>
        <div className="divide-y divide-slate-100">
          {[
            { amount: '$4,200',  from: 'Vanta Digital',  to: 'bonUP Sol',     date: '2026-04-01', status: 'Settled'  },
            { amount: '$1,500',  from: 'Orin Staffing',  to: 'Clearpath Inc', date: '2026-03-28', status: 'Settled'  },
            { amount: '$12,500', from: 'Meridian Labs',  to: 'bonUP Sol',     date: '2026-03-22', status: 'Pending'  },
          ].map((pmt, i) => (
            <div key={i} className="flex items-center justify-between py-3 text-sm">
              <div>
                <p className="font-semibold text-slate-800">{pmt.amount}</p>
                <p className="text-xs text-slate-400">{pmt.from} → {pmt.to}</p>
              </div>
              <div className="text-right">
                <p className="text-xs text-slate-500">{pmt.date}</p>
                <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                  pmt.status === 'Settled' ? 'bg-green-50 text-green-700' : 'bg-yellow-50 text-yellow-700'
                }`}>
                  {pmt.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Upcoming Live Sessions */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="mb-4 text-base font-semibold text-slate-800">Upcoming Live Sessions</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {[
            { name: 'Q2 Contract Review',    date: '2026-04-12', time: '2:00 PM', participants: 'You, Meridian Labs' },
            { name: 'Onboarding — Fenix Co', date: '2026-04-17', time: '10:30 AM', participants: 'You, Fenix Creative' },
          ].map((session, i) => (
            <div key={i} className="rounded-lg border border-slate-200 p-4">
              <p className="font-semibold text-slate-800">{session.name}</p>
              <p className="mt-1 text-xs text-slate-500">{session.date} at {session.time}</p>
              <p className="mt-1 text-xs text-slate-400">{session.participants}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
