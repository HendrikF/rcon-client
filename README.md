# RCON Client

A client implementation of the Source RCON Protocol.

The RCON Protocol allows remote command execution in game servers that implement it.

NOTE: Command completion and discovery is specialized to the command syntax of Minecraft, but all game specific parts are separated from the core.

See https://developer.valvesoftware.com/wiki/Source_RCON_Protocol
and https://wiki.vg/RCON for more information on the protocol.

## Configuration

The config file is created at `~/.rcon`, where `~` is your users home directory.

The history file is located at `~.rcon_history`.

## Command completion

You have to execute `help` so that the client can learn the availabe commands.
Additionally you may need to execute `help <command>` too, because Minecraft might only show a summary.

## License

MIT License
