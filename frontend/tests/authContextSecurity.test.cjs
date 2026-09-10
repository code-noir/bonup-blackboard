const { test, beforeEach, afterEach } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const ts = require('typescript')
const { JSDOM } = require(path.join(process.env.BONUP_TEST_TOOLS || '.', 'jsdom'))
const resolve = Module._resolveFilename
Module._resolveFilename = function (name, ...args) {
  return resolve.call(this, name.startsWith('@/') ? path.join(__dirname, '../src', name.slice(2)) : name, ...args)
}
for (const ext of ['.ts','.tsx']) require.extensions[ext] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'), {
  compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020,esModuleInterop:true},
}).outputText,filename)
const React = require('react')
const { act } = React
const { createRoot } = require('react-dom/client')
const { MemoryRouter, useLocation } = require('react-router-dom')
const axios = require('axios').default
const {default:api,tokenStorage,operatorTokenStorage,impersonationTokenStorage}=require('../src/api/client.ts')
const {AuthProvider,useAuth}=require('../src/context/AuthContext.tsx')
const {OperatorProvider,useOperator}=require('../src/context/OperatorContext.tsx')
const CustomerSignOutButton=require('../src/components/layout/CustomerSignOutButton.tsx').default
const AdminLayout=require('../src/pages/admin/AdminLayout.tsx').default
const OperatorLogin=require('../src/pages/OperatorLogin.tsx').default
let dom,root,auth,operator,calls,location
const ok=(config,data={})=>({config,data,status:200,statusText:'OK',headers:{}})
function Probe() {
  auth=useAuth();operator=useOperator();location=useLocation().pathname
  return React.createElement(React.Fragment,null,
    React.createElement(CustomerSignOutButton),
    location==='/operator/login' ? React.createElement(OperatorLogin) : React.createElement(AdminLayout))
}
beforeEach(()=>{
  dom=new JSDOM('<div id="root"></div>',{url:'https://app.example.invalid/'})
  global.window=dom.window;global.document=dom.window.document;global.localStorage=dom.window.localStorage;global.Event=dom.window.Event
  global.IS_REACT_ACT_ENVIRONMENT=true
  calls=[]
  api.defaults.adapter=async config=>{
    calls.push(config)
    return ok(config,config.url==='/operator/me/' ? {operator:{id:1,email:'operator@example.invalid'}} : {id:1,email:'customer@example.invalid'})
  }
  root=createRoot(document.getElementById('root'))
})
afterEach(async()=>{await act(async()=>root.unmount());dom.window.close()})
const mount=()=>act(async()=>root.render(React.createElement(MemoryRouter,{initialEntries:['/operator']},React.createElement(AuthProvider,null,React.createElement(OperatorProvider,null,React.createElement(Probe))))))
const credentials=()=>{tokenStorage.set('customer','customer-refresh');operatorTokenStorage.set('operator','operator-refresh')}
const viewAs=()=>impersonationTokenStorage.set('view-as','synthetic-session',{id:2,email:'view@example.invalid'})

