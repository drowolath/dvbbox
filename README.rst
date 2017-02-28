======
dvbbox
======

dvbbox is a simple tool to manage pre-encoded TS media files, create playlists
and stream them out.

Requirements
============

* vlc-nox>=2.0.3: for streaming
* libav-tools>=0.8.17: to check media file's meta-data
* redis-server>=2.4: to store programs and media file's meta-data
* an .INI configuration file (see: :ref:`dvbbox_config`)

Installation
============

.. important::

   Make sure you did install vlc-nox, libav-tools, and redis-server first!

You can install a .deb packaged version:

.. code-block::

   $ git clone https://github.com/drowolath/dvbbox.git
   $ cd dvbbox
   $ make
   $ sudo make install

Or if you don't want to use some arbitrary packaging format (and you shouldn't):

.. code-block::

   $ git clone https://github.com/drowolath/dvbbox.git
   $ cd dvbbox
   $ pip install -r requirements.txt
   $ python setup.py sdist
   $ pip install dist/python-dvbbox-*.tar.gz --user

Some quick notions
==================

dvbbox uses three (3) major concepts:

* Media: pre-encoded TS media files
* Program: a timetable giving the start time of different media files for a given day and a given
service id
* Listing: an .INI file where sections are dates (formatted as %d/%m) and options are media
file names (no path, no extension)

dvbbox allows you to:

* seek informations for, rename and delete media files
* seek informations for, check, update, backup, delete and stream programs
* parse and apply listings

For a provided listing, dvbbox will parse it and create a program out of it. If some media files
don't exist at all (on the server and on the eventual peers), their duration is set to 0 and the
parsing goes on.

Documentation
=============

Full documentation is available under folder docs/
