import os
import string
import uuid
import json

from PblCommand import PblCommand

SDK_VERSION = "3"

class PblProjectCreator(PblCommand):
    name = 'new-project'
    help = 'Create a new Pebble project'

    def configure_subparser(self, parser):
        parser.add_argument("name", help = "Name of the project you want to create")
        parser.add_argument("--simple", action="store_true", help = "Use a minimal c file")
        parser.add_argument("--javascript", action="store_true", help = "Generate javascript related files")
        parser.add_argument("--worker", action="store_true", help = "Generate background worker related files")

    def run(self, args):
        print "Creating new project {}".format(args.name)

        # User can give a path to a new project dir
        project_path = args.name
        project_name = os.path.split(project_path)[1]
        project_root = os.path.join(os.getcwd(), project_path)

        project_src = os.path.join(project_root, "src")

        # Create directories
        os.makedirs(project_root)
        os.makedirs(os.path.join(project_root, "resources"))
        os.makedirs(project_src)

        # Create main .c file
        with open(os.path.join(project_src, "%s.c" % (project_name)), "w") as f:
            f.write(FILE_SIMPLE_MAIN if args.simple else FILE_DUMMY_MAIN)

        # Add appinfo.json file
        appinfo_dummy = DICT_DUMMY_APPINFO.copy()
        appinfo_dummy['uuid'] = str(uuid.uuid4())
        appinfo_dummy['project_name'] = project_name
        with open(os.path.join(project_root, "appinfo.json"), "w") as f:
            f.write(FILE_DUMMY_APPINFO.substitute(**appinfo_dummy))

        # Add .gitignore file
        with open(os.path.join(project_root, ".gitignore"), "w") as f:
            f.write(FILE_GITIGNORE)

        # Add javascript files if applicable
        if args.javascript:
            project_js_src = os.path.join(project_src, "js")
            os.makedirs(project_js_src)

            with open(os.path.join(project_js_src, "pebble-js-app.js"), "w") as f:
                f.write(FILE_DUMMY_JAVASCRIPT_SRC)

        # Add background worker files if applicable
        if args.worker:
            project_worker_src = os.path.join(project_root, "worker_src")
            os.makedirs(project_worker_src)
            # Add simple source file
            with open(os.path.join(project_worker_src, "%s_worker.c" % (project_name)), "w") as f:
                f.write(FILE_DUMMY_WORKER)

        # Add wscript file
        with open(os.path.join(project_root, "wscript"), "w") as f:
            f.write(FILE_WSCRIPT)

FILE_GITIGNORE = """
# Ignore build generated files
build
"""

FILE_WSCRIPT = """
#
# This file is the default set of rules to compile a Pebble project.
#
# Feel free to customize this to your needs.
#

import os.path

top = '.'
out = 'build'

def options(ctx):
    ctx.load('pebble_sdk')

def configure(ctx):
    ctx.load('pebble_sdk')

def build(ctx):
    ctx.load('pebble_sdk')

    build_worker = os.path.exists('worker_src')
    binaries = []

    for p in ctx.env.TARGET_PLATFORMS:
        ctx.set_env(ctx.all_envs[p])
        ctx.set_group(ctx.env.PLATFORM_NAME)
        app_elf='{}/pebble-app.elf'.format(ctx.env.BUILD_DIR)
        ctx.pbl_program(source=ctx.path.ant_glob('src/**/*.c'),
        target=app_elf)

        if build_worker:
            worker_elf='{}/pebble-worker.elf'.format(ctx.env.BUILD_DIR)
            binaries.append({'platform': p, 'app_elf': app_elf, 'worker_elf': worker_elf})
            ctx.pbl_worker(source=ctx.path.ant_glob('worker_src/**/*.c'),
            target=worker_elf)
        else:
            binaries.append({'platform': p, 'app_elf': app_elf})

    ctx.set_group('bundle')
    ctx.pbl_bundle(binaries=binaries, js=ctx.path.ant_glob('src/js/**/*.js'))
"""

FILE_WSCRIPT_2 = """
#
# This file is the default set of rules to compile a Pebble project.
#
# Feel free to customize this to your needs.
#
import os.path
top = '.'
out = 'build'
def options(ctx):
    ctx.load('pebble_sdk')
def configure(ctx):
    ctx.load('pebble_sdk')
def build(ctx):
    ctx.load('pebble_sdk')
    ctx.pbl_program(source=ctx.path.ant_glob('src/**/*.c'),
                    target='pebble-app.elf')
    if os.path.exists('worker_src'):
        ctx.pbl_worker(source=ctx.path.ant_glob('worker_src/**/*.c'),
                        target='pebble-worker.elf')
        ctx.pbl_bundle(elf='pebble-app.elf',
                        worker_elf='pebble-worker.elf',
                        js=ctx.path.ant_glob('src/js/**/*.js'))
    else:
        ctx.pbl_bundle(elf='pebble-app.elf',
                        js=ctx.path.ant_glob('src/js/**/*.js'))
"""

