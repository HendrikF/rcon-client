#!/usr/bin/python3
import configparser
import sys
import atexit
import os
import readline

from rcon.rcon import Connection

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

# readline + history

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
        command = input('> ')
        if command in ['q', 'quit', 'exit']:
            break
        result = c.execute(command)
        if command.startswith('help'):
            # insert line breaks into help output
            result = '\n/'.join(result.split('/'))
        print(result)
except (EOFError, KeyboardInterrupt):
    print('')