'''Adapter module to synchronize sanitized versions of the profile 
directory with other activity instances. 
'''

import shutil
import tempfile
import os
import stat
import subprocess
import re

from sugar import env

def _copy_dir(src, dst):
    ''' recursively copying folder src, the target folder dst exist already '''
    names = os.listdir(src)
    for name in names:
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if os.path.isdir(srcname):
                if not os.path.exists(dstname):
                    os.mkdir(dstname)
                _copy_dir(srcname, dstname)
            else:
                shutil.copy2(srcname, dstname)
        except (IOError, os.error), why:
            print 'Can\'t copy %s to %s: %s' % (`srcname`, `dstname`, str(why))

def _chmod_dir(folder):
    ''' chmod a folder recursively '''
    names = os.listdir(folder)
    for name in names:
        name = os.path.join(folder, name)
        try:
            mode = os.stat(name)[stat.ST_MODE]
            os.chmod(name, (mode | stat.S_IWGRP | stat.S_IRGRP))
            if os.path.isdir(name):
                _chmod_dir(name)            
        except (IOError, os.error), why:
            print 'Can\'t chmod %s: %s' % (`name`, str(why))

def create_local_profile(sar):
    ''' create local profile from shared profile'''

    profile_inst = os.path.join(sar, 'instance/profile')
    profile_data = os.path.join(sar, 'data/profile')    

    # copy old profile data if exist
    if not os.path.exists(profile_inst):
        os.mkdir(profile_inst)
        if os.path.exists(profile_data):
            folder = os.readlink(profile_data)
            if os.path.exists(folder):        
                _copy_dir(folder, profile_inst)

def update_shared_profile(sar):
    '''impose appropriate permissions and synchronize 
    with the shared profile '''

    profile_inst = os.path.join(sar, 'instance/profile')
    profile_data = os.path.join(sar, 'data/profile')
    profile_data_tmp = os.path.join(sar, 'data/profile_tmp')

    # copy profile to $STAGING_AREA
    staging_area = tempfile.mkdtemp(dir=os.path.join(sar, 'instance'))   
    _copy_dir(profile_inst, staging_area)

    # change entries to be rw for the group
    _chmod_dir(staging_area)

    # create a tempfile in $SAR/data
    new_profile = tempfile.mkdtemp(dir=os.path.join(sar, 'data'))
    os.chmod(new_profile, 0770)

    # clone the contents of the $STAGING_AREA into $NEW_PROFILE
    _copy_dir(staging_area, new_profile)
    shutil.rmtree(staging_area)

    # atomically swing symlink $SAR/data/profile to point to $NEW_PROFILE    
    os.symlink(new_profile, profile_data_tmp)
    os.rename(profile_data_tmp, profile_data)

def _in_use(folder):
    ''' check if there are processes running under the uid 
    owning the folder 
    '''
    if env.is_emulator():
        # FIXME: must find a way to deal with this in sugar-jhbuild
        return True
    uid = os.stat(folder)[stat.ST_UID]
    fdp = subprocess.Popen(['ps', '--no-headers', '-f', 'U', str(uid)], 
                         stdout=subprocess.PIPE)
    data = fdp.stdout.read()
    command = '.*(%d).*' % uid
    ret = re.compile(command).match(data)
    if ret:
        return True
    return False

def garbage_collector(sar):
    ''' garbage-collection step in order to reclaim the resources used by 
    old revisions of the profile 
    '''
    sar_data = os.path.join(sar, 'data')
    names = os.listdir(sar_data)
    for name in names:
        path = os.path.join(sar_data, name)
        if os.path.isdir(path) and not os.path.islink(path):
            path_profile = os.readlink(os.path.join(sar, 'data/profile'))
            if not path_profile == path and not _in_use(path):
                shutil.rmtree(path)
   

