#!/usr/bin/env python
# encoding: utf-8

"""
Manages TS files playlists for future broadcasting
"""


import collections
import ConfigParser
import json as _json
import logging
import os
import re
import redis
import shlex
import shutil
import socket
import subprocess as sub
import sys
import time
import xmltodict
from api.models import db, User
from datetime import datetime, timedelta
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from flask import Flask
from flask_script import Manager
from itertools import chain, islice, izip
from logging.handlers import RotatingFileHandler
from smtplib import SMTP

# get config reader
config = ConfigParser.ConfigParser(allow_no_value=True)
config.read('/etc/dvbbox/configuration')

# define logger
logger = logging.getLogger()
logger.setLevel(int(config.get('LOG', 'level')))
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s %(message)s',
    datefmt=config.get('LOG', 'datefmt')
    )
logs = RotatingFileHandler(config.get('LOG', 'filepath'), 'a', 1000000, 1)
logs.setLevel(int(config.get('LOG', 'level')))
logs.setFormatter(formatter)
logger.addHandler(logs)

# define constants
disk_usage = collections.namedtuple('usage', 'total used free')
duration_regex = re.compile('.*\nduration=(.*)\n.*')
media_folders = config.options('MEDIA_FOLDERS')
playlists_folder = config.get('DATA_FOLDERS', 'playlists')
redis_url = ("redis://(:(?P<password>(.*))@)?(?P<host>(.*)):"
             "(?P<port>(\d+))/(?P<db>(\d+))")
redis_programs = re.compile(redis_url).search(config.get('REDIS', 'programs'))
redis_media = re.compile(redis_url).search(config.get('REDIS', 'media'))
redis_media_db = redis.Redis(**redis_media.groupdict())
redis_programs_db = redis.Redis(**redis_programs.groupdict())
app = Flask(__name__)
app.config['DEBUG'] = config.get('FLASK', 'DEBUG')
app.config['SECRET_KEY'] = config.get('FLASK', 'SECRET_KEY')
app.config['USE_TOKEN_AUTH'] = config.get('FLASK', 'USE_TOKEN_AUTH')
app.config['REDIS_URL'] = config.get('REDIS', 'programs')
app.logger.addHandler(logs)
manager = Manager(app)

reload(sys)
sys.setdefaultencoding('utf-8')

__all__ = [
    'app',
    'config',
    'copyfile',
    'logger',
    'redis_programs_db',
    'Listing',
    'manager',
    'Media',
    'Partition',
    'Program',
    ]


def copyfile(source, remote=None):
    """copies file to local storage"""
    if not remote:
        remotepath = source
    else:
        remotepath = '{0}:{1}'.format(remote, source)
    storages = iter(config.options('MEDIA_FOLDERS'))
    for storage in storages:
        if Partition(storage).usage < 0.9:
            cmd = 'rsync --progress -z {0} {1}'.format(
                remotepath, storage)
            sub.call(shlex.split(cmd))
            break


class Partition(object):
    """represents a partition on the server"""
    def __init__(self, path):
        self.path = path

    @property
    def size(self):
        st = os.statvfs(self.path)
        free = st.f_bavail * st.f_frsize
        total = st.f_blocks * st.f_frsize
        used = (st.f_blocks - st.f_bfree) * st.f_frsize
        result = disk_usage(total, used, free)
        return result

    @property
    def usage(self):
        return float(self.size.used)/float(self.size.total)

    def bytes2human(self, value):
        symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
        prefix = {}
        for i, s in enumerate(symbols):
            prefix[s] = 1 << (i+1)*10
        for s in reversed(symbols):
            if value >= prefix[s]:
                value = float(value) / prefix[s]
                return '%.1f%s' % (value, s)
        return "%sB" % value


