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
import svnsync

class color:
   PURPLE = '\033[95m'
   CYAN = '\033[96m'
   DARKCYAN = '\033[36m'
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

def _debug(msg):
	if dbg:
		print("%s"%msg)

def _error(error,level=1):
	if level:
		print("%sError:%s %s"%(color.RED,color.END,error))
	else:
			print("%sWarning:%s %s"%(color.YELLOW,color.END,error))
#def _error

def _read_config(conf_file):
	#read config
	try:
		with open(conf_file) as f:
			data=json.load(f)
		#set default values
	except Exception as e:
		print("Conf file %s couldn't be parsed: %s"%(conf_file,e))

	try:
		default={}

		default.update({'minutes_between_sync':data['default']['minutes_between_syncs']})
		default.update({'dest_path':data['default']['default_dest_path']})
		default.update({'delete_when_processed':data['default']['default_delete_when_processed']})
		default.update({'single_commit':data['default']['default_single_commit']})
		default.update({'user_to_commit':data['default']['default_user_to_commit']})
		default.update({'blacklist':data['default']['default_blacklist']})
		default.update({'whitelist':data['default']['default_whitelist']})

		repos_dict={}
		for repo,data in data['repositories'].items():
			repo_aux={}
			if 'disabled' in data.keys():
					if data['disabled'].lower()=='false':
						_error("Repository %s is disabled"%repo)
						continue
			repo_aux=data.copy()
			if 'orig_type' not in repo_aux.keys() or not repo_aux['orig_type']:
				_error("Repository %s has no orig_type defined"%repo)
				continue
			if not 'orig_url' in repo_aux.keys() or not repo_aux['orig_url']:
				_error("Repository %s has no orig_url defined"%repo)
				continue
			if 'dest_type' not in repo_aux.keys() or not repo_aux['dest_type']:
				_error("Repository %s has no dest_type defined"%repo)
				continue
			if 	not "dest_url" in repo_aux.keys() or not data['dest_url']:
				_error("Repository %s has no dest_url defined"%repo)
				continue
			if 	not "dest_path" in repo_aux.keys() or not repo_aux['dest_path']:
				_error("Setting default dest path %s"%default['dest_path'],0)
				repo_aux.update({"dest_path":default['dest_path']})
			if 	not "user_to_commit" in repo_aux.keys() or not repo_aux['user_to_commit']:
				_error("Setting default user %s"%default['user_to_commit'],0)
				repo_aux.update({"user_to_commit":default['user_to_commit']})
			if 	not "single_commit" in repo_aux.keys() or not repo_aux['single_commit']:
				repo_aux.update({"single_commit":default['single_commit']})
			if 	not "delete_when_processed" in repo_aux.keys() or not repo_aux['delete_when_processed']:
				_error("Setting default delete when processed %s"%default['delete_when_processed'],0)
				repo_aux.update({"delete_when_processed":default['delete_when_processed']})
			if 	"blacklist" in repo_aux.keys():
				repo_aux['blacklist'].extend(default['blacklist'])
			else:
				repo_aux['blacklist']=default['blacklist']
			if 'whitelist' in repo_aux.keys():
				repo_aux['whitelist'].extend(default['whitelist'])
			else:
				repo_aux['whitelist']=default['whitelist']
			if _validate_config(repo_aux):
				repos_dict.update({repo:repo_aux})
	except Exception as e:
		print("Error configuring %s"%(e))
	return repos_dict	

def _validate_config(repo_dict):
	sw_validate=True
	if 'dest_path' in repo_dict.keys():
		if repo_dict['dest_path']:
			if not os.path.isdir(repo_dict['dest_path']):
				try:
					os.makedirs(repo_dict['dest_path'])
				except:
					_error("Unable to create dest dir %s"%repo_dict['dest_path'])
					sw_validate=False
		else:
			_error("Dest dir not set")
			sw_validate=False
	else:
		_error("Dest dir not set")
		sw_validate=False
	if sw_validate:
		if not 'user_to_commit' in repo_dict.keys() or not repo_dict['user_to_commit']:
			_error("There's no user to commit")
			sw_validate=False
	return sw_validate

def _process_repos(repos_dict):
	for repo,data in repos_dict.items():
		print("Processing %s"%repo)
		print("Repo type: %s"%data['orig_type'])
		print("Repo dest: %s"%data['dest_url'])
		print("Repo dest type: %s"%data['dest_type'])
		print("----------")
		if data['orig_type'].lower()=='git':
			repo=gitsync.gitsync()
		elif data['orig_type'].lower()=='svn':
			repo=svnsync.svnsync()
		repo.set_config(data)
		repo.sync()
#def _process_repos


#def _process_repos(repos_dict)

dbg=True
conf_file="./config.json"
repos_dict=_read_config(conf_file)
_process_repos(repos_dict)
