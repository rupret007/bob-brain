/* Real phone-sized browser login/composer/history/tools checks; no auth output. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const pw = require(process.env.BOB_PLAYWRIGHT_MODULE || './node_modules/playwright');
pw.expect = require((process.env.BOB_PLAYWRIGHT_MODULE || './node_modules/playwright') + '/test').expect;
const base = process.env.WEBBOB_URL || 'https://jeffs-mac-mini.tail758ab4.ts.net';
const engine = process.env.WEBBOB_BROWSER || 'webkit';
const full = process.env.WEBBOB_FULL === '1';
const evidence = path.join(__dirname, 'evidence', 'e2e-0927-' + engine + (full ? '-final' : '-baseline'));
fs.mkdirSync(evidence, {recursive:true, mode:0o700});
const checks = [], errors = [], httpErrors = [];
const appendCheck = checks.push.bind(checks);
checks.push = (...rows) => {
  for (const row of rows) console.log(JSON.stringify({check:row.check,provider:row.provider}));
  return appendCheck(...rows);
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const browser = await pw[engine].launch({headless:true});
  const context = await browser.newContext({viewport:{width:390,height:844}, isMobile:true, hasTouch:true, deviceScaleFactor:3});
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  page.on('pageerror', e => errors.push(e.message));
  page.on('response', r => { if (r.status() >= 500) httpErrors.push({path:new URL(r.url()).pathname,status:r.status()}); });
  try {
    await page.goto(base);
    await page.locator('#password').waitFor();
    await page.locator('#password').fill('wrong-e2e-password');
    await page.locator('#login-form button').click();
    await pw.expect(page.locator('#login-error')).toContainText('did not match');
    await page.locator('#password').fill(fs.readFileSync(path.join(__dirname,'.password'),'utf8').trim());
    await page.locator('#login-form button').click();
    await page.waitForURL(base + '/');
    await pw.expect(page.locator('#message')).toBeEnabled();
    const cookie = (await context.cookies()).find(c => c.name === 'bob_session');
    assert(cookie && cookie.httpOnly && cookie.sameSite === 'Strict');
    if (base.startsWith('https:')) assert(cookie.secure);
    checks.push({check:'login_rejection_success_secure_cookie',ok:true});
    const previous = await page.locator('#conversations').inputValue();
    await page.locator('#open-chats').click();
    await page.locator('#new-chat-dialog').click();
    await pw.expect(page.locator('#conversations')).not.toHaveValue(previous);
    await pw.expect(page.locator('#stop')).toBeHidden();
    const cid = await page.locator('#conversations').inputValue();
    async function send(text) {
      const old = await (await context.request.get(base + '/api/conversations/' + cid)).json();
      await page.locator('#message').fill(text);
      await page.locator('#send').click();
      let value;
      const end = Date.now()+300000;
      while(Date.now()<end) {
        value = await (await context.request.get(base + '/api/conversations/' + cid)).json();
        if(value.messages.length>old.messages.length && ['done','error','waiting'].includes(value.messages.at(-1).status)) break;
        await sleep(400);
      }
      const message=value.messages.at(-1);
      assert.equal(message.status,'done',message.content);
      await pw.expect(page.locator('#stop')).toBeHidden({timeout:10000});
      await pw.expect(page.locator('#message')).toHaveValue('');
      checks.push({check:text,provider:message.provider,reply:message.content,conversation_id:cid});
      return message;
    }
    let message = await send('My imaginary boat is named Copper Heron. Give it a short motto and explain why it fits.');
    assert(['codex','cursor','claude','gemini','minimax'].includes(message.provider));
    await page.reload();
    await pw.expect(page.locator('#messages')).toContainText('Copper Heron');
    assert.equal(await page.locator('#conversations').inputValue(),cid);
    message = await send('What is my imaginary boat called, and what motto did you suggest?');
    assert(message.content.toLowerCase().includes('copper heron'));
    if (!(await page.locator('[data-chip="job"]').isVisible())) await page.locator('#toggle-chips').click();
    await page.locator('[data-chip="job"]').click();
    await pw.expect(page.locator('#message')).toHaveValue('start a job: ');
    await page.locator('#message').fill('');
    checks.push({check:'start_job_chip_prefills_composer',ok:true});
    if(full) {
      message = await send('run command: uptime');
      assert.equal(message.provider,'mini'); assert(message.content.includes('exit 0'));
      message = await send('repo status: conductor');
      assert.equal(message.provider,'mini'); assert(message.content.includes('draft/'));
      message = await send('run command: git push --force');
      assert.equal(message.action_card.state,'refused');
      await page.locator('[data-chip="council"]').click();
      await pw.expect(page.locator('.action-approve').last()).toHaveText('Yes, run council');
      await page.locator('.action-deny').last().click();
      await pw.expect(page.locator('#messages')).toContainText('dismissed');
      checks.push({check:'council_chip_and_dismiss',ok:true});
      await page.locator('.bottom-tab[data-bottom="settings"]').click();
      await page.locator('#provider-choice').selectOption('codex');
      await page.locator('.bottom-tab[data-bottom="chat"]').click();
      await page.locator('#message').fill('Tell me a detailed fictional story about an imaginary lighthouse keeper, with at least twelve paragraphs.');
      await page.locator('#send').click();
      await pw.expect(page.locator('#stop')).toBeVisible();
      await page.locator('#stop').click();
      await pw.expect(page.locator('#stop')).toBeHidden({timeout:15000});
      const stopped = await (await context.request.get(base + '/api/conversations/' + cid)).json();
      assert.equal(stopped.messages.at(-1).status,'cancelled');
      checks.push({check:'stop_cancels_real_reply',ok:true});
    }
    for(const tab of ['ops','lanes','settings','chat']) {
      await page.locator(`.bottom-tab[data-bottom="${tab}"]`).click();
      await page.locator(`[data-view="${tab}"]:not([hidden])`).waitFor();
      const metrics=await page.evaluate(() => ({width:innerWidth,scroll:document.documentElement.scrollWidth}));
      assert(metrics.scroll<=metrics.width,JSON.stringify({tab,metrics}));
      if(tab==='chat') await pw.expect(page.locator('#messages .message').last()).toHaveCSS('opacity','1');
      await page.screenshot({path:path.join(evidence,tab+'.png'),animations:'disabled'});
      checks.push({check:'phone_tab_'+tab,no_horizontal_overflow:true});
    }
    // A second phone viewport catches controls pushed outside the screen.
    await page.setViewportSize({width:430,height:932});
    const sendBox=await page.locator('#send').boundingBox();
    assert(sendBox && sendBox.y+sendBox.height<=932 && sendBox.x+sendBox.width<=430);
    await page.screenshot({path:path.join(evidence,'chat-large-phone.png'),animations:'disabled'});
    await page.locator('.bottom-tab[data-bottom="settings"]').click();
    await page.locator('#logout-settings').click();
    await page.waitForURL('**/login');
    assert.equal((await context.request.get(base+'/api/session')).status(),401);
    checks.push({check:'logout_invalidates_session',ok:true});
    assert.deepEqual(errors,[]); assert.deepEqual(httpErrors,[]);
    const result={result:'PASS',url:base,engine,checks,browserErrors:errors,httpErrors};
    fs.writeFileSync(path.join(evidence,'proof.json'),JSON.stringify(result,null,2)+'\n',{mode:0o600});
    console.log(JSON.stringify({result:'PASS',engine,checks:checks.length,evidence}));
  } catch(e) {
    await page.screenshot({path:path.join(evidence,'failure.png')}).catch(()=>{});
    fs.writeFileSync(path.join(evidence,'proof.json'),JSON.stringify({result:'FAIL',error:e.message,checks,browserErrors:errors,httpErrors},null,2));
    throw e;
  } finally { await browser.close(); }
})().catch(e => {console.error(e.stack);process.exitCode=1;});
