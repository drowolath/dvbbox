#!/usr/bin/env python
#encoding: utf-8


import collections
import imp
import logging
import os
import redis
import shlex
import shutil
import subprocess as sub
import sys
import time
import xmltodict
from datetime import datetime, timedelta
from itertools import chain, islice, izip
settings = imp.load_source('settings', '/etc/dvbbox/settings.py')

reload(sys)
sys.setdefaultencoding('utf-8')

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(funcName)s %(message)s',
    datefmt='%d-%m-%Y %H:%M:%S',
    filename=settings.LOGFILE,
    level=logging.DEBUG
    )

DB = redis.Redis(**settings.DATABASE)
_ntuple_diskusage = collections.namedtuple('usage', 'total used free')

class System(object):
    """collection of static methods related to the system state"""
    
    @staticmethod
    def which(program):
        u"""Vérifie qu'un exécutable existe bel et bien"""
        def is_exe(fpath):
            return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
        fpath, fname = os.path.split(program)
        if fpath:
            if is_exe(program):
                return program
        else:
            for path in os.environ["PATH"].split(os.pathsep):
                path = path.strip('"')
                exe_file = os.path.join(path, program)
                if is_exe(exe_file):
                    return exe_file
        return None

    @staticmethod
    def diskusage(path):
        """Calcul de l'occupation disque d'un répertoire"""
        st = os.statvfs(path)
        free = st.f_bavail * st.f_frsize
        total = st.f_blocks * st.f_frsize
        used = (st.f_blocks - st.f_bfree) * st.f_frsize
        result =  _ntuple_diskusage(total, used, free)
        return float(result.used)/float(result.total)

    @staticmethod
    def nodeinfos():
        u"""Checks disk occupation, API availability"""
        folders = settings.MEDIA_FOLDERS
        infos = {
            'diskinfos': [],
            'api': False,
            'channels': None,
            }
        cmd = "df -h {0}".format(
            ' '.join(folders))
        result = sub.Popen(
            shlex.split(cmd),
            stdout=sub.PIPE,
            stderr=sub.PIPE
            )
        result = result.communicate()
        infos['diskinfos'] = result[0] or result[1]
        result = sub.Popen(
            shlex.split("cat /var/tmp/dvbbox_api.pid"),
            stdout=sub.PIPE,
            stderr=sub.PIPE
            )
        result = result.communicate()
        if result[0]:
            infos['api'] = result[0].strip()
        p1 = sub.Popen(
            shlex.split("ps aux"),
            stdout=sub.PIPE,
            stderr=sub.PIPE
            )
        p2 = sub.Popen(
            shlex.split("grep [v]lc"),
            stdin=p1.stdout,
            stdout=sub.PIPE,
            stderr=sub.PIPE
            )
        p1.stdout.close()
        result = p2.communicate()
        infos['channels'] = result[0] or result[1]
        return infos

