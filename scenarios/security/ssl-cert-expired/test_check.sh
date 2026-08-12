#!/bin/bash
# Self-test for this lab's grader. Run: bash test_check.sh
#
# It builds a throwaway root, plants a specific end-state in it, path-shifts
# check.sh onto that root, and asserts the exit code. The point is the
# fail-closed cases: a renewed cert with no monitor, a monitor that always
# says OK, a monitor that always alarms, and an unscheduled monitor must all
# be rejected. Reverting the PREVENT block in check.sh turns rows 2-5 green,
# which is how this file earns its keep.
#
# nginx/crontab are stubbed (not installed on a dev laptop); openssl is real.

cd "$(dirname "$0")" || exit 1
PASS=0; FAIL=0

run_case() {
  local mode="$1" want="$2"
  local SB; SB=$(mktemp -d)
  mkdir -p "$SB/bin" "$SB/etc/nginx/ssl" "$SB/etc/cron.d" "$SB/usr/local/bin"
  printf '#!/bin/bash\nexit 0\n' > "$SB/bin/nginx"; chmod +x "$SB/bin/nginx"
  printf '#!/bin/bash\nexit 1\n' > "$SB/bin/crontab"; chmod +x "$SB/bin/crontab"
  local PATH_SAVED="$PATH"; export PATH="$SB/bin:$PATH"
  cp probe-expired.pem "$SB/probe-expired.pem"

  local CERTP="$SB/etc/nginx/ssl/cert.pem" KEYP="$SB/etc/nginx/ssl/key.pem"
  local MON="$SB/usr/local/bin/check-cert-expiry"

  mkcert() { openssl req -x509 -nodes -newkey rsa:2048 -keyout "$KEYP" -out "$CERTP" -days "$1" -subj '/CN=localhost' >/dev/null 2>&1; }
  mkmon() {
    case "$1" in
      good) cat > "$MON" <<'G'
#!/bin/bash
C="$1"; W="${WARN_DAYS:-30}"
openssl x509 -in "$C" -noout -checkend 0 >/dev/null 2>&1 || exit 2
openssl x509 -in "$C" -noout -checkend $((86400 * W)) >/dev/null 2>&1 || exit 1
exit 0
G
;;
      alwaysok)   printf '#!/bin/bash\nexit 0\n' > "$MON";;
      alwaysfail) printf '#!/bin/bash\nexit 1\n' > "$MON";;
    esac
    chmod +x "$MON"
  }
  mksched() { echo '17 3 * * * root check-cert-expiry' > "$SB/etc/cron.d/cert-expiry"; }

  case "$mode" in
    full_fix)        mkcert 365; mkmon good; mksched;;
    no_monitor)      mkcert 365;;
    stub_alwaysok)   mkcert 365; mkmon alwaysok; mksched;;
    stub_alwaysfail) mkcert 365; mkmon alwaysfail; mksched;;
    unscheduled)     mkcert 365; mkmon good;;
    expired_cert)    mkcert 1;   mkmon good; mksched;;
    mismatch_key)    mkcert 365; openssl req -x509 -nodes -newkey rsa:2048 -keyout "$KEYP" -out "$SB/o.pem" -days 365 -subj '/CN=other' >/dev/null 2>&1; mkmon good; mksched;;
  esac

  sed -e "s#^CERT=/etc/nginx/ssl/cert.pem#CERT=$CERTP#" \
      -e "s#^KEY=/etc/nginx/ssl/key.pem#KEY=$KEYP#" \
      -e "s#/usr/local/bin/check-cert-expiry#$MON#g" \
      -e "s#/usr/local/bin/cert-expiry-check#$SB/absent1#g" \
      -e "s#/opt/fixitlab/check-cert-expiry.sh#$SB/absent2#g" \
      -e "s#/etc/cron.daily/cert-expiry#$SB/absent3#g" \
      -e "s#/etc/crontab /etc/cron.d/\*#$SB/etc/crontab $SB/etc/cron.d/*#" \
      -e "s#\"/etc/cron.daily/#\"$SB/etc/cron.daily/#" \
      -e "s#/etc/systemd/system/\*cert\*.timer#$SB/etc/systemd/system/*cert*.timer#" \
      check.sh > "$SB/check.sh"

  bash "$SB/check.sh" >/dev/null 2>&1; local got=$?
  [ "$got" -ne 0 ] && got=1   # normalise any non-zero to "rejected"

  export PATH="$PATH_SAVED"; rm -rf "$SB"

  if [ "$got" = "$want" ]; then
    printf '  ok   %-16s exit=%s\n' "$mode" "$got"; PASS=$((PASS + 1))
  else
    printf '  FAIL %-16s exit=%s want=%s\n' "$mode" "$got" "$want"; FAIL=$((FAIL + 1))
  fi
}

echo "grader self-test: only a complete fix may pass"
run_case full_fix        0
run_case no_monitor      1
run_case stub_alwaysok   1
run_case stub_alwaysfail 1
run_case unscheduled     1
run_case expired_cert    1
run_case mismatch_key    1
echo "passed=$PASS failed=$FAIL"
[ "$FAIL" -eq 0 ]
