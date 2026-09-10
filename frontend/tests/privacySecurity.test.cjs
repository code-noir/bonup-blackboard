const { test, beforeEach } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')
const { JSDOM } = require(process.env.BONUP_TEST_TOOLS ? path.join(process.env.BONUP_TEST_TOOLS, 'jsdom') : 'jsdom')
const dom = new JSDOM('<div></div>', { url: 'https://app.example.invalid/' })
global.window = dom.window; global.document = dom.window.document
global.localStorage = dom.window.localStorage; global.Event = dom.window.Event
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
}).outputText, filename)
const axios = require('axios').default
const { default: api, apiPath, tokenStorage, operatorTokenStorage, impersonationTokenStorage } = require('../src/api/client.ts')
const { safeContractHtml, pastePlainText } = require('../src/lib/safeHtml.ts')
const ok = (config, data = {}) => ({ config, data, status: 200, statusText: 'OK', headers: {} })
const unauthorized = config => Promise.reject(new axios.AxiosError('Unauthorized', 'ERR_BAD_REQUEST', config, {}, { status:401, data:{}, headers:{}, config }))
beforeEach(() => { localStorage.clear(); api.defaults.adapter = async config => ok(config) })

test('arbitrary external URLs and alternate API origins never receive credentials', async () => {
  tokenStorage.set('synthetic-customer-access','synthetic-customer-refresh')
  let called = 0
  api.defaults.adapter = async config => { called++; return ok(config) }
  for (const url of ['https://external.invalid/api/file', '//external.invalid/api/file', '/api/../other', 'data:text/plain,unsafe']) {
    await assert.rejects(api.get(url))
  }
  await assert.rejects(api.get('/uploads/', {baseURL:'https://external.invalid/api'}))
  assert.equal(called,0)
})

test('same-origin API routes retain expected credential separation', async () => {
  tokenStorage.set('customer','customer-refresh'); operatorTokenStorage.set('operator','operator-refresh')
  impersonationTokenStorage.set('view-as','synthetic-session',{id:1,email:'fixture@example.invalid',first_name:'Fixture',last_name:''})
  const received=[]
  api.defaults.adapter = async config => { received.push(config.headers.Authorization); return ok(config) }
  await api.get('/uploads/'); await api.get('/operator/me/'); await api.post('/operator/view-as/exit/')
  assert.deepEqual(received,['Bearer view-as','Bearer operator','Bearer view-as'])
})

test('simultaneous customer and operator refreshes never exchange credentials', async () => {
  tokenStorage.set('old-customer','customer-refresh'); operatorTokenStorage.set('old-operator','operator-refresh')
  const refreshed=[],retried=[]
  axios.defaults.adapter = async config => {
    const operator = config.url.includes('/operator/')
    refreshed.push(operator ? 'operator' : 'customer')
    await new Promise(resolve => setTimeout(resolve,10))
    return ok(config,{access:operator?'new-operator':'new-customer'})
  }
  api.defaults.adapter = async config => {
    if (!config._retry) return unauthorized(config)
    retried.push([config.url,config.headers.Authorization]); return ok(config)
  }
  await Promise.all([api.get('/uploads/'),api.get('/operator/me/')])
  assert.equal(refreshed.length,2)
  assert.deepEqual(retried.sort(),[['/operator/me/','Bearer new-operator'],['/uploads/','Bearer new-customer']])
})

test('logout during refresh cannot restore credentials', async () => {
  tokenStorage.set('old','refresh')
  let finish, started
  const ready = new Promise(resolve => { started = resolve })
  axios.defaults.adapter = config => { started(); return new Promise(resolve => { finish=()=>resolve(ok(config,{access:'late-token'})) }) }
  api.defaults.adapter = unauthorized
  const pending=api.get('/uploads/')
  await ready; tokenStorage.clear(); finish()
  await assert.rejects(pending)
  assert.equal(tokenStorage.getAccess(),null)
})

