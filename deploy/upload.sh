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

upload() {
    echo -n "Uploading... "
    rsync --checksum --times --delete --update --human-readable --recursive --exclude-from=deploy/exclude.conf . "$HASS_SSH_URL":~
    echo "done."
}

check() {
    echo -n "Checking... "
    response=$(curl -s -S -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $HASS_WEB_TOKEN" "$HASS_WEB_URL"/api/config/core/check_config)
    result=$(echo $response | jq -e '.result == "valid"')
    if [ $? -eq 0 ]; then
        echo "done."
    else
        echo "failed: $(echo $response | jq -e '.errors')"
        exit 1
    fi
}

reload() {
    echo -n "Reloading... "
    curl -s -S -o /dev/null -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $HASS_WEB_TOKEN" "$HASS_WEB_URL"$1
    echo "done."
}

case "$1" in
    "all" )
        if [ "$2" != "--skip-upload" ]; then
            upload
        fi
        check
        if [ "$2" != "--skip-reload" ]; then
            reload "/api/services/homeassistant/restart"
        fi
        ;;
    "automations" )
        if [ "$2" != "--skip-upload" ]; then
            upload
        fi
        check
        if [ "$2" != "--skip-reload" ]; then
            reload "/api/services/automation/reload"
        fi
        ;;
    "groups" )
        if [ "$2" != "--skip-upload" ]; then
            upload
        fi
        check
        if [ "$2" != "--skip-reload" ]; then
            reload "/api/services/group/reload"
        fi
        ;;
    "scenes" )
        if [ "$2" != "--skip-upload" ]; then
            upload
        fi
        check
        if [ "$2" != "--skip-reload" ]; then
            reload "/api/services/scene/reload"
        fi
        ;;
    "scripts" )
        if [ "$2" != "--skip-upload" ]; then
            upload
        fi
        check
        if [ "$2" != "--skip-reload" ]; then
            reload "/api/services/script/reload"
        fi
        ;;
    *)
        echo "Usage: $0 <all | automations | groups | scenes | scripts> [--skip-upload | --skip-reload]"
        exit 1
        ;;
esac
