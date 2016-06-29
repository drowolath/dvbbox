## Example settings.py file for dvbbox

# dvbbox uses a redis database exclusively, no other support is envisionned yet
DATABASE = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'password': None
    }

# folders in which media files can be found
MEDIA_FOLDERS = [
    '/somewhere/over/the/rainbow',
    ]

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
