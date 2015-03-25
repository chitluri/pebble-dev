#! /usr/bin/env python
# encoding: utf-8
# WARNING! Do not edit! http://waf.googlecode.com/git/docs/wafbook/single.html#_obtaining_the_waf_file

import json
import os
import sys
import time
import waflib.extras.ldscript as ldscript
import waflib.extras.mkbundle as mkbundle
import waflib.extras.objcopy as objcopy
import waflib.extras.xcode_pebble
import waflib.extras.pebble_sdk_gcc as pebble_sdk_gcc
from waflib.extras.pebble_platform import pebble_platforms
from waflib.extras.pebble_sdk_version import set_env_sdk_version
from waflib import Logs
from waflib.TaskGen import before_method,feature
def _do_nothing(task):
	pass
def options(opt):
	opt.load('gcc')
	opt.add_option('-d','--debug',action='store_true',default=False,dest='debug',help='Build in debug mode')
	opt.add_option('-t','--timestamp',dest='timestamp',help="Use a specific timestamp to label this package (ie, your repository's last commit time), defaults to time of build")
def configure(conf):
	if not conf.options.debug:
		conf.env.append_value('DEFINES','RELEASE')
	else:
		print"Debug enabled"
	pebble_sdk=conf.root.find_dir(os.path.dirname(__file__)).parent.parent.parent
	if pebble_sdk is None:
		conf.fatal("Unable to find Pebble SDK!\n"+"Please make sure you are running waf directly from your SDK.")
	pebble_sdk_common=pebble_sdk.find_node('common')
	conf.env.PEBBLE_SDK_COMMON=pebble_sdk_common.abspath()
	supported_platforms=os.listdir(pebble_sdk.abspath())
	sdk_check_nodes=['lib/libpebble.a','pebble_app.ld.template','tools','include','include/pebble.h']
	invalid_platforms=[]
	for p in supported_platforms:
		pebble_sdk_platform=pebble_sdk.find_node(p)
		for n in sdk_check_nodes:
			if pebble_sdk_platform.find_node(n)is None:
				if pebble_sdk_common.find_node(n)is None:
					invalid_platforms.append(p)
					break
	for p in invalid_platforms:
		supported_platforms.remove(p)
	appinfo_json_node=conf.path.get_src().find_node('appinfo.json')
	if appinfo_json_node is None:
		conf.fatal('Could not find appinfo.json')
	with open(appinfo_json_node.abspath(),'r')as f:
		appinfo=json.load(f)
	if"targetPlatforms"not in appinfo:
		target_platforms=supported_platforms
	else:
		target_platforms=list(set(supported_platforms)&set(appinfo['targetPlatforms']))
	if len(target_platforms)<1:
		conf.fatal("No valid targetPlatforms specified in appinfo.json. Valid options are {}".format(supported_platforms))
	conf.env.TARGET_PLATFORMS=sorted(target_platforms,reverse=True)
	env=conf.env
	for p in conf.env.TARGET_PLATFORMS:
		conf.setenv(p,env)
		conf.env.PLATFORM=pebble_platforms[p]
		conf.env.PEBBLE_SDK=pebble_sdk.find_node(str(p)).abspath()
		conf.env.PLATFORM_NAME=conf.env.PLATFORM['NAME']
		conf.env.BUILD_DIR=conf.env.PLATFORM['BUILD_DIR']
		conf.env.PBW_BIN_DIR=conf.env.PLATFORM['PBW_BIN_DIR']
		conf.env.append_value('INCLUDES',conf.env.BUILD_DIR)
		conf.env.append_value('DEFINES',conf.env.PLATFORM['DEFINES'])
		conf.msg("Found Pebble SDK for {} in:".format(p),conf.env.PEBBLE_SDK)
		process_info=pebble_sdk.find_node(str(p)).find_node('include/pebble_process_info.h')
		set_env_sdk_version(conf,process_info)
		pebble_sdk_gcc.configure(conf)
def find_sdk_component(bld,env,component):
	node=bld.root.find_node(env.PEBBLE_SDK).find_node(component)
	if node is None:
		return bld.root.find_node(env.PEBBLE_SDK_COMMON).find_node(component)
	else:
		return node
