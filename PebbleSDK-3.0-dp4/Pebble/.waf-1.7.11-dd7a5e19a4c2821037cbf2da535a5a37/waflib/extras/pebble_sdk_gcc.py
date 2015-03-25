#! /usr/bin/env python
# encoding: utf-8
# WARNING! Do not edit! http://waf.googlecode.com/git/docs/wafbook/single.html#_obtaining_the_waf_file

import os
import inject_metadata
def configure(conf):
	CROSS_COMPILE_PREFIX='arm-none-eabi-'
	conf.env.AS=CROSS_COMPILE_PREFIX+'gcc'
	conf.env.AR=CROSS_COMPILE_PREFIX+'ar'
	conf.env.CC=CROSS_COMPILE_PREFIX+'gcc'
	conf.env.LD=CROSS_COMPILE_PREFIX+'ld'
	conf.env.SIZE=CROSS_COMPILE_PREFIX+'size'
	optimize_flag='-Os'
	conf.load('gcc')
	conf.env.CFLAGS=['-std=c99','-mcpu=cortex-m3','-mthumb','-ffunction-sections','-fdata-sections','-g',optimize_flag]
	if(conf.env.SDK_VERSION_MAJOR==5)and(conf.env.SDK_VERSION_MINOR>19):
		conf.env.append_value('CFLAGS','-D_TIME_H_')
	c_warnings=['-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-error=unused-function','-Wno-error=unused-variable']
	conf.env.append_value('CFLAGS',c_warnings)
	conf.env.LINKFLAGS=['-mcpu=cortex-m3','-mthumb','-Wl,--gc-sections','-Wl,--warn-common',optimize_flag]
	conf.env.SHLIB_MARKER=None
	conf.env.STLIB_MARKER=None
def gen_inject_metadata_rule(bld,src_bin_file,dst_bin_file,elf_file,resource_file,timestamp,has_jsapp,has_worker):
	def inject_data_rule(task):
		bin_path=task.inputs[0].abspath()
		elf_path=task.inputs[1].abspath()
		if len(task.inputs)>=3:
			res_path=task.inputs[2].abspath()
		else:
			res_path=None
		tgt_path=task.outputs[0].abspath()
		cp_result=task.exec_command('cp "{}" "{}"'.format(bin_path,tgt_path))
		if cp_result<0:
			from waflib.Errors import BuildError
			raise BuildError("Failed to copy %s to %s!"%(bin_path,tgt_path))
		inject_metadata.inject_metadata(tgt_path,elf_path,res_path,timestamp,allow_js=has_jsapp,has_worker=has_worker)
	sources=[src_bin_file,elf_file]
	if resource_file is not None:
		sources.append(resource_file)
	bld(rule=inject_data_rule,name='inject-metadata',source=sources,target=dst_bin_file)