test('operator UI logout dispatches correct credentials and preserves customer login',async()=>{
  credentials();await mount()
  await act(async()=>Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Sign out of Operator Console').click())
  const request=calls.find(c=>c.url==='/operator/auth/logout/')
  assert.ok(request);assert.equal(request.headers.Authorization,'Bearer operator');assert.equal(JSON.parse(request.data).refresh,'operator-refresh')
  assert.equal(operatorTokenStorage.getRefresh(),null);assert.equal(operatorTokenStorage.getAccess(),null)
  assert.equal(tokenStorage.getRefresh(),'customer-refresh');assert.equal(location,'/operator/login')
  assert.ok(!calls.some(c=>c.url==='/users/logout/'))
})

test('operator logout ends local View-As while calling operator server endpoint',async()=>{
  credentials();viewAs();await mount()
  await act(async()=>operator.logoutOperator())
  assert.equal(impersonationTokenStorage.getAccess(),null);assert.equal(operator.impersonatedUser,null)
  assert.equal(calls.find(c=>c.url==='/operator/auth/logout/').headers.Authorization,'Bearer operator')
  assert.equal(tokenStorage.getRefresh(),'customer-refresh')
})

test('network failure clears operator credentials and login UI reports unconfirmed revocation',async()=>{
  credentials();viewAs();await mount()
  api.defaults.adapter=async()=>{throw new Error('synthetic-private-provider-error')}
  await act(async()=>Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Sign out of Operator Console').click())
  assert.equal(operatorTokenStorage.getAccess(),null);assert.equal(operatorTokenStorage.getRefresh(),null);assert.equal(impersonationTokenStorage.getAccess(),null)
  assert.match(document.querySelector('[role="alert"]').textContent,/Server sign-out could not be confirmed/)
  assert.doesNotMatch(document.body.textContent,/synthetic-private/)
})

for(const failure of [false,true]) test(`stale operator profile ${failure?'rejection':'cancellation'} cannot clear new identity`,async()=>{
  credentials();await mount()
  let finish,started
  const ready=new Promise(resolve=>{started=resolve})
  api.defaults.adapter=config=>new Promise((resolve,reject)=>{finish=()=>failure?reject(new Error('old failure')):resolve(ok(config,{operator:{id:1}}));started()})
  let pending
  await act(async()=>{pending=operator.refreshOperator();await ready;operatorTokenStorage.set('new-operator','new-refresh');finish();await pending})
  assert.equal(operatorTokenStorage.getAccess(),'new-operator');assert.equal(operatorTokenStorage.getRefresh(),'new-refresh')
})

test('current operator authentication rejection clears invalid credentials',async()=>{
  credentials();await mount()
  api.defaults.adapter=async config=>{config._retry=true;throw new axios.AxiosError('Unauthorized','ERR_BAD_REQUEST',config,{}, {status:401,config,data:{},headers:{}})}
  await act(async()=>operator.refreshOperator())
  assert.equal(operatorTokenStorage.getRefresh(),null);assert.equal(operator.operator,null)
})

test('customer-visible View-As action exits only View-As and preserves underlying tokens',async()=>{
  credentials();viewAs();await mount()
  await act(async()=>Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Exit User View').click())
  assert.equal(calls.find(c=>c.url==='/operator/view-as/exit/').headers.Authorization,'Bearer view-as')
  assert.ok(!calls.some(c=>c.url==='/users/logout/'))
  assert.equal(impersonationTokenStorage.getAccess(),null)
  assert.equal(operatorTokenStorage.getRefresh(),'operator-refresh');assert.equal(tokenStorage.getRefresh(),'customer-refresh');assert.equal(location,'/operator')
})

test('direct customer logout refuses View-As before sending any logout request',async()=>{
  credentials();viewAs();await mount()
  await assert.rejects(auth.logout(),/Exit User View/)
  assert.ok(!calls.some(c=>c.url==='/users/logout/'))
  assert.equal(tokenStorage.getRefresh(),'customer-refresh')
})

test('ordinary customer sign-out still revokes customer refresh only',async()=>{
  credentials();await mount()
  await act(async()=>Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Sign out').click())
  assert.equal(calls.find(c=>c.url==='/users/logout/').headers.Authorization,'Bearer customer')
  assert.equal(tokenStorage.getRefresh(),null);assert.equal(operatorTokenStorage.getRefresh(),'operator-refresh');assert.equal(location,'/login')
})

for (const [mime,tag] of [['image/png','img'],['audio/mpeg','audio'],['video/mp4','video'],['application/pdf','iframe']]) {
  test(`public Share ${mime} retains same-origin delivery in built-page component check`,async()=>{
    const built=fs.readFileSync(path.join(__dirname,'../dist/index.html'),'utf8')
    const page=new JSDOM(built,{url:'https://app.example.invalid/share/synthetic-share'})
    const policy=page.window.document.querySelector('meta[http-equiv="Content-Security-Policy"]').content
    assert.equal(policy,"script-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'")
    page.window.close()
    const {Routes,Route}=require('react-router-dom')
    const VaultShare=require('../src/pages/VaultShare.tsx').default
    const delivery='/api/uploads/shares/synthetic-share/delivery/'
    api.defaults.adapter=async config=>{
      calls.push(config)
      return ok(config,{file_name:'synthetic-fixture',file_type:mime==='application/pdf'?'pdf':'other',content_type:mime,file_size:10,delivery_url:delivery})
    }
    await act(async()=>root.render(React.createElement(MemoryRouter,{initialEntries:['/share/synthetic-share']},React.createElement(Routes,null,React.createElement(Route,{path:'/share/:token',element:React.createElement(VaultShare)})))))
    assert.equal(document.querySelector(tag).getAttribute('src'),delivery)
    assert.equal(calls[0].headers.Authorization,undefined)
    assert.equal(new URL(document.querySelector('a').href).origin,window.location.origin)
    assert.ok(!document.querySelector('object,embed'))
  })
}
