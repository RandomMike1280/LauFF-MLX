/* LauFF single-garden mailbox. Set GAME_TOKEN and WORKER_TOKEN in Script Properties.
 * Deploy as a web app executing as owner, access Anyone. Tokens authenticate POST bodies or game-only GET payloads.
 * Cache eviction is fail-closed: the game must start a new session.
 */
const TTL_MS = 45000;
const CACHE_KEY = 'lauff-v1';
const MOVES = ['MOVE_NORTH','MOVE_EAST','MOVE_SOUTH','MOVE_WEST'];
function doGet(e) {
  if (!e || !e.parameter || !e.parameter.q) return output('LauFF relay v3: authenticated game GET / worker POST');
  try {
    if (e.parameter.q.length > 16000) return output('ERROR|REQUEST');
    const q = JSON.parse(e.parameter.q);
    // Never permit worker credentials or result injection through the GET route.
    if (!q || !['probe','start','observe','poll','ack','cancel'].includes(q.op)) return output('ERROR|OP');
    return handle(q);
  } catch (error) { return output('ERROR|INVALID'); }
}
function output(s) { return ContentService.createTextOutput(s).setMimeType(ContentService.MimeType.TEXT); }
function doPost(e) {
  try {
    if (!e || !e.postData || e.postData.contents.length > 16000) return output('ERROR|REQUEST');
    const q = JSON.parse(e.postData.contents);
    return handle(q);
  } catch (error) { return output('ERROR|INVALID'); }
}
function handle(q) {
  try {
    if (!q || typeof q !== 'object' || typeof q.op !== 'string') return output('ERROR|REQUEST');
    const role = q.op && q.op.indexOf('worker_') === 0 ? 'WORKER_TOKEN' : 'GAME_TOKEN';
    const expected = PropertiesService.getScriptProperties().getProperty(role);
    if (!expected || expected.length < 32 || q.token !== expected) return output('ERROR|AUTH');
    const lock = LockService.getScriptLock();
    if (!lock.tryLock(500)) return output('ERROR|BUSY');
    try {
      const cache = CacheService.getScriptCache();
      let state = JSON.parse(cache.get(CACHE_KEY) || 'null');
      const result = exchange(q, state, Date.now(), () => Utilities.getUuid());
      if (result.state) cache.put(CACHE_KEY, JSON.stringify(result.state), 300);
      return output(result.text);
    } finally { lock.releaseLock(); }
  } catch (error) { return output('ERROR|INVALID'); }
}
function validInt(n, low, high) { return typeof n === 'number' && Number.isSafeInteger(n) && n >= low && n <= high; }
function validateObservation(o, session) {
  if (!o || o.v !== 1 || o.session !== session || !validInt(o.seq, 1, 1000000000) ||
      !validInt(o.x, -10000, 10000) || !validInt(o.z, -10000, 10000) ||
      typeof o.can_harvest !== 'boolean' || !validInt(o.fruit_count, 0, 1000000) ||
      !validInt(o.fruit_capacity, 1, 1000000) || !Array.isArray(o.tiles) || o.tiles.length !== 5 ||
      !['NONE','HARVEST_CONFIRMED','HARVEST_UNCONFIRMED','WAIT','REJECTED','PAUSED','MOVED','MOVE_UNCONFIRMED','CAPACITY','ERROR'].includes(o.previous_outcome)) throw Error('observation');
  if (o.autonomous !== undefined && typeof o.autonomous !== 'boolean') throw Error('mode');
  const offsets = [[0,0],[0,-1],[1,0],[0,1],[-1,0]];
  o.tiles.forEach((t, i) => {
    if (!t || t.x !== o.x + offsets[i][0] || t.z !== o.z + offsets[i][1] ||
        typeof t.known !== 'boolean' || typeof t.has_fruit !== 'boolean' ||
        typeof t.plant !== 'string' || t.plant.length > 80 ||
        typeof t.fruit_percent !== 'number' || !Number.isFinite(t.fruit_percent) ||
        t.fruit_percent < -1 || t.fruit_percent > 10000) throw Error('tile');
  });
}
function exchange(q, s, now, uuid) {
  const out = text => ({state:s, text});
  if (q.op === 'probe') return out('PONG|1');
  if (q.op === 'start') {
    s = {session:uuid(), sequence:0, pending:null, command:null, ack:null};
    return out('SESSION|' + s.session);
  }
  if (q.op === 'worker_poll') return out(JSON.stringify({v:1, session:s && s.session,
    observation:s && s.pending && now < s.pending.deadline_ms ? s.pending : null, ack:s && s.ack}));
  if (!s || q.session !== s.session) return out('ERROR|SESSION');
  if (q.op === 'observe') {
    validateObservation(q.observation, s.session);
    const o = q.observation;
    if (o.seq < s.sequence || (o.seq === s.sequence && !s.pending)) return out('ERROR|SEQUENCE');
    if (o.seq === s.sequence) {
      if (JSON.stringify(o) !== JSON.stringify(s.pending.observation)) return out('ERROR|CONFLICT');
      return out('PENDING'); // retry does not extend lifetime
    }
    if (s.pending && now < s.pending.deadline_ms) return out('ERROR|OUTSTANDING');
    s.sequence = o.seq;
    s.pending = {observation:o, created_ms:now, deadline_ms:now + TTL_MS};
    s.command = null;
    return out('PENDING');
  }
  if (q.op === 'cancel') {
    const outcome = q.outcome || 'REJECTED';
    if (!['PAUSED','REJECTED'].includes(outcome)) return out('ERROR|ACK');
    if (s.pending) s.ack = {session:s.session, seq:s.sequence, outcome, at_ms:now};
    s.pending = null; s.command = null;
    return out('OK');
  }
  if (q.op === 'ack') {
    if (!validInt(q.seq, 1, 1000000000) || q.seq !== s.sequence ||
        !['HARVEST_CONFIRMED','HARVEST_UNCONFIRMED','WAIT','REJECTED','PAUSED','MOVED','MOVE_UNCONFIRMED','CAPACITY','ERROR'].includes(q.outcome)) return out('ERROR|ACK');
    if (!s.pending) return out(s.ack && s.ack.seq === q.seq && s.ack.outcome === q.outcome ? 'OK' : 'ERROR|ACK');
    s.ack = {session:s.session, seq:q.seq, outcome:q.outcome, at_ms:now};
    s.pending = null; s.command = null;
    return out('OK');
  }
  if (!s.pending || q.seq !== s.sequence) return out('ERROR|SEQUENCE');
  if (now >= s.pending.deadline_ms) { s.pending = null; s.command = null; return out('ERROR|EXPIRED'); }
  if (q.op === 'worker_result') {
    if (!['HARVEST','WAIT',...MOVES].includes(q.action)) return out('ERROR|ACTION');
    if (MOVES.includes(q.action)) {
      const o = s.pending.observation;
      if (o.autonomous !== true || o.can_harvest || o.fruit_count >= o.fruit_capacity ||
          !o.tiles[MOVES.indexOf(q.action)+1].known) return out('ERROR|MOVE');
    }
    if (s.command && s.command !== q.action) return out('ERROR|CONFLICT');
    s.command = q.action;
    return out('OK');
  }
  if (q.op === 'poll') {
    if (!s.command) return out('PENDING');
    const o = s.pending.observation;
    return out(['C',s.session,o.seq,o.x,o.z,s.pending.deadline_ms-now,s.command].join('|'));
  }
  return out('ERROR|OP');
}
// The pure state machine is shared with offline contract tests; Apps Script ignores this.
if (typeof module !== 'undefined') module.exports = {exchange, validateObservation};
