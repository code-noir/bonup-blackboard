import { useState } from 'react'
import { useAuth } from '@/context/AuthContext'

export default function Analysis() {
  const { user } = useAuth()
  const isPayg = user?.subscription_tier === 'per_contract'

  const [contractText, setContractText] = useState('')
  const [analysisResult, setAnalysisResult] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  async function handleAnalyze() {
    if (!contractText.trim()) return
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

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: '#0F1F3D', marginBottom: 6 }}>
        🔍 Contract Analysis
      </h1>
      <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 24 }}>
        Paste or type your contract below, then click Analyze for a full AI-powered breakdown.
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
