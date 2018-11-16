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
import datetime
import gettext
gettext.textdomain('shigitsu')
_=gettext.gettext
#plugins
import gitsync
import svnsync

#Global variables
dbg=True
conf_dir="/usr/share/shigitsu/config.d"
log_dir="/usr/share/shigitsu/"
log_file="shigitsu.log"
#conf_file="./config.json"
repos_dict={}
default={}

#Helper class for colorize text output
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
#class color

def _debug(msg):
	if dbg:
		print("%s"%msg)
#def _debug

def _error(error,level=1):
	if level:
		msg=("%sError:%s %s"%(color.RED,color.END,error))
		err_msg=("Error: %s"%(error))
	else:
		msg=("%sWarning:%s %s"%(color.YELLOW,color.END,error))
		err_msg=("Warning: %s"%(error))
	print(msg)
	_write_log(err_msg)
#def _error

def	_read_default_config():
	global log_dir
	try:
		with open("%s/defaults.json"%conf_dir) as f:
			data=json.load(f)
	except Exception as e:
		_error("Default config could not be read: %s"%e)
		sys.exit(1)
	default.update({'minutes_between_sync':data['minutes_between_syncs']})
	default.update({'download_path':data['default_download_path']})
	log_dir=data['default_download_path']
	default.update({'delete_when_processed':data['default_delete_when_processed']})
	default.update({'single_commit':data['default_single_commit']})
	default.update({'user_to_commit':data['default_user_to_commit']})
	default.update({'blacklist':data['default_blacklist']})
	default.update({'whitelist':data['default_whitelist']})
	default.update({'dest_url':data['default_dest_url']})
	default.update({'dest_type':data['default_dest_type']})
	default.update({'local_commits_db':data['local_commits_db']})
#def	_read_default_config

def _read_config(conf_file):
	global log_dir
	repos_dict={}
	try:
		with open(conf_file) as f:
			data=json.load(f)
		#set default values
	except Exception as e:
		msg=("Conf file %s couldn't be parsed: %s"%(conf_file,e))
		_error(msg)
		return(repos_dict)

	try:
		for repo,data in data['repositories'].items():
			repo_aux={}
			if 'disabled' in data.keys():
					if data['disabled'].lower()=='false':
						_error("Repository %s is disabled"%repo)
						continue
			if 'orig_type' not in data.keys() or not data['orig_type']:
				_error("Repository %s has no orig_type defined"%repo)
				continue
			if not 'orig_url' in data.keys() or not data['orig_url']:
				_error("Repository %s has no orig_url defined"%repo)
				continue
			if 'dest_type' not in data.keys() or not data['dest_type']:
				if 'dest_type' not in default.keys() or not default['dest_type']:
					_error("Repository %s has no dest_type defined"%repo)
					continue
				else:
					data['dest_type']=default['dest_type']
					_error("%s: Setting default dest_type %s"%(repo,default['dest_type']),0)
			if 	not "dest_url" in data.keys() or not data['dest_url']:
				if 	not "dest_url" in default.keys() or not default['dest_url']:
					_error("Repository %s has no dest_url defined"%repo)
					continue
				else:
					data['dest_url']=default['dest_url']
					_error("%s: Setting default dest_url %s"%(repo,default['dest_url']),0)
			if 	not "download_path" in data.keys() or not data['download_path']:
				if 	not "download_path" in default.keys() or not default['download_path']:
					_error("%s: Dest path not set"%(repo))
				else:
					_error("%s: Setting default dest path %s"%(repo,default['download_path']),0)
					data.update({"download_path":default['download_path']})
			if 	not "user_to_commit" in data.keys() or not data['user_to_commit']:
				_error("%s: Setting default user %s"%(repo,default['user_to_commit']),0)
				data.update({"user_to_commit":default['user_to_commit']})
			if 	not "single_commit" in data.keys() or not data['single_commit']:
				data.update({"single_commit":default['single_commit']})
			if 	not "delete_when_processed" in data.keys() or not data['delete_when_processed']:
				_error("%s: Setting default delete when processed %s"%(repo,default['delete_when_processed']),0)
				data.update({"delete_when_processed":default['delete_when_processed']})
			if 	"blacklist" in data.keys():
				data['blacklist'].extend(default['blacklist'])
			else:
				data['blacklist']=default['blacklist']
			if 'whitelist' in data.keys():
				data['whitelist'].extend(default['whitelist'])
			else:
				data['whitelist']=default['whitelist']
			if 'local_commits_db' in default.keys():
				data['local_commits_db']=default['local_commits_db']
			if _validate_config(data):
				repos_dict.update({repo:data})
				log_dir=data['download_path']
	except Exception as e:
		print("Error configuring %s"%(e))
	_write_log("")
	_write_log(":::::::::: INIT :::::::::")
	return repos_dict	
