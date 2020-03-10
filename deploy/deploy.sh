#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Usage: $0 <all | automations | groups | scenes | scripts> [--skip-upload | --skip-reload]"
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
        if [ "$2" != "--skip-upload" ]; then
            echo -n "Uploading everything... "
            rsync --checksum --times --delete --update --human-readable --recursive --exclude-from=deploy/exclude.conf . "$HASS_SSH_URL"
            echo "done."
        fi
        if [ "$2" != "--skip-reload" ]; then
            echo -n "Restarting Home Assistant... "
            curl -s -S -o /dev/null -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $HASS_WEB_TOKEN" "$HASS_WEB_URL"/api/services/homeassistant/restart
            echo "done."
        fi
        ;;
    "automations" )
        if [ "$2" != "--skip-upload" ]; then
            echo -n "Uploading automations... "
            rsync --checksum --times --delete --update --human-readable --recursive --exclude-from=deploy/exclude.conf automations/ "$HASS_SSH_URL"/automations
            echo "done."
        fi
        if [ "$2" != "--skip-reload" ]; then
            echo -n "Reloading automations... "
            curl -s -S -o /dev/null -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $HASS_WEB_TOKEN" "$HASS_WEB_URL"/api/services/automation/reload
            echo "done."
        fi
        ;;
    "groups" )
        if [ "$2" != "--skip-upload" ]; then
            echo -n "Uploading groups... "
            rsync --checksum --times --delete --update --human-readable --recursive --exclude-from=deploy/exclude.conf groups.yaml "$HASS_SSH_URL"
            echo "done."
        fi
        if [ "$2" != "--skip-reload" ]; then
            echo -n "Reloading groups... "
            curl -s -S -o /dev/null -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $HASS_WEB_TOKEN" "$HASS_WEB_URL"/api/services/group/reload
            echo "done."
        fi
        ;;
    "scenes" )
        if [ "$2" != "--skip-upload" ]; then
            echo -n "Uploading scenes... "
            rsync --checksum --times --delete --update --human-readable --recursive --exclude-from=deploy/exclude.conf scenes.yaml "$HASS_SSH_URL"
            echo "done."
        fi
        if [ "$2" != "--skip-reload" ]; then
            echo -n "Reloading scenes... "
            curl -s -S -o /dev/null -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $HASS_WEB_TOKEN" "$HASS_WEB_URL"/api/services/scene/reload
            echo "done."
        fi
        ;;
    "scripts" )
        if [ "$2" != "--skip-upload" ]; then
            echo -n "Uploading scripts... "
            rsync --checksum --times --delete --update --human-readable --recursive --exclude-from=deploy/exclude.conf scripts/ "$HASS_SSH_URL"/scripts
            echo "done."
        fi
        if [ "$2" != "--skip-reload" ]; then
            echo -n "Reloading scripts... "
            curl -s -S -o /dev/null -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $HASS_WEB_TOKEN" "$HASS_WEB_URL"/api/services/script/reload
            echo "done."
        fi
        ;;
    *)
        echo "Usage: $0 <all | automations | groups | scenes | scripts> [--skip-upload | --skip-reload]"
        exit 1
        ;;
esac
