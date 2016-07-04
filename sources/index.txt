.. _dvbbox:

dvbbox
======

dvbbox is a very simple library for managing static media file and
orchestrating their streaming to allow one to create a TV channel.

You will just have to tell dvbbox where you store your files and you can then use it
to manage said files, create playlists and launch them for IP streaming.

.. attention::

   the media files must already be transcoded following the
   `MPEG-TS <https://en.wikipedia.org/wiki/MPEG_transport_stream>`_ standard


How to use
----------

At the very moment, dvbbox requires an awful amount of presets before working properly.
We are working on that, but bear with us as we explain why it is so.

Data storage
************

dvbbox awaits data to be stored in a redis database (exclusively).

* you should have a dataset called "files": this dataset is actually a sorted set
  where the keys are the filepaths of the media files, and the scores their duration.

* playlists are recorded as sorted sets also, named under the format "day:service_id":
  the keys are strings under the format "filenames:index" (index being an arbitrary value),
  and their scores are the timestamp at which they are programmed to be played.

Settings
********

dvbbox requires you to have a file /etc/dvbbox/settings.py readable by the user actually
using dvbbox. This file gathers all the settings useful to the application to work.

It's a python script, containing declarations of global values.

CHANNELS
........

A dictionnary where the keys are service IDs; each one of them holds another dictionnary
with the following keys: name, audio_pid, video_pid, vlc_telnet_port, udp_multicast

DATABASE
........

A dictionnary where the keys are keyword arguments used in the redis.Redis function.
Essentially: host, port, db, password.

LOGFILE
.......

A string representing the full path to the file holding the logs

MEDIA_FOLDERS
.............

A list of absolute paths to directories where media files are stored

PLAYLISTS_FOLDER
................

A string representing the full path to the directory holding each channel XSPF file.

PEERS
.....

This notion is important: dvbbox is designed to function as a cluster. So it can
contact another server to update its content (playlists wise and media files wise).

This settings is a list of dictionnaries. Where each dictionnary is a DATABASE parameter,
only with a remote server settings.

VLC_TELNET_PASSWORD
...................

A string representing a secret passphrase to access the telnet interface of a VLC stream.

Table of Contents
-----------------

.. toctree::
   :maxdepth: 3
   :glob:

   *
