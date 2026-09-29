/* Real Gemini Live proof against an explicitly supplied authenticated server.
   Browser microphone fixture -> real AudioWorklet -> Live -> real audio playback.
   Only a version tool is invoked; no jobs, messages or credentials are emitted. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const playwright = require(process.env.BOB_PLAYWRIGHT_MODULE || 'playwright');
const root = process.env.BOB_VOICE_PROOF_ROOT;
if (!root) throw new Error('Set BOB_VOICE_PROOF_ROOT to an isolated proof-server data folder.');
const server = JSON.parse(fs.readFileSync(path.join(root, 'server.json'), 'utf8'));
const url = process.env.BOB_VOICE_PROOF_URL || server.url;
const engine = process.argv.includes('--webkit') ? 'webkit' : 'chromium';
const evidence = process.env.BOB_VOICE_PROOF_OUTPUT;
if (!evidence) throw new Error('Set BOB_VOICE_PROOF_OUTPUT to an evidence directory.');
const fixtures = process.env.BOB_VOICE_FIXTURES;
if (!fixtures) throw new Error('Set BOB_VOICE_FIXTURES to the folder with question-short/story/interrupt/tool WAV fixtures.');
fs.mkdirSync(evidence, {recursive:true});

async function instrument(page) {
  await page.addInitScript(() => {
    const NativeAudio = window.AudioContext;
    const NativeSocket = window.WebSocket;
    window.voiceProof = {inputPackets:0,outputPackets:0,outputBytes:0,starts:0,stops:0,interruptions:0,tools:0,toolResponses:0,turns:0,tracks:[],sockets:[],closes:[],audio:[],contexts:[]};
    window.AudioContext = class extends NativeAudio {
      constructor(...args) { super(...args); voiceProof.contexts.push(this); }
      createBufferSource() {
        const source = super.createBufferSource(), start = source.start.bind(source), stop = source.stop.bind(source);
        source.start = (...a) => { voiceProof.starts++; return start(...a); };
        source.stop = (...a) => { voiceProof.stops++; return stop(...a); };
        return source;
      }
    };
    window.WebSocket = class extends NativeSocket {
      constructor(...args) {
        super(...args); voiceProof.sockets.push(this);
        this.addEventListener('close', event => voiceProof.closes.push({code:event.code,wasClean:event.wasClean}));
        this.addEventListener('message', event => {
          try {
            const value = JSON.parse(typeof event.data === 'string' ? event.data : new TextDecoder().decode(event.data));
            const content = value.serverContent || {};
            if (content.interrupted) voiceProof.interruptions++;
            if (content.turnComplete) voiceProof.turns++;
            if (value.toolCall) voiceProof.tools++;
            for (const part of content.modelTurn?.parts || []) if (part.inlineData?.mimeType?.startsWith('audio/pcm')) {
              voiceProof.outputPackets++; voiceProof.outputBytes += atob(part.inlineData.data).length;
              if (voiceProof.audio.length < 100) voiceProof.audio.push(part.inlineData.data);
            }
          } catch (_) {}
        });
      }
      send(raw) {
        const value=JSON.parse(raw);
        if (value.realtimeInput?.audio) voiceProof.inputPackets++;
        if (value.toolResponse) {
          voiceProof.toolResponses++;
          voiceProof.outputAtToolResponse=voiceProof.outputPackets;
          voiceProof.turnsAtToolResponse=voiceProof.turns;
        }
        return super.send(raw);
      }
    };
    // Synthetic spoken input is reproducible on Chromium and WebKit. All the
    // production capture/resampling/streaming/playback code still runs unchanged.
    let micContext, destination;
    // WebKit may return another MediaDevices wrapper on the next property read.
    // Override its prototype so the synthetic source is stable across reads.
    Object.defineProperty(Object.getPrototypeOf(navigator.mediaDevices), 'getUserMedia', {configurable:true,writable:true,value:async () => {
      // Use the context already unlocked by the user tap. A second artificial
      // context needs a second activation in WebKit (real getUserMedia does not).
      micContext = voiceProof.contexts.at(-1);
      voiceProof.microphoneContext = micContext;
      destination = micContext.createMediaStreamDestination();
      voiceProof.tracks.push(...destination.stream.getTracks());
      return destination.stream;
    }});
    window.feedVoiceFixture = async (base64) => {
      const bytes = Uint8Array.from(atob(base64), c => c.charCodeAt(0));
      const buffer = await micContext.decodeAudioData(bytes.buffer);
      const source = NativeAudio.prototype.createBufferSource.call(micContext); source.buffer = buffer; source.connect(destination);
      source.start();
      return new Promise(resolve => { source.onended = resolve; });
    };
  });
}

(async () => {
  const browser = await playwright[engine].launch({headless:true,
    ...(engine === 'chromium' && process.env.BOB_CHROMIUM_PATH ? {executablePath:process.env.BOB_CHROMIUM_PATH} : {})});
  const context = await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:1});
  const page = await context.newPage();
  // Older WebKit's Playwright waitForFunction uses eval, which the app correctly
  // forbids. Poll via the inspector instead; keep the production CSP enforced.
  page.waitForFunction = async (predicate, argument, options = {}) => {
    const deadline = Date.now() + (options.timeout || 30000);
    while (Date.now() < deadline) {
      if (await page.evaluate(predicate, argument)) return;
      await new Promise(resolve => setTimeout(resolve, 150));
    }
    throw new Error('Timed out waiting for browser condition: ' + predicate.toString());
  };
  const errors = [], results = {engine,url,synthetic_microphone:true,real_provider:true,checks:[]};
  page.on('pageerror', e => errors.push(e.message));
  await instrument(page);
  const screenshot = name => page.screenshot({path:path.join(evidence,`${engine}-${name}.png`)});
  const feed = async name => page.evaluate(data => window.feedVoiceFixture(data),fs.readFileSync(path.join(fixtures,name+'.wav')).toString('base64'));
  try {
    await page.goto(url+'/login');
    await page.locator('#password').fill(fs.readFileSync(server.password_file,'utf8').trim());
    await page.locator('#login-form button').click();await page.waitForURL(url+'/');
    await page.waitForFunction(()=>!document.querySelector('#message').disabled);
    await page.evaluate(async()=>{
      const session=await (await fetch('/api/session')).json();
      const c=await (await fetch('/api/conversations',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf},body:'{}'})).json();
      localStorage.setItem('bob.conversation',c.id);
    });
    await page.reload();await page.waitForFunction(()=>!document.querySelector('#message').disabled);
    errors.length = 0; // Initial navigation may abort the previous page's fetches.
    // Record only allowlisted playback diagnostics, never provider payloads or credentials.
    await page.evaluate(()=>{
      voiceProof.playbackErrors=[];voiceProof.maxQueuedAudioSeconds=0;
      const play=window.BobVoice.prototype.play;
      window.BobVoice.prototype.play=function(s,data){
        try{return play.call(this,s,data);}
        catch(error){voiceProof.playbackErrors.push({kind:['Audio backlog','Invalid audio'].includes(error.message)?error.message:'Playback error',
          queuedSeconds:Math.max(0,s.nextAudio-s.audio.currentTime)});throw error;}
        finally{voiceProof.maxQueuedAudioSeconds=Math.max(voiceProof.maxQueuedAudioSeconds,s.nextAudio-s.audio.currentTime);}
      };
    });
    const layout=await page.evaluate(()=>{
      const mic=document.querySelector('#mic').getBoundingClientRect(),call=document.querySelector('#live-call').getBoundingClientRect();
      return {overflow:document.documentElement.scrollWidth>innerWidth,right_of_mic:call.left>=mic.right,tap_width:call.width,tap_height:call.height,secure:isSecureContext};
    });
    assert.equal(layout.overflow,false);assert.equal(layout.right_of_mic,true);assert.ok(layout.tap_width>=44&&layout.tap_height>=44);assert.equal(layout.secure,true);
    results.layout=layout;await screenshot('iphone-composer');
    await page.locator('#live-call').click();
    await page.waitForFunction(()=>document.querySelector('#call-dialog').dataset.phase==='listening',null,{timeout:40000});
    await screenshot('iphone-listening');
    const firstTurn=await page.evaluate(()=>voiceProof.turns);
    await feed('question-short');
    await page.waitForFunction(n=>voiceProof.turns>n,firstTurn,{timeout:45000});
    assert.match(await page.locator('.call-bob').last().textContent(),/send/i);
    assert.ok((await page.locator('.call-bob').last().textContent()).trim().split(/\s+/).length <= 45,
      'The explicitly short memory answer must remain brief');
    results.checks.push('spoken input, native spoken reply, shared memory');
    await screenshot('iphone-memory');
    {
      const before=await page.evaluate(()=>({turns:voiceProof.turns,replies:document.querySelectorAll('.call-bob').length,
        outputPackets:voiceProof.outputPackets}));
      await feed('story-complete');
      await page.waitForFunction(n=>voiceProof.turns>n,before.turns,{timeout:90000});
      assert.ok(await page.locator('.call-bob').count()>before.replies, 'A new completed story reply is required');
      const story=await page.locator('.call-bob').last().textContent();
      const words=story.trim().split(/\s+/).length;
      assert.ok(words>=100 && words<=250, 'Requested roughly 150-word story; received '+words+' words');
      assert.match(story,/compass/i);
      assert.doesNotMatch(story,/(?:better at|prefer|can only|must|need to|have to)\s+(?:keep(?:ing)?\s+(?:things|it|replies)\s+)?(?:brief|short|casual)|can(?:not|'t)\s+(?:tell|write|give)\s+(?:you\s+)?(?:a\s+)?(?:long|story)/i);
      assert.ok(await page.evaluate(n=>voiceProof.outputPackets>n,before.outputPackets), 'Story must include actual audio');
      results.requested_story={words,sha256:require('node:crypto').createHash('sha256').update(story).digest('hex')};
      results.checks.push('requested longer story completes with real spoken audio while short answers stay brief');
      await screenshot('iphone-requested-story');
      await page.waitForFunction(()=>document.querySelector('#call-dialog').dataset.phase==='listening',null,{timeout:90000});
    }
    {
      const before=await page.evaluate(()=>({interruptions:voiceProof.interruptions,stops:voiceProof.stops,starts:voiceProof.starts}));
      await feed('story');
      await page.waitForFunction(n=>voiceProof.starts>n,before.starts,{timeout:45000});
      await feed('interrupt');
      await page.waitForFunction(n=>voiceProof.interruptions>n,before.interruptions,{timeout:20000});
      const after=await page.evaluate(()=>({interruptions:voiceProof.interruptions,stops:voiceProof.stops}));
      assert.ok(after.stops>before.stops);results.barge_in={before,after};
      results.checks.push('real provider barge-in clears queued playback');await screenshot('iphone-interrupted');
      // Listening during the interruption is not the end of the new utterance.
      // Wait for Bob's short reply and its completed turn before the next ask.
      // Native transcription may spell the same spoken acknowledgement "Ok".
      await page.waitForFunction(()=>[...document.querySelectorAll('.call-bob')].some(e=>/\bok(?:ay)?\b.*\bjeff\b/i.test(e.textContent)),null,{timeout:45000});
      await page.waitForTimeout(2000);
      await page.waitForFunction(()=>document.querySelector('#call-dialog').dataset.phase==='listening',null,{timeout:45000});
      await feed('tool');
      await page.waitForFunction(()=>voiceProof.tools>0,null,{timeout:45000});
      // The spoken acknowledgement can vary. Only the durable server receipt
      // proves that the actual request was dispatched.
      await page.waitForFunction(async()=>{
        const id=localStorage.getItem('bob.conversation');
        const conversation=await (await fetch('/api/conversations/'+id)).json();
        return conversation.messages.some(m=>m.role==='assistant'&&m.provider==='dispatcher'&&/Web Bob|[0-9a-f]{7}/.test(m.content));
      },null,{timeout:45000});
      await page.waitForFunction(()=>voiceProof.toolResponses>0
        && voiceProof.outputPackets>voiceProof.outputAtToolResponse
        && voiceProof.turns>voiceProof.turnsAtToolResponse,null,{timeout:45000});
      const conversation = await page.evaluate(async()=>{
        const id=localStorage.getItem('bob.conversation');
        return (await fetch('/api/conversations/'+id)).json();
      });
      const receipt=conversation.messages.find(m=>m.role==='assistant'&&m.provider==='dispatcher'&&m.content.includes(server.sha.slice(0,7)));
      assert.ok(receipt, 'a real server dispatcher receipt is required');
      assert.ok(!conversation.messages.some(m=>m.task_id||m.task_ids?.length),'Voice proof must not queue work');
      results.tool_receipt=receipt.content;
      results.checks.push('spoken version lookup reaches authenticated chat handler and receives spoken acknowledgement');
    }
    await page.setViewportSize({width:1280,height:900});await screenshot('desktop-call');
    results.transcript_sha256=require('node:crypto').createHash('sha256').update(await page.locator('#call-transcript').textContent()).digest('hex');
    await page.locator('#end-call').click();
    await page.waitForFunction(()=>document.querySelector('#call-status').textContent.includes('transcript saved'),null,{timeout:15000});
    const microphone = await page.evaluate(()=>voiceProof.tracks.map(t=>t.readyState));
    assert.ok(microphone.length > 0 && microphone.every(state=>state==='ended'),
      'Hangup must stop microphone tracks immediately: ' + JSON.stringify(microphone));
    // WebSocket.close starts an asynchronous close handshake. Saving a short
    // transcript can finish before CLOSED; require completion within five seconds.
    await page.waitForFunction(()=>voiceProof.sockets.length > 0 && voiceProof.sockets.every(s=>s.readyState===3),null,{timeout:5000});
    results.media=await page.evaluate(()=>({inputPackets:voiceProof.inputPackets,outputPackets:voiceProof.outputPackets,outputBytes:voiceProof.outputBytes,
      starts:voiceProof.starts,stops:voiceProof.stops,maxQueuedAudioSeconds:voiceProof.maxQueuedAudioSeconds,
      playbackErrors:voiceProof.playbackErrors,tracksEnded:voiceProof.tracks.every(t=>t.readyState==='ended'),socketsClosed:voiceProof.sockets.every(s=>s.readyState===3)}));
    assert.ok(results.media.inputPackets>10&&results.media.outputBytes>10000&&results.media.starts>0);
    assert.ok(results.media.tracksEnded&&results.media.socketsClosed);results.checks.push('hangup releases microphone and audio transport');
    await page.locator('#end-call').click();await page.reload();
    await page.waitForFunction(()=>/Instinct/i.test(document.querySelector('#messages').textContent));
    results.checks.push('transcript persists through reload');await screenshot('desktop-saved-chat');
    // Browser-level denial recovery with no provider call.
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(()=>{Object.defineProperty(Object.getPrototypeOf(navigator.mediaDevices),'getUserMedia',{configurable:true,writable:true,
      value:async()=>{throw new DOMException('Permission denied','NotAllowedError');}});});
    await page.locator('#live-call').click();
    await page.waitForFunction(()=>document.querySelector('#call-status').textContent.includes('Microphone blocked'));
    await screenshot('iphone-permission');results.checks.push('microphone denial shows recovery and leaves chat usable');
    await page.locator('#end-call').click();
    await page.evaluate(()=>{
      window.AudioContext.prototype.resume = function() {
        return new Promise((_resolve,reject)=>{window.rejectStartupAudio=reject;});
      };
      Object.defineProperty(Object.getPrototypeOf(navigator.mediaDevices),'getUserMedia',{configurable:true,writable:true,
        value:()=>{
          const destination=voiceProof.contexts.at(-1).createMediaStreamDestination();
          const stream=destination.stream;voiceProof.tracks.push(...stream.getTracks());
          return new Promise(resolve=>{window.grantStartupMicrophone=()=>resolve(stream);});
        }});
    });
    await page.locator('#live-call').click();
    await page.locator('#end-call').click();
    await page.evaluate(async()=>{
      rejectStartupAudio(new DOMException('Closed during permission prompt','InvalidStateError'));
      await new Promise(resolve=>setTimeout(resolve,100));
      grantStartupMicrophone();
    });
    await page.waitForFunction(()=>voiceProof.tracks.length>0&&voiceProof.tracks.every(t=>t.readyState==='ended'));
    assert.equal(await page.locator('#call-dialog').getAttribute('data-phase'),'ended');
    await page.locator('#end-call').click();
    await page.locator('#live-call').click();
    await page.evaluate(async()=>{
      rejectStartupAudio(new DOMException('Audio unavailable','NotAllowedError'));
      await new Promise(resolve=>setTimeout(resolve,100));
      grantStartupMicrophone();
    });
    await page.waitForFunction(()=>document.querySelector('#call-status').textContent.includes('Audio could not start'));
    assert.equal(await page.locator('#live-call').getAttribute('aria-pressed'),'false');
    assert.equal(await page.evaluate(()=>voiceProof.sockets.length),0, 'Permission/startup failure must not open the provider');
    assert.equal(await page.evaluate(()=>voiceProof.tracks.every(t=>t.readyState==='ended')),true);
    await screenshot('iphone-audio-startup');
    results.checks.push('late microphone and rejected audio startup clean up without unhandled errors or provider calls');
    assert.deepEqual(errors,[]);results.page_errors=errors;results.ok=true;
    fs.writeFileSync(path.join(evidence,`${engine}-proof.json`),JSON.stringify(results,null,2)+'\n');
    console.log(JSON.stringify(results,null,2));
  } catch(error){
    await screenshot('failure').catch(()=>{});
    console.error(error.message);console.error('UI:',await page.locator('#call-status').textContent().catch(()=>''));
    console.error('Page errors:',errors);process.exitCode=1;
    console.error('Media diagnostics:',await page.evaluate(()=>({contexts:voiceProof.contexts.map(c=>c.state),microphone:voiceProof.microphoneContext?.state,
      tracks:voiceProof.tracks.map(t=>t.readyState),sockets:voiceProof.sockets.map(s=>s.readyState),closes:voiceProof.closes,input:voiceProof.inputPackets,output:voiceProof.outputPackets,
      playbackErrors:voiceProof.playbackErrors,maxQueuedAudioSeconds:voiceProof.maxQueuedAudioSeconds,
      microphoneFunction: navigator.mediaDevices.getUserMedia.toString().slice(0,100)})).catch(()=>null));
  } finally {
    // Even a failed assertion must hang up its own call before closing the tab.
    if (await page.locator('#live-call[aria-pressed="true"]').count()) {
      await page.locator('#end-call').click().catch(()=>{});
      await page.waitForTimeout(700);
    }
    await browser.close();
  }
})().catch(e=>{console.error(e.message);process.exitCode=1;});
