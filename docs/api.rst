.. _dvbbox_api:

API
===

dvbbox propose deux interfaces programmables:

 * une interface en ligne de commande (propulsée par :code:`Flask-Script`)
 * une interface REST, accessible via HTTP (propulsée par :code:`Flask`)

.. _dvbbox_cli:
   
Command Line Interface
----------------------

A l'installation , une commande est aussitôt mise à disposition sous :file:`/usr/bin/dvbbox`.
Elle est accessible en exécution à tous les utilisateurs.

En pratique, un seul utilisateur peut vraiment tout faire avec: l'utilisateur qui a les droits
d'écriture sur le fichier de log configuré dans :file:`/etc/dvbbox/configuration`.
Les autres utilisateurs peuvent simplement effectuer des opérations de lecture d'information.

:code:`dvbbox media`
********************

La commande :code:`dvbbox media` permet littéralement de gérer les fichiers TS.

Elle permet d'avoir des infos sur un fichier:

.. code-block:: bash

   $ dvbbox media mymediafile.ts
   Filepath: /opt/tsfiles/mymediafile.ts
   Duration: 3600  # la durée est en secondes
   85  # l'identifiant de la chaine sur laquelle le fichier sera diffusé
   01-08-2017 15:00:00  # les dates et heures de diffusion sur cette chaine
   02-08-2017 23:45:17
   86  # une autre chaine sur laquelle le fichier sera diffusé
   02-02-2017 08:00:00  # les dates et heures de diffusion sur cette chaine

.. important::

   dvbbox ne fait aucune restriction sur la diffusion multi-canal d'un fichier:
   le même fichier peut être diffusé sur plusieurs chaines différentes.

Elle permet aussi de renommer un fichier:

:code:`$ dvbbox media mymediafile.ts --rename yourmediafile.ts`

Elle permet enfin de supprimer un fichier:

:code:`$ dvbbox media yourmediafile.ts --delete`

:code:`dvbbox listing`
**********************

La commande :code:`dvbbox listing` permet de traiter et éventuellement d'appliquer un listing.

Pour traiter un listing:

.. code-block:: bash

   $ dvbbox listing /var/tmp/dvbbox/uploads/listing_du_date1_au_date3

   date1
   =====
   date1 heure1: film1 (x secondes)
   date1 heure2: film2 (y secondes)
   ...
   End: date2 04:50:00

   date2
   =====
   date2 heure1: film1 (x secondes)
   date2 heure2: film2 (y secondes)
   ...
   End: date3 02:10:00

   date3
   =====
   date3 heure1: film1 (x secondes)
   date3 heure2: film2 (0 secondes)  # ce fichier n'existe donc pas
   ...
   End: date4 03:00:00

Pour appliquer un listing:

.. code-block:: bash

   $ dvbbox listing /var/tmp/dvbbox/uploads/listing_du_date1_au_date3 --service_id 85

.. important::

   Quand un fichier n'existe pas, il est quand même conservé dans la liste de lecture
   avec un chemin par défaut et une durée nulle. On peut donc appliquer un listing,
   même si certains fichiers n'existent pas. La synchronisation entre pairs peut
   résoudre celà, sinon il ne faut pas oublier de copier le fichier sur le serveur.

:code:`dvbbox program`
**********************

La commande de vérification, mise à jour et diffusion des programmes.

Avoir le programme d'une chaine, un jour donné
..............................................

.. code-block:: bash

   $ dvbbox program 09082017 --service_id 85

   Ma chaine
   =========

   09082017:
   09-08-2017 07:30:00: /opt/tsfiles/fichier_0.ts
   09-08-2017 09:30:00: /opt/tsfiles/fichier_1.ts
   09-08-2017 13:40:56: /opt/tsfiles/fichier_2.ts
   09-08-2017 14:10:00: /opt/tsfiles/fichier_3.ts # ce fichier par exemple n'existe pas
   09-08-2017 14:10:00: /opt/tsfiles/fichier_4.ts  

Avoir uniquement un résumé du programme d'un jour donné
.......................................................

.. code-block:: bash

   $ dvbbox program 09082017 --service_id 85 --check

   Ma chaine
   =========

   09082017:
   --------
   The following files are missing:
   /opt/tsfiles/fichier_4.ts

   # si tout va bien, le texte précédent sera remplacé par OK

