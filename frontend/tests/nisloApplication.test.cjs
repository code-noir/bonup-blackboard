const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.join(__dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('Nislo has a dedicated authenticated application route and shell navigation', () => {
  const app = read('src/App.tsx')
  const shell = read('src/components/layout/NisloShell.tsx')
  const styles = read('src/nislo.css')

  assert.match(app, /path="\/apps\/nislo"/)
  assert.match(app, /NisloShell/)
  for (const label of ['Discover', 'Friends', 'Invites', 'My Communities']) {
    assert.match(shell, new RegExp(label))
  }
  assert.match(shell, /bonUP/)
  assert.match(shell, /nislo-platform-bar/)
  assert.match(shell, /nislo-platform-sidebar/)
  assert.match(shell, /nislo-platform-search/)
  assert.match(shell, /nislo-workspace-bar/)
  assert.doesNotMatch(shell, /Opportunities/)
  assert.match(shell, /Outlet/)
  assert.match(styles, /--nislo-bg: #f6f7f5/)
  assert.match(styles, /background: #243447/)
  assert.match(styles, /overflow-x: auto/)
  assert.match(styles, /min-height: calc\(100vh - 130px\)/)
})

test('Nislo gates legacy Blackboard navigation from the canonical entitlement', () => {
  const shell = read('src/components/layout/NisloShell.tsx')

  assert.match(shell, /const hasBlackboardAccess = user\?\.has_blackbod_access === true/)
  assert.match(shell, /function sidebarItems\(hasBlackboardAccess: boolean\)/)
  assert.match(shell, /hasBlackboardAccess \? \[\{ to: '\/apps\/blackbod', label: 'Blackboard'/)
  assert.match(shell, /hasBlackboardAccess \? \[\{ to: '\/notifications', label: 'Notifications'/)
  assert.match(shell, /const platformSidebarItems = sidebarItems\(hasBlackboardAccess\)/)
  assert.match(shell, /hasBlackboardAccess && \(\s*<NavLink[\s\S]*to="\/notifications"/)
  assert.doesNotMatch(shell, /const sidebarItems = \[/)
})

test('Nislo frontend is wired to real social and Community APIs', () => {
  const api = read('src/api/nislo.ts')
  const app = read('src/App.tsx')

  for (const endpoint of [
    '/communities/discover/',
    '/communities/people/',
    '/communities/friends/',
    '/communities/join-requests/',
    '/communities/',
    '/users/me/invitations/',
  ]) assert.match(api, new RegExp(endpoint.replaceAll('/', '\\/')))
  assert.match(app, /NisloDiscover/)
  assert.match(app, /NisloFriends/)
  assert.match(app, /NisloInvites/)
  assert.match(app, /NisloCommunities/)
  assert.match(app, /NisloCommunityProfile/)
})

test('Discover and My Communities contain valid zero-state and creation-gate UX', () => {
  const discover = read('src/pages/nislo/NisloDiscover.tsx')
  const primitives = read('src/components/nislo/NisloPrimitives.tsx')
  const communities = read('src/pages/nislo/NisloCommunities.tsx')

  assert.match(discover, /No Communities found yet/)
  assert.match(discover, /nislo-hero-visual/)
  assert.match(discover, /People you may know/)
  assert.match(primitives, /Request to Join/)
  assert.match(discover, /Invite People/)
  assert.match(communities, /You need at least one accepted friend/)
  assert.match(communities, /canCreate/)
  assert.match(communities, /Create private Community/)
})

test('Friends, join requests, and external bonUP invitations expose real actions', () => {
  const friends = read('src/pages/nislo/NisloFriends.tsx')
  const invites = read('src/pages/nislo/NisloInvites.tsx')

  assert.match(friends, /Accept/)
  assert.match(friends, /Decline/)
  assert.match(invites, /Approve/)
  assert.match(invites, /Create invitation/)
  assert.match(invites, /Nislo never creates a friendship without their consent/)
})
