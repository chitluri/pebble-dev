#! /usr/bin/env python
# encoding: utf-8
# WARNING! Do not edit! http://waf.googlecode.com/git/docs/wafbook/single.html#_obtaining_the_waf_file

from waflib import Task
import json
import string
import uuid
def generate_appinfo(input_filename,output_filename):
	with open(input_filename,'r')as json_file:
		try:
			app_info=json.load(json_file)
		except ValueError ,e:
			raise Exception('Could not parse appinfo.json file: '+str(e))
	try:
		app_uuid=uuid.UUID(app_info['uuid'])
	except KeyError:
		raise Exception('Could not find $.uuid in appinfo.json')
	uuid_initializer_string='{ %s }'%", ".join(["0x%02X"%ord(b)for b in app_uuid.bytes])
	try:
		name=app_info['shortName']
	except KeyError:
		raise Exception('Could not find $.shortName in appinfo.json')
	try:
		company_name=app_info['companyName']
	except KeyError:
		raise Exception('Could not find $.companyName in appinfo.json')
	try:
		version_code=app_info['versionCode']
	except KeyError:
		raise Exception('Could not find $.versionCode in appinfo.json')
	try:
		version_label=app_info['versionLabel']
		version_label_major=0
		version_label_minor=0
		version_label_list=version_label.split('.')
		if len(version_label_list)>=1:
			version_label_major=version_label_list[0]
		if len(version_label_list)>=2:
			version_label_minor=version_label_list[1]
		if len(version_label_list)>2:
			raise Exception('appinfo.json versionLabel format for app revision must be "Major" or "Major.Minor"')
		try:
			if int(version_label_major)<0 or int(version_label_major)>255:
				raise ValueError
			if int(version_label_minor)<0 or int(version_label_minor)>255:
				raise ValueError
		except ValueError:
			raise Exception('appinfo.json versionLabel contains invalid or out of range values [0-255]')
	except KeyError:
		raise Exception('Could not find $.versionLabel in appinfo.json')
	try:
		is_watchface=app_info['watchapp']['watchface']
	except KeyError:
		is_watchface=False
	try:
		only_shown_on_communication=app_info['watchapp']['onlyShownOnCommunication']
	except KeyError:
		only_shown_on_communication=False
	try:
		is_hidden=app_info['watchapp']['hiddenApp']
	except KeyError:
		is_hidden=False
	icon_resource_id=None
	try:
		for r in app_info['resources']['media']:
			if'menuIcon'in r and r['menuIcon']:
				if icon_resource_id is not None:
					raise Exception('More than one resource is set to be your menuIcon!')
				icon_resource_id='RESOURCE_ID_'+r['name']
	except KeyError:
		pass
	if icon_resource_id is None:
		icon_resource_id='DEFAULT_MENU_ICON'
	flags=[]
	if is_watchface:
		flags.append('PROCESS_INFO_WATCH_FACE')
	if only_shown_on_communication:
		flags.append('PROCESS_INFO_VISIBILITY_SHOWN_ON_COMMUNICATION')
	if is_hidden:
		flags.append('PROCESS_INFO_VISIBILITY_HIDDEN')
	if len(flags):
		flags_string=' | '.join(flags)
	else:
		flags_string='0'
	with open(output_filename,'w')as f:
		f.write('#include "pebble_process_info.h"\n')
		f.write('#include "src/resource_ids.auto.h"\n')
		f.write(PEBBLE_APP_INFO_TEMPLATE.substitute(version_major=version_label_major,version_minor=version_label_minor,name=name,company=company_name,icon_resource_id=icon_resource_id,flags=flags_string,uuid=uuid_initializer_string).encode('utf-8'))
PEBBLE_APP_INFO_TEMPLATE=string.Template("""
const PebbleProcessInfo __pbl_app_info __attribute__ ((section (".pbl_header"))) = {
  .header = "PBLAPP",
  .struct_version = { PROCESS_INFO_CURRENT_STRUCT_VERSION_MAJOR, PROCESS_INFO_CURRENT_STRUCT_VERSION_MINOR },
  .sdk_version = { PROCESS_INFO_CURRENT_SDK_VERSION_MAJOR, PROCESS_INFO_CURRENT_SDK_VERSION_MINOR },
  .process_version = { ${version_major}, ${version_minor} },
  .load_size = 0xb6b6,
  .offset = 0xb6b6b6b6,
  .crc = 0xb6b6b6b6,
  .name = "${name}",
  .company = "${company}",
  .icon_resource_id = ${icon_resource_id},
  .sym_table_addr = 0xA7A7A7A7,
  .flags = ${flags},
  .num_reloc_entries = 0xdeadcafe,
  .uuid = ${uuid},
  .virtual_size = 0xb6b6
};
""")
