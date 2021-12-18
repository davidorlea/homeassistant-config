#!/bin/bash

if [ -z "$HASS_SSH_URL" ]; then
    echo "You need to set deployment parameter HASS_SSH_URL"
    exit 1
fi

ssh "$HASS_SSH_URL" << 'EOF'
    source $VENV_DIR/bin/activate
    python --version
    pip --version
    pip --disable-pip-version-check install -U setuptools wheel
    pip --disable-pip-version-check install -r requirements.txt
    deactivate
EOF
