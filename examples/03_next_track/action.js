#!/usr/bin/env node

/**
 * Media Player Control - Next Track
 * Send next track command to first available media player via D-Bus
 */

const { exec } = require('child_process');

// Get list of active MPRIS media players
exec('dbus-send --session --dest=org.freedesktop.DBus --type=method_call --print-reply /org/freedesktop/DBus org.freedesktop.DBus.ListNames | grep "org.mpris.MediaPlayer2"', 
    (error, stdout, stderr) => {
        if (error) {
            console.log('No media players found');
            return;
        }
        
        // Parse first available player
        const lines = stdout.split('\n');
        const playerLine = lines.find(line => line.includes('org.mpris.MediaPlayer2'));
        
        if (!playerLine) {
            console.log('No media players found');
            return;
        }
        
        const playerName = playerLine.trim().replace(/^.*"(.*)".*$/, '$1');
        console.log(`Found media player: ${playerName}`);
        
        // Send next track command
        const nextCommand = `dbus-send --print-reply --session --dest=${playerName} /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Next`;
        
        exec(nextCommand, (error, stdout, stderr) => {
            if (error) {
                console.error(`Failed to send next track command: ${error.message}`);
            } else {
                console.log('Next track command sent');
            }
        });
    }
);