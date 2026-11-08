#!/bin/sh
# Certbot deploy-hook på en reverse proxy foran SCADA'en (v4.11.0): send det fornyede Let's Encrypt-certifikat videre til
# SCADA-serveren, så den bruger samme certifikat (deploy/cert-receive.sh tager imod og installerer det).
#
# Installation på proxyen (som root):
#   install -m 0755 proxy-cert-push.sh /etc/letsencrypt/renewal-hooks/deploy/scada-cert-push.sh
#   ssh-keygen -t ed25519 -N '' -C proxy-cert -f /root/.ssh/scada-cert
#   echo 'SCADA_HOST=10.1.130.50' > /etc/default/scada-cert-push    (+ evt. SCADA_NAME=scada.laces.dk)
#   ssh-keyscan -t ed25519 <SCADA_HOST> >> /root/.ssh/known_hosts
# og på SCADA-serveren i /root/.ssh/authorized_keys:
#   from="<proxyens IP mod SCADA>",command="/usr/local/lib/hypervisionplc-scada/cert-receive.sh",restrict <indhold af scada-cert.pub>
#
# Certbot sætter RENEWED_LINEAGE (fx /etc/letsencrypt/live/scada.laces.dk). Andre certifikater på proxyen springes over.
# Kør i hånden med:  RENEWED_LINEAGE=/etc/letsencrypt/live/scada.laces.dk /etc/letsencrypt/renewal-hooks/deploy/scada-cert-push.sh
set -u
[ -f /etc/default/scada-cert-push ] && . /etc/default/scada-cert-push
SCADA_HOST=${SCADA_HOST:?SCADA_HOST mangler i /etc/default/scada-cert-push}
SCADA_NAME=${SCADA_NAME:-scada.laces.dk}
KEY=${KEY:-/root/.ssh/scada-cert}
L=${RENEWED_LINEAGE:-}

case "$L" in */"$SCADA_NAME") ;; *) exit 0 ;; esac
# live/ er symlinks til archive/ — -h sender selve filerne
if tar -C "$L" -chf - fullchain.pem privkey.pem \
    | ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=yes "root@$SCADA_HOST"; then
    logger -t scada-cert-push "certifikatet for $SCADA_NAME er sendt til $SCADA_HOST"
else
    logger -t scada-cert-push "FEJL: kunne ikke sende certifikatet for $SCADA_NAME til $SCADA_HOST"
    exit 1
fi
