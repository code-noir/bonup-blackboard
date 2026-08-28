const USAGE_ROWS = [
  { label: 'Active contracts',       value: 'Unlimited', green: true },
  { label: 'Contract Analysis',      value: 'Unlocked',  green: true },
  { label: 'Contract Counter',       value: 'Unlocked',  green: true },
  { label: 'Contract Import',        value: 'Unlocked',  green: true },
  { label: 'Businesses on account',  value: '0 of 35',   green: false, bold: true },
]

type PlanCard = {
  id: string
  label: string
  labelColor?: string
  name: string
  price: string | null
  priceSuffix: string
  description: string
  button: string
  buttonStyle: React.CSSProperties
  buttonDisabled?: boolean
  cardBorder?: string
  custom?: boolean
}

const PLANS: PlanCard[] = [
  {
    id: 'sol',
    label: 'Sol network',
    name: 'Sol Member',
    price: '$10',
    priceSuffix: '/month',
    description: 'For Sol group participants only. Assigned automatically — not available for open purchase.',
    button: 'Invitation only',
    buttonStyle: { background: '#F3F4F6', color: '#9CA3AF', border: 'none', cursor: 'default' },
    buttonDisabled: true,
  },
  {
    id: 'payg',
    label: 'Pay per use',
    name: 'Pay As You Go',
    price: '$25',
    priceSuffix: '/contract',
    description: 'No monthly fee. No lifecycle management. Pay for each contract individually.',
    button: 'Switch to this',
    buttonStyle: { background: 'white', color: '#374151', border: '1px solid #D1D5DB' },
  },
  {
    id: 'starter',
    label: 'Starter',
    name: 'Blackbòd Starter',
    price: '$19',
    priceSuffix: '/month',
    description: 'Personal identity only. Full contract lifecycle and AI assistant included.',
    button: 'Downgrade',
    buttonStyle: { background: 'white', color: '#374151', border: '1px solid #D1D5DB' },
  },
  {
    id: 'pro',
    label: 'Pro',
    name: 'Blackbòd Pro',
    price: '$149',
    priceSuffix: '/month',
    description: 'Personal + 1 business. Contract Analysis included.',
    button: 'Downgrade',
    buttonStyle: { background: 'white', color: '#374151', border: '1px solid #D1D5DB' },
  },
  {
    id: 'business',
    label: 'Business',
    name: 'Blackbòd Business',
    price: '$399',
    priceSuffix: '/month',
    description: 'Personal + up to 4 businesses. Counter unlocked.',
    button: 'Downgrade',
    buttonStyle: { background: 'white', color: '#374151', border: '1px solid #D1D5DB' },
  },
  {
    id: 'enterprise',
    label: 'Current plan',
    labelColor: '#F5A623',
    name: 'Blackbòd Enterprise',
    price: '$999',
    priceSuffix: '/month',
    description: 'Personal + up to 35 businesses. Counter, Import, and Analysis — all unlocked.',
    button: 'Active',
    buttonStyle: { background: 'white', color: '#374151', border: '1px solid #D1D5DB', cursor: 'default' },
    buttonDisabled: true,
    cardBorder: '2px solid #F5A623',
  },
  {
    id: 'custom',
    label: 'Custom',
    name: 'Need more?',
    price: null,
    priceSuffix: '',
    description: 'More than 35 businesses or high-volume contracting? We\'ll build a plan around you.',
    button: 'Contact sales',
    buttonStyle: { background: 'white', color: '#8B5CF6', border: '1px solid #8B5CF6' },
    custom: true,
  },
]

const ROW1 = PLANS.slice(0, 3)
const ROW2 = PLANS.slice(3)

