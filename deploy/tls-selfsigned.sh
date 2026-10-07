#!/bin/sh
# Opret et selvsigneret certifikat til nginx, hvis der ikke allerede ligger et.
#   sh deploy/tls-selfsigned.sh <hostnavn> [ip]      fx: sh deploy/tls-selfsigned.sh scada.laces.dk 10.1.1.31
# Overskriver ALDRIG et eksisterende certifikat (fx et senere Let's Encrypt-certifikat).
# Tving nyt selvsigneret certifikat: slet /etc/hypervisionplc-scada/tls/ først.
set -eu
export PATH="/usr/local/sbin:/usr/sbin:/sbin:$PATH"

HOST=${1:?brug: tls-selfsigned.sh <hostnavn> [ip]}
IP=${2:-}
DIR=/etc/hypervisionplc-scada/tls

if [ -f "$DIR/fullchain.pem" ] && [ -f "$DIR/privkey.pem" ]; then
    echo "Certifikat findes allerede i $DIR — rører det ikke"
    exit 0
fi

install -d -m 0750 "$DIR"
SAN="DNS:$HOST"
[ -n "$IP" ] && SAN="$SAN,IP:$IP"

openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
    -keyout "$DIR/privkey.pem" -out "$DIR/fullchain.pem" -days 825 \
    -subj "/CN=$HOST/O=HypervisionPLC SCADA" \
    -addext "subjectAltName=$SAN" \
    -addext "basicConstraints=critical,CA:FALSE" \
    -addext "keyUsage=critical,digitalSignature" \
    -addext "extendedKeyUsage=serverAuth" 2>/dev/null
chmod 0600 "$DIR/privkey.pem"
chmod 0644 "$DIR/fullchain.pem"

echo "Selvsigneret certifikat oprettet for $SAN (gyldigt 825 dage):"
openssl x509 -in "$DIR/fullchain.pem" -noout -fingerprint -sha256