def build(bld):
	bld.load('file_name_c_define')
	for p in bld.env.TARGET_PLATFORMS:
		bld.add_group(p)
	bld.add_group('bundle')
	appinfo_json_node=bld.path.get_src().find_node('appinfo.json')
	if appinfo_json_node is None:
		bld.fatal('Could not find appinfo.json')
	with open(appinfo_json_node.abspath(),'r')as f:
		appinfo=json.load(f)
	resources_dict=appinfo['resources']
	app_ld_template_node=find_sdk_component(bld,bld.env,'pebble_app.ld.template')
	import waflib.extras.generate_appinfo as generate_appinfo
	def _generate_appinfo_c_file(bld,appinfo_json_node,appinfo_c_node):
		def _generate_appinfo_c_file_rule(task):
			generate_appinfo.generate_appinfo(task.inputs[0].abspath(),task.outputs[0].abspath())
		bld(rule=_generate_appinfo_c_file_rule,source=appinfo_json_node,target=appinfo_c_node)
	def _create_resources_json(task):
		resources_dict=task.generator.resources_dict
		resources_json=task.outputs[0]
		resources_map=enumerate(resources_dict["media"],1)
		images_map=filter((lambda(idx,res):res["type"]in["pbi","pbi8","png"]),resources_map)
		image_uris=map((lambda(idx,img):("app://images/"+img["name"],idx)),images_map)
		with open(resources_json.abspath(),'w')as f:
			json.dump(dict(image_uris),f)
	import waflib.extras.process_resources as process_resources
	def _generate_resources(bld,appinfo_json_node):
		resource_id_header=bld.path.get_bld().make_node(bld.env.BUILD_DIR).make_node('src/resource_ids.auto.h')
		process_resources.gen_resource_deps(bld,resources_dict=resources_dict,resources_path_node=bld.path.get_src().find_node('resources'),output_pack_node=bld.path.get_bld().make_node(bld.env.BUILD_DIR).make_node('app_resources.pbpack'),output_id_header_node=resource_id_header,output_version_header_node=None,resource_header_path="pebble.h",tools_path=find_sdk_component(bld,bld.env,'tools'))
	for p in bld.env.TARGET_PLATFORMS:
		bld.set_env(bld.all_envs[p])
		bld.set_group(bld.env.PLATFORM_NAME)
		bld(rule=_do_nothing,name='Start build for {}'.format(p),color='PINK',always=True,platform=p)
		app_ld_auto_node=bld.path.get_bld().make_node(bld.env.BUILD_DIR).make_node('pebble_app.ld.auto')
		bld(features='subst',source=app_ld_template_node,target=app_ld_auto_node,**bld.env.PLATFORM)
		if len(resources_dict["media"])>0:
			bld(rule=_create_resources_json,resources_dict=resources_dict,source=appinfo_json_node,target=bld.path.get_bld().make_node(bld.env.BUILD_DIR).make_node('timeline_resources.json'))
		appinfo_c_node=bld.path.get_bld().make_node(bld.env.BUILD_DIR).make_node('appinfo.auto.c')
		_generate_appinfo_c_file(bld,appinfo_json_node,appinfo_c_node)
		_generate_resources(bld,appinfo_json_node)
def append_to_attr(self,attr,new_values):
	values=self.to_list(getattr(self,attr,[]))
	values.extend(new_values)
	setattr(self,attr,values)
def setup_pebble_cprogram(self,name):
	append_to_attr(self,'source',[self.path.get_bld().make_node(self.env.BUILD_DIR).make_node('appinfo.auto.c')])
	append_to_attr(self,'stlibpath',[find_sdk_component(self.bld,self.env,'lib').abspath()])
	append_to_attr(self,'stlib',['pebble'])
	append_to_attr(self,'linkflags',['-Wl,--build-id=sha1','-Wl,-Map,pebble-%s.map,--emit-relocs'%(name)])
	if not getattr(self,'ldscript',None):
		setattr(self,'ldscript',self.path.get_bld().make_node(self.env.BUILD_DIR).make_node('pebble_app.ld.auto').path_from(self.path))
@feature('c')
@before_method('process_source')
def setup_pebble_c(self):
	append_to_attr(self,'includes',[find_sdk_component(self.bld,self.env,'include').path_from(self.bld.path),'.','src'])
	append_to_attr(self,'cflags',['-fPIE'])
@feature('cprogram')
@before_method('process_source')
def setup_cprogram(self):
	append_to_attr(self,'linkflags',['-mcpu=cortex-m3','-mthumb','-fPIE'])
@feature('cprogram_pebble_app')
@before_method('process_source')
def setup_pebble_app_cprogram(self):
	setup_pebble_cprogram(self,'app')
@feature('cprogram_pebble_worker')
@before_method('process_source')
def setup_pebble_worker_cprogram(self):
	setup_pebble_cprogram(self,'worker')
