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
