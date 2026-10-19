#!/bin/bash
# Run 2 setup: static ffmpeg + tailscale binaries into ~/bin (no sudo). Reversible: rm the files.
set -u
mkdir -p ~/bin ~/nuc-tools/dl && cd ~/nuc-tools/dl
exec > ~/nuc-tools/selfcheck2.log 2>&1
date
if ! [ -x ~/bin/ffmpeg ]; then
  curl -fsSL -o ffmpeg.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz && \
  tar -xJf ffmpeg.tar.xz && d=$(ls -d ffmpeg-*-amd64-static | head -1) && cp "$d/ffmpeg" "$d/ffprobe" ~/bin/ && rm -rf "$d" ffmpeg.tar.xz
fi
~/bin/ffmpeg -hide_banner -version | head -1
if ! [ -x ~/bin/tailscale ]; then
  v=$(curl -fsSL 'https://pkgs.tailscale.com/stable/?mode=json' | python3 -c 'import sys,json;print(json.load(sys.stdin)["TarballsVersion"])')
  curl -fsSL -o ts.tgz "https://pkgs.tailscale.com/stable/tailscale_${v}_amd64.tgz" && tar -xzf ts.tgz && cp tailscale_${v}_amd64/tailscale tailscale_${v}_amd64/tailscaled ~/bin/ && rm -rf tailscale_${v}_amd64 ts.tgz
fi
~/bin/tailscale version | head -1
# ffmpeg benchmark: 20 s 1080p synthetic x264 encode
t0=$(date +%s.%N); ~/bin/ffmpeg -hide_banner -loglevel error -f lavfi -i testsrc2=size=1920x1080:rate=30 -t 20 -c:v libx264 -preset medium -y /tmp/bench.mp4; t1=$(date +%s.%N)
echo "FFBENCH_SEC $(echo "$t1 - $t0" | bc 2>/dev/null || python3 -c "print($t1-$t0)")"
rm -f /tmp/bench.mp4
echo DONE