class Media(object):
    """a media object is a file with .ts extension.
       Its informations are stored in a REDIS database
       so each instanciation won't compute again the values"""
    def __init__(self, filename):
        self.filename = filename
        if not filename.endswith('.ts'):
            self.filename += '.ts'
        files = DB.zrange('files', 0, -1, withscore=True)
        #zscan_iter isn't available before redis-server:2.8
        infos = filter(lambda x: x[0].split('/')[-1] == self.filename, files)
        if not infos:
            self.update()
        else:
            self.filepath, self.duration = infos.pop()

    def __duration__(self):
        """uses avprobe to list metainfos, and gawk to extract info"""
        cmd1 = "avprobe -show_format {filepath}".format(filepath=self.filepath)
        cmd2 = ("gawk 'match($0,/%s/,matches) "
                "{print matches[1]}'" % 'duration=(.[^,]*)')
        process_1 = sub.Popen(
            shlex.split(cmd1),
            stdout=sub.PIPE,
            stderr=sub.PIPE)
        process_2 = sub.Popen(
            shlex.split(cmd2),
            stdin=process_1.stdout,
            stdout=sub.PIPE)
        process_1.stderr.close()
        result = process_2.communicate()[0].strip('\n')
        return eval(result)

    def __repr__(self):
        return '<Media {}>'.format(self.filepath)
    
    @staticmethod
    def all():
        """method to get all mediafiles currently existing on disk(s).
           Only the first occurence of a file is listed, others are
           ignored"""
        media = set()
        filenames = {}
        for media_folder in settings.MEDIA_FOLDERS:
            try:
                files = iter(os.listdir(media_folder))
                for filename in files:
                    if filename in filenames or not filename.endswith('.ts'):
                        continue
                    filenames[filename] = 1
                    media.add(os.path.join(media_folder, filename))
            except OSError:
                msg = '{} does not exist'.format(media_folder)
                logging.error(msg)
                print msg
        return media

    @property
    def exists(self):
        """method to check if the filename actually
           exists. It is also used to update the REDIS database"""
        search = filter(lambda x: x.split('/')[-1]==self.filename, self.all())
        if search:
            filepath = search.pop()
            if not hasattr(self, 'filepath'):
                DB.zadd('files', filepath, 0)
                msg = '{redis_handler} : ADD {filepath}'.format(
                    redis_handler = DB, filepath = filepath)
                logging.info(msg)
                print msg
            self.filepath = filepath
            return True
        else:
            # file is not on disk, we destroy any reference to it everywhere
            if DB.zrem('files', self.filepath):
                # if there was a reference to the file in REDIS database
                msg = '{redis_handler} : DEL {filepath}'.format(
                    redis_handler = DB, filepath = self.filepath)
                logging.info(msg)
                print msg
            self.filepath = None
            self.duration = 0
            return False

    @property
    def schedules(self):
        """goes through the sorted sets ddmmyyyy:id and checks
           every occurence of filename""" 
        schedules = {}
        for key in [i for i in DB.keys() if ':' in i]:
            channel = int(key.split(':')[1])
            infos = DB.zrange(key, 0, -1, withscores=True)
            for filename, timestamp in infos:
                if filename.startswith(self.filename):
                    if not schedules.has_key(channel):
                        schedules[channel] = []
                    schedules[channel].append(timestamp)
        return schedules

    def rename(self, newname):
        """renames file"""
        if not newname.endswith('.ts'):
            newname += '.ts'
        if self.exists:
            oldpath = self.filepath
            newpath = self.filepath.replace(self.filename, newname)
            shutil.move(oldpath, newpath)
            self.filepath = newpath
            self.filename = newname
            DB.zrem('files', oldpath)
            DB.zadd('files', self.filepath, self.duration)
            return True
        else:
            msg = '{} does not exist'.format(self.filepath)
            logging.error(msg)
            raise ValueError(msg)
    
    def update(self):
        """updates attributes"""
        if self.exists:
            try:
                self.duration = self.__duration__
            except OSError:
                msg = 'check if avprobe and gawk are installed'
                logging.error(msg)
                raise OSError(msg)
            except Exception:
                self.duration = 0
            DB.zadd('files', self.filepath, self.duration)

    def delete(self):
        """deletes a file on disk given it's not scheduled for broadcast"""
        schedules = self.schedules
        now = time.time()
        timestamps = [
            filter(lambda x: x>= now, times)
            for schedule, times in schedules.items()
            ]
        timestamps = [
            timestamp for filtered_timestamps in timestamps
            for timestamp in filtered_timestamps
            ]
        if not timestamps:
            # the file is not scheduled at all
            os.remove(self.filepath)
            msg = "DEL {}".format(self.filepath)
            logging.info(msg)
            print msg
            self.update()
            return True
        else:
            msg = '{0} is scheduled for the following dates: {1}'.format(
                self.filename,
                '\n'.join([
                    datetime.fromtimestamp(i).strftime('%d-%m-%Y %H:%M:%S')
                    for i in timestamps
                    ])
                )
            logging.warning(msg)
            raise OSError(msg)


