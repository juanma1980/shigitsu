#!/usr/bin/env python3
#Plugin for syncing
#Any plugin must implement the following public methods:
#	* set_config
#	* sync
#Any plugin must implement the following public mmembers:
#	* config dict with the config values (as in config file)

class svnsync():

	def __init__(self,*args,**kwargs):
		self.config=[]
	#def __init__

	def sync(self):
		pass

	def _list_repos(repo_url):
		dest_path='/tmp/tmpfile'
		try:
			req=Request(repo_url, headers={'User-Agent':'Mozilla/5.0'})
			with urllib.request.urlopen(req) as f:
				content=(f.read().decode('utf-8'))
			soup=BeautifulSoup(content,"html.parser")
			available_repos=soup.findAll('a', attrs={ "itemprop" : "name codeRepository"})
			print("Available repos at %s"%git_repo)
			repo_names=[]
			for repo in available_repos:
				repo_name=''.join(repo['href'].split('/')[2:])
				repo_names.append(repo_name)
			available_repos=sorted(repo_names,key=str.lower)

		except Exception as e:
			print(e)
		return available_repos
	#def _list_repos

	def _get_repo(self,repo,repo_name):
		dest_path="/tmp/%s"%repo_name
		_debug("Cloning %s in %s"%(repo,dest_path))
		try:
			git.Repo.clone_from(repo,dest_path)
		except Exception as e:
			dest_path=""
			print(e)
		return dest_path
	#def _get_git_repo

	def _check_repo_consistency(self,repo_path):
		repo=Repo(repo_path)
		sw_ok=True
		#Change to debian/bionic
		try:
			repo.git.checkout('debian/xenial')
		except Exception as e:
			_debug(e)
			sw_ok=False
		#Merge with master
		if sw_ok:
			repo.git.merge("master")
		return sw_ok
	#def _check_repo_consistency

	def _get_commits(self,repo_path):
		repo=Repo(repo_path)
		commits=repo.git.rev_list("--first-parent","--pretty","master","debian/xenial")
		commits_array=commits.split('\n')
		commits_dict=OrderedDict()
		msg=''
		commit=''
		author=''
		date=''
		for data in commits_array:
			if data.startswith('Merge'):
				pass
			elif data.startswith('commit'):
				if commit:
					commits_dict.update({commit:{'author':author,'date':date,'msg':msg}})
					msg=''
					commit=''
					author=''
					date=''
				commit=data
			elif data.startswith('Author'):
				author=data
			elif data.startswith('Date'):
				date=data
			elif data=='':
				continue
			else:
				msg+="%s "%data.strip()
		return commits_dict
	#def _get_commits

	def _sync_repo(self,repo_path):
		commits=self._get_commits(repo_path)
		print (commits)
	#def sync_commits
