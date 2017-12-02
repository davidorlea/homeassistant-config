#!/bin/bash

if [ $# -lt 1 ]
then
    echo "Usage: $0 [automations|groups|scripts]"
    exit 1
fi

if [ -z "$HASS_SSH_URL" ]; then
    echo "You need to set deployment parameter HASS_SSH_URL"
    exit 1
fi

if [ -z "$HASS_WEB_URL" ]; then
    echo "You need to set deployment parameter HASS_WEB_URL"
    exit 1
fi

case "$1" in
    "automations" )
        echo -n "Deploying automations... "
        scp -q automations.yaml "$HASS_SSH_URL"
        echo "done."
        echo -n "Reloading automations... "
        curl -s -S -o /dev/null -X POST -H "Content-Type: application/json" "$HASS_WEB_URL"/api/services/automation/reload
        echo "done."
        ;;
    "groups" )
        echo -n "Deploying groups... "
        scp -q groups.yaml "$HASS_SSH_URL"
        echo "done."
        echo -n "Reloading groups... "
        curl -s -S -o /dev/null -X POST -H "Content-Type: application/json" "$HASS_WEB_URL"/api/services/group/reload
        echo "done."
        ;;
    "scripts" )
        echo -n "Deploying scripts... "
        scp -q scripts.yaml "$HASS_SSH_URL"
        echo "done."
        echo -n "Reloading scripts... "
        curl -s -S -o /dev/null -X POST -H "Content-Type: application/json" "$HASS_WEB_URL"/api/services/script/reload
        echo "done."
        ;;
    *)
        echo "Usage: $0 [automations|groups|scripts]"
        exit 1
        ;;
esac
