from __future__ import annotations
import json
from pathlib import Path
import threading
import time
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from .protocol import observation, POLL_SECONDS


class Relay:
    def __init__(self, url, token):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname != 'script.google.com' or not parsed.path.endswith('/exec'):
            raise ValueError('use a deployed https://script.google.com/.../exec relay URL')
        if len(token) < 32:
            raise ValueError('worker token must have at least 32 characters')
        self.url, self.token, self.last_request = url, token, 0.0

    def call(self, op, **values):
        time.sleep(max(0, POLL_SECONDS - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        body = json.dumps(dict(values, op=op, token=self.token)).encode()
        request = Request(self.url, data=body, headers={'Content-Type':'application/json'}, method='POST')
        with urlopen(request, timeout=4.5) as response:
            raw = response.read(32001)
        if len(raw) > 32000:
            raise ValueError('relay response too large')
        text = raw.decode()
        if text.startswith('ERROR|'):
            raise ValueError(text)
        return text


class Evidence:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / 'events.jsonl'
        self.lock = threading.Lock()
        self.state = {'status':'starting', 'mode':'real neural worker', 'latest':None, 'ack':None}

    def update(self, **values):
        with self.lock:
            self.state.update(values)
            self.state['updated_at'] = time.time()

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def record(self, kind, **values):
        event = dict(values, kind=kind, at=time.time())
        with self.lock, self.path.open('a') as stream:
            stream.write(json.dumps(event, allow_nan=False) + '\n')
        return event


def decide(obs, trial, threshold):
    observation(obs)
    # Capacity/harvestability are vetoes. The positive decision requires MN9 output.
    return ('HARVEST' if trial['score_hz'] >= threshold and obs['can_harvest']
            and obs['fruit_count'] < obs['fruit_capacity'] else 'WAIT')


def run_worker(relay, brain, calibration, evidence, stop, silenced=False, navigation=None, navigation_calibration=None):
    completed = None
    last_ack = None
    trial_counter = 0
    evidence.record('start', provenance=brain.provenance, calibration=calibration,
                    intervention='sweet-neuron outgoing synapses silenced' if silenced else 'normal')
    evidence.update(status='waiting for game', threshold_hz=calibration['threshold_hz'],
                    provenance=brain.provenance, calibration=calibration, intervention='silenced' if silenced else 'normal')
    if navigation is not None:
        evidence.record('navigation_model', provenance=navigation.provenance, calibration=navigation_calibration)
        evidence.update(navigation_provenance=navigation.provenance,
                        navigation_calibration=navigation_calibration,
                        navigation_enabled=True)
    while not stop.is_set():
        try:
            message = json.loads(relay.call('worker_poll'))
            ack = message.get('ack')
            if ack and ack != last_ack:
                evidence.record('game_outcome', **ack)
                evidence.update(ack=ack)
                last_ack = ack
            pending = message.get('observation')
            if pending is None:
                evidence.update(status='waiting for game', error=None)
                stop.wait(POLL_SECONDS)
                continue
            obs = observation(pending['observation'])
            key = (obs['session'], obs['seq'])
            if completed and completed['key'] == key:
                # Safe retry of the same decision; never recompute a duplicate observation.
                action = completed['action']
            else:
                remaining = (pending['deadline_ms'] - pending['created_ms']) / 1000
                if not 0 < remaining <= 45:
                    raise ValueError('invalid relay deadline')
                trial_counter += 1
                # Live seeds cannot overlap calibration or held-out seeds.
                seed = 1_000_000 + trial_counter
                evidence.update(status='simulating one second', observation=obs)
                trial = brain.trial(obs['can_harvest'], seed, silenced)
                if trial.get('visual_activity') is not None:
                    evidence.update(brain_activity=dict(trial['visual_activity'], at=time.time(), phase='feeding',
                                                        session=obs['session'], seq=obs['seq']))
                action = decide(obs, trial, calibration['threshold_hz'])
                nav_trial = None
                if (navigation is not None and obs.get('autonomous') is True and
                    not obs['can_harvest'] and obs['fruit_count'] < obs['fruit_capacity']):
                    from .navigation import cues_from_observation, decode, DIRECTIONS
                    evidence.update(status='simulating neural direction response')
                    nav_trial = navigation.trial(cues_from_observation(obs), seed + 2_000_000, silenced)
                    if nav_trial.get('visual_activity') is not None:
                        evidence.update(brain_activity=dict(nav_trial['visual_activity'], at=time.time(), phase='navigation',
                                                            session=obs['session'], seq=obs['seq']))
                    action = decode(nav_trial, navigation_calibration['decoder'])
                    # A veto never substitutes a different direction.
                    if action.startswith('MOVE_'):
                        destination = obs['tiles'][1+DIRECTIONS.index(action[5:])]
                        if not destination['known']:
                            action = 'WAIT'
                    nav_trial['action'] = action
                trial['navigation'] = nav_trial
                event = evidence.record('neural_decision', observation=obs, trial=trial, action=action,
                                        fingerprint=brain.fingerprint, threshold_hz=calibration['threshold_hz'])
                evidence.update(latest=event)
                completed = {'key':key, 'action':action}
            # The relay enforces its own deadline after simulation and before delivery.
            response = relay.call('worker_result', session=key[0], seq=key[1], action=action)
            if response != 'OK':
                raise ValueError('unexpected result acknowledgement')
            evidence.update(status='decision published; awaiting game outcome', error=None)
        except Exception as error:
            # Never log request bodies or credentials.
            name = type(error).__name__
            reason = str(error) if isinstance(error, ValueError) else name
            evidence.record('worker_error', error=reason)
            evidence.update(status='connection/model error; no new command', error=reason)
        stop.wait(POLL_SECONDS)
