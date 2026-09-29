const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.join(__dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('Profile uses the canonical Vault-backed photo flow', () => {
  const profile = read('src/pages/Profile.tsx')
  const avatar = read('src/components/identity/CanonicalAvatar.tsx')
  const auth = read('src/types/auth.ts')
  const delivery = read('src/api/fileDelivery.ts')

  for (const value of ['Change Photo', '/uploads/?canonical=true', '/uploads/', '/users/me/profile-photo/', 'Save photo', 'Cancel', 'Remove photo', 'profile_photo_visible']) {
    assert.match(profile, new RegExp(value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
  assert.match(profile, /PrivateFilePreview/)
  assert.match(profile, /CanonicalAvatar/)
  assert.match(avatar, /fetchPrivateFile/)
  assert.match(avatar, /initials/)
  assert.match(auth, /profile_photo_url\?: string \| null/)
  assert.match(delivery, /users\/\[0-9\]\{13\}\/profile-photo/)
})

test('Profile photo UI does not introduce a second storage or public URL path', () => {
  const profile = read('src/pages/Profile.tsx')
  assert.doesNotMatch(profile, /localStorage.*photo/i)
  assert.doesNotMatch(profile, /https?:\/\//)
})

console.log('canonical profile photo assertions passed')
