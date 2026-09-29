const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.join(__dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('Community identity editing is owner-only and uses the existing UUID route', () => {
  const workspace = read('src/pages/nislo/NisloCommunityWorkspace.tsx')
  const api = read('src/api/nislo.ts')

  assert.match(workspace, /current_member_role === 'owner'/)
  assert.match(workspace, /view=settings/)
  assert.match(workspace, /Community Details/)
  assert.match(workspace, /Save Changes/)
  assert.match(workspace, /Community name/)
  assert.match(workspace, /Description/)
  assert.match(workspace, /Community name is required\./)
  assert.match(workspace, /maxLength=\{200\}/)
  assert.match(workspace, /updated\.name/)
  assert.match(workspace, /updated\.description/)
  assert.match(api, /updateCommunity\(id: string, name: string, description: string\)/)
  assert.match(api, /nisloPatch<MyCommunity>\(`\/communities\/\$\{id\}\/`/)
})

test('Community settings remain viewable without exposing member rename controls', () => {
  const workspace = read('src/pages/nislo/NisloCommunityWorkspace.tsx')

  assert.match(workspace, /Only the Community owner can edit its identity\./)
  assert.match(workspace, /readOnly/)
  assert.match(workspace, /isOwner && <Link className="nislo-button nislo-button-secondary"/)
  assert.match(workspace, /Settings/)
  assert.match(workspace, /Cancel/)
})