class Channel(object):
    """represents a handler for a DVB-IP stream"""
    def __init__(self, service_id):
        self.service_id = int(service_id)
        if not settings.CHANNELS.has_key(service_id):
            msg = '{} is not configured in /etc/dvbbox/settings.py'.format(
                self.service_id)
            logging.error(msg)
            raise ValueError(msg)
        else:
            for i, j in settings.CHANNELS[service_id]:
                vars(self)[i] = j

    def __program__(self, date=None, db=DB):
        """retreives informations about programs"""        
        dates = []
        programs = {}
        if not date:
            limit = datetime.today() - timedelta(30)
            dates.append(limit.strftime('%d%m%Y'))
            d = limit
            for i in range(60):
                d += timedelta(1)
                dates.append(d.strftime('%d%m%Y'))
        else:
            dates = [date]
        for date in dates:
            infos = {}
            key = '{0}:{1}'.format(date, self.service_id)
            schedule = db.zrange(key, 0, -1, withscores=True)
            for filename, timestamp in schedule:
                fileobj = Media(filename.split(':')[0])
                if not infos.get(filename):
                    infos[filename] = {
                        'duration': fileobj.duration,
                        'filepath': fileobj.filepath
                        }
                    infos[filename]['timestamps'] = []
                infos[filename]['timestamps'].append(timestamp)
            if len(dates) == 1:
                return infos
            else:
                programs[date] = infos
        return programs

    def program(self, date=datetime.now().strftime('%d%m%Y'), timestamp=None):
        """returns program of a given day, at a given timestamp"""
        programs = self.__program__(date)
        if programs and timestamp:
            marker = timestamp - min(
                [
                    timestamp-item
                    for sublist in [j['timestamps']
                                    for i, j in programs.items()]
                    for item in sublist if item<=timestamp
                ]
            )
            programs = {k: {
                'duration': v['duration'],
                'filepath': v['filepath'],
                'timestamps': [i for i in v['timestamps'] if i>=marker]
                } for k, v in programs.items()}
            
            programs = {k: v for k, v in programs.items() if v['timestamps']}
        return programs

    def checkprogram(self, date):
        """checks if a program for a given date is valid"""
        key = '{0}:{1}'.format(date, self.service_id)
        pipe = DB.pipeline()
        jobs = pipe.zrange(
            key,0,0,withscores=True).zrange(
                key,-1,-1,withscores=True)
        start, stop = jobs.execute()
        programs = self.__program__(date)
        if not programs:
            logging.warning('No program for {0} on {1}'.format(
                self.service_id, date))
            return None
        else:
            no_show_files = [
                filename for filename in programs if not Media(filename).exists
                ]
            if no_show_files:
                msg = 'Following files do not exist: {}'.format(
                    '\n'.join(no_show_files))
                logging.error(msg)
                return ValueError(msg)
            else:
                return True

    def syncprogram(self, date):
        """checks if peers got a more relevant program
           and adequately syncs"""
        key = '{0}:{1}'.format(date, self.service_id)
        peers = settings.PEERS_DATABASES
        remotes = {}
        for peer in peers:
            r = redis.Redis(**peer)
            bar = r.zrange(key, -1, -1, withscores=True)
            if bar:
                remotes[bar[0][1]] = peer['host']
        if remotes:
            key = '{0}:{1}'.format(date, self.service_id)
            last_item = DB.zrange(key, -1, -1, withscores=True)
            good_peer = remotes[max(remotes.keys())]
            # peer with most consistent prog
            good_peer = filter(lambda x: x['host'] == good_peer, peers).pop()
            remote_redis = redis.Redis(**good_peer)
            remote_schedule = self.__programs__(date=date, db=remote_redis)
            if not remote_schedule.get(date):
                msg = "No program for {0} on {1}".format(
                    date, good_peer['host'])
                logging.error(msg)
                print msg
                raise ValueError(msg)
            else:
                files_to_copy = filter(lambda x: not Media(x).exists,
                                       remote_schedule[date])
                copied = []
                for filename in files_to_copy:
                    remotepath = remote_schedule[date][filename]['filepath']
                    storages = iter(settings.MEDIA_FOLDERS)
                    try:
                        while True:
                            storage = storages.next()
                            if System.diskusage(storage) < 0.9:
                                cmd = ("rsync --progress -z "
                                       "{0}:{1} {2}").format(
                                           good_peer['host'],
                                           remotepath,
                                           storage)
                                sub.call(shlex.split(cmd))
                                logging.info('{0} copié depuis {1}'.format(
                                    filename, good_peer['host']))
                                Media(filename)
                                copied.append(filename)
                                break
                    except StopIteration:
                        not_copied = [
                            i for i in files_to_copy if not i in copied
                            ]
                        msg = ("No more space left on disk. Following files "
                               "couldn't be rsync-ed: {0}").format(
                                   '\n'.join(not_copied))
                        logging.warning(msg)
                        print msg
            if not last_item or max(remotes.keys()) > last_item[0][1]:
                remote = remote_redis.zrange(key, 0, -1, withscores=True)
                DB.delete(key)
                msg = "Deleted all schedules related to {0}".format(key)
                logging.info(msg)
                print msg
                DB.zadd(key, **dict(remote))
                msg = "Synced schedules for {0} with {1}".format(
                    key, remotes[max(remotes.keys())])
                logging.info(msg)
                print msg
            
    def createxspf(self, date=datetime.now().strftime('%d%m%Y'),
                   start='073000', marker=None):
        """creates a XSPF playlist from schedule in REDIS database"""
        key = '{0}:{1}'.format(date, self.service_id)
        recalculated_start = 0
        try:
            initial = time.mktime(
                time.strptime('{0} {1}'.format(date, start), '%d%m%Y %H%M%S')
                )
            xspf = {'playlist': {
                '@xmlns': 'http://xspf.org/ns/0/',
                '@xmlns:vlc':
                    'http://www.videolan.org/vlc/playlist/ns/0/',
                '@version': '1'}}
            fulldate = '{day}/{month}/{year}'.format(
                day=date[:2],
                month=date[2:4],
                year=date[4:]
                )
            xspf['playlist']['title'] = fulldate
            xspf['playlist']['trackList'] = {'track': []}
            other = {
                'extension': {
                    'vlc:option': [],
                    'vlc:item': [],
                    '@application': 'http://www.videolan.org/vlc/playlist/0'
                    }
                }
            #  maintenant on récupère les films qui doivent être diffusés
            media = DB.zrange(key, 0, -1, withscores=True)
            if marker:
                recalculated_start = marker - min(
                    [
                        marker-item
                        for item in [i[1] for i in media] if item<=marker
                    ]
                )
                media = DB.zrangebyscore(
                    key, recalculated_start,
                    initial+86400, withscores=True)

            steps = izip(
                *[
                    chain(islice(media, i, None), islice(media, None, i))
                    for i in range(2)
                    ]
                )
            index = 0
            while True:
                uri = 'http://www.videolan.org/vlc/playlist/0'
                start, stop = steps.next()
                index += 1
                extension = {
                    '@application': uri,
                    'vlc:id': index,
                    'vlc:option': []
                }
                tsfile = Media(start[0].split(':')[0])
                stop = stop[1]
                if start[1] == recalculated_start:
                    extension['vlc:option'].append(
                        'start-time={0}'.format(
                            (marker - recalculated_start)
                            )
                        )
                if stop <= start[1]:
                    stop = initial+86340
                    
                duration = stop - start[1]
                if tsfile.duration < duration:
                    repeat = int(round(duration/tsfile.duration)) - 1
                    if repeat < 0:
                        return None
                    elif repeat:
                        extension['vlc:option'].append(
                            'input-repeat={0}'.format(repeat)
                            )
                track = {
                    'location': 'file:///{0}'.format(tsfile.filepath),
                    'duration': tsfile.duration
                    }
                track['extension'] = extension
                xspf['playlist']['trackList']['track'].append(track)
                other['extension']['vlc:item'].append({'@tid': str(index)})
        except StopIteration:
            document = xmltodict.unparse(xspf, pretty=True)
            document = document.replace('></vlc:item>', '/>')
            extensions = xmltodict.unparse(other, pretty=True)
            extensions = extensions.replace(
                '<?xml version="1.0" encoding="utf-8"?>',
                ''
                )
            extensions = extensions.replace('\n', '\n\t')
            extensions = extensions.replace('></vlc:item>', '/>')
            result = document.split(
                '</playlist>')[0]+extensions+'\n</playlist>'
            return result
        except Exception as exc:
            result = exc
            return result

    def stream(self, duplicate=None):
        """streams a xspf file"""
        u"""Méthode permettant de lancer la diffusion IP de la chaine"""
        moment = '{day}{month}{year}'.format(
            day=str(time.localtime().tm_mday).zfill(2),
            month=str(time.localtime().tm_mon).zfill(2),
            year=str(time.localtime().tm_year)
        )
        result = self.createxspf(moment, timestamp=time.time())
        if type(result) is unicode:
            xspffile = os.path.join(
                settings.PLAYLISTS_FOLDER,
                str(self.service_id),
                '{0}.xspf'.format(moment)
                )
            with open(xspffile, 'w') as f:
                f.write(result)
            if not duplicate:
                cmd = ("cvlc %s -I telnet --telnet-host 0.0.0.0 "
                       "--telnet-password %s --telnet-port %s "
                       "--sout '#standard{"
                       "access=udp,"
                       "mux=ts{pid-video=%s,pid-audio=%s,pcr=100},"
                       "dst=%s}' --playlist-tree --ttl 10 "
                       "vlc://quit") % (
                           xspffile,
                           settings.VLC_TELNET_PASSWORD,
                           self.telnet_port,
                           self.pid_video,
                           self.pid_audio,
                           self.udp
                        )
            else:
                default_dst = ("dst=udp{mux=ts{pid-video=%s,pid-audio=%s,"
                               "pcr=100},dst=%s}") % (self.pid_video,
                                                      self.pid_audio,
                                                      self.udp)
                duplicate.append(default_dst)
                dst = ','.join(duplicate)
                cmd = ("cvlc %s -I telnet --telnet-host 0.0.0.0 "
                       "--telnet-password %s --telnet-port %s "
                       "--sout '#duplicate{%s}  --playlist-tree --ttl 10 "
                       "vlc://quit") % (
                           xspffile,
                           settings.VLC_TELNET_PASSWORD,
                           self.telnet_port,
                           dst)
            process = sub.Popen(
                shlex.split(cmd),
                stdout=sub.PIPE,
                stderr=sub.PIPE)
            return process
        else:
            # on a une erreur
            return result.message

        
