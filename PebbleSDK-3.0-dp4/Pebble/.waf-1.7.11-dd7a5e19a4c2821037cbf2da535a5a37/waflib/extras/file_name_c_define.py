#! /usr/bin/env python
# encoding: utf-8
# WARNING! Do not edit! http://waf.googlecode.com/git/docs/wafbook/single.html#_obtaining_the_waf_file

from waflib.TaskGen import feature,after_method
@feature('c')
@after_method('create_compiled_task')
def file_name_c_define(self):
	for task in self.tasks:
		if len(task.inputs)>0:
			task.env.append_value('DEFINES','__FILE_NAME__="%s"'%task.inputs[0].name)
