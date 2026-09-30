from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import secrets
import threading
from .neural import MaleCNS, calibrate, load_calibration
from .worker import Relay, Evidence, run_worker
from .viewer import serve


def private_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
    path.chmod(0o600)


def main(argv=None):
    p = argparse.ArgumentParser(description='LauFF: MaleCNS feeding-circuit experiment')
    sub = p.add_subparsers(dest='command', required=True)
    setup = sub.add_parser('configure', help='generate local credentials and a Lau module; does not deploy')
    setup.add_argument('--relay-url', required=True)
    movement = setup.add_mutually_exclusive_group(required=True)
    movement.add_argument('--bounds', type=int, nargs=4, metavar=('MIN_X','MAX_X','MIN_Z','MAX_Z'))
    movement.add_argument('--unbounded', action='store_true', help='remove the artificial garden rectangle; game restrictions still apply')
    setup.add_argument('--capabilities-verified', action='store_true', help='only after successful real-game probes')
    setup.add_argument('--config', type=Path, default=Path('.local/config.json'))
    for name in ('calibrate', 'run'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--upstream', type=Path, default=Path('vendor/drosophila-brain-mlx'))
        cmd.add_argument('--pack', type=Path)
        cmd.add_argument('--calibration', type=Path, default=Path('outputs/calibration.json'))
        if name == 'calibrate':
            cmd.add_argument('--trials', type=int, default=10)
        else:
            cmd.add_argument('--config', type=Path, default=Path('.local/config.json'))
            cmd.add_argument('--output', type=Path, default=Path('outputs/live'))
            cmd.add_argument('--port', type=int, default=8765)
            cmd.add_argument('--autonomous', action='store_true', help='enable validated experimental FC2/PFL3 movement when the game requests fly auto')
            cmd.add_argument('--navigation-calibration', type=Path, default=Path('outputs/navigation/calibration.json'))
            cmd.add_argument('--silenced', action='store_true', help='block outgoing sweet-neuron transmission for the live control experiment')
    view = sub.add_parser('view', help='show a local viewer without starting a brain or connecting to the game')
    view.add_argument('--port', type=int, default=8765)
    view.add_argument('--calibration', type=Path, default=Path('outputs/calibration.json'))
    args = p.parse_args(argv)
    if args.command == 'configure':
        bounds = args.bounds or [-1, 1, -1, 1]
        lowx, highx, lowz, highz = bounds
        if not (-9999 <= lowx <= highx <= 9999 and -9999 <= lowz <= highz <= 9999):
            p.error('invalid bounds')
        if args.config.exists():
            config = json.loads(args.config.read_text())
        else:
            config = {'game_token':secrets.token_hex(32), 'worker_token':secrets.token_hex(32)}
        Relay(args.relay_url, config['worker_token'])  # validate without connecting
        config.update(relay_url=args.relay_url, bounds=bounds, unbounded=args.unbounded, capabilities_verified=args.capabilities_verified)
        private_json(args.config, config)
        private_json(args.config.parent / 'relay-properties.json',
                     {'GAME_TOKEN':config['game_token'], 'WORKER_TOKEN':config['worker_token']})
        values = [args.relay_url, config['game_token'], args.capabilities_verified, *bounds, args.unbounded]
        # JSON strings and booleans have compatible literals in Lau; array becomes a list literal.
        module = 'return {' + ', '.join(json.dumps(v) for v in values) + '}\n'
        target = args.config.parent / 'LauFFConfig.laum'
        target.write_text(module)
        target.chmod(0o600)
        print(f'Wrote {args.config}, {target}, and relay-properties.json. Credentials are not printed.')
        print('In-game capabilities: ' + ('marked verified' if args.capabilities_verified else 'UNVERIFIED; client stays paused'))
        return 0
    if args.command == 'view':
        evidence = Evidence(Path('outputs/viewer'))
        evidence.update(status='Viewer only — no simulation or game connection')
        if args.calibration.exists():
            report = json.loads(args.calibration.read_text())
            evidence.update(provenance=report.get('provenance'), threshold_hz=report.get('threshold_hz'),
                            intervention='offline calibration evidence', calibration=report)
        server = serve(evidence, args.port)
        print(f'Viewer: http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    pack = args.pack or args.upstream / 'data/pack/male_cns_v1'
    brain = MaleCNS(args.upstream, pack)
    if args.command == 'calibrate':
        private_json(args.calibration, {'passed':False, 'status':'calibration starting', 'fingerprint':brain.fingerprint})
        try:
            report = calibrate(brain, args.trials, checkpoint=lambda r: private_json(args.calibration, r))
        except ValueError as error:
            print(f'CALIBRATION FAILED: {error}')
            return 1
        private_json(args.calibration, report)
        print(f'Calibration PASS: threshold {report["threshold_hz"]:.2f} Hz; {args.calibration}')
        return 0
    config = json.loads(args.config.read_text())
    if not config.get('capabilities_verified'):
        raise SystemExit('Run real-game probes before marking capabilities verified and enabling live control.')
    report = load_calibration(args.calibration, brain)
    navigation = navigation_report = None
    if args.autonomous:
        from .navigation import Navigation, load_navigation
        navigation = Navigation(brain)
        navigation_report = load_navigation(args.navigation_calibration, navigation)
    from .activity import ActivityMap
    brain.visual = ActivityMap(brain.pack)
    relay = Relay(config['relay_url'], config['worker_token'])
    evidence = Evidence(args.output)
    server = serve(evidence, args.port)
    stop = threading.Event()
    # Metal simulation stays on the main thread; viewer is read-only and runs separately.
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f'Viewer: http://127.0.0.1:{server.server_port}; Ctrl-C stops the worker.', flush=True)
    try:
        run_worker(relay, brain, report, evidence, stop, args.silenced, navigation, navigation_report)
    except KeyboardInterrupt:
        stop.set()
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
