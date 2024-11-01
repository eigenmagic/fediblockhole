# FediBlockHole

A tool for keeping a Mastodon instance blocklist synchronised with remote lists.

The broad design goal for FediBlockHole is to support pulling in a list of
blocklists from a set of trusted sources, merge them into a combined blocklist,
and then push that merged list to a set of managed instances.

Mastodon admins can choose who they think maintain quality lists and subscribe
to them, helping to distribute the load for maintaining blocklists among a
community of people. Control ultimately rests with the admins themselves so they
can outsource as much, or as little, of the effort to others as they deem
appropriate.

Inspired by the way PiHole works for maintaining a set of blocklists of adtech
domains. Builds on the work of
[@CaribenxMarciaX@scholar.social](https://scholar.social/@CaribenxMarciaX) and
[@gingerrroot@kitty.town](https://kitty.town/@gingerrroot) who started the
#Fediblock hashtag and did a lot of advocacy around it, often at great personal
cost.

## Features

### Blocklist Sources

 - Read domain block lists from other instances via the Mastodon API.
 - Supports both public lists (no auth required) and 'admin' lists requiring
   authentication to an instance.
 - Read domain block lists from arbitrary URLs, including local files.
 - Supports CSV and JSON format blocklists
 - Supports RapidBlock CSV and JSON format blocklists

### Blocklist Export/Push

 - Push a merged blocklist to a set of Mastodon instances.
 - Export per-source, unmerged block lists to local files, in CSV format.
 - Export merged blocklists to local files, in CSV format.
 - Read block lists from multiple remote instances
 - Read block lists from multiple URLs, including local files
 - Write a unified block list to a local CSV file
 - Push unified blocklist updates to multiple remote instances
 - Control import and export fields

### Flexible Configuration

 - Provides (hopefully) sensible defaults to minimise first-time setup.
 - Global and fine-grained configuration options available for those complex situations that crop up sometimes.
 - Allowlists to override blocks in blocklists to ensure you never block instances you want to keep.
 - Blocklist thresholds if you want to only block when an instance shows up in multiple blocklists.

## Installing

Installable using `pip`.

```
python3 -m pip install fediblockhole
```

Install from source by cloning the repo, `cd fediblockhole` and run:

```
python3 -m pip install .
```

Installation adds a commandline tool: `fediblock-sync`

Instance admins who want to use this tool for their instance will need to add an
Application at `https://<instance-domain>/settings/applications/` so they can
authorize the tool to create and update domain blocks with an OAuth token.

More on authorization by token below.

### Reading remote instance blocklists

If a remote instance makes its domain blocks public, you don't need
a token to read them.

If a remote instance only shows its domain blocks to local accounts
you'll need to have a token with `read:blocks` authorization set up.
If you have an account on that instance, you can get a token by setting up a new
Application at `https://<instance-domain>/settings/applications/`.

To read admin blocks from a remote instance, you'll need to ask the instance
admin to add a new Application at
`https://<instance-domain>/settings/applications/` and then tell you the access
token.

The application needs the `admin:read:domain_blocks` OAuth scope. You can allow
full `admin:read` access, but be aware that this authorizes someone to read all
the data in the instance. That's asking a lot of a remote instance admin who
just wants to share domain_blocks with you.

The `admin:read:domain_blocks` scope is available as of Mastodon v4.1.0, but for
earlier versions admins will need to use the manual method described below.

You can update the scope for your application in the database directly like
this:

```
UPDATE oauth_applications as app
  SET scopes = 'admin:read:domain_blocks'
  FROM oauth_access_tokens as tok
  WHERE app.id = tok.application_id
  AND app.name = '<the_app_name>'
;
```

When that's done, regenerate the token (so it has the new scopes) in the
application screen in the instance GUI. FediBlockHole should then able to use
the app token to read domain blocks via the API, but nothing else.

Alternately, you could ask the remote instance admin to set up FediBlockHole and
use it to dump out a CSV blocklist from their instance and then put it somewhere
trusted parties can read it. Then you can define the blocklist as a URL source,
as explained below.

### Writing instance blocklists

To write domain blocks into an instance requires both the `admin:read` and
`admin:write:domain_blocks` OAuth scopes.

The tool needs `admin:read:domain_blocks` scope to read the current list of
domain blocks so we update ones that already exist, rather than trying to add
all new ones and clutter up the instance.

`admin:read` access is needed to check if the instance has any accounts that
follow accounts on a domain that is about to get `suspend`ed and automatically
drop the block severity to `silence` level so people have time to migrate
accounts before a full defederation takes effect. Unfortunately, the statistics
measure used to learn this information requires `admin:read` scope.

You can add `admin:read` scope in the application admin screen. Please be aware
that this grants full read access to all information in the instance to the
application token, so make sure you keep it a secret. At least remove
world-readable permission to any config file you put it in, e.g.:

```
chmod o-r <configfile>
```

You can also grant full `admin:write` scope to the application, but if you'd
prefer to keep things more tightly secured, limit the scope to
`admin:read:domain_blocks`.

Again, this scope is only available in the application config screen as of
Mastodon v4.1.0. If your instance is on an earlier version, you'll need to use
SQL to set the scopes in the database and then regenerate the token:

```
UPDATE oauth_applications as app
  SET scopes = 'admin:read admin:write:domain_blocks'
  FROM oauth_access_tokens as tok
  WHERE app.id = tok.application_id
  AND app.name = '<the_app_name>'
;
```

When that's done, FediBlockHole should be able to use its token to authorise
adding or updating domain blocks via the API.

## Using the tool

Run the tool like this:

```
fediblock-sync -c <configfile_path>
```

If you put the config file in `/etc/default/fediblockhole.conf.toml` you don't
need to pass in the config file path.

For a list of possible configuration options, check the `--help`.

You can also read the heavily commented sample configuration file in the repo at
[etc/sample.fediblockhole.conf.toml](https://github.com/eigenmagic/fediblockhole/blob/main/etc/sample.fediblockhole.conf.toml).

## Configuring

Once you have your applications and tokens and scopes set up, create a
configuration file for FediBlockHole to use. You can put it anywhere and use the
`-c <configfile>` commandline parameter to tell FediBlockHole where it is.

Or you can use the default location of `/etc/default/fediblockhole.conf.toml`.

As the filename suggests, FediBlockHole uses TOML syntax.

There are 4 key sections:
 
 1. `blocklist_urls_sources`: A list of URLs to read blocklists from
 1. `blocklist_instance_sources`: A list of Mastodon instances to read blocklists from via API
 1. `blocklist_instance_destinations`: A list of Mastodon instances to write blocklists to via API
 1. `allowlist_url_sources`: A list of URLs to read allowlists from

More detail on configuring the tool is provided below.

### URL sources

The URL sources is a list of URLs to fetch blocklists from.

Supported formats are currently:

 - Comma-Separated Values (CSV)
 - JSON
 - Mastodon v4.1 flavoured CSV
 - RapidBlock CSV
 - RapidBlock JSON

Blocklists must provide a `domain` field, and should provide a `severity` field.

`domain` is the domain name of the instance to be blocked/limited.

`severity` is the severity level of the block/limit. Supported values are: `noop`, `silence`, and `suspend`.

Optional fields that the tool understands are `public_comment`, `private_comment`, `reject_media`, `reject_reports`, and `obfuscate`.

#### CSV format

A CSV format blocklist must contain a header row with at least a `domain` and `severity` field.

Optional fields, as listed about, may also be included.

#### Mastodon v4.1 CSV format

As of v4.1.0, Mastodon can export domain blocks as a CSV file. However, in their
infinite wisdom, the Mastodon devs decided that field names should begin with a
`#` character in the header, unlike the field names in the JSON output via the
API… or in pretty much any other CSV file anywhere else.

Setting the format to `mastodon_csv` will strip off the `#` character when
parsing and FediBlockHole can then use Mastodon v4.1 CSV blocklists like any
other CSV formatted blocklist.

#### JSON format

JSON is also supported. It uses the same format as the JSON returned from the Mastodon API.

This is a list of dictionaries, with at minimum a `domain` field, and preferably
a `severity` field. The other optional fields are, well, optional.

#### RapidBlock CSV format

The RapidBlock CSV format has no header and a single field, so it's not
_strictly_ a CSV file as there are no commas separating values. It is basically
just a list of domains to block, separated by '\r\n'.

When using this format, the tool assumes the `severity` level is `suspend`.

#### RapidBlock JSON format

The RapidBlock JSON format provides more detailed information about domain
blocks, but is still somewhat limited.

It has a single `isBlocked` flag indicating if a domain should be blocked or
not. There is no support for the 'silence' block level.

There is no support for 'reject_media' or 'reject_reports' or 'obfuscate'.

All comments are public, by virtue of the public nature of RapidBlock.

### Instance sources

The tool can also read domain_blocks from instances directly.

The configuration is a list of dictionaries of the form:
```
{ domain = '<domain_name>', token = '<BearerToken>', admin = false }
```

The `domain` is the fully-qualified domain name of the API host for an instance
you want to read domain blocks from. 

The `token` is an optional OAuth token for the application that's configured in
the instance to allow you to read domain blocks, as discussed above.

The `token` can also be specified using environment variables. This provides
improved security compared to storing the OAuth token in a configuration file,
but it will require the environment variable to be set so that FediBlockHole can
access it. See below in [Instance destinations](#instance-destinations) for more
detail on how to use environment variables to provide authentication tokens.

`admin` is an optional field that tells the tool to use the more detailed admin
API endpoint for domain_blocks, rather than the more public API endpoint that
doesn't provide as much detail. You will need a `token` that's been configured to
permit access to the admin domain_blocks scope, as detailed above.

### Instance destinations

The tool supports pushing a unified blocklist to multiple instances.

Configure the list of instances you want to push your blocklist to in the
`blocklist_instance_destinations` list. Each entry is of the form:

```
{ domain = '<domain_name>', import_fields = ['public_comment'], max_severity = 'suspend', max_followed_severity = 'suspend' }
```

The field `domain` is required. It is the fully-qualified domain name of the
instance you want to push to. 

A BearerToken is also required, for authenticating with the instance. It can be provided in two ways:

1. A token can be provided directly in the entry as a `token` field, like this:
    ```
    { domain = '<domain_name>', token = '<BearerToken>', import_fields = ['public_comment'], max_severity = 'suspend', max_followed_severity = 'suspend' }
    ```
    This was the only mechanism available up to version 0.4.5 of Fediblockhole.

1. A token can be provided from the environment.

    If a token is not directly provided with the `token` field, Fediblockhole will
    look for an environment variable that contains the token.

    By default, the name of the environment variable will be the domain name
    converted to upper case and with dot/period characters converted to
    underscores, and the suffix `_TOKEN`. For example, the token variable for the
    domain `eigenmagic.net` would be `EIGENMAGIC_NET_TOKEN`.

    You can also specify the environment variable to look for, using the
    `token_env_var` field, like this:
    ```
    { domain = '<domain_name>', token_env_var = 'MY_CUSTOM_DOMAIN_TOKEN', import_fields = ['public_comment'], max_severity = 'suspend', max_followed_severity = 'suspend' }
    ```

    Fediblockhole will then look for a token in the `MY_CUSTOM_DOMAIN_TOKEN` environment variable.

    If a specific `token_env_var` is provided, the default variable name will
    not be used. If both the `token` and `token_env_var` fields are provided,
    the token provided in the `token` field will be used, and a warning will be
    issued to notify you that you might have misconfigured things.


The BearerToken is
an application token with both `admin:read:domain_blocks` and
`admin:write:domain_blocks` authorization.

The fields `max_followed_severity` and `import_fields` are optional.

The optional `import_fields` setting allows you to restrict which fields are
imported from each instance. If you want to import the `reject_reports` settings
from one instance, but no others, you can use the `import_fields` setting to do
it. **Note:** The `domain` and `severity` fields are always imported.

The optional `max_severity` setting limits the maximum severity you will allow a
remote blocklist to set. This helps you import a list from a remote instance but
only at the `silence` level, even if that remote instance has a block at
`suspend` level. If not set, defaults to `suspend`.

The optional `max_followed_severity` setting sets a per-instance limit on the
severity of a domain_block if there are accounts on the instance that follow
accounts on the domain to be blocked. If `max_followed_severity` isn't set, it
defaults to `silence`.

This setting exists to give people time to move off an instance that is about to
be defederated and bring their followers from your instance with them. Without
it, if a new `suspend` block appears in any of the blocklists you subscribe to (or
a block level increases from `silence` to `suspend`) and you're using the default
`max` mergeplan, the tool would immediately suspend the instance, cutting
everyone on the blocked instance off from their existing followers on your
instance, even if they move to a new instance. If you actually want that
outcome, you can set `max_followed_severity = 'suspend'` and use the `max`
mergeplan.

Once the follow count drops to 0 on your instance, the tool will automatically
use the highest severity it finds again (if you're using the `max` mergeplan).

### Allowlists

Sometimes you might want to completely ignore the blocklist definitions for
certain domains. That's what allowlists are for.

Allowlists remove any domain in the list from the merged list of blocks before
the merged list is saved out to a file or pushed to any instance.

Allowlists can be in any format supported by `blocklist_urls_sources` but ignore
all fields that aren't `domain`.

You can also allow domains on the commandline by using the `-A` or `--allow`
flag and providing the domain name to allow. You can use the flag multiple
times to allow multiple domains.

It is probably wise to include your own instance domain in an allowlist so you
don't accidentally defederate from yourself.

## More advanced configuration

For a list of possible configuration options, check the `--help` and read the
sample configuration file in `etc/sample.fediblockhole.conf.toml`.

### save_intermediate

This option tells the tool to save the unmerged blocklists it fetches from
remote instances and URLs into separate files. This is handy for debugging, or
just to have a non-unified set of blocklist files.

Works with the `savedir` setting to control where to save the files.

These are parsed blocklists, not the raw data, and so will be affected by `import_fields`.

The filename is based on the URL or domain used so you can tell where each list came from.

### savedir

Sets where to save intermediate blocklist files. Defaults to `/tmp`.

### blocklist_auditfile

If provided, will save an audit file of counts and percentages by domain. Useful for debugging 
thresholds. Defaults to None.

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

### override_private_comment

Defaults to None.

Stamp all *new* blocks pushed to a remote server with this comment or code. 
Helps to identify blocks you've created on a server via Fediblockhole versus ones that
already existed.

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