export default function Billing() {
  return (
    <div style={{ background: '#F9FAFB', minHeight: '100vh' }}>
      <div style={{ maxWidth: 900, margin: '0 auto', padding: '40px 24px' }}>

        {/* Page header */}
        <div style={{ marginBottom: 32 }}>
          <h1 style={{ fontSize: 28, fontWeight: 700, color: '#0F1F3D', margin: 0 }}>
            Billing
          </h1>
          <p style={{ fontSize: 14, color: '#F5A623', marginTop: 6 }}>
            Manage your plan, payment method, and invoices.
          </p>
        </div>

        {/* Current Plan Card */}
        <div style={{
          background: 'white',
          borderRadius: 12,
          padding: 32,
          marginBottom: 32,
          border: '1px solid #E5E7EB',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
        }}>
          {/* Left */}
          <div>
            <span style={{
              border: '1px solid #F5A623',
              color: '#F5A623',
              fontSize: 11,
              fontWeight: 600,
              padding: '3px 12px',
              borderRadius: 20,
              display: 'inline-block',
              marginBottom: 16,
            }}>
              ACTIVE
            </span>
            <div style={{ fontSize: 36, fontWeight: 700, color: '#D1D5DB', lineHeight: 1.15 }}>
              Blackbòd<br />Enterprise
            </div>
            <p style={{ fontSize: 13, color: '#9CA3AF', marginTop: 8 }}>
              Personal identity · Up to 35 businesses · All features unlocked
            </p>
          </div>

          {/* Right */}
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 48, fontWeight: 300, color: '#9CA3AF', lineHeight: 1 }}>
              $999
            </div>
            <div style={{ fontSize: 13, color: '#9CA3AF' }}>per month</div>
            <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 8 }}>
              Renews{' '}
              <span style={{ fontWeight: 600, color: '#374151' }}>May 8, 2026</span>
            </div>
            <span style={{ fontSize: 13, color: '#374151', cursor: 'pointer', marginTop: 8, display: 'block' }}>
              Manage billing
            </span>
          </div>
        </div>

        {/* Two-column: Plan Usage + Payment Method */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 32,
          marginBottom: 32,
        }}>
          {/* Plan Usage */}
          <div>
            <div style={{
              fontSize: 11, fontWeight: 600, color: '#9CA3AF',
              textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 16,
            }}>
              Plan Usage
            </div>
            {USAGE_ROWS.map((row) => (
              <div
                key={row.label}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '14px 0',
                  borderBottom: '1px solid #F3F4F6',
                  fontSize: 14,
                  color: '#374151',
                }}
              >
                <span>{row.label}</span>
                <span style={{
                  color: row.green ? '#10B981' : '#374151',
                  fontWeight: row.green ? 500 : (row.bold ? 700 : 400),
                }}>
                  {row.value}
                </span>
              </div>
            ))}
          </div>

          {/* Payment Method */}
          <div>
            <div style={{
              fontSize: 11, fontWeight: 600, color: '#9CA3AF',
              textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 16,
            }}>
              Payment Method
            </div>
            <div style={{
              fontSize: 18, color: '#374151',
              letterSpacing: '0.15em', marginBottom: 12,
            }}>
              •••• •••• •••• 4242
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 10, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
                  Card Holder
                </div>
                <div style={{ fontSize: 13, color: '#374151' }}>bonup account</div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
                  Expires
                </div>
                <div style={{ fontSize: 13, color: '#374151' }}>09 / 28</div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 16 }}>
              <span style={{ fontSize: 13, color: '#8B5CF6', cursor: 'pointer' }}>Update card</span>
              <span style={{ fontSize: 13, color: '#9CA3AF', cursor: 'pointer' }}>Remove</span>
            </div>
          </div>
        </div>

        {/* Change Plan */}
        <div style={{ marginBottom: 40 }}>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: '#0F1F3D', marginBottom: 4 }}>
            Change plan
          </h2>
          <p style={{ fontSize: 13, color: '#F5A623', marginBottom: 24 }}>
            Upgrades apply immediately. Downgrades take effect at the next billing cycle.
          </p>

          {/* Row 1 — 3 cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 16 }}>
            {ROW1.map((plan) => (
              <PlanCardItem key={plan.id} plan={plan} />
            ))}
          </div>

          {/* Row 2 — 4 cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
            {ROW2.map((plan) => (
              <PlanCardItem key={plan.id} plan={plan} />
            ))}
          </div>
        </div>

        {/* Invoices */}
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: '#0F1F3D', marginBottom: 8 }}>
            Invoices
          </h2>
          <div style={{
            background: 'white',
            borderRadius: 12,
            border: '1px solid #E5E7EB',
            padding: 60,
            textAlign: 'center',
          }}>
            <div style={{ fontSize: 32, color: '#D1D5DB', marginBottom: 16 }}>🧾</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: '#0F1F3D', marginBottom: 8 }}>
              No invoices yet
            </div>
            <p style={{ fontSize: 13, color: '#9CA3AF', maxWidth: 360, margin: '0 auto' }}>
              Once Stripe is connected and billing goes live, your invoices will appear here and be available to download.
            </p>
          </div>
        </div>

      </div>
    </div>
  )
}

function PlanCardItem({ plan }: { plan: PlanCard }) {
  return (
    <div style={{
      background: 'white',
      borderRadius: 12,
      padding: 24,
      border: plan.cardBorder ?? '1px solid #E5E7EB',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      minHeight: 280,
    }}>
      <div>
        <div style={{
          fontSize: 11,
          color: plan.labelColor ?? '#9CA3AF',
          marginBottom: 8,
        }}>
          {plan.label}
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, color: '#0F1F3D', marginBottom: 8 }}>
          {plan.name}
        </div>
        {plan.custom ? (
          <div style={{ fontSize: 32, fontWeight: 700, color: '#9CA3AF', lineHeight: 1.1 }}>
            Let's talk
          </div>
        ) : (
          <div>
            <span style={{ fontSize: 28, fontWeight: 700, color: '#0F1F3D' }}>{plan.price}</span>
            <span style={{ fontSize: 13, color: '#9CA3AF' }}>{plan.priceSuffix}</span>
          </div>
        )}
        <p style={{ fontSize: 12, color: '#9CA3AF', margin: '12px 0', lineHeight: 1.6 }}>
          {plan.description}
        </p>
      </div>
      <button
        disabled={plan.buttonDisabled}
        style={{
          width: '100%',
          height: 40,
          borderRadius: 8,
          fontSize: 13,
          fontWeight: 500,
          cursor: plan.buttonDisabled ? 'default' : 'pointer',
          ...plan.buttonStyle,
        }}
      >
        {plan.button}
      </button>
    </div>
  )
}
