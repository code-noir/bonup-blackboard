import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

// Tier: 'Free Trial' | 'Sol Member' | 'As You Go' | 'Blackboard Basic' | 'Blackboard Pro' | 'Blackboard Business' | 'Blackboard Premium'
const USER_TIER = 'Blackboard Business'

export default function Dashboard() {
  const navigate = useNavigate()
  const { user, isOnTrial, trialDaysRemaining, hasTrialExpired } = useAuth()
  return (
    <div className="space-y-6">
      <p style={{ fontSize: 13, color: '#9CA3AF', paddingTop: 14, paddingBottom: 14 }}>
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
            style={{ background: '#fff', borderRadius: 11, padding: '18px 20px', border: '1px solid rgba(0,0,0,0.05)' }}
          >
            <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#9CA3AF' }}>{label}</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
          </div>
        ))}
      </div>

      {/* Trial banner — active */}
      {isOnTrial() && (() => {
        const days = trialDaysRemaining()
        const pct = Math.min(100, ((30 - days) / 30) * 100)
        return (
          <div style={{
            background: 'linear-gradient(to right, #0F1F3D, #1a3460)',
            borderRadius: 11, padding: '20px 24px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <div>
              <p style={{ fontSize: 14, fontWeight: 600, color: 'white', margin: 0 }}>
                🎉 Your free trial
              </p>
              <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)', marginTop: 4 }}>
                {days} days remaining — Full Blackboard Pro access included
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <div>
                <div style={{ width: 200, height: 4, background: 'rgba(255,255,255,0.2)', borderRadius: 2 }}>
                  <div style={{ width: `${pct}%`, height: '100%', background: '#2DD4BF', borderRadius: 2 }} />
                </div>
                <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', marginTop: 4, textAlign: 'right' }}>
                  {days} days left
                </p>
              </div>
              <button
                onClick={() => navigate('/settings')}
                style={{
                  background: '#F5A623', color: '#0F1F3D',
                  border: 'none', borderRadius: 8,
                  padding: '8px 16px', fontSize: 12,
                  fontWeight: 600, cursor: 'pointer',
                  marginLeft: 16,
                }}
                onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.9')}
                onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
              >
                Choose a Plan
              </button>
            </div>
          </div>
        )
      })()}

      {/* Trial banner — expired */}
      {hasTrialExpired() && (
        <div style={{
          background: 'rgba(220,38,38,0.08)',
          border: '1px solid rgba(220,38,38,0.2)',
          borderRadius: 11, padding: '16px 24px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div>
            <p style={{ fontSize: 14, fontWeight: 600, color: '#DC2626', margin: 0 }}>
              ⚠️ Your trial has ended
            </p>
            <p style={{ fontSize: 12, color: '#6B7280', marginTop: 4 }}>
              Subscribe to create new contracts. Your existing contracts are safe for 1 year.
            </p>
          </div>
          <button
            onClick={() => navigate('/settings')}
            style={{
              background: '#0F1F3D', color: 'white',
              border: 'none', borderRadius: 8,
              padding: '8px 16px', fontSize: 12,
              fontWeight: 600, cursor: 'pointer',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
          >
            Choose a Plan
          </button>
        </div>
      )}

      {/* Sol Member banner */}
      {user?.subscription_tier === 'sol_member' && (
        <div style={{
          background: '#E0F2FE',
          border: '1px solid #BAE6FD',
          borderRadius: 8,
          padding: '12px 16px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <p style={{ fontSize: 13, color: '#075985', margin: 0, fontWeight: 500 }}>
            ◎ Sol Member — Saving with your community. $10/month
          </p>
        </div>
      )}

      {/* Power Tools */}
      <div>
        <p style={{ fontSize: 14, fontWeight: 600, color: '#0F1F3D', marginBottom: 14 }}>Power Tools</p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          {/* Contract Analysis card */}
          <div style={{
            background: 'white', borderRadius: 11, padding: 20,
            border: '1px solid rgba(0,0,0,0.05)',
          }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>🔍</div>
            <p style={{ fontSize: 14, fontWeight: 600, color: '#0F1F3D', margin: 0 }}>Contract Analysis</p>
            <p style={{ fontSize: 12, color: '#6B7280', margin: '8px 0 16px' }}>
              Get a full AI-powered breakdown of any contract before you sign.
            </p>
            {USER_TIER === 'As You Go' && (
              <div style={{ marginBottom: 12 }}>
                <span style={{
                  display: 'inline-block', fontSize: 11, color: '#D97706',
                  background: '#FEF3C7', borderRadius: 4, padding: '2px 8px',
                  marginBottom: 4,
                }}>
                  $25 per contract · $25 per analysis · $25 per counter
                </span>
              </div>
            )}
            <button
              onClick={() => navigate('/analysis')}
              style={{
                display: 'block', height: 32, padding: '0 16px',
                background: '#0F1F3D', color: 'white',
                border: 'none', borderRadius: 8,
                fontSize: 12, fontWeight: 500, cursor: 'pointer',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
            >
              Analyze a Contract
            </button>
          </div>

          {/* Contract Counter card */}
          <div style={{
            background: 'white', borderRadius: 11, padding: 20,
            border: '1px solid rgba(0,0,0,0.05)',
          }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>⚡</div>
            <p style={{ fontSize: 14, fontWeight: 600, color: '#0F1F3D', margin: 0 }}>Contract Counter</p>
            <p style={{ fontSize: 12, color: '#6B7280', margin: '8px 0 16px' }}>
              Respond to any contract with a professional AI-powered counter.
            </p>
            {USER_TIER === 'As You Go' && (
              <div style={{ marginBottom: 12 }}>
                <span style={{
                  display: 'inline-block', fontSize: 11, color: '#D97706',
                  background: '#FEF3C7', borderRadius: 4, padding: '2px 8px',
                  marginBottom: 4,
                }}>
                  $25 per contract · $25 per analysis · $25 per counter
                </span>
              </div>
            )}
            {(USER_TIER === 'Blackboard Basic' || USER_TIER === 'Sol Member') ? (
              <>
                <div style={{ fontSize: 20, marginBottom: 8 }}>🔒</div>
                <button
                  onClick={() => navigate('/counter')}
                  style={{
                    display: 'block', height: 32, padding: '0 16px',
                    background: '#F5A623', color: '#0F1F3D',
                    border: 'none', borderRadius: 8,
                    fontSize: 12, fontWeight: 500, cursor: 'pointer',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
                  onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                >
                  Upgrade to Blackboard Pro — $149/month
                </button>
              </>
            ) : (
              <button
                onClick={() => navigate('/counter')}
                style={{
                  display: 'block', height: 32, padding: '0 16px',
                  background: '#0F1F3D', color: 'white',
                  border: 'none', borderRadius: 8,
                  fontSize: 12, fontWeight: 500, cursor: 'pointer',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
                onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
              >
                Counter a Contract
              </button>
            )}
          </div>
        </div>
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