FILE_SIMPLE_MAIN = """#include <pebble.h>

int main(void) {
  app_event_loop();
}
"""

FILE_DUMMY_WORKER = """#include <pebble_worker.h>

int main(void) {
  worker_event_loop();
}
"""

FILE_DUMMY_MAIN = """#include <pebble.h>

static Window *window;
static TextLayer *text_layer;

static void select_click_handler(ClickRecognizerRef recognizer, void *context) {
  text_layer_set_text(text_layer, "Select");
}

static void up_click_handler(ClickRecognizerRef recognizer, void *context) {
  text_layer_set_text(text_layer, "Up");
}

static void down_click_handler(ClickRecognizerRef recognizer, void *context) {
  text_layer_set_text(text_layer, "Down");
}

static void click_config_provider(void *context) {
  window_single_click_subscribe(BUTTON_ID_SELECT, select_click_handler);
  window_single_click_subscribe(BUTTON_ID_UP, up_click_handler);
  window_single_click_subscribe(BUTTON_ID_DOWN, down_click_handler);
}

static void window_load(Window *window) {
  Layer *window_layer = window_get_root_layer(window);
  GRect bounds = layer_get_bounds(window_layer);

  text_layer = text_layer_create((GRect) { .origin = { 0, 72 }, .size = { bounds.size.w, 20 } });
  text_layer_set_text(text_layer, "Press a button");
  text_layer_set_text_alignment(text_layer, GTextAlignmentCenter);
  layer_add_child(window_layer, text_layer_get_layer(text_layer));
}

static void window_unload(Window *window) {
  text_layer_destroy(text_layer);
}

static void init(void) {
  window = window_create();
  window_set_click_config_provider(window, click_config_provider);
  window_set_window_handlers(window, (WindowHandlers) {
    .load = window_load,
    .unload = window_unload,
  });
  const bool animated = true;
  window_stack_push(window, animated);
}

static void deinit(void) {
  window_destroy(window);
}

int main(void) {
  init();

  APP_LOG(APP_LOG_LEVEL_DEBUG, "Done initializing, pushed window: %p", window);

  app_event_loop();
  deinit();
}
"""

DICT_DUMMY_APPINFO = {
    'company_name': 'MakeAwesomeHappen',
    'version_code': 1,
    'version_label': '1.0',
    'target_platform': '["aplite", "basalt"]',
    'sdk_version': SDK_VERSION,
    'is_watchface': 'false',
    'app_keys': """{
    "dummy": 0
  }""",
    'resources_media': '[]'
}

FILE_DUMMY_APPINFO = string.Template("""{
  "uuid": "${uuid}",
  "shortName": "${project_name}",
  "longName": "${project_name}",
  "companyName": "${company_name}",
  "versionCode": ${version_code},
  "versionLabel": "${version_label}",
  "sdkVersion": "${sdk_version}",
  "targetPlatforms": ${target_platform},
  "watchapp": {
    "watchface": ${is_watchface}
  },
  "appKeys": ${app_keys},
  "resources": {
    "media": ${resources_media}
  }
}
""")

FILE_DUMMY_JAVASCRIPT_SRC = """\
Pebble.addEventListener("ready",
    function(e) {
        console.log("Hello world! - Sent from your javascript application.");
    }
);
"""

class PebbleProjectException(Exception):
    pass

class InvalidProjectException(PebbleProjectException):
    pass

class OutdatedProjectException(PebbleProjectException):
    pass

def check_project_directory():
    """Check to see if the current directory matches what is created by PblProjectCreator.run.

    Raises an InvalidProjectException or an OutdatedProjectException if everything isn't quite right.
    """

    if not os.path.isdir('src'):
        raise InvalidProjectException

    app_info_path = os.path.join(os.getcwd(), "appinfo.json")
    with open(app_info_path, "r") as f:
        app_info_json = json.load(f)

    if os.path.islink('pebble_app.ld') \
            or os.path.exists('resources/src/resource_map.json') \
            or not os.path.exists('wscript') \
            or not 'sdkVersion' in app_info_json.keys() \
            or app_info_json["sdkVersion"] != SDK_VERSION:
        raise OutdatedProjectException

def requires_project_dir(func):
    def wrapper(self, args):
        check_project_directory()
        return func(self, args)
    return wrapper

