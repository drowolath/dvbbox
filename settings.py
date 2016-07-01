# encoding: uf-8

## Example settings.py file for dvbbox

# a channel is a handler name for a multicast stream
CHANNELS = {
    85: {
        'name': 'My Channel',
        'audio_pid': 30,
        'video_pid': 31,
        'vlc_telnet_port': 4000,
        'udp_multicast': '239.54.100.1:1234'
        },
    86: {
        'name': 'My Channel',
        'audio_pid': 32,
        'video_pid': 33,
        'vlc_telnet_port': 4001,
        'udp_multicast': '239.54.100.2:1234'
        },
    }

# dvbbox uses a redis database exclusively, no other support is envisionned yet
DATABASE = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'password': None
    }

LOGFILE = '/var/tmp/dvbbox.log'

# folders in which media files can be found
MEDIA_FOLDERS = [
    '/somewhere/over/the/rainbow',
    ]

PLAYLISTS_FOLDER = 'playlists/',

# peers with which the node can sync
PEERS = [
    {
        'host': 'peer.fqdn',
        'port': 6379,
        'db': 0,
        'password': None,
        },
    ]

VLC_TELNET_PASSWORD = 'somethingdeeplysecret',
