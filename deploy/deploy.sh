#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Usage: $0 <all | automations | groups | scripts>"
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

if [ -z "$HASS_WEB_TOKEN" ]; then
    echo "You need to set deployment parameter HASS_WEB_TOKEN"
    exit 1
fi

case "$1" in
    "all" )
        echo -n "Deploying everything... "
        rsync --checksum --delete --human-readable --recursive --exclude-from=deploy/exclude.conf . "$HASS_SSH_URL"
        echo "done."
        echo -n "Restarting Home Assistant... "
        curl -s -S -o /dev/null -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $HASS_WEB_TOKEN" "$HASS_WEB_URL"/api/services/homeassistant/restart
        echo "done."
        ;;
    "automations" )
        echo -n "Deploying automations... "
        rsync --checksum --delete --human-readable --recursive --exclude-from=deploy/exclude.conf automations/ "$HASS_SSH_URL"/automations
        echo "done."
        echo -n "Reloading automations... "
        curl -s -S -o /dev/null -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $HASS_WEB_TOKEN" "$HASS_WEB_URL"/api/services/automation/reload
        echo "done."
        ;;
    "groups" )
        echo -n "Deploying groups... "
        rsync --checksum --delete --human-readable --recursive --exclude-from=deploy/exclude.conf groups.yaml "$HASS_SSH_URL"
        echo "done."
        echo -n "Reloading groups... "
        curl -s -S -o /dev/null -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $HASS_WEB_TOKEN" "$HASS_WEB_URL"/api/services/group/reload
        echo "done."
        ;;
    "scripts" )
        echo -n "Deploying scripts... "
        rsync --checksum --delete --human-readable --recursive --exclude-from=deploy/exclude.conf scripts/ "$HASS_SSH_URL"/scripts
        echo "done."
        echo -n "Reloading scripts... "
        curl -s -S -o /dev/null -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $HASS_WEB_TOKEN" "$HASS_WEB_URL"/api/services/script/reload
        echo "done."
        ;;
    *)
        echo "Usage: $0 <all | automations | groups | scripts>"
        exit 1
        ;;
esac
