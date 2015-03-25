#! /usr/bin/env python
# encoding: utf-8
# WARNING! Do not edit! http://waf.googlecode.com/git/docs/wafbook/single.html#_obtaining_the_waf_file

def set_env_sdk_version(self,process_info_node):
	with open(process_info_node.abspath(),'r')as f:
		for line in f:
			if"PROCESS_INFO_CURRENT_SDK_VERSION_MAJOR"in line:
				self.env.SDK_VERSION_MAJOR=int(line.split(' ')[2].rstrip(),16)
			if"PROCESS_INFO_CURRENT_SDK_VERSION_MINOR"in line:
				self.env.SDK_VERSION_MINOR=int(line.split(' ')[2].rstrip(),16)
	return
