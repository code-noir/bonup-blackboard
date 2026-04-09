const CURRENT_PLAN = 'enterprise'

const PLANS = [
  {
    id: 'trial',
    name: 'Free Trial',
    price: 'Free',
    priceNum: null,
    description: '1 contract, full access, 30 days',
    features: [
      '1 contract included',
      'Full platform access',
      'Personal or business',
      'All features unlocked once',
      'No credit card required',
    ],
    actionLabel: 'Start Free Trial',
    actionStyle: { background: '#10B981', color: 'white' } as React.CSSProperties,
  },
  {
    id: 'sol_member',
    name: 'Sol Member',
    price: '$10',
    priceNum: 10,
    description: 'Community savings members',
    features: [
      'Everything in Blackboard Basic',
      'Auto-assigned when joining Sol group',
      'Personal identity only',
      'Contract Analysis included',
      'Community rate discount',
    ],
    actionLabel: 'Join a Sol Group',
    actionStyle: { background: '#6B7280', color: 'white' } as React.CSSProperties,
  },
  {
    id: 'per_contract',
    name: 'Pay As You Go',
    price: '$25',
    priceSuffix: '/use',
    priceNum: 25,
    description: 'No monthly commitment',
    features: [
      '$25 per contract created',
      '$25 per contract analysis',
      '$25 per contract counter',
      'Personal or business',
      'AI Assistant included',
      'Templates included',
      'No lifecycle management',
    ],
    actionLabel: 'Select Plan',
    actionStyle: null,
  },
  {
    id: 'basic',
    name: 'Blackboard Basic',
    price: '$19',
    priceNum: 19,
    description: 'Personal contracting',
    features: [
      'Personal identity only',
      'Unlimited contracts',
      'Contract Analysis unlimited',
      'AI Assistant',
      'Templates',
      'Contract lifecycle management',
      'Obligations tracking',
      'Payment tracking',
    ],
    actionLabel: 'Select Plan',
    actionStyle: null,
  },
  {
    id: 'pro',
    name: 'Blackboard Pro',
    price: '$149',
    priceNum: 149,
    description: 'Personal + 1 business',
    features: [
      'Personal + 1 business entity',
      'Everything in Basic',
      'Contract Counter unlocked',
      'Live Sessions',
      'Negotiation prep',
      'Priority support',
    ],
    actionLabel: 'Upgrade',
    actionStyle: null,
  },
  {
    id: 'business',
    name: 'Blackboard Business',
    price: '$399',
    priceNum: 399,
    description: 'Personal + up to 4 businesses',
    features: [
      'Personal + up to 4 businesses',
      'Everything in Pro',
      'Sol group management',
      'Multi-entity contract management',
      'Advanced analytics',
      'Team collaboration',
    ],
    actionLabel: 'Upgrade',
    actionStyle: null,
  },
  {
    id: 'enterprise',
    name: 'Blackboard Enterprise',
    price: '$999',
    priceNum: 999,
    description: 'Personal + up to 35 businesses',
    features: [
      'Personal + up to 35 businesses',
      'Everything in Business',
      'Contract Import',
      'Dedicated support',
      'Custom integrations',
      'White label options',
      'API access',
    ],
    actionLabel: 'Current Plan',
    actionStyle: null,
  },
]

const BILLING_HISTORY = [
  { date: 'Apr 9, 2026',  description: 'Blackboard Enterprise', amount: '$999.00', status: 'Paid' },
  { date: 'Mar 9, 2026',  description: 'Blackboard Enterprise', amount: '$999.00', status: 'Paid' },
  { date: 'Feb 9, 2026',  description: 'Blackboard Enterprise', amount: '$999.00', status: 'Paid' },
]

const DOWNGRADE_IDS = new Set(['trial', 'sol_member', 'per_contract', 'basic', 'pro', 'business'])

function planButton(planId: string): { label: string; style: React.CSSProperties } {
  if (planId === CURRENT_PLAN) {
    return {
      label: 'Current Plan',
      style: { background: '#E5E7EB', color: '#9CA3AF', cursor: 'default' },
    }
  }
  if (DOWNGRADE_IDS.has(planId)) {
    return {
      label: 'Switch Plan',
      style: { background: 'transparent', border: '1px solid #D1D5DB', color: '#374151' },
    }
  }
  return {
    label: 'Upgrade',
    style: { background: '#0F1F3D', color: 'white' },
  }
}

