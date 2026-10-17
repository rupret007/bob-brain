/* Browser proof predicate, also exercised by offline negative controls.
   Require an acknowledged new utterance after the actual provider interruption. */
module.exports = function interruptionAcknowledged(before) {
  const proof = window.voiceProof, protocol = window.voiceEvents?.snapshot();
  if (!proof || !protocol || proof.stops <= before.stops ||
      proof.startsAtInterruption === undefined || proof.starts <= proof.startsAtInterruption) return false;
  const interruption = protocol.events.findLast(event => event.kind === 'interrupted' &&
    event.counts.interruptions > before.interruptions);
  if (!interruption) return false;
  const generated = protocol.events.find(event => event.seq > interruption.seq &&
    event.kind === 'generation_complete' && event.counts.outputAudio > interruption.counts.outputAudio);
  const completed = generated && protocol.events.find(event => event.seq > generated.seq &&
    event.kind === 'turn_complete' && event.counts.outputAudio > interruption.counts.outputAudio);
  if (!completed) return false;
  const requests = [...document.querySelectorAll('.call-you')], replies = [...document.querySelectorAll('.call-bob')];
  if (requests.length <= before.requests || replies.length <= before.replies) return false;
  const request = requests.at(-1).textContent.replace(/^You:\s*/i, '').trim();
  const reply = replies.at(-1).textContent.replace(/^Bob:\s*/i, '').trim();
  if (!/\bstop\b/i.test(request) || !/\bok(?:ay)?\b/i.test(request) ||
      !/^ok(?:ay)?(?:\s*[,!]\s*|\s+)?(?:jeff)?[.!]?$/i.test(reply)) return false;
  // Native ASR can omit the name. Verify what was recognized and report that
  // limitation, while requiring it in the reply whenever the request retains it.
  return !/\bjeff\b/i.test(request) || /\bjeff\b/i.test(reply);
};