test('old response is rejected after account switch', async () => {
  tokenStorage.set('first','first-refresh')
  let finish,started
  const ready=new Promise(resolve=>{started=resolve})
  api.defaults.adapter = config=>{started();return new Promise(resolve=>{finish=()=>resolve(ok(config,{private:'old-account'}))})}
  const pending=api.get('/uploads/'); await ready
  tokenStorage.set('second','second-refresh');finish()
  await assert.rejects(pending)
  assert.equal(tokenStorage.getAccess(),'second')
})

test('refresh failure rejects every queued request', async () => {
  tokenStorage.set('old','refresh')
  axios.defaults.adapter=async()=>{ await new Promise(resolve=>setTimeout(resolve,5)); tokenStorage.clear(); throw new Error('Failed') }
  api.defaults.adapter=unauthorized
  const results=await Promise.allSettled([api.get('/uploads/'),api.get('/users/me/')])
  assert.ok(results.every(result=>result.status==='rejected'))
})

test('cancellation during refresh remains cancelled without logging out', async () => {
  tokenStorage.set('old','refresh')
  const controller=new AbortController()
  axios.defaults.adapter=async config=>{controller.abort();return ok(config,{access:'new'})}
  api.defaults.adapter=unauthorized
  await assert.rejects(api.get('/uploads/',{signal:controller.signal}))
  assert.equal(tokenStorage.getAccess(),'new')
})

test('rich text removes active content and resource locators but retains structure', () => {
  const html=safeContractHtml('<h2 id="section-1">Title</h2><p><strong>Terms</strong></p><img src="https://external.invalid/private" onerror="alert(1)"><svg onload="alert(1)"></svg><script>alert(1)</script><a href="javascript:alert(1)">link</a><span style="background:url(https://external.invalid/private)">text</span><iframe src="https://external.invalid"></iframe>')
  assert.match(html,/<strong>Terms<\/strong>/)
  assert.match(html,/id="section-1"/)
  for (const forbidden of ['onerror','onload','javascript:','<script','<svg','<iframe','external.invalid','style=']) assert.ok(!html.includes(forbidden))
})

test('built frontend has restrictive script and referrer policies', () => {
  const html=fs.readFileSync(path.join(__dirname,'../dist/index.html'),'utf8')
  const built = new JSDOM(html)
  assert.ok(built.window.document.querySelector('meta[http-equiv="Content-Security-Policy"]').content.includes("script-src 'self'"))
  built.window.close()
  assert.ok(html.includes('no-referrer'))
})

test('clipboard HTML is not inserted into contract editors', () => {
  let inserted, prevented=false
  document.execCommand=(command,show,value)=>{inserted=[command,value]}
  pastePlainText({preventDefault:()=>{prevented=true},clipboardData:{getData:type=>type==='text/plain'?'plain fixture':'<img onerror="unsafe">'}})
  assert.equal(prevented,true)
  assert.deepEqual(inserted,['insertText','plain fixture'])
})

test('expired View-As clears its context without clearing customer credentials', async () => {
  tokenStorage.set('customer', 'customer-refresh')
  impersonationTokenStorage.set('view-as', 'session', { id: 1, email: 'fixture@example.invalid', first_name: 'Fixture', last_name: '' })
  let ended = 0
  const listener = () => { ended++ }
  window.addEventListener('view-as-exited', listener)
  api.defaults.adapter = unauthorized
  await assert.rejects(api.get('/uploads/'), error => axios.isCancel(error))
  assert.equal(impersonationTokenStorage.getAccess(), null)
  assert.equal(tokenStorage.getAccess(), 'customer')
  assert.equal(ended, 1)
  window.removeEventListener('view-as-exited', listener)
})

