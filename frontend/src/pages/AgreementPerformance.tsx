const PERFORMANCE_AREAS = [
  {
    title: 'Performed Obligations',
    description: 'Work and payment duties will appear here after performance begins.',
  },
  {
    title: 'Payments Made',
    description: 'Payment records will be tracked against the signed agreement.',
  },
  {
    title: 'Delivery Records',
    description: 'Delivered work and supporting records will be organized here.',
  },
]

export default function AgreementPerformance() {
  return (
    <div style={{ padding: '32px 0' }}>
      <section style={{
        background: 'white',
        border: '1px solid rgba(0,0,0,0.06)',
        borderRadius: 8,
        padding: 22,
        marginBottom: 18,
      }}>
        <p style={{
          margin: '0 0 8px',
          fontSize: 11,
          fontWeight: 800,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          color: '#047857',
        }}>
          Performance
        </p>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: '#0F1F3D', margin: 0, letterSpacing: 0 }}>
          Agreement Performance
        </h1>
        <p style={{ fontSize: 14, color: '#64748B', margin: '9px 0 0', maxWidth: 780, lineHeight: 1.55 }}>
          Track performed obligations, payments, delivery, confirmations, and records.
        </p>
      </section>

      <section style={{
        background: '#F8FAFC',
        border: '1px solid #D1FAE5',
        borderRadius: 8,
        padding: 20,
        marginBottom: 18,
      }}>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>
          Select a signed agreement to view performance records.
        </h2>
        <p style={{ fontSize: 13, color: '#475569', margin: '8px 0 0', maxWidth: 760, lineHeight: 1.6 }}>
          Performance starts when a party checks off the first performed obligation. Until then, this module stays ready without changing the signed agreement record or its timeline.
        </p>
      </section>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 14,
      }}>
        {PERFORMANCE_AREAS.map((area) => (
          <section
            key={area.title}
            style={{
              background: 'white',
              border: '1px solid #E5E7EB',
              borderRadius: 8,
              padding: 18,
              minHeight: 132,
            }}
          >
            <div style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              background: '#ECFDF5',
              border: '1px solid #A7F3D0',
              marginBottom: 14,
            }} />
            <h3 style={{ fontSize: 15, fontWeight: 800, color: '#0F1F3D', margin: 0 }}>
              {area.title}
            </h3>
            <p style={{ fontSize: 12, color: '#64748B', lineHeight: 1.55, margin: '7px 0 0' }}>
              {area.description}
            </p>
          </section>
        ))}
      </div>
    </div>
  )
}
