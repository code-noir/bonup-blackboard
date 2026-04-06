import { useState } from 'react'
import { useAuth } from '@/context/AuthContext'

export default function Counter() {
  const { user } = useAuth()
  const isPayg = user?.subscription_tier === 'per_contract'

  const [contractText, setContractText] = useState('')
  const [counterTerms, setCounterTerms] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  async function handleSubmit() {
    if (!contractText.trim() || !counterTerms.trim()) return
    setIsSubmitting(true)
    try {
      await fetch('/api/contracts/counter/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contract_text: contractText, counter_terms: counterTerms }),
      })
      setSubmitted(true)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: '#0F1F3D', marginBottom: 6 }}>
        ⚡ Contract Counter
      </h1>
      <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 24 }}>
        Review a contract and submit your professional AI-powered counter terms.
      </p>

      {isPayg && (
        <div style={{
          background: '#ECFDF5', border: '1px solid #6EE7B7',
          borderRadius: 8, padding: '10px 14px',
          fontSize: 12, color: '#065F46', marginBottom: 16,
        }}>
          ✓ Included with Pay As You Go ($25 per contract)
        </div>
      )}

      {submitted ? (
        <div style={{
          background: '#F0FDF4', border: '1px solid #86EFAC',
          borderRadius: 11, padding: 24, textAlign: 'center',
        }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>✅</div>
          <p style={{ fontSize: 14, fontWeight: 600, color: '#166534' }}>
            Counter submitted successfully.
          </p>
          <button
            onClick={() => { setSubmitted(false); setContractText(''); setCounterTerms('') }}
            style={{
              marginTop: 16, height: 36, padding: '0 20px',
              background: '#0F1F3D', color: 'white',
              border: 'none', borderRadius: 8,
              fontSize: 13, fontWeight: 500, cursor: 'pointer',
            }}
          >
            Submit Another
          </button>
        </div>
      ) : (
        <>
          <div style={{
            background: 'white', borderRadius: 11,
            border: '1px solid rgba(0,0,0,0.08)', padding: 20, marginBottom: 16,
          }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 8 }}>
              Original Contract Text
            </label>
            <textarea
              value={contractText}
              onChange={(e) => setContractText(e.target.value)}
              placeholder="Paste the original contract text here…"
              style={{
                width: '100%', minHeight: 200,
                border: '1px solid #E5E7EB', borderRadius: 8,
                padding: 12, fontSize: 13, color: '#374151',
                lineHeight: 1.6, resize: 'vertical',
                outline: 'none', fontFamily: 'inherit',
                boxSizing: 'border-box',
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = '#6B7280')}
              onBlur={(e) => (e.currentTarget.style.borderColor = '#E5E7EB')}
            />
          </div>

          <div style={{
            background: 'white', borderRadius: 11,
            border: '1px solid rgba(0,0,0,0.08)', padding: 20, marginBottom: 16,
          }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 8 }}>
              Your Counter Terms
            </label>
            <textarea
              value={counterTerms}
              onChange={(e) => setCounterTerms(e.target.value)}
              placeholder="Describe your counter terms or proposed changes…"
              style={{
                width: '100%', minHeight: 200,
                border: '1px solid #E5E7EB', borderRadius: 8,
                padding: 12, fontSize: 13, color: '#374151',
                lineHeight: 1.6, resize: 'vertical',
                outline: 'none', fontFamily: 'inherit',
                boxSizing: 'border-box',
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = '#6B7280')}
              onBlur={(e) => (e.currentTarget.style.borderColor = '#E5E7EB')}
            />
          </div>

          <button
            onClick={handleSubmit}
            disabled={isSubmitting || !contractText.trim() || !counterTerms.trim()}
            style={{
              height: 40, padding: '0 24px',
              background: isSubmitting || !contractText.trim() || !counterTerms.trim()
                ? '#9CA3AF' : '#0F1F3D',
              color: 'white', border: 'none', borderRadius: 8,
              fontSize: 14, fontWeight: 600,
              cursor: isSubmitting || !contractText.trim() || !counterTerms.trim()
                ? 'default' : 'pointer',
            }}
            onMouseEnter={(e) => {
              if (!isSubmitting && contractText.trim() && counterTerms.trim())
                e.currentTarget.style.background = '#1a3460'
            }}
            onMouseLeave={(e) => {
              if (!isSubmitting && contractText.trim() && counterTerms.trim())
                e.currentTarget.style.background = '#0F1F3D'
            }}
          >
            {isSubmitting ? 'Submitting…' : 'Submit Counter'}
          </button>
        </>
      )}
    </div>
  )
}