test('final Axios destination cannot escape through normalization with any credential context', async () => {
  const bad = ['/api//external.invalid/file', '//external.invalid/file', '/api/\\external.invalid/file', '\\\\external.invalid/file',
    'http://external.invalid/api/file', 'https://external.invalid/api/file', 'https://app.example.invalid/api/file',
    '/api/%2f%2fexternal.invalid/file', '/api/%5cexternal.invalid/file', '/api/%252fexternal.invalid/file',
    '/api/%2e%2e/file', '/api/../file', '/api/./file', '/api/a/../../file', '/api/\n/external.invalid/file',
    '/api///external.invalid/file', ' /api/uploads/', '/api/uploads/#fragment']
  for (const context of ['customer','operator','view-as']) {
    tokenStorage.set('customer','customer-refresh')
    operatorTokenStorage.set('operator','operator-refresh')
    if (context === 'view-as') impersonationTokenStorage.set('view-as','session',{id:1})
    let dispatches=0
    api.defaults.adapter=async config=>{dispatches++; return ok(config)}
    for (const value of bad) await assert.rejects(api.get(value), value)
    assert.equal(dispatches,0)
    api.defaults.adapter=async config=>{
      const destination=new URL(api.getUri(config),window.location.origin)
      assert.equal(destination.origin,window.location.origin)
      assert.ok(destination.pathname.startsWith('/api/'))
      assert.equal(config.headers.Authorization,`Bearer ${context}`)
      return ok(config)
    }
    await api.get(context === 'operator' ? '/api/operator/me/' : '/api/uploads/')
  }
})

test('ordinary API forms and encoded query values retain their destination', async () => {
  for (const input of ['/api/uploads/','/uploads/','uploads/']) assert.equal(apiPath(input),'/api/uploads/')
  assert.equal(apiPath('/uploads/?q=https%3A%2F%2Fexample.invalid'),'/api/uploads/?q=https%3A%2F%2Fexample.invalid')
})

test('current editor formatting survives sanitize, save/reload, and render', () => {
  const input='<h2 style="margin:20px 0 4px;font-size:14px;font-weight:700;color:#0F1F3D">Heading</h2>'+
    '<p style="text-align:center;font-family:Georgia;font-size:24px;margin-left:40px"><b>bold</b><i>italic</i><u>under</u><strike>strike</strike><sup>2</sup><sub>3</sub></p>'+
    '<font face="Times New Roman" size="5">font</font><ol start="4" type="I" reversed><li value="6">item</li></ol>'+
    '<table><tbody><tr><th colspan="2">head</th></tr><tr><td>cell</td><td>cell</td></tr></tbody></table><a href="#section-1">anchor</a><div style="height:6px"></div>'
  const first=safeContractHtml(input)
  const reloaded=JSON.parse(JSON.stringify({html:first})).html
  const second=safeContractHtml(reloaded)
  assert.equal(second,first)
  const container=document.createElement('div');container.innerHTML=second
  for(const tag of ['b','i','u','strike','sup','sub','h2','ol','li','table','tbody','tr','td','th']) assert.ok(container.querySelector(tag),tag)
  const p=container.querySelector('p')
  assert.equal(p.style.textAlign,'center');assert.equal(p.style.fontSize,'24px');assert.equal(p.style.fontFamily,'Georgia');assert.equal(p.style.marginLeft,'40px')
  assert.equal(container.querySelector('font').getAttribute('face'),'Times New Roman')
  assert.equal(container.querySelector('font').getAttribute('size'),'5')
  assert.equal(container.querySelector('ol').getAttribute('start'),'4')
  assert.equal(container.querySelector('ol').getAttribute('type'),'I')
  assert.ok(container.querySelector('ol').hasAttribute('reversed'))
  assert.equal(container.querySelector('li').getAttribute('value'),'6')
  assert.equal(container.querySelector('h2').style.marginTop,'20px')
  assert.equal(container.querySelector('div').style.height,'6px')
})

test('formatting allowlist rejects active CSS, unsafe fonts and non-editor properties', () => {
  const html=safeContractHtml('<p class="fixed" style="text-align:right;position:fixed;background:url(https://external.invalid);--payload:url(https://external.invalid);font-family:evil;font-size:9999px;margin-left:9999px;behavior:url(evil);color:expression(alert(1))" onclick="alert(1)">safe</p><font face="evil" size="99">text</font><script>alert(1)</script><iframe src="https://external.invalid"></iframe><object data="https://external.invalid"></object><embed src="https://external.invalid"><a href="javascript:alert(1)">bad</a>')
  assert.match(html,/text-align: right/)
  for(const bad of ['external.invalid','position','background','--payload','evil','9999','onclick','<script','<iframe','<object','<embed','javascript:','class=']) assert.ok(!html.includes(bad),bad)
})
