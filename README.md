# animate-fastfetch

Character themed Fastfetch configurations. Each character lives in its own folder under `animate/` and can be selected with Fastfetch's `--config` option.

## Install

```sh
git clone https://github.com/shiningelf/animate-fastfetch.git
cd animate-fastfetch
./install.sh
```

Choose a character by passing its config file:

```sh
fastfetch --config ~/.config/fastfetch/animate/nezuko/config.jsonc
fastfetch --config ~/.config/fastfetch/animate/2b/config.jsonc
```

`--config` expects a config file, so include `config.jsonc` after the character folder. To install somewhere else, pass a destination to the installer:

```sh
./install.sh /path/to/fastfetch/animate
```

## Characters

### Nezuko

A custom two-column panel with a transparent portrait, Japanese quote, system and hardware cards, live network details, and a Demon Slayer footer mark.

![Nezuko theme snapshot](animate/nezuko/snapshot.png)

Requires Fastfetch 2.69+, Python 3, a Nerd Font, a Kitty graphics capable terminal, NetworkManager (`nmcli`), and `ip`.

### 2B

A POD 042 scan console layout with machine identity, system, processor, memory, storage, and network fields. This starter config uses Fastfetch's text modules and does not require character artwork.
