#!/bin/bash

BRIDGE="{PUBLIC_BRIDGE}"
IP="{IP_CIDR}"

# Attende che il bridge esista
while ! ip link show "$BRIDGE" >/dev/null 2>&1; do
    sleep 1
done

# Aggiunge l'IP se non già presente
if ! ip addr show "$BRIDGE" | grep -q "$IP"; then
    ip addr add "$IP" dev "$BRIDGE"
fi

ip link set "$BRIDGE" up