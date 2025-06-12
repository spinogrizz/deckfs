#!/usr/bin/env bash

# Try to focus using dbus
if command -v dbus-send >/dev/null 2>&1; then
    dbus-send --session --type=method_call \
        --dest=org.mozilla.firefox.ZGVmYXVsdA== \
        /org/mozilla/firefox/Remote \
        org.mozilla.firefox.focus 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "Firefox window focused"
        exit 0
    fi
fi

# Try to focus using gdbus if Firefox is already running
if command -v gdbus >/dev/null 2>&1 && pgrep firefox >/dev/null 2>&1; then
    gdbus call --session \
        --dest=org.gnome.Shell \
        --object-path=/org/gnome/Shell \
        --method=org.gnome.Shell.Eval \
        "global.get_window_actors().filter(w => w.get_meta_window().get_wm_class() == 'firefox')[0]?.get_meta_window().activate(global.get_current_time())" >/dev/null 2>&1
    echo "Firefox activated"
    exit 0
fi

# Launch a new Firefox instance
if command -v firefox >/dev/null 2>&1; then
    firefox >/dev/null 2>&1 &
    echo "Firefox launched"
    exit 0
else
    echo "Error: Firefox not found" >&2
    exit 1
fi 