.. _dvbbox:

dvbbox
======

dvbbox est un gestionnaire de listes de lecture de fichiers media (au format TS).
Il donne la possibilité de créer des listes de lecture qui seront diffusées plus tard via DVB-IP.

.. _dvbbox_pre_requis:

Pré-requis
----------

A lui tout seul, dvbbox réutilise bon nombre de logiciels:

* avprobe: pour lire les métadonnées d'un fichier TS
  
* vlc-nox: pour diffuser effectivement une playlist au format XSPF
    
* redis-server: moteur de base de données

* python2.7

  * python-redis (redis)

  * python-xmltodict (xmltodict)

  * python-flask: pour l'API REST

  * python-flask-httpauth: pour l'authentification par HTTPAuth à l'API REST

  * python-flask-redis: ORM pour gérer la base REDIS via l'application Flask

  * python-flask-script: pour créer un outil en CLI

.. _dvbbox_installation:
  
Installation
------------

Parce qu'on na pas de serveur de packages Python, on va devoir cloner le projet
et créer un .deb

.. code-block:: bash

   $ git clone http://gitlab.blueline.mg/default/dvbbox.git
   $ cd dvbbox
   dvbbox$ make
   dvbbox$ sudo make install
		
.. _dvbbox_conf:

Configuration
-------------

dvbbox range sa configuration dans :file:`/etc/dvbbox/configuration`.

Techniquement, c'est juste un script Python qui ne contient que des déclarations
de constantes.

Ci-dessous un exemple (toutes les constantes listées ici sont celles qui sont obligatoires):

.. code-block:: python

   [REDIS]
   url=redis://address:port/db
   
   [MEDIA_FOLDERS]
   /my/partition
   
   [PEERS]
   server.domain
   
   [PLAYLISTS]
   /var/tmp/dvbbox/playlists
   
   [LOG]
   filepath=/tmp/dvbbox.log
   level=10
   datefmt=%d-%m-%Y %H:%M:%S
   
   [FLASK]
   DEBUG=True
   USE_AUTH_TOKEN=True
   SECRET_KEY=somethingdeeplysecret
   
   [SERVICE:100]
   name=My Channel's name
   pid_video=2000
   pid_audio=2001
   vlc_telnet_port=4201
   vlc_telnet_password=somethingverysecret
   udp=mcast_address:port


.. _dvbbox_toc:

Documentation
-------------

.. toctree::
   :maxdepth: 4
   :glob:

   *
