// Drive the localhost mock rig in headless Chrome and capture demo frames.
import fs from 'node:fs';
import path from 'node:path';

const OUT = process.argv[2];
const BASE = 'http://127.0.0.1:18799';
const RESUME = process.argv[3];
fs.mkdirSync(OUT, { recursive: true });

const ver = await (await fetch('http://127.0.0.1:9333/json/version')).json();
const ws = new WebSocket(ver.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r, { once: true }));
let id = 0; const pending = new Map();
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); }
});
function send(method, params = {}, sessionId) {
  const i = ++id; ws.send(JSON.stringify({ id: i, method, params, sessionId }));
  return new Promise((res, rej) => pending.set(i, { res, rej }));
}
const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
const S = (m, p) => send(m, p, sessionId);
await S('Page.enable'); await S('DOM.enable'); await S('Runtime.enable');
const W = 820, H = 560;
await S('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 2, mobile: false });
await S('Emulation.setFocusEmulationEnabled', { enabled: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const ev = async expr => (await S('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result.value;

const frames = [];
let n = 0;
let currentUrl = '';
async function shot(caption, hold = 1) {
  const { data } = await S('Page.captureScreenshot', { format: 'png' });
  const f = path.join(OUT, `f${String(n++).padStart(3, '0')}.png`);
  fs.writeFileSync(f, Buffer.from(data, 'base64'));
  frames.push({ file: f, caption, hold, url: currentUrl });
}
async function go(url) {
  currentUrl = url;
  await S('Page.navigate', { url }); await sleep(700);
}
async function center(sel) {
  await ev(`document.querySelector(${JSON.stringify(sel)}).scrollIntoView({block:'center'})`);
  await sleep(150);
  return ev(`(()=>{const r=document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect();return {x:r.x+Math.min(r.width/2,60),y:r.y+r.height/2}})()`);
}
async function click(sel) {
  const { x, y } = await center(sel);
  for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased'])
    await S('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 });
  await sleep(120);
}
async function typeText(text, caption, chunks = 3) {
  const step = Math.ceil(text.length / chunks);
  for (let i = 0; i < text.length; i += step) {
    await S('Input.insertText', { text: text.slice(i, i + step) });
    await sleep(40);
    await shot(caption, 1);
  }
}
async function field(sel, text, caption) { await click(sel); await typeText(text, caption, Math.min(3, text.length)); }
async function select(name, optionText, caption) {
  await click(`#${name}-input`);
  await shot(caption, 1);
  const optSel = `[id^="react-select-${name}-option"]`;
  const idx = await ev(`[...document.querySelectorAll('${optSel}')].findIndex(o=>o.textContent===${JSON.stringify(optionText)})`);
  await click(`#react-select-${name}-option-${idx}`);
  await shot(caption, 2);
}

// 1. feed
await go(`${BASE}/feed`);
await shot('Scan: reads your JobRight feed, newest first', 5);
// 2. gate
await go(`${BASE}/jobs/info/a1f0c0de0001`);
await shot('Filter: title, term, pay, location all match', 4);
// 3. form
const apply = await ev(`document.getElementById('original-post').getAttribute('href')`);
await go(BASE + apply);
await ev(`document.querySelector('h2:nth-of-type(3)')?.scrollIntoView({block:'start'})`);
await shot('Fill: opens the application in its own tab', 3);
await field('#first_name', 'Test', 'Fill: real clicks and typing, field by field');
await field('#last_name', 'Applicant', 'Fill: real clicks and typing, field by field');
await field('#email', 'test@example.com', 'Fill: answers come from your standing answers');
await field('#phone', '5555550100', 'Fill: answers come from your standing answers');
// resume
const { root } = await S('DOM.getDocument', {});
const { nodeId } = await S('DOM.querySelector', { nodeId: root.nodeId, selector: '#resume' });
await center('#resume');
await S('DOM.setFileInputFiles', { nodeId, files: [RESUME] });
await sleep(400);
await shot('Upload: attaches the resume tailored for this job', 4);
await select('degree', 'Bachelor of Science (BS)', 'Dropdowns: opens, then clicks the option');
await select('sponsorship', 'No', 'Dropdowns: opens, then clicks the option');
await select('how_heard', 'Company careers page', 'Dropdowns: opens, then clicks the option');
await click('#why_us');
await typeText('I build backend services in Python and ship them with CI on GitHub Actions. Acme Robotics asks for the same stack, and my internship billing service is the closest match.', 'Essay: drafted from your resume, under the 1000 character limit', 4);
await click('#consent');
await shot('Consent: ticks the required box only', 3);
await center('#submit-application');
await ev(`window.scrollTo(0, document.body.scrollHeight)`); await sleep(150);
await ev(`document.getElementById('submit-application').style.outline='3px solid #E8590C';document.getElementById('submit-application').style.outlineOffset='3px'`);
await shot('Stops at Submit. You review and click it.', 8);

fs.writeFileSync(path.join(OUT, 'frames.json'), JSON.stringify(frames, null, 1));
console.log('frames', frames.length);
await send('Target.closeTarget', { targetId });
ws.close();
