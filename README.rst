dvbbox: Create your own DVB-IP channels
=======================================

dvbbox is a very simple library for managing static media file and orchestrating their streaming to
allow one to create a TV channel.

You will just have to tell dvbbox where you store your files and you can then use it
to manage said files, create playlists and launch them for IP streaming.

.. attention::

   the media files must already be transcoded following the `MPEG-TS <https://en.wikipedia.org/wiki/MPEG_transport_stream>`_ standard


The Basics
----------

You would create a playlist under the form of an INI file

.. code-block:: bash

   [day/month]
   filename_1
   filename_2
   ...

   [another_day/month]
   filename_x
   filename_y
   ...

And as simple as:


.. code-block:: bash

   $ dvbbox process /filepath/to/playlist [--apply]

you test and eventually apply your playlist. The result come with warnings and informations regarding mediafiles missing or mispelled.


Installation
------------

.. code-block:: bash

   $ pip install dvbbox

REST API
--------

The tool comes with an additional bonus: a REST API interfacing all the functionalities provided by the command-line tool