class Media(object):
    """represents a media on the server"""
    def __init__(self, filename):
        self.filename = filename
        if not self.filename.endswith('.ts'):
            self.filename = '{}.ts'.format(filename)
        self.filepath = self.all().get(self.filename, None)

    def __repr__(self):
        return '<Media {}>'.format(self.filepath or self.filename)

    @staticmethod
    def all():
        """returns all existing files on disks"""
        result = {}
        for folder in media_folders:
            for filename in os.listdir(folder):
                if filename.endswith('.ts'):
                    result[filename] = os.path.join(folder, filename)
        return result
    
    @property
    def duration(self):
        """reads duration from redis database.
        If it's not there, it calculates using avprobe"""
        if not self.filepath:
            value = 0
            redis_media_db.delete(self.filename)
            return value
        else:
            value = redis_media_db.get(self.filename)
            if not value:
                # get duration using avprobe
                cmd = "avprobe -show_format {}".format(self.filepath)
                p = sub.Popen(
                    shlex.split(cmd), stderr=sub.PIPE, stdout=sub.PIPE
                    )
                result = p.communicate()[0]
                try:
                    value = duration_regex.search(result).groups()[0].strip()
                    value = float(value)
                except:
                    value = 3.14  # file exists but we can't get duration
                finally:
                    redis_media_db.set(self.filename, value)
                    return value
            else:
                return float(value)

    def rename(self, newfilename):
        """renames file"""
        if self.filepath:
            oldpath = self.filepath
            if not newfilename.endswith('.ts'):
                newfilename += '.ts'
            newpath = oldpath.replace(self.filename, newfilename)
            shutil.move(oldpath, newpath)
            schedule = self.schedule()
            for key, timestamps in schedule.items():
                for timestamp in timestamps:
                    entry = redis_programs_db.zrangebyscore(
                        key, timestamp, timestamp
                        )
                    entry = entry.pop()
                    filepath, index = entry.split(':')
                    redis_programs_db.zrem(key, entry)
                    redis_programs_db.zadd(key, newpath+':'+index, timestamp)
            self.__init__(newfilename)

    def delete(self):
        """deletes file"""
        schedule = self.schedule()
        now = time.time()
        timestamps = []
        for key, timestamps in schedule.items():
            t = [j for j in timestamps if j >= now]
            timestamps += t
        timestamps = sorted(list(set(timestamps)))
        if not timestamps:
            redis_media_db.delete(self.filename)
            os.remove(self.filepath)
            logger.info('{} deleted'.format(self.filepath))
            self.__init__(self.filename)
        else:
            raise ValueError('Cannot delete for it is scheduled')

    def schedule(self, day=None, service_id=None):
        """returns timestamps at which the file
        is programmed for streaming"""
        programs_keys = [
            i for i in redis_programs_db.keys('*:*')
            if redis_programs_db.type(i) == 'zset'
            ]
        result = {}
        if day and not service_id:
            programs_keys = [
                i for i in programs_keys if i.startswith(day)
                ]
        elif not day and service_id:
            programs_keys = [
                i for i in programs_keys if i.startswith(service_id)
                ]
        elif day and service_id:
            programs_keys = ['{0}:{1}'.format(day, service_id)]
        # now we iterate over keys and get the result
        for key in programs_keys:
            program = Program(*key.split(':'))
            occurences = program.get_start_time(self.filename)
            if not result.get(key):
                result[key] = [i[1] for i in occurences]
            else:
                result[key] += [i[1] for i in occurences]
        result = {i: j for i, j in result.items() if j}
        return result


