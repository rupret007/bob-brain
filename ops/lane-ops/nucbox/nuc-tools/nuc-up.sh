#!/bin/bash
# Start userspace tailscaled + non-root sshd in WSL (idempotent)
# WSL eth0 MTU is 1280, so WireGuard packets from the default 1280 tailnet MTU get dropped (SSH stalls past ~1.2 KB of output). 1200 fits.
export TS_DEBUG_MTU=1200
mkdir -p $HOME/.local/ts
SOCK=$HOME/.local/ts/tailscaled.sock
pgrep -u "$USER" -x tailscaled >/dev/null || nohup $HOME/bin/tailscaled --tun=userspace-networking --statedir=$HOME/.local/ts --socket=$SOCK >$HOME/.local/ts/tailscaled.log 2>&1 &
pgrep -u "$USER" -f "$HOME/.local/sshd" >/dev/null || $HOME/.local/sshd/start.sh >/dev/null 2>&1
