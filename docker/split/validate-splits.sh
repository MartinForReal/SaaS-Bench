#!/bin/sh
img="$1"
for f in /split/"$img"/entrypoint-*.sh; do
  if sh -n "$f" 2>/tmp/err; then echo "OK $f"; else echo "SYNTAX_FAIL $f"; cat /tmp/err; fi
done