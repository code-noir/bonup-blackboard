/* Run with node --test; jsdom may be installed outside the repo (see Slice 4 notes). */
const { test, beforeEach, afterEach } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')
const { JSDOM } = require(process.env.BONUP_TEST_TOOLS ? path.join(process.env.BONUP_TEST_TOOLS, 'jsdom') : 'jsdom')
for (const ext of ['.ts', '.tsx']) require.extensions[ext] = (module, filename) => {
  const source = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText
  module._compile(source, filename)
}
const React = require('react')
const { act } = React
const { createRoot } = require('react-dom/client')
const { default: api, tokenStorage, impersonationTokenStorage } = require('../src/api/client.ts')
const { fetchPrivateFile, privateDeliveryPath, previewKind } = require('../src/api/fileDelivery.ts')
const { PrivateFilePreview, PrivateDownloadButton } = require('../src/components/files/PrivateFile.tsx')
const vault = '/api/uploads/00000000-0000-0000-0000-000000000001/delivery/'
const contract = '/api/contracts/00000000-0000-0000-0000-000000000002/documents/00000000-0000-0000-0000-000000000003/delivery/'
const lifecycle = '/api/lifecycle/items/00000000-0000-0000-0000-000000000002/attachments/00000000-0000-0000-0000-000000000003/delivery/'
let dom, root, created, revoked, calls, clicks
beforeEach(() => {
  dom = new JSDOM('<div id="root"></div>', { url: 'https://app.example.invalid/' })
  global.window = dom.window
  global.document = dom.window.document
  global.localStorage = dom.window.localStorage
  global.Event = dom.window.Event
  global.IS_REACT_ACT_ENVIRONMENT = true
  global.IntersectionObserver = class { constructor(cb) { this.cb = cb } observe() { this.cb([{ isIntersecting: true }]) } disconnect() {} }
  created = []; revoked = []; calls = []; clicks = []
  URL.createObjectURL = blob => { const value = 'blob:fixture-' + created.length; created.push({ value, blob }); return value }
  URL.revokeObjectURL = value => revoked.push(value)
  dom.window.HTMLAnchorElement.prototype.click = function () { clicks.push({ href: this.href, download: this.download }) }
  tokenStorage.set('synthetic-access', 'synthetic-refresh')
  api.defaults.adapter = async config => {
    calls.push(config)
    return { data: new Blob(['fixture'], { type: 'image/png' }), status: 200, headers: {}, config }
  }
  root = createRoot(document.getElementById('root'))
})
afterEach(async () => { await act(async () => root.unmount()); dom.window.close() })
const render = async props => act(async () => { root.render(React.createElement(PrivateFilePreview, props)) })

