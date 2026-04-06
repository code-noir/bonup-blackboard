import { useState } from 'react'

// Tier: 'Free Trial' | 'Sol Member' | 'As You Go' | 'Blackboard Basic' | 'Blackboard Pro' | 'Blackboard Business' | 'Blackboard Premium'
const USER_TIER = 'Blackboard Business'

export default function Analysis() {
  const [contractText, setContractText] = useState('')
  const [analysisResult, setAnalysisResult] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [showPaygConfirm, setShowPaygConfirm] = useState(false)

  async function runAnalyze() {
    setIsAnalyzing(true)
    setAnalysisResult('')
    try {
      const res = await fetch('/api/contracts/analyze/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contract_text: contractText }),
      })
      const data = await res.json()
      setAnalysisResult(data.result ?? JSON.stringify(data))
    } catch {
      setAnalysisResult('Analysis failed. Please try again.')
    } finally {
      setIsAnalyzing(false)
    }
  }

  function handleAnalyze() {
    if (!contractText.trim()) return
    if (USER_TIER === 'As You Go') {
      setShowPaygConfirm(true)
    } else {
      runAnalyze()
    }
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      {/* PAYG confirmation modal */}
      {showPaygConfirm && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
          zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: 'white', borderRadius: 12, padding: 32, maxWidth: 400, width: '90%',
            boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          }}>
            <p style={{ fontSize: 16, fontWeight: 700, color: '#0F1F3D', marginBottom: 8 }}>
              Confirm Analysis Charge
            </p>
            <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 16, lineHeight: 1.5 }}>
              You're on the Pay As You Go plan. This analysis will be charged to your account.
            </p>
            <div style={{
              background: '#FEF3C7', border: '1px solid #F59E0B',
              borderRadius: 8, padding: '10px 14px', marginBottom: 20, fontSize: 12, color: '#D97706',
            }}>
              $25 per contract · $25 per analysis · $25 per counter
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={() => { setShowPaygConfirm(false); runAnalyze() }}
                style={{
                  flex: 1, height: 38, background: '#0F1F3D', color: 'white',
                  border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                }}
              >
                Confirm — $25
              </button>
              <button
                onClick={() => setShowPaygConfirm(false)}
                style={{
                  flex: 1, height: 38, background: '#F3F4F6', color: '#374151',
                  border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: 'pointer',
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <h1 style={{ fontSize: 22, fontWeight: 700, color: '#0F1F3D', marginBottom: 6 }}>
        🔍 Contract Analysis
      </h1>
      <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 24 }}>
        Paste or type your contract below, then click Analyze for a full AI-powered breakdown.
      </p>

      {USER_TIER === 'As You Go' && (
        <div style={{
          background: '#FEF3C7', border: '1px solid #F59E0B',
          borderRadius: 8, padding: '10px 14px',
          fontSize: 12, color: '#D97706', marginBottom: 16,
        }}>
          ⚠️ Pay As You Go: $25 per contract · $25 per analysis · $25 per counter
        </div>
      )}

      <div style={{
        background: 'white', borderRadius: 11,
        border: '1px solid rgba(0,0,0,0.08)', padding: 20, marginBottom: 16,
      }}>
        <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 8 }}>
          Contract Text
        </label>
        <textarea
          value={contractText}
          onChange={(e) => setContractText(e.target.value)}
          placeholder="Paste your contract text here…"
          style={{
            width: '100%', minHeight: 240,
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
        onClick={handleAnalyze}
        disabled={isAnalyzing || !contractText.trim()}
        style={{
          height: 40, padding: '0 24px',
          background: isAnalyzing || !contractText.trim() ? '#9CA3AF' : '#0F1F3D',
          color: 'white', border: 'none', borderRadius: 8,
          fontSize: 14, fontWeight: 600,
          cursor: isAnalyzing || !contractText.trim() ? 'default' : 'pointer',
          marginBottom: 24,
        }}
        onMouseEnter={(e) => {
          if (!isAnalyzing && contractText.trim()) e.currentTarget.style.background = '#1a3460'
        }}
        onMouseLeave={(e) => {
          if (!isAnalyzing && contractText.trim()) e.currentTarget.style.background = '#0F1F3D'
        }}
      >
        {isAnalyzing ? 'Analyzing…' : 'Analyze Contract'}
      </button>

      <div style={{
        background: 'white', borderRadius: 11,
        border: '1px solid rgba(0,0,0,0.08)', padding: 20,
      }}>
        <p style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 12 }}>
          Analysis Results
        </p>
        <div style={{
          minHeight: 160, fontSize: 13,
          color: analysisResult ? '#374151' : '#9CA3AF',
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
        }}>
          {isAnalyzing ? (
            <span style={{ color: '#6B7280' }}>Analyzing your contract…</span>
          ) : (
            analysisResult || 'Analysis results will appear here…'
          )}
        </div>
      </div>
    </div>
  )
}