export default function Billing() {
  return (
    <div style={{ maxWidth: 900 }}>
      {/* Page header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#0F1F3D', margin: 0 }}>
          Billing &amp; Subscription
        </h1>
        <p style={{ fontSize: 13, color: '#6B7280', marginTop: 4 }}>
          Manage your plan and billing details
        </p>
      </div>

      {/* Current Plan */}
      <div style={{
        background: 'white',
        borderRadius: 11,
        padding: 24,
        marginBottom: 24,
        border: '1px solid rgba(0,0,0,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <span style={{ fontSize: 20, fontWeight: 700, color: '#0F1F3D' }}>
                Blackboard Enterprise
              </span>
              <span style={{
                background: '#D1FAE5', color: '#065F46',
                fontSize: 12, padding: '3px 10px', borderRadius: 20,
              }}>
                Active
              </span>
            </div>
            <div style={{ fontSize: 16, color: '#6B7280', marginBottom: 6 }}>$999/month</div>
            <div style={{ fontSize: 13, color: '#6B7280' }}>Next billing: May 9, 2026</div>
          </div>
          <span style={{ fontSize: 12, color: '#DC2626', cursor: 'pointer' }}>
            Cancel Subscription
          </span>
        </div>
      </div>

      {/* Available Plans */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: '#0F1F3D', marginBottom: 16 }}>
          Available Plans
        </h2>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 16,
        }}>
          {PLANS.map((plan) => {
            const isCurrent = plan.id === CURRENT_PLAN
            const btn = isCurrent
              ? { label: 'Current Plan', style: { background: '#E5E7EB', color: '#9CA3AF', cursor: 'default' } as React.CSSProperties }
              : plan.actionStyle
                ? { label: plan.actionLabel, style: plan.actionStyle }
                : planButton(plan.id)

            return (
              <div
                key={plan.id}
                style={{
                  background: 'white',
                  borderRadius: 11,
                  padding: 20,
                  border: isCurrent ? '2px solid #0F1F3D' : '1px solid rgba(0,0,0,0.06)',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
                  position: 'relative',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                {isCurrent && (
                  <span style={{
                    position: 'absolute', top: 14, right: 14,
                    background: '#0F1F3D', color: 'white',
                    fontSize: 11, padding: '3px 8px', borderRadius: 4,
                  }}>
                    Current Plan
                  </span>
                )}

                <div style={{ fontSize: 15, fontWeight: 700, color: '#0F1F3D', marginBottom: 4 }}>
                  {plan.name}
                </div>

                <div style={{ marginBottom: 0 }}>
                  <span style={{ fontSize: 22, fontWeight: 700, color: '#0F1F3D' }}>
                    {plan.price}
                  </span>
                  <span style={{ fontSize: 13, color: '#6B7280', fontWeight: 400 }}>
                    {plan.priceSuffix ?? (plan.priceNum !== null ? '/month' : '')}
                  </span>
                </div>

                <div style={{ fontSize: 12, color: '#6B7280', margin: '8px 0 16px' }}>
                  {plan.description}
                </div>

                <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 20px', flex: 1 }}>
                  {plan.features.map((f) => (
                    <li key={f} style={{ fontSize: 12, color: '#374151', lineHeight: 1.8 }}>
                      <span style={{ color: '#10B981' }}>✓</span> {f}
                    </li>
                  ))}
                </ul>

                <button
                  disabled={isCurrent}
                  style={{
                    width: '100%',
                    height: 36,
                    borderRadius: 8,
                    fontSize: 13,
                    fontWeight: 600,
                    border: 'none',
                    cursor: isCurrent ? 'default' : 'pointer',
                    ...btn.style,
                  }}
                >
                  {btn.label}
                </button>
              </div>
            )
          })}
        </div>
      </div>

      {/* Billing History */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: '#0F1F3D', marginBottom: 16 }}>
          Billing History
        </h2>
        <div style={{
          background: 'white',
          borderRadius: 11,
          overflow: 'hidden',
          border: '1px solid rgba(0,0,0,0.06)',
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#F9FAFB' }}>
                {['Date', 'Description', 'Amount', 'Status', 'Invoice'].map((col) => (
                  <th
                    key={col}
                    style={{
                      fontSize: 11, fontWeight: 600, color: '#6B7280',
                      textTransform: 'uppercase', letterSpacing: '0.06em',
                      padding: '12px 20px', textAlign: 'left',
                    }}
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {BILLING_HISTORY.map((row, i) => (
                <tr key={i} style={{ borderTop: '1px solid #F3F4F6' }}>
                  <td style={{ padding: '14px 20px', fontSize: 13, color: '#374151' }}>{row.date}</td>
                  <td style={{ padding: '14px 20px', fontSize: 13, color: '#374151' }}>{row.description}</td>
                  <td style={{ padding: '14px 20px', fontSize: 13, color: '#374151' }}>{row.amount}</td>
                  <td style={{ padding: '14px 20px' }}>
                    <span style={{
                      color: '#065F46', background: '#D1FAE5',
                      fontSize: 11, padding: '2px 8px', borderRadius: 4,
                    }}>
                      {row.status}
                    </span>
                  </td>
                  <td style={{ padding: '14px 20px' }}>
                    <span style={{ color: '#0F1F3D', fontSize: 12, cursor: 'pointer', textDecoration: 'underline' }}>
                      Download
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Payment Method */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: '#0F1F3D', marginBottom: 16 }}>
          Payment Method
        </h2>
        <div style={{
          background: 'white',
          borderRadius: 11,
          padding: 20,
          border: '1px solid rgba(0,0,0,0.06)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 22 }}>💳</span>
            <div>
              <div style={{ fontSize: 14, color: '#374151', fontWeight: 500 }}>
                •••• •••• •••• 4242
              </div>
              <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>Expires 12/27</div>
            </div>
          </div>
          <button style={{
            background: 'transparent',
            border: '1px solid #D1D5DB',
            color: '#374151',
            height: 32,
            padding: '0 16px',
            borderRadius: 8,
            fontSize: 12,
            cursor: 'pointer',
          }}>
            Update Payment Method
          </button>
        </div>
      </div>
    </div>
  )
}
