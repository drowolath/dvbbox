.. _dvbbox_underthehood:

Sous le capot
=============

dvbbox permet de créer des listes de lecture, `stockées sous forme de sets ordonnés dans une base de données REDIS <http://redis.io/topics/data-types>`_, à partir d'un listing; ces listes de
lecture sont ensuite transformées en fichiers XSPF au moment de leur diffusion.

Quelques notions doivent être mises en contexte avant de continuer.


Le fichier TS/media/multimedia/statique
---------------------------------------

Un fichier TS représente l'unité de base dans l'univers de dvbbox.

Il:

 * possède un nom toujours terminé par .ts: exemple.ts
 * est situé quelque part sur le disque: /chemin/absolu/vers/exemple.ts
 * a une durée bien déterminée

Dans sa :ref:`dvbbox_conf`, dvbbox liste dans la constante :code:`MEDIA_FOLDERS` tous les dossiers
où il pense pouvoir trouver des fichiers TS. Tout fichier TS n'étant pas dans ces dossiers ne sera
pas vu par dvbbox et pourra par exemple être considéré comme étant inexistant.

dvbbox permet de:

 * voir les infos relatives à un fichier TS, notamment les jours et heures auxquels il est
   censé être diffusé
 
 * renommer un fichier TS: il renomme aussi dans les différentes programmations

 * supprimer un fichier TS: la suppression est définitive

A propos de la durée d'un fichier TS
************************************

Calculer la durée d'un fichier TS se fait via la commande :code:`avprobe -show_format`.
Cette commande est gourmande en temps d'accès au disque. Pour économiser des ressources, dvbbox
ne l'exécute qu'une seule fois par fichier. Une fois que la durée a été calculée, dvbbox la stock
dans la base de données REDIS sous forme de (clé, valeur) où la clé est le nom du fichier et
la valeur sa durée.


Le listing
----------

Vous vous rappelez qu'en introduction on avait parlé de listing? Le listing c'est ce que dvbbox
utilise pour créer des listes de lecture, des programmes.

Un listing, c'est généralement copié dans le dossier mentionné dans la constante :code:`uploads`
dans le fichier de configuration; et ça ressemble à ça:

.. code-block:: bash

   [09/09]
   fichier_0
   fichier_1
   fichier_2
   fichier_3
   fichier_4
		
   [10/09]
   un_autre_fichier_0
   un_autre_fichier_1
   un_autre_fichier_2
   un_autre_fichier_3
   un_autre_fichier_4

Créer un listing est de la responsabilité de la personne qui veut créer des programmes.
En d'autres termes, l'ordre dans lequel on liste les fichiers à diffuser pour un jour donné,
est important et doit être vérifié à l'édition.

Une fois le listing créé, il faut l'envoyer sur un serveur où dvbbox est installé. Cet envoi
peut se faire via :code:`rsync`.

Supposons que:

 * votre listing soit enregistré sur votre machine sous le nom :file:`listing_du_0909_au_2009`

 * vous vouliez copier ce listing sur le serveur :file:`dektec-antananarivo-1.malagasy.com`

 * sur le serveur, dvbbox est installé et configuré avec :code:`uploads='/var/tmp/dvbbox/uploads'`


Traitement d'un listing
***********************

Traiter un listing c'est tout simplement réussir à créer une liste de lecture horodatée,
un programme donc, à partir dudit listing.

Si on reprend les suppositions précédentes, le traitement se fait simplement comme ceci:

:code:`$ dvbbox listing /var/tmp/dvbbox/uploads/listing_du_0909_au_2009`

Ce qui se passe dans ce bout de commande est magique: dvbbox va lire le listing, vérifier que chaque fichier existe bel et bien, et indiquer à quelle heure la programmation se termine pour chaque jour en additionnant les durées des fichiers. Un fichier qui n'existe pas est considéré comme ayant une durée nulle.

.. important::
   
   A ce stade, rien n'est encore stocké dans la base de données REDIS. C'est juste une opération
   de lecture.

Application d'un listing
************************

Appliquer un listing, c'est enregistrer effectivement les différents programmes dans la base de
données REDIS. Pour ce faire, dvbbox va traiter le listing (voir paragraphe précédent) puis
stocker le résultat dans la base REDIS sous forme de set ordonné.

Chaque set ordonné:

 * aura pour nom **jjmmaaaa:id**, où **jjmmaaaa** est le jour du programme (dans le listing
   c'est le nom de la section [jj/mm]) et **id** l'identifiant de la chaine qui va diffuser
   le programme

 * aura des valeurs qui seront au format **/chemin/vers/fichier/ts:index**, où
   **/chemin/vers/fichier/ts** est le chemin absolu vers le fichier TS prévu pour diffusion à ce
   moment et **index** un index arbitraire pour différentier les différentes occurences du fichier
   TS dans la programmation (on peut diffuser plusieurs fois le même fichier, le même jour); si
   un fichier TS n'existe pas, un chemin arbitraire lui est attribué

 * donnera un score à chaque valeur: ce score sera le timestamp désignant le moment
   (jour et heure) auquel il faut jouer le fichier; si une valeur a le même timestamp que
   la valeur qui la suit, ça veut dire que pour cette valeur le fichier n'existe pas.


La programmation
----------------

La programmation est la version horodatée d'un paragraphe d'un listing. A partir d'une section
d'un listing, dvbbox peut créer une liste de lecture précisant les heures auxquelles chaque
fichier doit être joué.

Comme on l'a vu dans le paragraphe précédent, dvbbox stock les programmes dans une base de données
REDIS sous forme de set ordonné.

Au moment de la diffusion, c'est ce set ordonné que dvbbox lit, et transforme en fichier XSPF
pour ensuite lancer VLC qui va simplement lire ce fichier.


La diffusion (le streaming)
---------------------------

Lorsqu'on demande à dvbbox de diffuser un programme sur une chaine, il va rechercher dans REDIS
le set ordonné **jjmmaaaa:id** et le transformer en fichier XSPF. Une fois le fichier XSPF créé,
il va demander à VLC de diffuser en multicast, via une interface réseau, le fichier XSPF.

