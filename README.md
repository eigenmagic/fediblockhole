# FediBlockHole

A tool for keeping a Mastodon instance blocklist synchronised with remote lists.

## Features

 - Read block lists from multiple remote instances
 - Read block lists from multiple URLs, including local files
 - Write a unified block list to a local CSV file
 - Push unified blocklist updates to multiple remote instances
 - Control import and export fields

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

## More advanced configuration

For a list of possible configuration options, check the `--help` and read the
sample configuration file in `etc/sample.fediblockhole.conf.toml`.

### keep_intermediate

This option tells the tool to save the unmerged blocklists it fetches from
remote instances and URLs into separate files. This is handy for debugging, or
just to have a non-unified set of blocklist files.

Works with the `savedir` setting to control where to save the files.

These are parsed blocklists, not the raw data, and so will be affected by `import_fields`.

The filename is based on the URL or domain used so you can tell where each list came from.

### savedir

Sets where to save intermediate blocklist files. Defaults to `/tmp`.

### no_push_instance

Defaults to False.

When set, the tool won't actually try to push the unified blocklist to any
configured instances.

If you want to see what the tool would try to do, but not actually apply any
updates, use `--dryrun`.

### no_fetch_url

Skip the fetching of blocklists from any URLs that are configured.

### no_fetch_instance

Skip the fetching of blocklists from any remote instances that are configured.

### mergeplan

If two (or more) blocklists define blocks for the same domain, but they're
different, `mergeplan` tells the tool how to resolve the conflict.

`max` is the default. It uses the _highest_ severity block it finds as the one
that should be used in the unified blocklist.

`min` does the opposite. It uses the _lowest_ severity block it finds as the one
to use in the unified blocklist.

A full discussion of severities is beyond the scope of this README, but here is
a quick overview of how it works for this tool.

The severities are:

 - **noop**, level 0: This is essentially an 'unblock' but you can include a
   comment.
 - **silence**, level 1: A silence adds friction to federation with an instance.
 - **suspend**, level 2: A full defederation with the instance.

With `mergeplan` set to `max`, _silence_ would take precedence over _noop_, and
_suspend_ would take precedence over both.

With `mergeplan` set to `min`, _silence_ would take precedence over _suspend_,
and _noop_ would take precedence over both.

You would want to use `max` to ensure that you always block with whichever your
harshest fellow admin thinks should happen.

You would want to use `min` to ensure that your blocks do what your most lenient
fellow admin thinks should happen.

### import_fields

`import_fields` controls which fields will be imported from remote
instances and URL blocklists, and which fields are pushed to instances from the
unified blocklist.

The fields `domain` and `severity` are always included, so only define extra
fields, if you want them.

You can't export fields you haven't imported, so `export_fields` should be a
subset of `import_fields`, but you can run the tool multiple times. You could,
for example, include lots of fields for an initial import to build up a
comprehensive list for export, combined with the `--no-push-instances` option so
you don't actually apply the full list to anywhere.

Then you could use a different set of options when importing so you have all the
detail in a file, but only push `public_comment` to instances.

### export_fields

`export_fields` controls which fields will get saved to the unified blocklist
file, if you export one.

The fields `domain` and `severity` are always included, so only define extra
fields, if you want them.