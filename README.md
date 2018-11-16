# Shigitsu

Shigitsu is a tiny program that synchronizes git repositories with subverdsion.

## Usage

Shigitsu reads the configuration from the files located in config.d
In this folder must be one default.json with default configs and as many "repositories.json" as needed.

### Default config:
config.d/defaults.json

* "minutes_between_syncs":"" -> Time in minutes between sync 
* "default_download_path":"" -> Default work path
* "default_delete_when_processed":"" -> If true then the dowloaded repos will be erased after sync
* "default_single_commit":"" -> If true shigitsu will only synchronize the last git commit. If false will sync all the commits one by one
* "default_user_to_commit":"" -> Default user for svn
* "default_dest_type":"" -> It could be svn or git. At this moment only "git" works
* "default_dest_url": "" -> Url with the svn repository
* "default_blacklist":[] -> List of blacklisted repositories 
* "default_whitelist":[] -> Whitelist of repositories to update
* "local_commits_db":"" -> If true the database with the commits will be stored in the user's home. If false it will be stored at /usr/share/shigitsu

### Repositories config:
```
{
	"repositories":
	{
		"Team name": -> Name of the team at github
		{
			"disabled":"", -> If true then the team will be ignored
			"orig_type":"git", -> Actually only "git" works
			"orig_url":"", -> Base url of the team (https://github.com/team_name
			"dest_type": "", -> Actually only "svn" works
			"dest_url": "", -> As default_dest_url
			"blacklist": [], -> As default_blacklist
			"whitelist": [], -> As default_whitelist
			"dest_path":"", -> As default_dest_path
			"delete_when_processed":"", -> As default_delete_when_procesed
			"single_commit":"", -> As default_single_commit
			"user_to_commit":"" -> As default_user_to_commit
		}
	}
}

```

