from __future__ import annotations

import argparse
import json
import shlex
import sys
from urllib import error, request


def send_command(endpoint: str, command: str, source: str) -> dict[str, object]:
    payload = {
        'command': command,
        'source': source,
    }
    data = json.dumps(payload).encode('utf-8')

    req = request.Request(
        endpoint,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    with request.urlopen(req, timeout=5) as response:
        raw = response.read().decode('utf-8')
        if not raw:
            return {'ok': False, 'error': 'Empty response body'}
        return json.loads(raw)


def validate_input_targeting(command: str) -> str | None:
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.strip().split()

    if not parts or parts[0].lower() != 'input':
        return None

    if len(parts) < 4:
        return (
            'Scanner client requires targeted input syntax: '
            'input [type] [player-1|player-2] [msg] [..args]'
        )

    target = parts[2].lower()
    if target not in {'player-1', 'player-2'}:
        return (
            'Scanner client only allows player-targeted input. '
            'Use input [type] [player-1|player-2] [msg] [..args].'
        )

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Interactive terminal client for posting scanner commands to Flask.'
    )
    parser.add_argument(
        '--endpoint',
        default='http://127.0.0.1:5500/scanner/input',
        help='Scanner input endpoint URL (default: %(default)s).'
    )
    parser.add_argument(
        '--source',
        default='terminal-scanner',
        help='Value to send as source in scanner payload (default: %(default)s).'
    )

    args = parser.parse_args()

    print('Scanner Terminal Client')
    print(f'Endpoint: {args.endpoint}')
    print('Type scanner commands and press Enter.')
    print('Type /quit to exit, /help for tips.')

    while True:
        try:
            line = input('scanner> ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\nExiting scanner terminal client.')
            return 0

        if not line:
            continue

        if line.lower() in {'/quit', 'quit', 'exit'}:
            print('Exiting scanner terminal client.')
            return 0

        if line.lower() in {'/help', 'help'}:
            print('Commands:')
            print('  help')
            print('  ?')
            print('  mv [cardid] [cardholderid|target_character_id] [index?]')
            print('  rm [energyid]')
            print('  create_energy [energyid] [player-1|player-2] [energyholderid] [attached_card_id|none]')
            print('  create-energy [energyid] [player-1|player-2] [energyholderid] [attached_card_id|none]')
            print('  mv-energy [energyid] [target_card_id|shared-energy|energy-discard]')
            print('  mvenergy [energyid] [target_card_id|shared-energy|energy-discard]')
            print('  create_card [cardid] [player-1|player-2] [character|tool|item|stadium|supporter] [cardholderid] [card_class] [has_atk_1] [has_active] [has_atk_2] [hp] [maxhp] [attached_card_id|none]')
            print('  create-card [cardid] [player-1|player-2] [character|tool|item|stadium|supporter] [cardholderid] [card_class] [has_atk_1] [has_active] [has_atk_2] [hp] [maxhp] [attached_card_id|none]')
            print('  game-phase [no-input|phase2|atk]')
            print('  phase [no-input|phase2|atk]')
            print('  player-turn [player-1|player-2]')
            print('  turn [player-1|player-2]')
            print('  stat [player-1|player-2] [attribute] [value]')
            print('  flip [cardid]')
            print('  hp [cardid] [hp] [maxhp]')
            print('  maxhp [cardid] [maxhp]')
            print('  max-hp [cardid] [maxhp]')
            print('  border [cardid] [hex]')
            print('  changetype [cardid] [NONE|WW|PERC|PIANO|STRING|GUITAR|CHOIR|BRASS]')
            print('  change-type [cardid] [NONE|WW|PERC|PIANO|STRING|GUITAR|CHOIR|BRASS]')
            print('  input [type] [player-1|player-2] [msg] [..args]')
            print('    input selection [player] [msg] [display1,display2], [highlight1,highlight2], [num-cards], [allow-repeat] [allow-none]')
            print('    input kei-watanabe-drumkidworkshop [player] [msg] [card1,card2,...]')
            print('    input kei_watanabe_drumkidworkshop [player] [msg] [card1,card2,...]')
            print('    input numerical-entry [player] [msg]')
            print('    input numerical_entry [player] [msg]')
            print('    input d6 [player] [msg] [1-6]')
            print('    input coin [player] [msg] [0|1]   (0=tails, 1=heads)')
            print('    input on [player] [msg]')
            print('    input off [player] [msg]')
            print('  notify [player-1|player-2] [msg]')
            print('  winner [player-1|player-2]')
            print('  reveal [player-1|player-2] [list of cards]')
            print('  boom [cardid] [asset?]')
            print('  view')
            print('  view [admin|player-1|player-2]')
            print('  shuffle-animation')
            print('  unselect-all')
            print('  unselectall')
            continue

        input_validation_error = validate_input_targeting(line)
        if input_validation_error:
            print(input_validation_error)
            continue

        try:
            response = send_command(args.endpoint, line, args.source)
            print(json.dumps(response, indent=2, sort_keys=True))
        except error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace')
            print(f'HTTP {exc.code}: {body}')
        except error.URLError as exc:
            print(f'Network error: {exc.reason}')
        except TimeoutError:
            print('Request timed out.')
        except json.JSONDecodeError as exc:
            print(f'Invalid JSON response: {exc}')
        except Exception as exc:  # defensive fallback for terminal UX
            print(f'Unexpected error: {exc}')


if __name__ == '__main__':
    sys.exit(main())
