import json
import os
import re
import shutil
import hashlib
import collections

from PblCommand import PblCommand
from PblProjectCreator import *

def generate_appinfo_from_old_project(project_root):
    app_info_path = os.path.join(project_root, "appinfo.json")
    with open(app_info_path, "r") as f:
        app_info_json = json.load(f, object_pairs_hook=collections.OrderedDict)

    app_info_json["targetPlatforms"] = ["aplite", "basalt"]
    app_info_json["sdkVersion"] = "3"

    with open(app_info_path, "w") as f:
        json.dump(app_info_json, f, indent=2, separators=(',', ': '))

def convert_project():
    project_root = os.getcwd()

    generate_appinfo_from_old_project(project_root)

    wscript_path = os.path.join(project_root, "wscript")

    wscript2xhash = hashlib.md5(FILE_WSCRIPT_2).hexdigest()
    with open(wscript_path, "r") as f:
        current_hash = hashlib.md5(f.read()).hexdigest()

    if wscript2xhash != current_hash:
        print 'WARNING: You had modified your wscript and those changes will be lost.\nSaving your old wscript in wscript.backup.'
        os.rename(wscript_path, wscript_path + '.backup')

    print 'Generating new 3.x wscript'
    with open(wscript_path, "w") as f:
        f.write(FILE_WSCRIPT)

    os.system('pebble clean')

class PblProjectConverter(PblCommand):
    name = 'convert-project'
    help = """convert an existing Pebble project to the current SDK.

Note: This will only convert the project, you'll still have to update your source to match the new APIs."""

    def run(self, args):
        try:
            check_project_directory()
            print "No conversion required"
            return 0
        except OutdatedProjectException:
            convert_project()
            print "Project successfully converted!"
            return 0