Mettre à jour le programme d'un jour donné sur une chaine donnée
................................................................

Cette commande va re-vérifier l'existence des fichiers listés dans la programmation, et corriger
les chemins et les heures de début en fonction. En effet, si dans la programmation, un fichier
manque, l'heure de début sera la même que celle du film suivant. Si la commande retrouve le
fichier sur le disque elle va donc modifier décaler les heures de début des fims suivant pour
insérer le nouveau film.

.. code-block:: bash

   $ dvbbox program 09082017 --service_id 85 --update
  
Synchroniser la programmation entre pairs pour un jour donné, sur une chaine donnée
...................................................................................

La synchronisation consiste à scanner tous les serveurs pairs, et déterminer si pour la chaine et
le jour donnés leur programmation est plus pertinente que celle possédée par le serveur.

.. important::

   Pour l'instant la pertinence d'une programmation ne se base que sur son heure de fin.
   Plus elle est se rapproche de 07h30 le lendemain, en y restant inférieur,
   plus elle est pertinente.

.. code-block:: bash

   $ dvbbox program 09082017 --service_id 85 --sync

Si une programmation pertinente est trouvée parmi les serveurs pairs:

 * suivant cette nouvelle programmation, les fichiers manquants sont copiés à partir du serveur
   qui a fourni cette programmation pertinente

 * la programmation en cours est remplacée

 * la programmation est ensuite mise à jour pour corriger les éventuelles imperfections

Supprimer une programmation pour un jour donné, sur une chaine donnée
.....................................................................

.. code-block:: bash

   $ dvbbox program 09082017 --service_id 85 --delete

Diffuser une programmation d'une chaine donnée
..............................................

.. code-block:: bash

   $ dvbbox program 09082017 --service_id 85 --stream

:code:`dvbbox adduser`
**********************

Cette commande permet d'autoriser un utilisateur à accéder à l'API REST

.. code-block:: bash

   $ dvbbox adduser johndoe
   Password:
   Confirm:

.. _dvbbox_api_rest:

Interface HTTP
--------------

On peut communiquer avec dvbbox à coup de requêtes HTTP.
Toutes les fonctions de bases de son API interne sont disponibles.

L'API est protégée par un token d'authentification: à chaque requête, il faut fournir un jeton
d'identification. Ce dernier a une durée de vie limitée (1h).

Pour obtenir le jeton, on utilise son login et son mot de passe:

.. code-block:: bash

   ~$ curl --user username:password -X POST /api/dvbbox/auth/request-token

ou si vous préférez (et vous devriez) `httpie <http://httpie.org>`_

.. code-block:: bash

   ~$ http --auth username POST /api/dvbbox/auth/request-token

Vous obtiendrez un document JSON contenant le token. Enregistrez ce token
dans une variable de session pour utilisation future

.. attention::

   Dans la suite nous utiliserons $TK pour faire référence au token d'authentification.

   Nous utiliserons :file:`/api/dvbbox/` pour désigner l'URI de l'API.

   Pour les exemples, nous utiliserons la version **v1** de l'API


:code:`GET /api/dvbbox/`
************************

Cette commande va récupérer le catalogue de commandes disponibles via l'interface HTTP. En gros,
c'est pour lister les différentes versions

.. code-block:: json

   {
    "versions": {
        "v1": {
            "infos_url": "/api/dvbbox/v1/infos/", 
            "listing_url": "/api/dvbbox/v1/listing/", 
            "media_url": "/api/dvbbox/v1/media/", 
            "programs_url": "/api/dvbbox/v1/programs/"
        }
    }
   }


:code:`GET /api/dvbbox/v1/media/`
*********************************

Cette commande renvoie la liste de tous les fichiers TS présents sur le serveur.

.. code-block:: json

   {
    "total": 300,
    "media": [
     {
        "filename": "film1",
        "ressource_uri": "/api/dvbbox/v1/media/film1"
     },
     ...
     {
        "filename": "film300",
        "ressource_uri": "/api/dvbbox/v1/media/film300"
     },
    ],
   }

:code:`POST /api/dvbbox/v1/media/`
**********************************

