#!/usr/bin/env python3
import urllib
from urllib.request import Request
from urllib.request import urlretrieve
import os
import sys
import tempfile
import shutil
import subprocess
from bs4 import BeautifulSoup
import git
from git import Repo
from collections import OrderedDict
import json
import gettext
gettext.textdomain('sync_to_svn')
_=gettext.gettext
#plugins
import gitsync

def _debug(msg):
	if dbg:
		print("%s"%msg)

def _read_config(conf_file):
	#read config
	try:
		with open(conf_file) as f:
			data=json.load(f)
		#set default values
		minutes_between_sync=data['default']['minutes_between_syncs']
		default_dest_path=data['default']['default_dest_path']
		default_delete_when_processed=data['default']['default_delete_when_processed']
		default_single_commit=data['default']['default_single_commit']
		default_user_to_commit=data['default']['default_user_to_commit']

		repos_dict={}
		for repo,data in data['repositories'].items():
			repo_aux={}
			if 'disabled' in data.keys():
					if data['disabled'].lower()=='false':
						print("Repository %s is disabled"%repo)
						continue
			if "orig_type" in data.keys():
				repo_aux.update({"orig_type":data['orig_type']})
			else:
				print("Repository %s has no orig_type defined"%repo)
				continue
			if 	"orig_url" in data.keys():
				repo_aux.update({"orig_url":data['orig_url']})
			else:
				print("Repository %s has no orig_url defined"%repo)
				continue
			if 	"dest_type" in data.keys():
				repo_aux.update({"dest_type":data['dest_type']})
			else:
				print("Repository %s has no dest_type defined"%repo)
				continue
			if 	"dest_url" in data.keys():
				repo_aux.update({"dest_url":data['dest_url']})
			else:
				print("Repository %s has no dest_url defined"%repo)
				continue
			if 	"dest_path" in data.keys():
				repo_aux.update({"dest_path":data['dest_path']})
			else:
				repo_aux.update({"dest_path":default_dest_path})
			if 	"user_to_commit" in data.keys():
				repo_aux.update({"user_to_commit":data['user_to_commit']})
			else:
				repo_aux.update({"user_to_commit":default_user_to_commit})
			if 	"single_commit" in data.keys():
				repo_aux.update({"single_commit":data['single_commit']})
			else:
				repo_aux.update({"single_commit":default_single_commit})
			if 	"delete_when_processed" in data.keys():
				repo_aux.update({"delete_when_processed":data['delete_when_processed']})
			else:
				repo_aux.update({"delete_when_processed":default_delete_when_processed})
			if 	"blacklist" in data.keys():
				repo_aux.update({"blacklist":data['blacklist']})
			if 	"whitelist" in data.keys():
				repo_aux.update({"whitelist":data['whitelist']})
			if _validate_config(repo_aux):
				repos_dict.update({repo:repo_aux})
	except Exception as e:
		print("Conf file %s couldn't be parsed: %s"%(conf_file,e))
	return repos_dict	

def _validate_config(repo_dict):
	sw_validate=True
	if 'dest_path' in repo_dict.keys():
		if repo_dict['dest_path']:
			if not os.path.isdir(repo_dict['dest_path']):
				try:
					os.makedirs(repo_dict['dest_path'])
				except:
					print("Unable to create dest dir %s"%repo_dict['dest_path'])
					sw_validate=False
		else:
			print("Dest dir not set")
			sw_validate=False
	if sw_validate:
		if 'user_to_commit' in repo_dict.keys():
			if not repo_dict['user_tp_commit']:
				print("There's no user to commit")
				sw_validate=False
		else:
			print("There's no user to commit")
			sw_validate=False
	return sw_validate

dbg=True
conf_file="./config.json"
repos_dict=_read_config(conf_file)
print(repos_dict)
