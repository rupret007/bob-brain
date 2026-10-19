# Playwright user-space libs (no sudo). Source before running Playwright on the NucBox.
export LD_LIBRARY_PATH=/home/rupret/.local/pwlibs/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
# dlopen-only libs (GLESv2, x264) live in ~/.local/pwlibs, which Playwright ldconfig check cannot see; the libs are present, so skip that check.
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1
