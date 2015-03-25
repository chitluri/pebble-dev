#! /usr/bin/env python
# encoding: utf-8
# WARNING! Do not edit! http://waf.googlecode.com/git/docs/wafbook/single.html#_obtaining_the_waf_file

import json
import os
import time
import re
import sys
import waflib
COLOR_FILENAME_SUFFIX='~color'
BLACK_WHITE_FILENAME_SUFFIX='~bw'
def process_font_cmd(script,ttf,pfo,entry):
	m=re.search('([0-9]+)',entry['name'])
	if m==None:
		if entry['name']!='FONT_FALLBACK'and entry['name']!='FONT_FALLBACK_INTERNAL':
			raise ValueError('Font {0}: no height found in name\n'.format(entry['name']))
		height=14
	else:
		height=int(m.group(0))
	extended='--extended'if entry.get('extended')else''
	tracking_adjust='--tracking %i'%entry['trackingAdjust']if'trackingAdjust'in entry else''
	has_regex='characterRegex'in entry and entry['characterRegex']
	character_regex='--filter "%s"'%entry['characterRegex'].encode('utf8')if has_regex else''
	character_list='--list "%s"'%entry['characterList']if'characterList'in entry else''
	legacy='--legacy'if entry.get('compatibility')=="2.7"else''
	cmd="python '{}' pfo {} {} {} {} {} {} '{}' '{}'".format(script,extended,height,tracking_adjust,character_regex,character_list,legacy,ttf,pfo)
	return cmd
def find_most_specific_filename(bld,root_node,general_filename):
	suffixes=[BLACK_WHITE_FILENAME_SUFFIX,COLOR_FILENAME_SUFFIX]
	components=os.path.splitext(general_filename)
	if any([components[0].endswith(sfx)for sfx in suffixes]):
		raise Exception("Short filename cannot end with platform suffixes (%s)"%general_filename)
	color_mode_sfx=BLACK_WHITE_FILENAME_SUFFIX
	if bld.env.PLATFORM_NAME=="basalt":
		color_mode_sfx=COLOR_FILENAME_SUFFIX
	specific_filename=components[0]+color_mode_sfx+components[1]
	specific_node=root_node.find_node(specific_filename)
	if specific_node:
		return specific_filename
	return general_filename