Cette commande prend en paramètre (dans le champ :code:`file`) un fichier représentant
une liste de films. La commande va simplement renvoyer les informations sur ces fichiers et
préciser si un ou plusieurs fichiers n'existent pas.

.. code-block:: json

   {
    "total": 300,
    "errors": ["film296", "film297", "film298", "film299", "film300"],
    "media": [
     {
        "filepath": "/path/on/disk/to/film1",
        "duration": 5629,
        "schedule": {
         "85": [
          '1470246856.16',
          '1472232060.8388784',
          '1471959675.5386558',
          '1471640321.2960572',
          '1470561951.6',
          '1471340593.76',
          '1472502050.4977453',
          '1470854778.72'
         ]
        }
     },
     ...
     {
        "filepath": "/path/on/disk/to/film295",
        "duration": 2378,
        "schedule": {
         "8": [
          '1470246856.16',
          '1472232060.8388784',
          '1471959675.5386558',
          '1471640321.2960572',
          '1470561951.6',
          '1471340593.76',
          '1472502050.4977453',
          '1470854778.72'
         ]
        }
     },
    ],
   }

:code:`PUT /api/dvbbox/v1/media/`
*********************************

Cette commande permet de rechercher tous les films correspondant à la regex :code:`".*value.*"`,
où :code:`value` est la valeur du champ :file:`search`.

:code:`GET /api/dvbbox/v1/media/un_fichier`
*******************************************

Cette commande permet d'avoir les informations sur un fichier donné

.. code-block:: json

   {
    "filepath": "/path/on/disk/to/film1",
    "duration": 5629,
    "schedule": {
     "85": [
      '1470246856.16',
      '1472232060.8388784',
      '1471959675.5386558',
      '1471640321.2960572',
      '1470561951.6',
      '1471340593.76',
      '1472502050.4977453',
      '1470854778.72'
     ]
    }
   }

:code:`PUT /api/dvbbox/v1/media/un_fichier`
*******************************************

Cette fonction sert à renommer un fichier TS. Il suffit, pour ça, de fournir le nouveau nom
(sans extension) dans le champ :file:`new_name` du formulaire soumis.

:code:`DELETE /api/dvbbox/v1/media/un_fichier`
*******************************************

Il est assez évident que cette fonction supprime un fichier TS donné.

.. attention::

   Cette action est irréversible.

:code:`POST /api/dvbbox/v1/listing/`
************************************

Cette fonction soumet un listing pour traitement et éventuellement application.
Le champ du formulaire accueillant le fichier est :file:`file`.
Si on veut effectivement appliquer le listing, il suffit de préciser sur quelle chaine on veut
l'appliquer en remplissant le champ :file:`service_id` du formulaire.

:code:`GET /api/dvbbox/v1/programs/`
************************************

Cette fonction va donner une liste de tous les jours et les chaines pour lesquelles il existe
un programme. Aucun détail sur le programme ne sera donné.

.. code-block:: json

   {
    "total": 1,
    "result": [
     {
      "service_id": "85",
      "date": "01012017",
     },
    ],
   }

:code:`POST /api/dvbbox/v1/programs/`
*************************************

Si on dispose d'un fichier donnant la programmation horodatée pour un jour donné sur une
chaine donnée, on peut très bien l'appliquer sur le serveur. Le formulaire attend ce fichier
dans le champ :code:`file`.


:code:`GET /api/dvbbox/v1/programs/day/service_id`
**************************************************

Cette fonction récupère un document JSON donnant le programme d'un jour donné, sur une chaine
donnée. Le résultat ressemble à ceci:

.. code-block:: json

   {
    "total": 60,
    "result": [
     {
      "start-time": "01-01-2017 07:30:00",
      "media": {
       "filename": "film1",
       "ressource_uri": "/api/dvbbox/v1/media/film1",
      }
     },
     ...
    ],
   }

:code:`DELETE /api/dvbbox/v1/programs/day/service_id`
*****************************************************

Il est assez évident que cette fonction supprime un programme donné pour une chaine donnée.

.. attention::

   Cette action est irréversible.

:code:`PUT /api/dvbbox/v1/programs/day/service_id`
**************************************************

Cette fonction met à jour un programme donné sur une chaine donnée.
