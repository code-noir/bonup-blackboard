import { useState, useEffect } from 'react'
import { useAuth } from '@/context/AuthContext'
import { useNotification } from '@/context/NotificationContext'
import api from '@/api/client'

const LABEL: React.CSSProperties = {
  fontSize: 11, fontWeight: 500, color: '#4B5563',
  marginBottom: 4, display: 'block',
  textTransform: 'uppercase', letterSpacing: '0.06em',
}

const FIELD: React.CSSProperties = {
  width: '100%', background: 'white',
  border: '1px solid #D1D5DB', borderRadius: 8,
  padding: '8px 12px', fontSize: 13, color: '#374151',
  outline: 'none', boxSizing: 'border-box',
}

const FIELD_RO: React.CSSProperties = {
  ...FIELD, background: '#F9FAFB', color: '#9CA3AF', cursor: 'default',
}

function ff(e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) {
  e.currentTarget.style.borderColor = '#243447'
  e.currentTarget.style.boxShadow = '0 0 0 2px rgba(15,31,61,0.08)'
}
function fb(e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) {
  e.currentTarget.style.borderColor = '#D1D5DB'
  e.currentTarget.style.boxShadow = 'none'
}

export default function Profile() {
  const { user, refreshUser } = useAuth()
  const notify = useNotification()

  const [firstName, setFirstName]     = useState('')
  const [lastName, setLastName]       = useState('')
  const [occupation, setOccupation]   = useState('')
  const [phone, setPhone]             = useState('')
  const [address1, setAddress1]       = useState('')
  const [address2, setAddress2]       = useState('')
  const [city, setCity]               = useState('')
  const [stateRegion, setStateRegion] = useState('')
  const [country, setCountry]         = useState('')
  const [zip, setZip]                 = useState('')
  const [bio, setBio]                 = useState('')
  const [saving, setSaving]           = useState(false)

  // Load profile from API + localStorage on mount
  useEffect(() => {
    api.get<{
      first_name: string; last_name: string; phone: string | null;
      city: string | null; state_region: string | null; country: string | null;
    }>('/users/me/')
      .then(({ data }) => {
        setFirstName(data.first_name || 'Chazz')
        setLastName(data.last_name || 'Wrangler')
        setPhone(data.phone ?? '')
        setCity(data.city ?? '')
        setStateRegion(data.state_region ?? '')
        setCountry(data.country ?? '')
      })
      .catch(() => {
        setFirstName('Chazz')
        setLastName('Wrangler')
      })

    // Persist-locally only fields
    const local = JSON.parse(localStorage.getItem('bb_profile_extra') ?? '{}')
    setOccupation(local.occupation ?? 'Entrepreneur')
    setAddress1(local.address1 ?? '')
    setAddress2(local.address2 ?? '')
    setZip(local.zip ?? '')
    setBio(local.bio ?? '')
  }, [])

  async function handleSave() {
    setSaving(true)
    try {
      await api.patch('/users/me/', { first_name: firstName, last_name: lastName })

      if (phone !== (user?.bon_id ? '' : '')) {
        await api.post('/users/me/update-phone/', { phone }).catch(() => {})
      }

      if (city || stateRegion || country) {
        await api.post('/users/me/update-location/', {
          city, state_region: stateRegion, country,
        }).catch(() => {})
      }

      // Persist locally-only fields
      localStorage.setItem('bb_profile_extra', JSON.stringify({ occupation, address1, address2, zip, bio }))

      await refreshUser()
      notify.success('Profile saved successfully')
    } catch {
      notify.error('Failed to save. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  const initials = ([firstName[0], lastName[0]].filter(Boolean).join('') || '?').toUpperCase()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* Page header */}
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#0F1F3D', margin: 0 }}>My Profile</h1>
        <p style={{ fontSize: 13, color: '#6B7280', margin: '4px 0 0' }}>
          Your personal identity on bonUP Blackbòd
        </p>
      </div>

      {/* Card */}
      <div style={{
        maxWidth: 600, margin: '0 auto', width: '100%',
        background: 'white', borderRadius: 11,
        border: '1px solid rgba(0,0,0,0.06)',
        padding: 28,
      }}>

        {/* Avatar */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: 28 }}>
          <div style={{
            width: 80, height: 80, borderRadius: '50%',
            background: '#243447', color: 'white',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 28, fontWeight: 600,
          }}>
            {initials}
          </div>
          <span style={{ fontSize: 12, color: '#6B7280', marginTop: 8, cursor: 'pointer' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#0F1F3D')}
            onMouseLeave={e => (e.currentTarget.style.color = '#6B7280')}
          >
            Change Photo
          </span>
          {user?.bon_id && (
            <span style={{ fontSize: 13, color: '#8B5CF6', fontFamily: 'DM Mono, monospace', marginTop: 4 }}>
              {user.bon_id}
            </span>
          )}
        </div>

        {/* Form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Row 1: First / Last name */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={LABEL}>First Name *</label>
              <input value={firstName} onChange={e => setFirstName(e.target.value)}
                style={FIELD} onFocus={ff} onBlur={fb} />
            </div>
            <div>
              <label style={LABEL}>Last Name *</label>
              <input value={lastName} onChange={e => setLastName(e.target.value)}
                style={FIELD} onFocus={ff} onBlur={fb} />
            </div>
          </div>

          {/* Row 2: Bond ID / Occupation */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={LABEL}>Bond ID</label>
              <input value={user?.bon_id ?? ''} readOnly style={{ ...FIELD_RO, fontFamily: 'DM Mono, monospace', letterSpacing: '0.04em' }} />
            </div>
            <div>
              <label style={LABEL}>Occupation</label>
              <input value={occupation} onChange={e => setOccupation(e.target.value)}
                placeholder="e.g. Contractor, Consultant"
                style={FIELD} onFocus={ff} onBlur={fb} />
            </div>
          </div>

          {/* Row 3: Email / Phone */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={LABEL}>Email</label>
              <input value={user?.email ?? ''} readOnly style={FIELD_RO} />
            </div>
            <div>
              <label style={LABEL}>Phone Number</label>
              <input value={phone} onChange={e => setPhone(e.target.value)}
                placeholder="+1 (555) 000-0000"
                style={FIELD} onFocus={ff} onBlur={fb} />
            </div>
          </div>

          {/* Row 4: Address */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={LABEL}>Address Line 1</label>
              <input value={address1} onChange={e => setAddress1(e.target.value)}
                style={FIELD} onFocus={ff} onBlur={fb} />
            </div>
            <div>
              <label style={LABEL}>Address Line 2</label>
              <input value={address2} onChange={e => setAddress2(e.target.value)}
                style={FIELD} onFocus={ff} onBlur={fb} />
            </div>
          </div>

          {/* Row 5: City / State */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={LABEL}>City</label>
              <input value={city} onChange={e => setCity(e.target.value)}
                style={FIELD} onFocus={ff} onBlur={fb} />
            </div>
            <div>
              <label style={LABEL}>State / Province</label>
              <input value={stateRegion} onChange={e => setStateRegion(e.target.value)}
                style={FIELD} onFocus={ff} onBlur={fb} />
            </div>
          </div>

          {/* Row 6: Country / Zip */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={LABEL}>Country</label>
              <input value={country} onChange={e => setCountry(e.target.value)}
                style={FIELD} onFocus={ff} onBlur={fb} />
            </div>
            <div>
              <label style={LABEL}>Zip / Postal Code</label>
              <input value={zip} onChange={e => setZip(e.target.value)}
                style={FIELD} onFocus={ff} onBlur={fb} />
            </div>
          </div>

          {/* Row 7: Bio */}
          <div>
            <label style={LABEL}>Bio / About</label>
            <textarea
              value={bio}
              onChange={e => setBio(e.target.value.slice(0, 300))}
              rows={3}
              placeholder="Brief description about yourself"
              style={{ ...FIELD, resize: 'vertical', lineHeight: 1.5 }}
              onFocus={ff as unknown as React.FocusEventHandler<HTMLTextAreaElement>}
              onBlur={fb as unknown as React.FocusEventHandler<HTMLTextAreaElement>}
            />
            <div style={{ fontSize: 11, color: '#9CA3AF', textAlign: 'right', marginTop: 2 }}>
              {bio.length}/300
            </div>
          </div>

          {/* Save */}
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              width: '100%', height: 40,
              background: saving ? '#9CA3AF' : '#243447',
              color: 'white', border: 'none', borderRadius: 8,
              fontSize: 14, fontWeight: 600,
              cursor: saving ? 'default' : 'pointer',
              marginTop: 8,
            }}
            onMouseEnter={e => { if (!saving) e.currentTarget.style.opacity = '0.85' }}
            onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
          >
            {saving ? 'Saving…' : 'Save Profile'}
          </button>
        </div>
      </div>
    </div>
  )
}
