#!/usr/bin/env python
#encoding: utf-8


import imp
import logging
import os
import redis
import shlex
import shutil
import sub as sub
import sys
import time
from datetime import datetime
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
#EOF
    

                
                