def gen_resource_deps(bld,resources_dict,resources_path_node,output_pack_node,output_id_header_node,output_version_header_node,resource_header_path,tools_path,is_system=False,pfs_resources_header_node=None,font_key_header_node=None,font_key_table_node=None,font_key_include_path=None,timestamp=None,builtin_resources_node=None):
	bitmap_script=tools_path.find_node('bitmapgen.py')
	png_script=tools_path.find_node('png2pblpng.py')
	font_script=tools_path.find_node('font/fontgen.py')
	pack_entries=[]
	builtin_entries=[]
	font_keys=[]
	pfs_files=[]
	pfs_resources=[]
	resource_id_aliases=[]
	def deploy_generator(entry):
		res_type=entry["type"]
		def_name=entry["name"]
		skip_copy=entry.get("skipCopy")
		builtin=entry["builtin"]if"builtin"in entry else False
		if"targetPlatforms"in entry and bld.env.PLATFORM_NAME not in entry["targetPlatforms"]:
			return
		if("BOARD"in bld.env):
			output_base_node=resources_path_node.get_bld()
		else:
			output_base_node=resources_path_node.get_bld().make_node(bld.env.BUILD_DIR)
		if not is_system and builtin:
			raise ValueError("The 'builtin' modifier cannot be used ""in appinfo.json (see {0})".format(def_name))
		input_file=find_most_specific_filename(bld,resources_path_node,str(entry["file"]))
		input_node=resources_path_node.find_node(input_file)
		if input_node is None and not skip_copy:
			bld.fatal("Could not find %s resource <%s>"%(res_type,input_file))
		if"aliases"in entry:
			for alias in entry["aliases"]:
				resource_id_aliases.append((str(alias),str(def_name)))
				if res_type=='font':
					font_keys.append(alias)
		def append_entry(entry):
			(builtin_entries if builtin else pack_entries).append(entry)
		if bld.env.ONLY_SDK and res_type!='font':
			return
		if res_type=="raw":
			output_node=output_base_node.make_node(input_file)
			append_entry((output_node,def_name))
			if not skip_copy:
				bld(rule="cp ${SRC} ${TGT}",source=input_node,target=output_node)
		elif res_type=="png"or res_type=="pbi"or res_type=="pbi8":
			output_type=res_type
			if(bld.env.SDK_VERSION_MAJOR==5 and bld.env.SDK_VERSION_MINOR<20)or(output_type=="pbi"):
				output_type="pbi"
				format="bw"
			elif bld.env.PLATFORM_NAME=="basalt":
				format="color"
			else:
				format="bw"
			components=os.path.splitext(input_file)
			output_node=output_base_node.make_node(components[0]+'.'+str(output_type))
			append_entry((output_node,def_name))
			if output_type=="png":
				bld(rule="python '{}' '{}' '{}'".format(png_script.abspath(),input_node.abspath(),output_node.abspath()),source=input_node,target=output_node)
			else:
				bld(rule="python '{}' pbi '{}' '{}' '{}'".format(bitmap_script.abspath(),format,input_node.abspath(),output_node.abspath()),source=[input_node,bitmap_script],target=output_node)
		elif res_type=="png-trans":
			color_tag="white"if"WHITE"in def_name else"black"
			output_pbi=output_base_node.make_node(input_file+'.'+color_tag+'.pbi')
			append_entry((output_pbi,def_name))
			if"WHITE"in def_name:
				bld(rule="python '{}' white_trans_pbi '{}' '{}'".format(bitmap_script.abspath(),input_node.abspath(),output_pbi.abspath()),source=[input_node,bitmap_script],target=output_pbi)
			elif"BLACK"in def_name:
				bld(rule="python '{}' black_trans_pbi '{}' '{}'".format(bitmap_script.abspath(),input_node.abspath(),output_pbi.abspath()),source=[input_node,bitmap_script],target=output_pbi)
			else:
				raise Exception("png-trans with neither white or black in the name: "+def_name)
		elif res_type=="font":
			output_pfo=output_base_node.make_node(input_file+'.'+str(def_name)+'.pfo')
			fontgen_cmd=process_font_cmd(font_script.abspath(),input_node.abspath(),output_pfo.abspath(),entry)
			append_entry((output_pfo,def_name))
			font_keys.append(def_name)
			bld(rule=fontgen_cmd,source=[input_node,font_script],target=output_pfo)
		else:
			waflib.Logs.error("Error Generating Resources: File: "+input_file+" has specified invalid type: "+res_type)
			waflib.Logs.error("Must be one of (raw, png, png-trans, font)")
			raise waflib.Errors.WafError("Generating resources failed")
	if timestamp==None:
		timestamp=int(time.time())
	for res in resources_dict["media"]:
		deploy_generator(res)
	if"files"in resources_dict:
		id_offset=len(pack_entries)
		for f in resources_dict["files"]:
			filename=f["name"]
			first_name=f["resources"][0]
			last_name=f["resources"][-1]
			pfs_files.append((first_name,last_name,filename,id_offset))
			for r in f["resources"]:
				pfs_resources.append(r);
			id_offset=id_offset+len(f["resources"])
	def create_node_with_suffix(node,suffix):
		return node.parent.find_or_declare(node.name+suffix)
	manifest_node=create_node_with_suffix(output_pack_node,'.manifest')
	table_node=create_node_with_suffix(output_pack_node,'.table')
	data_node=create_node_with_suffix(output_pack_node,'.data')
	md_script=tools_path.find_node('pbpack_meta_data.py')
	resource_code_script=tools_path.find_node('generate_resource_code.py')
	data_sources=[]
	table_string="python '{}' table '{}'".format(md_script.abspath(),table_node.abspath())
	manifest_string="python '{}' manifest '{}' '{}'".format(md_script.abspath(),manifest_node.abspath(),timestamp)
	content_string="python '{}' content '{}'".format(md_script.abspath(),data_node.abspath())
	resource_ids_header_string="python '{script}' resource_id_header ""'{output_header}'  '{resource_include}' ".format(script=resource_code_script.abspath(),output_header=output_id_header_node.abspath(),resource_include=resource_header_path)
	for entry in pack_entries:
		data_sources.append(entry[0])
		table_string+=' "%s" '%entry[0].abspath()
		manifest_string+=' "%s" '%entry[0].abspath()
		content_string+=' "%s" '%entry[0].abspath()
		resource_ids_header_string+=' "%s" '%str(entry[1])
	for entry in pfs_resources:
		resource_ids_header_string+=' "%s" '%str(entry)
	builtin_data_sources=[]
	for entry in builtin_entries:
		builtin_data_sources.append(entry[0])
		resource_ids_header_string+=' "%s" '%str(entry[1])
	if resource_id_aliases:
		resource_ids_header_string+=' --aliases '
		resource_ids_header_string+=" ".join(['"%s" "%s"'%alias for alias in resource_id_aliases])
	font_extended_keys=set([key+"_EXTENDED"for key in font_keys])
	font_extended_keys_missing=font_extended_keys.difference(set(pfs_resources))
	if font_extended_keys_missing:
		resource_ids_header_string+=' --invalids '
		resource_ids_header_string+=" ".join([str(key)for key in font_extended_keys_missing])
	def touch(task):
		open(task.outputs[0].abspath(),'a').close()
	bld(rule=table_string,source=data_sources+[md_script],target=table_node)
	bld(rule=manifest_string,source=data_sources+[md_script],target=manifest_node)
	bld(rule=content_string,source=data_sources+[md_script],target=data_node)
	bld(rule="cat '{}' '{}' '{}' > '{}'".format(manifest_node.abspath(),table_node.abspath(),data_node.abspath(),output_pack_node.abspath()),source=[manifest_node,table_node,data_node],target=output_pack_node)
	bld(rule=resource_ids_header_string,source=resource_code_script,target=output_id_header_node,before=['c'])
	if is_system:
		resource_version_header_string="python '{script}' resource_version_header ""{version_def_name} '{output_header}' {timestamp} ""'{resource_include}' '{data_file}'".format(script=resource_code_script.abspath(),output_header=output_version_header_node.abspath(),version_def_name='SYSTEM_RESOURCE_VERSION',timestamp=timestamp,resource_include=resource_header_path,data_file=data_node.abspath())
		bld(rule=resource_version_header_string,source=[resource_code_script,data_node],target=output_version_header_node)
	if font_key_header_node and font_key_table_node and font_key_include_path:
		key_list_string=" ".join(font_keys)
		bld(rule="python '{script}' font_key_header '{font_key_header}' ""{key_list}".format(script=resource_code_script.abspath(),font_key_header=font_key_header_node.abspath(),key_list=key_list_string),source=resource_code_script,target=font_key_header_node)
		bld(rule="python '{script}' font_key_table '{font_key_table}' "" '{resource_id_header}' '{font_key_header}' {key_list}".format(script=resource_code_script.abspath(),font_key_table=font_key_table_node.abspath(),resource_id_header=output_id_header_node.abspath(),font_key_header=font_key_include_path,key_list=key_list_string),source=resource_code_script,target=font_key_table_node)
	if pfs_resources_header_node:
		pfs_resources_string=''
		for(first_name,last_name,filename,id_offset)in pfs_files:
			pfs_resources_string+="%s %s %s %s "%(first_name,last_name,filename,id_offset)
		bld(rule="python '{script}' pfs_files_header '{header}' ""'{resource_id_header}' {pfs_resources_string}".format(script=resource_code_script.abspath(),header=pfs_resources_header_node.abspath(),resource_id_header=output_id_header_node.abspath(),pfs_resources_string=pfs_resources_string),target=pfs_resources_header_node)
	if builtin_resources_node and builtin_data_sources:
		inputs_string=''
		for(builtin_data_node,def_name)in builtin_entries:
			inputs_string+="%s %s "%(builtin_data_node.abspath(),def_name)
		rule="python '{script}' builtin_resources ""'{output_path}' '{id_header_path}' {inputs_string}"
		rule=rule.format(script=resource_code_script.abspath(),output_path=builtin_resources_node.abspath(),id_header_path=output_id_header_node.abspath(),inputs_string=inputs_string)
		bld(rule=rule,source=builtin_data_sources+[resource_code_script],target=builtin_resources_node)
