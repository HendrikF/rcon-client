#!/usr/bin/python3
import configparser
import sys
import atexit
import os
import rlcompleter
import readline
import re
import itertools
import collections

from rcon.rcon import Connection

commands_learned = {}

debug = (lambda *args, **kw: print(*args, **kw, file=sys.stderr, flush=True)) if len(sys.argv) >= 2 and sys.argv[1] == '--debug' else (lambda *args, **kw: None)

# config

config_file = os.path.expanduser('~/.rcon')
config = configparser.ConfigParser()
config['rcon'] = {
    'host': 'localhost',
    'port': 25575,
    'password': 'secret'
}
if len(config.read(config_file)) == 0:
    with open(config_file, 'w') as configfile:
        config.write(configfile)

# readline history

hist_file = os.path.expanduser('~/.rcon_history')
try:
    readline.read_history_file(hist_file)
    hist_len = readline.get_current_history_length()
except FileNotFoundError:
    open(hist_file, 'wb').close()
    hist_len = 0

def save_hist(prev_hist_len, hist_file):
    new_hist_len = readline.get_current_history_length()
    readline.set_history_length(1000)
    readline.append_history_file(new_hist_len - prev_hist_len, hist_file)
atexit.register(save_hist, hist_len, hist_file)

# auto completion

readline.parse_and_bind('tab: complete')
# removed <>
readline.set_completer_delims(''' \t\n`~!@#$%^&*()-=+[{]}\|;:'",/?''')

debug('== RESTART ==')

def completer(text, state):
    # text will be the current word to complete
    line_buffer = readline.get_line_buffer()
    begin = readline.get_begidx()
    end = readline.get_endidx()

    parts_before_cursor = re.split('\s+', line_buffer[:begin].rstrip(' '))
    if len(parts_before_cursor) == 1 and parts_before_cursor[0] == '':
        parts_before_cursor = []
    debug(parts_before_cursor, text, state)

    # complete help with actual commands
    if len(parts_before_cursor) >= 1 and parts_before_cursor[0] == 'help':
        parts_before_cursor.pop(0)

    d = commands_learned
    for part in parts_before_cursor:
        # try to find part as a real command
        tmp = d.get(part, None)
        if tmp is None:
            # part is not a real command
            # look for placeholders that part could be substituted for
            placeholders = list(filter(
                lambda possibility: possibility.startswith('<') and possibility.endswith('>'),
                d.keys()))
            tmp = {}
            # continue completion with all possible placeholders
            for placeholder in placeholders:
                for k, v in d[placeholder].items():
                    tmp[k] = v
        d = tmp

    parts_possible = list(filter(lambda part: part.startswith(text), d.keys()))

    if not len(parts_possible):
        debug('Unknown command - cannot complete')

    if len(parts_possible) == 1 and state == 0:
        readline.insert_text(' ')
        debug('SPACE')

    return parts_possible[state]

readline.set_completer(completer)

def peek_iter(iterable, n):
    """ provides access to n following elements of an iterable

        the last item will be followed by multiple None

        for current, next1, next2 in peek_iter(iterable, 2): ...
    """
    iterator = itertools.chain(iterable, [None]*n)
    queue = collections.deque(maxlen=n+1)
    for i in range(n):
        queue.append(next(iterator))
    for item in iterator:
        queue.append(item)
        yield tuple(queue)

def learn_commands(help_output):
    """ populates the commands_learned dict

        the goal is a structure like this:
        {
          "data": {
            "get": {
              "block": {},
              "entity": {}
            },
            "modify": {
              "block": {},
              "entity": {}
            }
          },
          "help": {
            "<command>": {}
          }
        }

        which would mean that the following commands are known:
        /data get block
        /data get entity
        /data modify block
        /data modify entity
        /help <command>

        command aliases are created by referencing the target dict from the alias
    """
    for line in help_output.split('\n'):
        if line.startswith('/'):
            parts = re.split('\s+', line.lstrip('/'))
            d = commands_learned
            # use our peek_iter to have a look at the following parts
            # we need this to detect aliases
            for part, next1, next2 in peek_iter(parts, 2):
                if next1 == '->':
                    # alias
                    # create and get alias target, because it might not exist yet
                    target = commands_learned.setdefault(next2, {})
                    d.setdefault(part, target)
                    break
                elif part.startswith('(') and part.endswith(')'):
                    # choice (x|y)
                    choices = part[1:-1].split('|')
                    for choice in choices:
                        d.setdefault(choice, {})
                    # we cannot continue, choices have to be at the end of commands
                    # (we cannot decide which choice to append following parts to)
                    break
                elif part.startswith('[') and part.endswith(']'):
                    # optional choice [x|y]
                    choices = part[1:-1].split('|')
                    if len(choices) == 1:
                        # not a choice, just an option
                        d = d.setdefault(choices.pop(0), {})
                    else:
                        for choice in choices:
                            d.setdefault(choice, {})
                        # we cannot continue, choices have to be at the end of commands
                        # (we cannot decide which choice to append following parts to)
                        break
                else:
                    d = d.setdefault(part, {})
    debug('knowledge', commands_learned)

# fix newlines

def fix_newlines(command, result):
    """ add newlines to common commands

        Minecrafts rcon is buggy and does not send any newlines
    """
    if (result.startswith('Unknown command') and
            result != 'Unknown command or insufficient permissions'):
        # insert newline before the command
        result = re.sub('^Unknown command', '\g<0>\n', result)
    elif command.startswith('help'):
        # insert newlines in front of commands
        result = re.sub('(.)/', '\g<1>\n/', result)
    return result

# connection

host = config.get('rcon', 'host')
port = config.getint('rcon', 'port')

c = Connection(host, port)
if c.authenticate(config.get('rcon', 'password')):
    print('Connected to {addr}'.format(
        addr=(host, port)
    ))
else:
    print('Wrong Password')
    sys.exit(1)

try:
    while True:
        command = input('> ').rstrip()
        if command in ['q', 'quit', 'exit']:
            break
        result = c.execute(command)
        result = fix_newlines(command, result)
        if command.startswith('help'):
            learn_commands(result)
        print(result)
except (EOFError, KeyboardInterrupt):
    print('')
