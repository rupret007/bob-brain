#!/bin/bash
. "$(cd "$(dirname "$0")" && pwd)/common.sh"
service_loop reviewer 300 "$@"