class Program(object):
    """represents a program for a service_id, for a given day"""
    def __init__(self, day, service_id, timestamp=None):
        """
        :day: string representing a day under format %d%m%Y
        :service_id: integer representing a service id on a TV network
        :timestamp: float representing a moment in time from which we want
        the program
        """
        if not timestamp:
            timestamp = 0
        self.day = day
        self.service_id = service_id
        self.limit = time.mktime(
            time.strptime('{} 073000'.format(self.day), '%d%m%Y %H%M%S')
            ) + (24*3600)
        self.timestamp = float(timestamp) or time.mktime(
            time.strptime('{} 073000'.format(self.day), '%d%m%Y %H%M%S')
            )
        self.redis_zset_key = '{day}:{service_id}'.format(
            day=day, service_id=service_id)
        self.infos = redis_programs_db.zrange(
            self.redis_zset_key, 0, -1, withscores=True
            )
        # self.infos is already sorted
        if self.infos:
            initial = self.infos[0][1]
            if self.timestamp >= initial:
                recalculated_start = (
                    self.timestamp - min(
                        [
                            self.timestamp-item for entry, item in self.infos
                            if item <= self.timestamp
                            ]
                        )
                    )
                self.infos = redis_programs_db.zrangebyscore(
                    self.redis_zset_key,
                    recalculated_start,
                    initial+86400,
                    withscores=True
                    )

    def get_start_time(self, filename):
        """returns the start time(s) of a filename in the program"""
        if not filename.endswith('.ts'):
            filename += '.ts'
        try:  # redis-server >= 2.8
            result = redis_programs_db.zscan(
                self.redis_zset_key,
                match="*/{}:*".format(filename)
                )[1]
        except redis.ResponseError:  # redis-server < 2.8
            result = [
                infos for infos in self.infos
                if infos[0].split(':')[0].endswith('/'+filename)
                ]
        finally:
            result = sorted(result, key=lambda x: x[1])
            return result

    def checkerrors(self):
        """checks if self.infos is coherent and has no quirks.
           Returns a generator of missing files"""
        if not self.infos:
            msg = "No program to check for service_id {0} on {1}".format(
                self.service_id, self.day)
            logger.warning(msg)
            raise ValueError(msg)
        for key, timestamp in self.infos:
            filepath, _ = key.split(':')
            filename = filepath.split('/')[-1]
            if not Media.all().get(filename):
                yield filepath

    def write(self, data):
        """takes a list of indexed filepaths and timestamps
        and writes to the redis database"""
        for i, j in data:
            redis_programs_db.zadd(self.redis_zset_key, i, j)
                
    def backup(self, backup_filepath):
        """writes the program on disk for backup purpose"""
        if self.infos:
            self.infos = sorted(
                self.infos,
                key=lambda x: x[1]
                )
            # now the program is sorted by start times
            with open(backup_filepath, 'w') as f:
                for filepath, timestamp in self.infos:
                    msg = "{0}: {1}\n".format(
                        datetime.fromtimestamp(timestamp).strftime(
                            config.get('LOG', 'datefmt')),
                        filepath
                        )
                    f.write(msg)
            msg = "Program for service_id {0} on {1} backed up to {2}".format(
                self.service_id, self.day, backup_filepath)
            logger.info(msg)

    def update(self):
        """corrects filepaths in program, sets start time to previous
           entry in program for missing filepaths"""
        if self.infos:
            logger.info("Updating program for {0} on {1}".format(
                self.service_id, self.day))
            real_start_timestamp = 0
            for _, scheduled_timestamp in self.infos:
                filepath, index = _.split(':')
                filename = filepath.split('/')[-1]
                media = Media(filename)
                if not media.filepath:
                    # the file simply does not exist
                    logger.warning("{} does not exist".format(filename))
                else:
                    filepath = media.filepath
                    duration = media.duration
                    if scheduled_timestamp < real_start_timestamp:
                        msg = ("{0} start time changed from "
                               "{1} to {2}").format(
                            filepath,
                            datetime.fromtimestamp(
                                scheduled_timestamp).strftime(
                                    config.get('LOG', 'datefmt')
                                    ),
                            datetime.fromtimestamp(
                                real_start_timestamp).strftime(
                                    config.get('LOG', 'datefmt')
                                    )
                            )
                        logger.debug(msg)
                        scheduled_timestamp = real_start_timestamp
                    real_start_timestamp = (
                        scheduled_timestamp + duration
                        )
                redis_programs_db.zrem(self.redis_zset_key, _)
                redis_programs_db.zadd(
                    self.redis_zset_key,
                    '{0}:{1}'.format(filepath, index),
                    scheduled_timestamp
                    )

    def delete(self):
        """deletes program from redis database"""
        redis_programs_db.delete(self.redis_zset_key)
        self.__init__(self.day, self.service_id)

    def sync(self):
        """syncs with peers specified in the configuration.
           It copies the program with the latest starting time.
           Requires other peers's redis database to be accessible
           remotely."""
        remotes = {}  # we will map last starting time to peers
        for peer in config.options('PEERS'):
            db = redis.Redis(host=peer, socket_timeout=5)
            first_program_entry = db.zrange(
                self.redis_zset_key, 0, 0, withscores=True)
            last_program_entry = db.zrange(
                self.redis_zset_key, -1, -1, withscores=True)
            if last_program_entry:
                remotes[last_program_entry[0][1]] = (peer, first_program_entry)
        if remotes:
            remote = remotes[max(remotes.keys())]  # remote==(fqdn, start_time)
            remote_redis = redis.Redis(host=remote[0])
            remote_program = remote_redis.zrange(
                self.redis_zset_key, 0, -1, withscores=True)
            # we copy missing files
            for _, scheduled_timestamp in remote_program:
                filepath = _.split(':')[0]
                filename = filepath.split('/')[-1]
                media = Media(filename)
                if not media.filepath:
                    logger.debug("Copy {0} from {1}".format(
                        filepath, remote[0]))
                    copyfile(filepath, remote=remote[0])
            # we eventually replace local program
            if self.infos:
                remote_length = remote_program[-1][1] - remote_program[0][1]
                local_length = self.infos[-1][1] - self.infos[0][1]
                pertinence = remote_length > local_length
            if not self.infos or pertinence:
                logger.debug("Updating local program for {}".format(
                    self.redis_zset_key))
                self.delete()
                logger.debug("Deleted local program for {}".format(
                    self.redis_zset_key))
                self.write(remote_program)
                logger.debug("Writing new program for {}".format(
                    self.redis_zset_key))
            self.update()

    def xspf(self):
        """creates an XSPF playlist out of program's infos"""
        initial = time.mktime(
            time.strptime('{0} 073000'.format(self.day), '%d%m%Y %H%M%S')
            )
        xspf = {'playlist': {
            '@xmlns': 'http://xspf.org/ns/0/',
            '@xmlns:vlc':
                'http://www.videolan.org/vlc/playlist/ns/0/',
            '@version': '1'}}
        fulldate = '{day}/{month}/{year}'.format(
            day=self.day[:2],
            month=self.day[2:4],
            year=self.day[4:]
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
        infos = self.infos
        steps = izip(
            *[
                chain(islice(infos, i, None), islice(infos, None, i))
                for i in range(2)
                ]
            )
        index = 0
        for start, stop in steps:
            uri = 'http://www.videolan.org/vlc/playlist/0'
            index += 1
            extension = {
                '@application': uri,
                'vlc:id': index,
                'vlc:option': []
            }
            media = Media(start[0].split(':')[0].split('/')[-1])
            stop = stop[1]
            if index == 1 and self.timestamp:
                extension['vlc:option'].append(
                    'start-time={0}'.format(
                        (self.timestamp - start[1])
                        )
                    )
            if stop <= start[1]:
                stop = initial+86340
            duration = stop - start[1]
            if media.duration < duration:
                repeat = int(round(duration/media.duration)) - 1
                if repeat < 0:
                    return None
                elif repeat:
                        extension['vlc:option'].append(
                            'input-repeat={0}'.format(repeat)
                            )
            track = {
                'location': 'file:///{0}'.format(media.filepath),
                'duration': media.duration
                }
            track['extension'] = extension
            xspf['playlist']['trackList']['track'].append(track)
            other['extension']['vlc:item'].append({'@tid': str(index)})
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

    def play(self, output, udp_addr=None):
        """streams via DtPlay"""
        key = 'SERVICE:'+str(self.service_id)
        try:
            config.options(key)
        except:
            msg = '{} is not configured'.format(self.service_id)
            logger.error(msg)
            raise ValueError(msg)
        else:
            fileinfo, starttime = self.infos[0]
            media = Media(fileinfo.split(':')[0].split('/')[-1])
            trimmed_file = media.filepath.replace(
                media.filename,
                'trimmed/trimmed_'+media.filename
                )
            seconds = self.timestamp - starttime
            if 0 < (media.duration - seconds) <= 5:
                # if there are 3à seconds or less remaining
                # before next movie, we do nothing other than pause
                self.infos = self.infos[1:]
                time.sleep(media.duration - seconds)
            elif starttime == self.timestamp or media.duration <= seconds:
                pass
            else:
                m, s = divmod(seconds+10, 60)
                # trimming is estimated at 10 seconds
                h, m = divmod(m, 60)
                h_m_s = "%d:%02d:%02d" % (h, m, s)
                trim_file = (
                    "/usr/bin/avconv -i {0} -ss {1} -codec copy "
                    "-mpegts_service_id {2} -mpegts_start_pid {3} "
                    "-metadata service_provider='My TV' "
                    "-metadata service_name='{4}' "
                    "-f mpegts -muxrate 2500k -y {5}").format(
                        media.filepath,
                        h_m_s,
                        self.service_id,
                        config.get(key, 'pid_video'),
                        config.get(key, 'name'),
                        trimmed_file
                        )
                logger.debug(trim_file)
                sub.call(shlex.split(trim_file))
                self.infos[0] = (trimmed_file+':x', self.timestamp)
            for k, _ in self.infos[:-1]:  # self.infos is already filtered
                filepath = k.split(':')[0]
                cmd = ("/usr/local/bin/DtPlay {0} "
                       "-r {1} -i {2} -ipa {3} -ipt 10").format(
                           filepath,
                           config.get(key, 'bitrate'),
                           output,
                           udp_addr or config.get(key, 'udp')
                           )
                logger.debug(cmd)
                sub.call(shlex.split(cmd))
            while time.time() < self.limit:
                k, _ = self.infos[-1]
                filepath = k.split(':')[0]
                cmd = ("/usr/local/bin/DtPlay {0} "
                       "-r {1} -i {2} -ipa {3} -ipt 10").format(
                           filepath,
                           config.get(key, 'bitrate'),
                           output,
                           udp_addr or config.get(key, 'udp')
                           )
                logger.debug(cmd)
                sub.call(shlex.split(cmd))

    def stream(self):
        """streams via VLC"""
        key = 'SERVICE:'+str(self.service_id)
        try:
            config.options(key)
        except:
            msg = '{} is not configured'.format(self.service_id)
            logger.error(msg)
            raise ValueError(msg)
        else:
            xspf = self.xspf()
            xspffile = os.path.join(
                playlists_folder, self.redis_zset_key.replace(':', '_')
                )
            with open(xspffile+'.xspf', 'w') as f:
                f.write(xspf)
            cmd = ("cvlc %s -I telnet --telnet-host 0.0.0.0 "
                   "--telnet-password %s --telnet-port %s "
                   "--sout '#standard{"
                   "access=udp,"
                   "mux=ts{pid-video=%s,pid-audio=%s,pcr=50},"
                   "dst=%s}' --playlist-tree --ttl 10 "
                   "vlc://quit") % (
                       xspffile+'.xspf',
                       config.get(key, 'vlc_telnet_password'),
                       config.get(key, 'vlc_telnet_port'),
                       config.get(key, 'pid_video'),
                       config.get(key, 'pid_audio'),
                       config.get(key, 'udp')
                    )
            logger.debug("Launching VLC for {0}".format(xspffile))
            process = sub.Popen(
                shlex.split(cmd),
                stdout=sub.PIPE,
                stderr=sub.PIPE
                )
            return process


class Listing(object):
    """represents a listing uploaded to create several programs"""
    def __init__(self, filepath):
        self.filepath = filepath
        listing = ConfigParser.ConfigParser(allow_no_value=True)
        listing.read(self.filepath)
        days = listing.sections()
        today = time.localtime()
        year = today.tm_year
        self.days = []
        for day in days:
            year = today.tm_year
            if int(day[3:]) < today.tm_mon:
                year += 1
            bar = '{0}{1}'.format(day, year)
            bar = bar.replace('/', '')
            self.days.append(bar)
        self.filenames = {}
        filenames = [listing.options(i) for i in days]
        filenames = [
            i for sublist in filenames for i in sublist
            ]
        filenames = list(set(filenames))
        for filename in filenames:
            media = Media(filename)
            duration = media.duration
            for peer in config.options('PEERS'):
                db = redis.Redis(host=peer, socket_timeout=5)
                bar = db.get(filename+'.ts') or 0
                if float(bar) > duration:
                    duration = float(bar)
            # we got the maximum duration, remotes included
            self.filenames[filename] = [media.filepath, duration]

    def parse(self):
        """parses the listing and produces programs"""
        day = None
        data = None
        with open(self.filepath) as infile:
            for line in infile:
                line = line.replace('\n', '').replace('\r', '')
                if line and line.startswith('['):
                    if day:
                        yield _json.dumps(data) + '\n'
                    data = {}
                    day = line.replace(
                        '[', '').replace(
                            ']', '').replace(
                                '/', '')
                    day = [i for i in self.days if i.startswith(day)].pop()
                    start = time.mktime(
                        time.strptime('{} 073000'.format(day), '%d%m%Y %H%M%S')
                        )
                    data['day'] = day
                elif line:
                    filepath, duration = self.filenames[line]
                    data[start] = {
                        'filepath': filepath or os.path.join(
                            config.options('MEDIA_FOLDERS')[0],
                            line+'.ts'
                            ),
                        'duration': duration
                        }
                    start += duration
            else:
                yield _json.dumps(data) + '\n'

    def apply(self, data, service_id):
        """apply parsed data to one service_id"""
        logger.info("Applying {0} to service id {1}".format(
            self.filepath, service_id))
        for infos in data:
            index = 0
            infos = infos.replace('\n', '')
            infos = _json.loads(infos)
            zset_key = '{0}:{1}'.format(infos['day'], service_id)
            redis_programs_db.delete(zset_key)
            logger.debug("Deleting entry {}".format(zset_key))
            del infos['day']
            logger.debug("Inserting scores")
            timestamps = sorted(infos)
            for timestamp in timestamps:
                info = infos[timestamp]
                filepath = info['filepath']
                logger.debug("{0}: {1}".format(
                    datetime.fromtimestamp(float(timestamp)).strftime(
                        config.get('LOG', 'datefmt')),
                    filepath+':'+str(index))
                             )
                redis_programs_db.zadd(
                    zset_key, filepath+':'+str(index), float(timestamp)
                    )
                index += 1


@manager.option(dest='filename')
@manager.option('--rename', dest='rename',
                help='rename the media file')
@manager.option('--delete', action='store_true',
                help='delete the media file')
@manager.option('--json', action='store_true',
                help='get result as json')
def media(filename, rename=None, delete=False, json=False):
    """media file management"""
    if filename == "update":  # update redis_media_db
        media = Media.all()
        media_indb = redis_media_db.keys()
        to_delete = filter(lambda x: not media.get(x), media_indb)
        for i in to_delete:
            redis_media_db.delete(i)
            msg = "REDIS DB DELETE {}".format(i)
            logger.warning(msg)
        to_add = filter(lambda x: x not in media_indb, media)
        for i in to_add:
            m = Media(i)
            msg = "REDIS DB SET {0}: {1}".format(i, m.duration)
            logger.debug(msg)
        logger.debug("Media database updated")
    else:
        mediafile = Media(filename)
        if not mediafile.filepath:
            msg = "{} does not exist\n".format(filename)
            logger.error(msg)
            print msg
        elif rename:
            mediafile.rename(rename)
        elif delete:
            try:
                mediafile.delete()
            except ValueError:
                msg = "Cannot delete {}. It's scheduled for streaming".format(
                    filename)
                logger.error(msg)
                print msg
        schedule = mediafile.schedule()
        result = {
            'location': mediafile.filepath,
            'duration': mediafile.duration,
            'schedule': {}
            }
        if not json:
            print 'Location: {}'.format(result['location'])
            print 'Duration: {}'.format(result['duration'])
        bar = {}
        for entry in schedule:
            day, service_id = entry.split(':')
            if service_id not in bar:
                bar[service_id] = []
            bar[service_id] += sorted(schedule[entry])
        for service_id, timestamps in bar.items():
            if timestamps:
                timestamps = sorted(list(set(timestamps)))
                if not json:
                    print service_id
                    for timestamp in timestamps:
                        print datetime.fromtimestamp(
                            float(timestamp)).strftime(
                                config.get('LOG', 'datefmt'))
                    print '\n'
                else:
                    result['schedule'][service_id] = timestamps
        if json:
            return result


@manager.option(dest='filepath')
@manager.option('--service_id', dest='service_id',
                help="apply the listing to a service id")
def listing(filepath, service_id=None):
    """Parses a listing and eventually applies it"""
    l = Listing(filepath)
    if service_id:
        l.apply(l.parse(), service_id)
    else:
        for infos in l.parse():
            infos = _json.loads(infos)
            day = infos['day']
            del infos['day']
            timestamps = sorted(infos)
            print '{0}\n{1}\n'.format(day, '='*len(day))
            for timestamp in timestamps:
                info = infos[timestamp]
                filepath = info['filepath']
                filename = filepath.split('/')[-1]
                duration = info['duration']
                print '{0}: {1} ({2}s)'.format(
                    datetime.fromtimestamp(float(timestamp)).strftime(
                        config.get('LOG', 'datefmt')),
                    filename,
                    duration
                    )
            end = float(timestamp) + duration
            print 'End: {}\n\n'.format(
                datetime.fromtimestamp(end).strftime(
                    config.get('LOG', 'datefmt'))
                )


@manager.option(dest='date', help="program's date formatted as dmY")
@manager.option('--service_id', dest='service_id',
                help='service id')
@manager.option('--timestamp', dest='timestamp',
                help='program starting time')
@manager.option('--update', action='store_true',
                help='updates filepaths in program')
@manager.option('--stream', action='store_true',
                help="stream the service_id's program using VLC")
@manager.option('--play-on', dest='play_on',
                help="Dtplay the service_id's program via specified port")
@manager.option('--delete', action="store_true",
                help="delete permanently the program(s) from the database")
@manager.option('--backup', action="store_true",
                help="backup schedule")
@manager.option('--sync', action='store_true',
                help='sync program with peers')
@manager.option('--send', dest='send', help='send result via email')
def program(date, service_id=None, timestamp=None, sync=False,
            update=False, backup=False, delete=False,
            stream=False, play_on=None, send=None):
    if timestamp and timestamp.lower() == 'now':
        timestamp = time.time()
    dt = datetime.strptime(date, '%d%m%Y')
    weekday = dt.isoweekday()
    service_ids = [
        i.split(':')[1] for i in config.sections() if i.startswith('SERVICE:')
        ]
    dates = [date]
    if (sync or update or backup) and weekday == 6:
        # if given date is weekday == 6, then perform the action
        # for weekday == 6, weekday == 0 and weekday == 1
        for i in range(1, 3):
            dates.append(
                (dt+timedelta(i)).strftime('%d%m%Y')
                )
    elif stream and date != datetime.today().strftime('%d%m%Y'):
        msg = "Streaming date must be today's"
        sys.exit(msg)

    if service_id:
        service_id = str(service_id)
        if service_id not in service_ids:
            print "{} is not configured".format(service_id)
            sys.exit(2)
        else:
            service_ids = [service_id]

    msg = ''
    for service_id in service_ids:
        msg += '{0}\n{1}\n\n'.format(
            config.get('SERVICE:{}'.format(service_id), 'name'),
            '='*len(config.get('SERVICE:{}'.format(service_id), 'name'))
            )
        for date in dates:
            msg += '{0}:\n{1} '.format(date, '-'*len(date))
            program = Program(date, service_id, timestamp)
            if sync:
                program.sync()
                msg += '\nSynced'
            elif update:
                program.update()
                msg += '\nUpdated'
            elif backup:
                program.backup()
                msg += '\nBacked up'
            elif stream:
                assert len(dates) == 1
                program = Program(date, service_id, time.time())
                process = program.stream()
                msg += "\nLaunched streaming for {0}:{1} with PID {2}".format(
                    date, service_id, process.pid)
            elif play_on:
                assert len(dates) == 1
                program = Program(date, service_id, time.time())
                program.play(*play_on.split(','))
            elif delete:
                program.delete()
            else:
                result = sorted(program.infos, key=lambda x: x[1])
                if not result:
                    msg += '\nNo program'
                else:
                    for entry, timestamp in result:
                        msg += '\n{0}: {1}'.format(
                            datetime.fromtimestamp(timestamp).strftime(
                                config.get('LOG', 'datefmt')),
                            entry.split(':')[0]
                            )
            msg += '\n\n'
    print msg
    if send:
        # send via email
        subject = "dvbbox healthcheck for {}".format(', '.join(dates))
        dst = [send]
        orig = "dvb@{0}".format(socket.gethostname())
        message_to_send = MIMEText(msg, 'plain', 'utf-8')
        message_to_send.set_charset('utf-8')
        message_to_send['Subject'] = Header(subject, 'utf-8')
        message_to_send['From'] = orig
        message_to_send['To'] = ", ".join(dst)
        message_to_send['Date'] = formatdate(localtime=True)
        message_to_send['Message-ID'] = make_msgid()
        mailer = SMTP('localhost')
        mailer.sendmail(orig, dst, message_to_send.as_string())


@manager.command
def clean():
    """remove old xspf files and old trimmed files"""
    today = datetime.today().date()
    playlists_folder = config.get('DATA_FOLDERS', 'playlists')
    filenames = (
        i for i in os.listdir(playlists_folder)
        if (i.endswith('.xspf') and
            datetime.strptime(i.split('_')[0], '%d%m%Y').date() < today)
        )
    for filename in filenames:
        os.remove(os.path.join(playlists_folder, filename))
    for folder in config.options('MEDIA_FOLDERS'):
        try:
            for i in os.listdir(os.path.join(folder, 'trimmed')):
                os.remove(os.path.join(folder, 'trimmed', i))
        except OSError:
            continue


@manager.command
def adduser(username):
    u"""Adds user to the REST API"""
    from getpass import getpass
    password = getpass()
    password2 = getpass(prompt='Confirm: ')
    if password != password2:
        sys.exit('Sorry, passwords are not matching.')
        db.set(username, username)
        user = User(username=username)
        user.password = password
        print("User {} is correctly created.".format(username))


def cli():
    manager.run()

if __name__ == '__main__':
    cli()