test('fetch uses authenticated client and normalizes the API base path', async () => {
  await fetchPrivateFile(vault, new AbortController().signal)
  assert.equal(calls[0].url, vault.slice(4))
  assert.equal(calls[0].headers.Authorization, 'Bearer synthetic-access')
  assert.equal(calls[0].responseType, 'blob')
})
test('external, bearer, malformed and unrelated URLs never reach the API client', async () => {
  for (const value of ['https://external.invalid/file', '//external.invalid/file', '/api/users/', '/api/uploads/shares/token/delivery/', vault + '?redirect=x', vault.replace('/api/', '/api/../api/')]) {
    await assert.rejects(fetchPrivateFile(value, new AbortController().signal))
  }
  assert.equal(calls.length, 0)
})
test('only contract, lifecycle and Vault private routes are accepted', () => {
  for (const value of [vault, contract, lifecycle]) assert.equal(privateDeliveryPath(value), value.slice(4))
})
test('preview creates a Blob URL and replacement/unmount revoke it', async () => {
  await render({ path: vault })
  assert.equal(document.querySelector('img').getAttribute('src'), 'blob:fixture-0')
  await render({ path: contract })
  assert.deepEqual(revoked, ['blob:fixture-0'])
  await act(async () => root.render(null))
  assert.deepEqual(revoked, ['blob:fixture-0', 'blob:fixture-1'])
})
test('lazy thumbnail loads an authenticated image Blob', async () => {
  await render({ path: vault, thumbnail: true })
  assert.equal(calls.length, 1)
  assert.ok(document.querySelector('img'))
})
test('pending preview is cancelled on unmount', async () => {
  let config
  api.defaults.adapter = value => { config = value; return new Promise(() => {}) }
  await render({ path: vault })
  await act(async () => root.render(null))
  assert.equal(config.signal.aborted, true)
  assert.equal(created.length, 0)
})
test('authentication context change revokes old content', async () => {
  await render({ path: vault })
  api.defaults.adapter = async () => { throw new Error('denied') }
  await act(async () => impersonationTokenStorage.set('synthetic-view-as', 'synthetic-session', { id: 1, email: '', first_name: '', last_name: '' }))
  assert.ok(revoked.includes('blob:fixture-0'))
  assert.equal(document.querySelector('img'), null)
})
test('failed previews show a generic error', async () => {
  api.defaults.adapter = async () => { throw new Error('private locator') }
  await render({ path: vault })
  assert.match(document.querySelector('[role="alert"]').textContent, /Could not load/)
  assert.doesNotMatch(document.body.textContent, /private locator/)
})
test('unsafe types cannot become an iframe or object URL', async () => {
  for (const type of ['text/html', 'image/svg+xml', 'application/xml', 'application/octet-stream']) {
    assert.equal(previewKind(type), null)
  }
  api.defaults.adapter = async config => ({ data: new Blob(['fixture'], { type: 'text/html' }), status: 200, headers: {}, config })
  await render({ path: vault })
  assert.equal(created.length, 0)
  assert.equal(document.querySelector('iframe'), null)
})
test('PDF uses a sandboxed Blob iframe', async () => {
  api.defaults.adapter = async config => ({ data: new Blob(['fixture'], { type: 'application/pdf' }), status: 200, headers: {}, config })
  await render({ path: vault })
  assert.equal(document.querySelector('iframe').getAttribute('sandbox'), '')
})
for (const [type, tag] of [['video/mp4', 'video'], ['audio/mpeg', 'audio']]) test(`${tag} renders after full Blob download`, async () => {
  api.defaults.adapter = async config => ({ data: new Blob(['fixture'], { type }), status: 200, headers: {}, config })
  await render({ path: vault })
  assert.equal(document.querySelector(tag).getAttribute('src'), 'blob:fixture-0')
})
for (const [name, value] of [['Vault', vault], ['contract', contract], ['lifecycle', lifecycle]]) test(`${name} download fetches bytes and cleans its object URL`, async () => {
  await act(async () => root.render(React.createElement(PrivateDownloadButton, { path: value, filename: 'fixture.pdf' })))
  await act(async () => document.querySelector('button').click())
  assert.equal(calls[0].url, value.slice(4))
  assert.equal(calls[0].params.download, '1')
  assert.equal(clicks[0].href, 'blob:fixture-0')
  await act(async () => root.render(null))
  assert.deepEqual(revoked, ['blob:fixture-0'])
})
test('page integration uses private helpers; public sharing retains direct delivery URLs', () => {
  const read = name => fs.readFileSync(path.join(__dirname, '../src/pages', name + '.tsx'), 'utf8')
  assert.match(read('Vault'), /<PrivateFilePreview/)
  assert.match(read('CreateContract'), /attachmentDownload.download\(file.fileUrl/)
  assert.match(read('AgreementPerformance'), /<PrivateDownloadButton/)
  const publicShare = read('VaultShare')
  assert.match(publicShare, /src=\{[^}]*delivery_url\}/)
  assert.doesNotMatch(publicShare, /fetchPrivateFile|PrivateFilePreview/)
})
