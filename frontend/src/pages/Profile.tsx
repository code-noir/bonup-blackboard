import { useState, useEffect, useRef } from 'react'
import { useAuth } from '@/context/AuthContext'
import { useNotification } from '@/context/NotificationContext'
import api from '@/api/client'
import { CanonicalAvatar } from '@/components/identity/CanonicalAvatar'
import { PrivateFilePreview } from '@/components/files/PrivateFile'

type VaultPhoto = {
  id: string
  file_url: string | null
  file_name: string
  file_type: string
  content_type: string
  file_size: number
  uploaded_at: string
}

const PROFILE_PHOTO_TYPES = new Set(['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/avif'])

function isProfilePhoto(file: VaultPhoto) {
  return file.file_type === 'image' && PROFILE_PHOTO_TYPES.has(file.content_type.split(';', 1)[0].toLowerCase()) && Boolean(file.file_url)
}

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
  const [photoChooserOpen, setPhotoChooserOpen] = useState(false)
  const [vaultPhotos, setVaultPhotos] = useState<VaultPhoto[]>([])
  const [photoLoading, setPhotoLoading] = useState(false)
  const [photoSaving, setPhotoSaving] = useState(false)
  const [photoError, setPhotoError] = useState('')
  const [photoAction, setPhotoAction] = useState<'none' | 'set' | 'remove'>('none')
  const [selectedPhoto, setSelectedPhoto] = useState<VaultPhoto | null>(null)
  const [photoVisible, setPhotoVisible] = useState(true)
  const photoInputRef = useRef<HTMLInputElement>(null)

  // Load profile from API + localStorage on mount
  useEffect(() => {
    api.get<{
      first_name: string; last_name: string; phone: string | null;
      city: string | null; state_region: string | null; country: string | null;
      profile_photo_visible?: boolean;
    }>('/users/me/')
      .then(({ data }) => {
        setFirstName(data.first_name || '')
        setLastName(data.last_name || '')
        setPhone(data.phone ?? '')
        setCity(data.city ?? '')
        setStateRegion(data.state_region ?? '')
        setCountry(data.country ?? '')
        setPhotoVisible(data.profile_photo_visible !== false)
      })
      .catch(() => {
        setFirstName(user?.first_name || '')
        setLastName(user?.last_name || '')
      })

    // Persist-locally only fields
    const local = JSON.parse(localStorage.getItem('bb_profile_extra') ?? '{}')
    setOccupation(local.occupation ?? 'Entrepreneur')
    setAddress1(local.address1 ?? '')
    setAddress2(local.address2 ?? '')
    setZip(local.zip ?? '')
    setBio(local.bio ?? '')
  }, [])

  async function openPhotoChooser() {
    setPhotoChooserOpen(true)
    setPhotoAction('none')
    setSelectedPhoto(null)
    setPhotoError('')
    setPhotoLoading(true)
    try {
      const { data } = await api.get<VaultPhoto[]>('/uploads/?canonical=true')
      setVaultPhotos(data.filter(isProfilePhoto))
    } catch {
      setPhotoError('Your Vault photos could not be loaded.')
    } finally {
      setPhotoLoading(false)
    }
  }

  function closePhotoChooser() {
    setPhotoChooserOpen(false)
    setPhotoAction('none')
    setSelectedPhoto(null)
    setPhotoError('')
  }

  function selectPhoto(photo: VaultPhoto) {
    setSelectedPhoto(photo)
    setPhotoAction('set')
    setPhotoError('')
  }

  async function uploadNewPhoto(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (!PROFILE_PHOTO_TYPES.has(file.type.toLowerCase())) {
      setPhotoError('Choose a JPEG, PNG, GIF, WebP, or AVIF image.')
      return
    }

    setPhotoSaving(true)
    setPhotoError('')
    const form = new FormData()
    form.append('file', file)
    form.append('file_type', 'image')
    try {
      const { data } = await api.post<VaultPhoto>('/uploads/', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      if (!isProfilePhoto(data)) {
        setPhotoError('The uploaded file is not available as a profile image.')
        return
      }
      setVaultPhotos((current) => [data, ...current.filter((photo) => photo.id !== data.id)])
      selectPhoto(data)
    } catch {
      setPhotoError('The photo could not be uploaded to Vault.')
    } finally {
      setPhotoSaving(false)
    }
  }

  async function savePhotoSelection() {
    if (photoAction === 'none') return
    setPhotoSaving(true)
    setPhotoError('')
    try {
      const { data } = await api.patch('/users/me/profile-photo/', {
        profile_photo_id: photoAction === 'remove' ? null : selectedPhoto?.id,
        profile_photo_visible: photoVisible,
      })
      setPhotoVisible(data.profile_photo_visible !== false)
      await refreshUser()
      notify.success(photoAction === 'remove' ? 'Profile photo removed.' : 'Profile photo saved.')
      closePhotoChooser()
    } catch {
      setPhotoError('Your profile photo could not be saved.')
    } finally {
      setPhotoSaving(false)
    }
  }

  async function changePhotoVisibility(visible: boolean) {
    setPhotoVisible(visible)
    if (!user?.profile_photo_id) return
    try {
      await api.patch('/users/me/profile-photo/', { profile_photo_visible: visible })
      await refreshUser()
    } catch {
      setPhotoVisible(!visible)
      notify.error('Profile photo visibility could not be changed.')
    }
  }

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
          <CanonicalAvatar identity={user || { first_name: firstName, last_name: lastName }} className="profile-page-avatar" label="Profile photo" />
          <button type="button" onClick={() => void openPhotoChooser()} style={{ background: 'none', border: 0, color: '#6B7280', cursor: 'pointer', fontSize: 12, marginTop: 8, padding: 0 }}>
            Change Photo
          </button>
          <label style={{ alignItems: 'center', color: '#6B7280', display: 'flex', fontSize: 11, gap: 6, marginTop: 8 }}>
            <input
              type="checkbox"
              checked={photoVisible}
              disabled={!user?.profile_photo_id}
              onChange={(event) => void changePhotoVisibility(event.target.checked)}
            />
            Show profile photo to authorized bonUP people
          </label>
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

      {photoChooserOpen && (
        <div role="dialog" aria-modal="true" aria-labelledby="profile-photo-title" style={{ background: 'rgba(15,31,61,.24)', inset: 0, position: 'fixed', zIndex: 80 }}>
          <div style={{ background: '#fff', borderRadius: 14, boxShadow: '0 22px 70px rgba(15,31,61,.22)', left: '50%', maxWidth: 620, padding: 24, position: 'absolute', top: '50%', transform: 'translate(-50%, -50%)', width: 'calc(100% - 32px)' }}>
            <div style={{ alignItems: 'start', display: 'flex', gap: 16, justifyContent: 'space-between' }}>
              <div>
                <h2 id="profile-photo-title" style={{ color: '#0F1F3D', fontSize: 18, margin: 0 }}>Change profile photo</h2>
                <p style={{ color: '#6B7280', fontSize: 12, margin: '5px 0 0' }}>Choose an image already stored in your Vault, or upload a new one.</p>
              </div>
              <button type="button" onClick={closePhotoChooser} disabled={photoSaving} aria-label="Close profile photo chooser" style={{ background: 'none', border: 0, color: '#6B7280', cursor: 'pointer', fontSize: 20 }}>×</button>
            </div>

            {photoError && <div role="alert" style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, color: '#991B1B', fontSize: 12, marginTop: 16, padding: 10 }}>{photoError}</div>}
            {photoLoading ? <div role="status" style={{ color: '#6B7280', padding: '28px 0', textAlign: 'center' }}>Loading your Vault photos…</div> : (
              <>
                <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fill, minmax(92px, 1fr))', marginTop: 18, maxHeight: 260, overflowY: 'auto' }}>
                  {vaultPhotos.map((photo) => (
                    <button key={photo.id} type="button" onClick={() => selectPhoto(photo)} aria-label={`Select ${photo.file_name}`} style={{ background: photo.id === selectedPhoto?.id ? '#EFF6FF' : '#F9FAFB', border: photo.id === selectedPhoto?.id ? '2px solid #2563EB' : '1px solid #E5E7EB', borderRadius: 9, cursor: 'pointer', height: 92, overflow: 'hidden', padding: 3 }}>
                      {photo.file_url && <PrivateFilePreview path={photo.file_url} title={photo.file_name} thumbnail className="profile-photo-thumbnail" />}
                    </button>
                  ))}
                </div>
                {!vaultPhotos.length && <p style={{ color: '#6B7280', fontSize: 12, margin: '18px 0 0' }}>No image files are available in your Vault yet.</p>}

                {selectedPhoto?.file_url && (
                  <div style={{ alignItems: 'center', background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: 9, display: 'flex', gap: 12, marginTop: 18, padding: 10 }}>
                    <PrivateFilePreview path={selectedPhoto.file_url} title={selectedPhoto.file_name} className="profile-photo-preview" />
                    <span style={{ color: '#374151', fontSize: 12 }}>{selectedPhoto.file_name}</span>
                  </div>
                )}

                <div style={{ alignItems: 'center', display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'space-between', marginTop: 22 }}>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input ref={photoInputRef} type="file" accept="image/jpeg,image/png,image/gif,image/webp,image/avif" onChange={(event) => void uploadNewPhoto(event)} style={{ display: 'none' }} />
                    <button type="button" onClick={() => photoInputRef.current?.click()} disabled={photoSaving} style={{ background: '#fff', border: '1px solid #D1D5DB', borderRadius: 8, color: '#374151', cursor: 'pointer', fontSize: 12, padding: '9px 12px' }}>Upload new photo</button>
                    <button type="button" onClick={() => { setSelectedPhoto(null); setPhotoAction('remove'); setPhotoError('') }} disabled={!user?.profile_photo_id || photoSaving} style={{ background: 'none', border: 0, color: '#B42318', cursor: 'pointer', fontSize: 12, padding: '9px 4px' }}>Remove photo</button>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button type="button" onClick={closePhotoChooser} disabled={photoSaving} style={{ background: '#fff', border: '1px solid #D1D5DB', borderRadius: 8, color: '#374151', cursor: 'pointer', fontSize: 12, padding: '9px 14px' }}>Cancel</button>
                    <button type="button" onClick={() => void savePhotoSelection()} disabled={photoAction === 'none' || photoSaving} style={{ background: photoAction === 'none' || photoSaving ? '#9CA3AF' : '#243447', border: 0, borderRadius: 8, color: '#fff', cursor: photoAction === 'none' || photoSaving ? 'default' : 'pointer', fontSize: 12, padding: '9px 14px' }}>{photoSaving ? 'Saving…' : 'Save photo'}</button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
