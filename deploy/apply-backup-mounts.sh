#!/bin/sh
# NFS-shares til backup (System › Backup › Destinationer). Køres som ROOT af systemd (hypervisionplc-scada-backupmount.service,
# udløst af .path-enheden når backup-mounts.request findes) — aldrig direkte af tjenesten.
#
# Anmodningen er HELE den ønskede liste, én linje pr. share: "<id> <vært>:/<sti>". Hver share monteres på /mnt/hv-backup/<id>;
# monteringer derunder, der ikke længere ønskes (eller peger et andet sted hen), afmonteres. Tjenesten skriver listen ved hver
# ændring og ved opstart, så monteringerne genskabes efter en genstart af maskinen.
#
# SIKKERHED: tjenesten (brugeren 'scada') ejer <data>/config og kan lægge hvad som helst dér. Derfor
#   * flyttes anmodningen (mv) ind i rootens egen mappe før den læses, og symlinks afvises;
#   * id, vært og sti valideres med faste mønstre (ingen mellemrum, ingen "..", ingen options) — intet når et shell uciteret;
#   * der monteres kun nfs/nfs4 og kun under /mnt/hv-backup, altid med nosuid,nodev,noexec og "soft" (en død server må
#     ikke hænge tjenesten);
#   * højst 10 shares.
# Ingen systemd-sandkasse (ProtectSystem/PrivateTmp): en montering i en privat navnerum ville ikke være synlig for tjenesten.
#
# Til test kan kommandoer og mapper overstyres: MOUNT, UMOUNT, MOUNTS, ROOT, DATA, STATE.
set -u
set -f
export PATH="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin"

MOUNT=${MOUNT:-mount}
UMOUNT=${UMOUNT:-umount}
MOUNTS=${MOUNTS:-/proc/mounts}
ROOT=${ROOT:-/mnt/hv-backup}
DATA=${DATA:-/var/lib/hypervisionplc-scada}
W=${STATE:-/var/lib/hypervisionplc-scada-net}
REQ=$DATA/config/backup-mounts.request
WORK=$W/backup-mounts.work
LOG=$W/backup-mounts.log
STATUS=$W/backup-mounts.json
OPTS="soft,timeo=150,retrans=2,nosuid,nodev,noexec,_netdev"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

[ -e "$REQ" ] || [ -L "$REQ" ] || exit 0
if [ -L "$REQ" ]; then
    rm -f "$REQ"; log "afvist: anmodningen var et symlink"; exit 0
fi
rm -f "$WORK"
mv -f "$REQ" "$WORK" 2>/dev/null || { log "afvist: kunne ikke flytte anmodningen"; exit 0; }
if [ -L "$WORK" ] || [ ! -f "$WORK" ]; then
    rm -f "$WORK"; log "afvist: anmodningen var ikke en almindelig fil"; exit 0
fi

mkdir -p "$ROOT"
chmod 0755 "$ROOT"

# Ønsket liste (validerede linjer)
WANT=""
n=0
while IFS=' ' read -r id src rest; do
    [ -n "${id:-}" ] || continue
    if [ -n "${rest:-}" ] || ! printf '%s' "$id" | grep -Eq '^[0-9a-f]{8}$' \
        || ! printf '%s' "$src" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9.-]{0,252}:/[A-Za-z0-9._/-]{0,200}$' \
        || printf '%s' "$src" | grep -q '\.\.'; then
        log "afvist linje: $(printf '%s' "$id $src" | tr -cd 'A-Za-z0-9.:/_ -' | cut -c1-120)"
        continue
    fi
    n=$((n + 1))
    [ "$n" -le 10 ] || { log "afvist: mere end 10 shares"; break; }
    WANT="$WANT$id $src
"
done <<EOF
$(tr -d '\r' < "$WORK")
EOF
rm -f "$WORK"

# Afmontér det, der ikke længere ønskes (eller har skiftet kilde)
awk -v root="$ROOT/" '$3 ~ /^nfs/ && index($2, root) == 1 { print $2, $1 }' "$MOUNTS" | while read -r mp src; do
    id=${mp#"$ROOT"/}
    if ! printf '%s' "$WANT" | grep -Fqx "$id $src"; then
        if $UMOUNT -l "$mp" 2>>"$LOG"; then log "afmonteret $mp ($src)"; else log "kunne ikke afmontere $mp"; fi
        rmdir "$mp" 2>/dev/null || true
    fi
done

# Montér det, der mangler; skriv status (læses af tjenesten og vises på siden)
json="{"
sep=""
printf '%s' "$WANT" | {
    while read -r id src; do
        [ -n "$id" ] || continue
        mp=$ROOT/$id
        mkdir -p "$mp"
        if awk -v mp="$mp" -v src="$src" '$2 == mp && $1 == src { f = 1 } END { exit !f }' "$MOUNTS"; then
            ok=true; err=""
        elif out=$($MOUNT -t nfs -o "$OPTS" -- "$src" "$mp" 2>&1); then
            ok=true; err=""; log "monteret $src på $mp"
        else
            ok=false; err=$(printf '%s' "$out" | tr -cd 'A-Za-z0-9.,:/()_ -' | cut -c1-200); log "montering af $src fejlede: $err"
        fi
        json="$json$sep\"$id\":{\"ok\":$ok,\"error\":\"$err\",\"ts\":$(date +%s)}"
        sep=","
    done
    printf '%s}\n' "$json" > "$STATUS.tmp"
    chmod 0644 "$STATUS.tmp"
    mv -f "$STATUS.tmp" "$STATUS"
}
exit 0
