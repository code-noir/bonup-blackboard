export default function TopBar() {
  return (
    <div className="fixed top-0 left-0 right-0 z-50 flex h-[34px] items-center bg-[#0F1F3D] px-5">
      <span
        style={{
          fontSize: 12,
          fontWeight: 600,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
        }}
      >
        <span style={{ color: '#ffffff' }}>bon</span>
        <span style={{ color: '#F5A623' }}>UP</span>
        <span style={{ color: 'rgba(255,255,255,0.3)', marginLeft: 6 }}>Blackboard</span>
      </span>
      <span
        style={{
          marginLeft: 14,
          fontSize: 10,
          fontStyle: 'italic',
          fontWeight: 300,
          color: 'rgba(255,255,255,0.25)',
        }}
      >
        Keeping the world together through clear contracting
      </span>
    </div>
  )
}