#def _read_config

def _validate_config(repo_dict):
	sw_validate=True
	if 'download_path' in repo_dict.keys():
		if repo_dict['download_path']:
			if not os.path.isdir(repo_dict['download_path']):
				try:
					os.makedirs(repo_dict['download_path'])
				except:
					_error("Unable to create dest dir %s"%repo_dict['download_path'])
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
	sync_result={}
	for repo,data in repos_dict.items():
		if sync_repos:
			data.update({'whitelist':sync_repos})
		print("Processing %s"%repo)
		_write_log("Processing %s"%repo)
		print("Repo type: %s"%data['orig_type'])
		_write_log("Repo type: %s"%data['orig_type'])
		print("Repo dest: %s"%data['dest_url'])
		_write_log("Repo dest: %s"%data['dest_url'])
		print("Repo dest type: %s"%data['dest_type'])
		_write_log("Repo dest type: %s"%data['dest_type'])
		print("Repo username: %s"%data['user_to_commit'])
		_write_log("Repo username: %s"%data['user_to_commit'])
		print("Blacklist: %s"%data['blacklist'])
		_write_log("Blacklist: %s"%data['blacklist'])
		print("Whitelist: %s"%data['whitelist'])
		_write_log("Whitelist: %s"%data['whitelist'])
		print("----------")
		_write_log("----------")
		if data['orig_type'].lower()=='git':
			sync_repo=gitsync.gitsync(force=sw_force)
		elif data['orig_type'].lower()=='svn':
			sync_repo=svnsync.svnsync(force=sw_force)
		sync_repo.set_config(data)
		sync_result.update({repo:sync_repo.sync()})
	_write_result_log(sync_result)

#def _process_repos

def _write_result_log(sync_result):
	try:
		with open("%s/%s"%(log_dir,log_file),'a') as f:
			for repo,result in sync_result.items():
				f.write("\n%s:\n"%(repo))
				for key,value in result.items():
					f.write(" + %s:\n"%(key))
					if type(value)==type([]):
						for val in value:
							if type(val)==type({}):
								for value_key, value_val in val.items():
									f.write("  * %s: %s\n"%(value_key,value_val))
							else:
								f.write("  * %s\n"%(val))
					else:
						f.write("  * %s\n"%(value))
	except Exception as e:
			print("Log file %s couldn't be opened: %s"%(log_file,e))


def _write_log(msg):
	global log_dir
	try:
		with open("%s/%s"%(log_dir,log_file),'a') as f:
			if msg:
				f.write("%s: %s\n"%(datetime.datetime.now().isoformat(),msg))
			else:
				f.write("\n")
	except Exception as e:
		print("Log file %s couldn't be opened: %s"%(log_file,e))
		print("Log Msg: %s"%msg)

#### MAIN PROGRAM ####
print("\nWelcome to %sShigitsu%s"%(color.RED,color.END))
sync_repos=[]
sw_force=False
if (sys.argv):
	for arg in sys.argv[1:]:
		if arg=='--force':
			sw_force=True
		else:
			sync_repos.append(arg)
resp=input("Start sync [y/n]? ")
if resp.lower()=='y':
	_read_default_config()
	print(default)
	for f in os.listdir(conf_dir):
		if f!='defaults.json' and f.endswith('.json'):
			repos_dict.update(_read_config("%s/%s"%(conf_dir,f)))
	_process_repos(repos_dict)
	_write_log(":::::::::: END :::::::::")
	print("\nProcess finished!!")