@feature('pbl_bundle')
def make_pbl_bundle(self):
	def report_memory_usage(task):
		src_path=task.inputs[0].abspath()
		size_output=task.generator.bld.cmd_and_log([task.env.SIZE,src_path],quiet=waflib.Context.BOTH,output=waflib.Context.STDOUT)
		text_size,data_size,bss_size=[int(x)for x in size_output.splitlines()[1].split()[:3]]
		app_ram_size=data_size+bss_size+text_size
		if task.generator.type=='app':
			max_ram=task.env.PLATFORM["MAX_APP_MEMORY_SIZE"]
		else:
			max_ram=task.env.PLATFORM["MAX_WORKER_MEMORY_SIZE"]
		free_size=max_ram-app_ram_size
		Logs.pprint('YELLOW',"%s %s memory usage:\n=============\n""Total footprint in RAM:         %6u bytes / ~%ukb\n""Free RAM available (heap):      %6u bytes\n"%(task.env.BUILD_DIR,task.generator.type,app_ram_size,max_ram/1024,free_size))
	def make_bin_file(self,type,elf_file,timestamp,has_japp,has_worker):
		platform_build_node=self.bld.path.get_bld().find_node(self.bld.env.BUILD_DIR)
		if type is not'worker':
			resources_file=platform_build_node.make_node('app_resources.pbpack.data')
		else:
			resources_file=None
		raw_bin_file=platform_build_node.make_node('pebble-{}.raw.bin'.format(type))
		bin_file=platform_build_node.make_node('pebble-{}.bin'.format(type))
		self.bld(rule=objcopy.objcopy_bin,source=elf_file,target=raw_bin_file)
		pebble_sdk_gcc.gen_inject_metadata_rule(self.bld,src_bin_file=raw_bin_file,dst_bin_file=bin_file,elf_file=elf_file,resource_file=resources_file,timestamp=timestamp,has_jsapp=has_jsapp,has_worker=has_worker)
		self.bld(rule=report_memory_usage,name='report-memory-usage',source=[elf_file],type=type,target=None)
		return bin_file
	def _make_watchapp_bundle(task):
		binaries=task.generator.bin_files
		js_files=task.generator.js_files
		outfile=task.outputs[0].abspath()
		return mkbundle.make_watchapp_bundle(timestamp=timestamp,appinfo=self.bld.path.get_src().find_node('appinfo.json').abspath(),binaries=binaries,js=js_files,outfile=outfile)
	timestamp=self.bld.options.timestamp
	pbw_basename='app_'+str(timestamp)if timestamp else self.bld.path.name
	pbz_output=self.bld.path.get_bld().make_node(pbw_basename+'.pbw')
	if timestamp is None:
		timestamp=int(time.time())
	bin_files=[]
	sources=[]
	js_nodes=self.to_nodes(getattr(self,'js',[]))
	js_files=[x.abspath()for x in js_nodes]
	has_jsapp=len(js_nodes)>0
	for binary in self.binaries:
		self.bld.set_env(self.bld.all_envs[binary['platform']])
		platform_build_node=self.bld.path.get_bld().make_node(self.bld.env.BUILD_DIR)
		platform_build_node.parent.mkdir()
		app_elf_file=self.bld.path.get_bld().make_node(binary['app_elf'])
		if app_elf_file is None:
			raise Exception("Must specify elf argument to pbl_bundle")
		if'worker_elf'in binary:
			worker_elf_file=self.bld.path.get_bld().make_node(binary['worker_elf'])
			app_bin_file=make_bin_file(self,'app',app_elf_file,timestamp,has_jsapp,True)
			worker_bin_file=make_bin_file(self,'worker',worker_elf_file,timestamp,has_jsapp,True)
			worker_bin_file_abspath=worker_bin_file.abspath()
			sources.append(worker_bin_file)
		else:
			app_bin_file=make_bin_file(self,'app',app_elf_file,timestamp,has_jsapp,False)
			worker_bin_file_abspath=None
		resources_pack=platform_build_node.make_node('app_resources.pbpack')
		sources.extend([app_bin_file,resources_pack])
		bin_files.append({'watchapp':app_bin_file.abspath(),'resources':resources_pack.abspath(),'worker_bin':worker_bin_file_abspath,'sdk_version':{'major':self.bld.env.SDK_VERSION_MAJOR,'minor':self.bld.env.SDK_VERSION_MINOR},'subfolder':self.bld.env.PBW_BIN_DIR})
	self.bld(rule=_make_watchapp_bundle,bin_files=bin_files,js_files=js_files,source=sources,target=pbz_output)
from waflib.Configure import conf
@conf
def pbl_bundle(self,*k,**kw):
	self(rule=_do_nothing,name='Start bundling',color='PINK',always=True)
	kw['features']='pbl_bundle'
	return self(*k,**kw)
@conf
def pbl_program(self,*k,**kw):
	kw['features']='c cprogram cprogram_pebble_app'
	return self(*k,**kw)
@conf
def pbl_worker(self,*k,**kw):
	kw['features']='c cprogram cprogram_pebble_worker'
	return self(*k,**kw)
