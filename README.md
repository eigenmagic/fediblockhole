# FediBlockHole

A tool for keeping a Mastodon instance blocklist synchronised with remote lists.

## Features

 - Import and export block lists from CSV files.
 - Read a block list from a remote instance (if a token is configured)

## Installing

Instance admins who want to use this tool will need to add an Application at
`https://<instance-domain>/settings/applications/` they can authorise with an
OAuth token. For each instance you connect to, add this token to the config file.

### Reading remote instance blocklists

To read admin blocks from a remote instance, you'll need to ask the instance admin to add a new Application at `https://<instance-domain>/settings/applications/` and then tell you the access token.

The application needs the `admin:read:domain_blocks` OAuth scope, but unfortunately this
scope isn't available in the current application screen (v4.0.2 of Mastodon at
time of writing). There is a way to do it with scopes, but it's really
dangerous, so I'm not going to tell you what it is here.

A better way is to ask the instance admin to connect to the PostgreSQL database
and add the scope there, like this:

```
UPDATE oauth_access_tokens
    SET scopes='admin:read:domain_blocks'
    WHERE token='<your_app_token>';
```

When that's done, FediBlockHole should be able to use its token to authorise
adding or updating domain blocks via the API.

### Writing instance blocklists

To write domain blocks into an instance requires both the
`admin:read:domain_blocks` and `admin:write:domain_blocks` OAuth scopes. The
`read` scope is used to read the current list of domain blocks so we update ones
that already exist, rather than trying to add all new ones and clutter up the
instance.

Again, there's no way to do this (yet) on the application admin
screen so we need to ask our destination admins to update the application
permissions similar to reading domain blocks:

```
UPDATE oauth_access_tokens
    SET scopes='admin:read:domain_blocks admin:write:domain_blocks'
    WHERE token='<your_app_token>';
```

When that's done, FediBlockHole should be able to use its token to authorise
adding or updating domain blocks via the API.

## Configuring

Once you have your applications and tokens and scopes set up, create a
configuration file for FediBlockHole to use. You can put it anywhere and use the
`-c <configfile>` commandline parameter to tell FediBlockHole where it is.

Or you can use the default location of `/etc/default/fediblockhole.conf.toml`.

As the filename suggests, FediBlockHole uses TOML syntax.

There are 2 key sections:

 1. `blocklist_instance_sources`: A list of instances to read blocklists from
 1. `blocklist_instance_destinations`: A list of instances to write blocklists to

Each is a list of dictionaries of the form:
```
{ domain = '<domain_name>', token = '<BearerToken>' }
```

The `domain` is the fully-qualified domain name of the API host for an instance
you want to read or write domain blocks to/from. The `BearerToken` is the OAuth
token for the application that's configured in the instance to allow you to
read/write domain blocks, as discussed above.

## Using the tool

Once you've configured the tool, run it like this:

```
fediblock_sync.py -c <configfile_path>
```

If you put the config file in `/etc/default/fediblockhole.conf.toml` you don't need to pass the config file path.