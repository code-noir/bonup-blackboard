const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const frontend = path.resolve(__dirname, '..')
const read = (file) => fs.readFileSync(path.join(frontend, file), 'utf8')
const home = read('src/pages/BonupHub.tsx')
const styles = read('src/home.css')
const shell = read('src/components/layout/PlatformShell.tsx')
const platformStyles = read('src/index.css')
const nisloStyles = read('src/nislo.css')

assert.match(home, /home-identity/)
assert.match(home, /Bon ID/)
assert.match(home, /View Profile/)
assert.match(home, /Edit Profile/)
assert.match(home, /CanonicalAvatar/)
assert.match(home, /FeaturedMedia/)
assert.match(home, /home-media-card/)
assert.match(home, /nisloApi\.communities\(\)/)
assert.match(home, /nisloApi\.friends\(\)/)
assert.match(home, /Your Communities will appear here\./)
assert.match(home, /Your circle is just getting started\./)
assert.match(home, /No new social activity yet\./)
assert.match(home, /has_blackbod_access/)
assert.match(home, /Structured agreements for commitments that matter\./)
assert.match(home, /\+ New Agreement/)
assert.match(home, /Open Blackboard/)
assert.match(home, /Learn about Blackboard/)

// Home must not request or render private Blackboard operational data.
for (const forbidden of [
  'HomeContract',
  "'/contracts/'",
  "'/activity/",
  'related_contract_id',
  'contract counts',
  'Agreement activity',
]) assert.doesNotMatch(home, new RegExp(forbidden.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))

assert.match(styles, /height: 88px/)
assert.match(styles, /home-media-poster/)
assert.match(styles, /overflow-x: auto/)
assert.match(styles, /home-blackboard-card/)
assert.match(styles, /@media \(max-width: 900px\)/)
assert.match(styles, /@media \(max-width: 640px\)/)

assert.match(shell, /label: 'Platform'/)
assert.match(shell, /label: 'Applications'/)
assert.match(shell, /label: 'Services'/)
assert.match(shell, /label: 'Account'/)
assert.match(shell, /label: 'Nislo'/)
assert.match(shell, /label: 'Blackboard'/)
assert.match(shell, /label: 'Agreement Activity'/)
assert.match(shell, /label: 'Vault'/)
assert.match(shell, /has_blackbod_access === true/)
assert.match(shell, /background: '#E8DED0'/)
assert.match(shell, /borderRight: '1px solid #DDD7CF'/)
assert.match(shell, /className="platform-nav-item"/)
assert.match(platformStyles, /\.platform-nav-item:hover[\s\S]*#F2ECE4/)
assert.match(platformStyles, /\.platform-nav-item:focus-visible[\s\S]*#2563EB/)
assert.match(nisloStyles, /\.nislo-platform-sidebar \{ background: #e8ded0/)
assert.doesNotMatch(shell, /background: '#111827'/)
assert.doesNotMatch(shell, /background: '#0B1220'/)

console.log('social-first Home assertions passed')