class Playlist(object):
    """playlists manager and scheduler"""
    def __init__(self, filepath):
        self.filepath = filepath

    def __read__(self):
        """reading the INI file"""
        infos = []
        today = time.localtime()
        year = today.tm_year
        data = None
        checked = {}
        with open(self.filepath) as f:
            for line in f:
                info = line.strip()
                if info.startswith('[') and info.endswith(']'):
                    if data: infos.append(data)
                    day = info[1:-1]
                    if int(day[3:]) < today.tm_mon:
                        year += 1
                    timestamp = time.mktime(
                        time.strptime(
                            '{day}{year}'.format(
                                day=day, year=year),
                        '%d/%m%Y'
                        )
                     )
                    start = timestamp + 27000
                    data=set()
                elif info:
                    if not info in checked:
                        checked[info] = Media(info)
                    data.add('{0}:{1}.ts:{2}'.format(
                        start, info, checked[info].duration))
                    start += checked[info].duration
            infos.append(data)
        return infos
    
    def apply(self, service_id):
        """parsing the INI file"""
        infos = self.__read__()
        result = []
        for info in infos:
            e = next(iter(info))
            d = datetime.fromtimestamp(float(e.split(':')[0]))
            if 60 * (60*d.hour + d.minute) >= 27000:
                day = d.date().strftime('%d%m%Y')
            else:
                day = d.date() - timedelta(1)
                day = day.strftime('%d%m%Y')
            key = '{0}:{1}'.format(day, self.service_id)
            errors = []
            programs = {}
            index = 0
            for program in info:
                index += 1
                start, filename, duration = program.split(':')
                start = float(start)
                duration = float(duration)
                if not duration:
                    errors.append(filename)
                else:
                    programs['{0}:{1}'.format(filename, index)] = start
            if errors:
                # report errors
                msg = ("No program created for {0} "
                       "because the following files "
                       "are missing: {1}").format(key,
                                                  '\n'.join(errors))
                logging.warning(msg)
                result.append(msg)
            else:
                DB.delete(key)
                DB.zadd(key, **programs)
                msg = "Program created for {0}".format(key)
                logging.info(msg)
                result.append(msg)
        return result
#EOF
    

                
                
